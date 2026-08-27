from datetime import timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Address, Contact, Meetup
from app.schemas import (
    AddressCreate,
    AddressReplace,
    ContactCreate,
    ContactReplace,
    ContactUpdate,
    MeetupCreate,
    NearbyCluster,
)

SORTABLE_FIELDS = ("id", "first_name", "last_name", "email", "company", "created_at", "updated_at")


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def get_contact(db: Session, contact_id: int) -> Contact | None:
    return db.get(Contact, contact_id)


def get_contact_by_email(db: Session, email: str) -> Contact | None:
    stmt = select(Contact).where(func.lower(Contact.email) == _normalize_email(email))
    return db.execute(stmt).scalar_one_or_none()


def count_contacts(db: Session) -> int:
    return db.execute(select(func.count()).select_from(Contact)).scalar_one()


def list_contacts(
    db: Session,
    *,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "id",
    order: str = "asc",
) -> tuple[list[Contact], int]:
    """Return (page of contacts, total matching count)."""
    # Addresses ride along on every ContactRead; load them in one extra query
    # per page rather than one per contact.
    stmt = select(Contact).options(selectinload(Contact.addresses))

    if search:
        pattern = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Contact.first_name).like(pattern),
                func.lower(Contact.last_name).like(pattern),
                func.lower(Contact.email).like(pattern),
                func.lower(func.coalesce(Contact.company, "")).like(pattern),
                func.lower(func.coalesce(Contact.phone, "")).like(pattern),
            )
        )

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    if sort_by not in SORTABLE_FIELDS:
        sort_by = "id"
    column = getattr(Contact, sort_by)
    stmt = stmt.order_by(column.desc() if order == "desc" else column.asc())

    items = db.execute(stmt.limit(limit).offset(offset)).scalars().all()
    return list(items), total


def create_contact(db: Session, payload: ContactCreate) -> Contact:
    data = payload.model_dump()
    data["email"] = _normalize_email(data["email"])
    contact = Contact(**data)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def replace_contact(db: Session, contact: Contact, payload: ContactReplace) -> Contact:
    for field, value in payload.model_dump().items():
        setattr(contact, field, _normalize_email(value) if field == "email" else value)
    db.commit()
    db.refresh(contact)
    return contact


def update_contact(db: Session, contact: Contact, payload: ContactUpdate) -> Contact:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, field, _normalize_email(value) if field == "email" else value)
    db.commit()
    db.refresh(contact)
    return contact


def delete_contact(db: Session, contact: Contact) -> None:
    db.delete(contact)
    db.commit()


def get_address(db: Session, address_id: int) -> Address | None:
    return db.get(Address, address_id)


def create_address(db: Session, contact: Contact, payload: AddressCreate) -> Address:
    address = Address(contact_id=contact.id, **payload.model_dump())
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


def replace_address(db: Session, address: Address, payload: AddressReplace) -> Address:
    for field, value in payload.model_dump().items():
        setattr(address, field, value)
    db.commit()
    db.refresh(address)
    return address


def delete_address(db: Session, address: Address) -> None:
    db.delete(address)
    db.commit()


def _city_key(city: str) -> str:
    return city.strip().lower()


def list_nearby_clusters(db: Session) -> list[NearbyCluster]:
    """Cities where at least two distinct contacts have an address, biggest first."""
    stmt = select(Address.city, Address.contact_id).where(Address.city.is_not(None)).order_by(Address.id)
    clusters: dict[str, tuple[str, dict[int, None]]] = {}
    for city, contact_id in db.execute(stmt):
        key = _city_key(city)
        if not key:
            continue
        # Keep the first-seen spelling; a dict keeps ids distinct and ordered.
        spelling, ids = clusters.setdefault(key, (city.strip(), {}))
        ids[contact_id] = None
    return sorted(
        (
            NearbyCluster(city=spelling, contact_ids=list(ids), contact_count=len(ids))
            for spelling, ids in clusters.values()
            if len(ids) >= 2
        ),
        key=lambda cluster: (-cluster.contact_count, cluster.city),
    )


def get_meetup(db: Session, meetup_id: int) -> Meetup | None:
    return db.get(Meetup, meetup_id)


def create_meetup(db: Session, payload: MeetupCreate) -> Meetup:
    data = payload.model_dump()
    data["city"] = data["city"].strip()
    if data["starts_at"].tzinfo is not None:
        # SQLite drops the offset on write; store UTC so the value reads back unchanged.
        data["starts_at"] = data["starts_at"].astimezone(timezone.utc)
    meetup = Meetup(**data)
    db.add(meetup)
    db.commit()
    db.refresh(meetup)
    return meetup


def meetup_guests(db: Session, meetup: Meetup) -> list[Contact]:
    """Contacts with at least one address in the meetup's city, each once, by id."""
    # Same normalisation as list_nearby_clusters, so a city that shows up as
    # "nearby" always yields its guests.
    in_city = select(Address.contact_id).where(
        func.lower(func.trim(Address.city)) == _city_key(meetup.city)
    )
    stmt = (
        select(Contact)
        .where(Contact.id.in_(in_city))
        .options(selectinload(Contact.addresses))
        .order_by(Contact.id)
    )
    return list(db.execute(stmt).scalars().all())
