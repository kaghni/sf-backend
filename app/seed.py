from app.crud import count_contacts, create_address, create_contact
from app.database import SessionLocal
from app.schemas import AddressCreate, ContactCreate

SAMPLE_CONTACTS = [
    ContactCreate(
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        phone="+1-415-555-0101",
        company="Analytical Engines",
        job_title="Mathematician",
        city="San Francisco",
        state="CA",
        country="USA",
        notes="First programmer.",
    ),
    ContactCreate(
        first_name="Grace",
        last_name="Hopper",
        email="grace@example.com",
        phone="+1-415-555-0102",
        company="US Navy",
        job_title="Rear Admiral",
        city="Arlington",
        state="VA",
        country="USA",
    ),
    ContactCreate(
        first_name="Alan",
        last_name="Turing",
        email="alan@example.com",
        phone="+44-20-5555-0103",
        company="Bletchley Park",
        job_title="Cryptanalyst",
        city="London",
        country="UK",
    ),
]


# Keyed by the contact's email; Ada gets one of each kind to show grouping.
SAMPLE_ADDRESSES = {
    "ada@example.com": [
        AddressCreate(type="Home", street="12 St James's Square", city="London", country="UK"),
        AddressCreate(
            type="Work",
            street="1 Market St, Suite 400",
            city="San Francisco",
            state="CA",
            postal_code="94105",
            country="USA",
        ),
    ],
    "grace@example.com": [
        AddressCreate(type="Work", city="Arlington", state="VA", country="USA"),
    ],
}


def seed_if_empty() -> int:
    """Insert sample contacts when the database has none. Returns rows added."""
    with SessionLocal() as db:
        if count_contacts(db) > 0:
            return 0
        for payload in SAMPLE_CONTACTS:
            contact = create_contact(db, payload)
            for address in SAMPLE_ADDRESSES.get(contact.email, []):
                create_address(db, contact, address)
        return len(SAMPLE_CONTACTS)
