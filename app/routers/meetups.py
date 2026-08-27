from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.models import Meetup
from app.schemas import ContactRead, ErrorResponse, MeetupCreate, MeetupRead, NearbyCluster

router = APIRouter(prefix="/api/v1/meetups", tags=["meetups"])

MEETUP_ID = Path(description="Identifier returned when the meetup was created.", examples=[1], ge=1)

NOT_FOUND = {
    "model": ErrorResponse,
    "description": "No meetup exists with that id.",
    "content": {"application/json": {"example": {"detail": "Meetup 42 not found"}}},
}


def _get_or_404(db: Session, meetup_id: int) -> Meetup:
    meetup = crud.get_meetup(db, meetup_id)
    if meetup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Meetup {meetup_id} not found")
    return meetup


def _read(db: Session, meetup: Meetup) -> MeetupRead:
    return MeetupRead(
        id=meetup.id,
        title=meetup.title,
        city=meetup.city,
        starts_at=meetup.starts_at,
        created_at=meetup.created_at,
        guests=[ContactRead.model_validate(contact) for contact in crud.meetup_guests(db, meetup)],
    )


@router.get(
    "/nearby",
    response_model=list[NearbyCluster],
    operation_id="listNearbyClusters",
    summary="List cities where contacts cluster",
    response_description="Cities with two or more contacts, largest cluster first.",
)
def list_nearby_clusters(db: Session = Depends(get_db)) -> list[NearbyCluster]:
    """
    Find the cities where two or more contacts live.

    Cities are matched case-insensitively across every contact address, and a
    contact counts once per city no matter how many addresses it has there.
    Each entry is a ready-made guest list for `POST /api/v1/meetups`.
    """
    return crud.list_nearby_clusters(db)


@router.post(
    "",
    response_model=MeetupRead,
    status_code=status.HTTP_201_CREATED,
    operation_id="createMeetup",
    summary="Create a meetup",
    response_description="The stored meetup with its derived guest list.",
)
def create_meetup(payload: MeetupCreate, db: Session = Depends(get_db)) -> MeetupRead:
    """
    Gather the contacts living in one city into a meetup.

    Only the title, city, and start time are stored. The guest list is derived
    on every read from the contacts that have an address in that city, so it
    stays correct as addresses are added, changed, or removed.
    """
    return _read(db, crud.create_meetup(db, payload))


@router.get(
    "/{meetup_id}",
    response_model=MeetupRead,
    operation_id="getMeetup",
    summary="Get a meetup",
    response_description="The requested meetup with its current guest list.",
    responses={status.HTTP_404_NOT_FOUND: NOT_FOUND},
)
def get_meetup(meetup_id: int = MEETUP_ID, db: Session = Depends(get_db)) -> MeetupRead:
    """Fetch a single meetup by its id, with guests recomputed from current addresses."""
    return _read(db, _get_or_404(db, meetup_id))
