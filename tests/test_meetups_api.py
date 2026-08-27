import base64

CONTACTS = "/api/v1/contacts"
BASE = "/api/v1/meetups"

PHOTO = "data:image/png;base64," + base64.b64encode(b"tiny-fake-png").decode()
MEETUP = {"title": "SF founders dinner", "city": "San Francisco", "starts_at": "2026-09-12T18:30:00Z"}


def _contact_in(client, payload, email: str, *cities: str, **extra) -> int:
    contact_id = client.post(CONTACTS, json={**payload, "email": email, **extra}).json()["id"]
    for city in cities:
        response = client.post(f"{CONTACTS}/{contact_id}/addresses", json={"type": "Home", "city": city})
        assert response.status_code == 201
    return contact_id


def test_nearby_is_empty_without_shared_cities(client, payload):
    _contact_in(client, payload, "ada@example.com", "London")
    _contact_in(client, payload, "grace@example.com", "Arlington")
    response = client.get(f"{BASE}/nearby")
    assert response.status_code == 200
    assert response.json() == []


def test_nearby_clusters_contacts_by_city_case_insensitively(client, payload):
    ada = _contact_in(client, payload, "ada@example.com", "San Francisco")
    grace = _contact_in(client, payload, "grace@example.com", "san francisco")
    alan = _contact_in(client, payload, "alan@example.com", "London")
    linus = _contact_in(client, payload, "linus@example.com", "London", "SAN FRANCISCO")

    clusters = client.get(f"{BASE}/nearby").json()
    assert clusters == [
        {"city": "San Francisco", "contact_ids": [ada, grace, linus], "contact_count": 3},
        {"city": "London", "contact_ids": [alan, linus], "contact_count": 2},
    ]


def test_nearby_counts_a_contact_once_per_city(client, payload):
    ada = _contact_in(client, payload, "ada@example.com", "London", "london")
    _contact_in(client, payload, "grace@example.com")
    assert client.get(f"{BASE}/nearby").json() == []

    grace = _contact_in(client, payload, "grace2@example.com", "London")
    clusters = client.get(f"{BASE}/nearby").json()
    assert clusters == [{"city": "London", "contact_ids": [ada, grace], "contact_count": 2}]


def test_create_meetup_derives_guests_from_city(client, payload):
    ada = _contact_in(client, payload, "ada@example.com", "san francisco", photo=PHOTO)
    grace = _contact_in(client, payload, "grace@example.com", "San Francisco")
    _contact_in(client, payload, "alan@example.com", "London")

    response = client.post(BASE, json=MEETUP)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["title"] == MEETUP["title"]
    assert body["city"] == "San Francisco"
    assert body["starts_at"] == "2026-09-12T18:30:00Z"
    assert body["created_at"]

    guests = {guest["id"]: guest for guest in body["guests"]}
    assert set(guests) == {ada, grace}
    assert guests[ada]["photo"] == PHOTO
    assert guests[grace]["photo"] is None
    assert guests[ada]["addresses"][0]["city"] == "san francisco"


def test_create_meetup_requires_fields(client):
    assert client.post(BASE, json={"title": "No city", "starts_at": MEETUP["starts_at"]}).status_code == 422
    assert client.post(BASE, json={**MEETUP, "title": ""}).status_code == 422
    assert client.post(BASE, json={**MEETUP, "starts_at": "tonight"}).status_code == 422


def test_get_meetup_recomputes_guests(client, payload):
    meetup_id = client.post(BASE, json=MEETUP).json()["id"]
    assert client.get(f"{BASE}/{meetup_id}").json()["guests"] == []

    ada = _contact_in(client, payload, "ada@example.com", "San Francisco")
    response = client.get(f"{BASE}/{meetup_id}")
    assert response.status_code == 200
    assert [guest["id"] for guest in response.json()["guests"]] == [ada]


def test_guest_with_two_addresses_in_city_appears_once(client, payload):
    ada = _contact_in(client, payload, "ada@example.com", "San Francisco", "SAN FRANCISCO")
    guests = client.post(BASE, json=MEETUP).json()["guests"]
    assert [guest["id"] for guest in guests] == [ada]
    assert len(guests[0]["addresses"]) == 2


def test_get_missing_meetup_returns_404(client):
    response = client.get(f"{BASE}/9999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Meetup 9999 not found"


def test_root_lists_meetups(client):
    assert client.get("/").json()["meetups"] == BASE
