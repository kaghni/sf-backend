import base64

BASE = "/api/v1/contacts"

PHOTO = "data:image/png;base64," + base64.b64encode(b"tiny-fake-png").decode()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "sqlite"


def test_create_contact(client, payload):
    response = client.post(BASE, json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["email"] == "ada@example.com"
    assert body["full_name"] == "Ada Lovelace"
    assert body["created_at"] and body["updated_at"]


def test_create_requires_valid_email(client, payload):
    response = client.post(BASE, json={**payload, "email": "not-an-email"})
    assert response.status_code == 422


def test_create_requires_names(client, payload):
    response = client.post(BASE, json={**payload, "first_name": ""})
    assert response.status_code == 422


def test_duplicate_email_conflicts(client, payload):
    assert client.post(BASE, json=payload).status_code == 201
    response = client.post(BASE, json={**payload, "email": "ADA@example.com"})
    assert response.status_code == 409


def test_get_contact(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.get(f"{BASE}/{contact_id}")
    assert response.status_code == 200
    assert response.json()["id"] == contact_id


def test_get_missing_contact_returns_404(client):
    assert client.get(f"{BASE}/9999").status_code == 404


def test_list_pagination_and_total(client, payload):
    for index in range(5):
        client.post(BASE, json={**payload, "email": f"user{index}@example.com"})

    response = client.get(BASE, params={"limit": 2, "offset": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["limit"] == 2 and body["offset"] == 2


def test_list_search(client, payload):
    client.post(BASE, json=payload)
    client.post(
        BASE,
        json={**payload, "first_name": "Grace", "last_name": "Hopper", "email": "grace@example.com", "company": "US Navy"},
    )

    hits = client.get(BASE, params={"search": "hopper"}).json()
    assert hits["total"] == 1
    assert hits["items"][0]["last_name"] == "Hopper"

    by_company = client.get(BASE, params={"search": "navy"}).json()
    assert by_company["total"] == 1

    misses = client.get(BASE, params={"search": "nobody"}).json()
    assert misses["total"] == 0


def test_list_sorting(client, payload):
    client.post(BASE, json={**payload, "last_name": "Zhang", "email": "z@example.com"})
    client.post(BASE, json={**payload, "last_name": "Adams", "email": "a@example.com"})

    names = [
        item["last_name"]
        for item in client.get(BASE, params={"sort_by": "last_name", "order": "asc"}).json()["items"]
    ]
    assert names == ["Adams", "Zhang"]


def test_list_rejects_bad_sort_field(client):
    assert client.get(BASE, params={"sort_by": "; DROP TABLE contacts"}).status_code == 422


def test_patch_updates_only_sent_fields(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.patch(f"{BASE}/{contact_id}", json={"phone": "+1-000-000-0000"})
    assert response.status_code == 200
    body = response.json()
    assert body["phone"] == "+1-000-000-0000"
    assert body["first_name"] == "Ada"
    assert body["company"] == "Analytical Engines"


def test_patch_duplicate_email_conflicts(client, payload):
    first = client.post(BASE, json=payload).json()["id"]
    client.post(BASE, json={**payload, "email": "grace@example.com"})
    response = client.patch(f"{BASE}/{first}", json={"email": "grace@example.com"})
    assert response.status_code == 409


def test_patch_same_email_is_allowed(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.patch(f"{BASE}/{contact_id}", json={"email": payload["email"]})
    assert response.status_code == 200


def test_put_replaces_contact(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.put(
        f"{BASE}/{contact_id}",
        json={"first_name": "Grace", "last_name": "Hopper", "email": "grace@example.com"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Grace Hopper"
    assert body["company"] is None  # omitted fields are cleared by PUT


def test_put_missing_contact_returns_404(client):
    response = client.put(
        f"{BASE}/9999",
        json={"first_name": "A", "last_name": "B", "email": "ab@example.com"},
    )
    assert response.status_code == 404


def test_delete_contact(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    assert client.delete(f"{BASE}/{contact_id}").status_code == 204
    assert client.get(f"{BASE}/{contact_id}").status_code == 404
    assert client.delete(f"{BASE}/{contact_id}").status_code == 404


def test_root_lists_entrypoints(client):
    body = client.get("/").json()
    assert body["contacts"] == BASE


def test_create_contact_with_photo(client, payload):
    response = client.post(BASE, json={**payload, "photo": PHOTO})
    assert response.status_code == 201
    assert response.json()["photo"] == PHOTO


def test_contact_without_photo_reads_null(client, payload):
    response = client.post(BASE, json=payload)
    assert response.status_code == 201
    assert response.json()["photo"] is None


def test_photo_rejects_non_data_uri(client, payload):
    assert client.post(BASE, json={**payload, "photo": "not-a-photo"}).status_code == 422


def test_photo_rejects_non_image_mime(client, payload):
    text_uri = "data:text/plain;base64," + base64.b64encode(b"hello").decode()
    assert client.post(BASE, json={**payload, "photo": text_uri}).status_code == 422


def test_photo_rejects_invalid_base64(client, payload):
    response = client.post(BASE, json={**payload, "photo": "data:image/png;base64,!!not-base64!!"})
    assert response.status_code == 422


def test_photo_rejects_empty_payload(client, payload):
    assert client.post(BASE, json={**payload, "photo": "data:image/png;base64,"}).status_code == 422


def test_photo_rejects_oversize(client, payload):
    huge = "data:image/png;base64," + base64.b64encode(b"x" * 110_000).decode()
    assert client.post(BASE, json={**payload, "photo": huge}).status_code == 422


def test_patch_without_photo_preserves_it(client, payload):
    contact_id = client.post(BASE, json={**payload, "photo": PHOTO}).json()["id"]
    response = client.patch(f"{BASE}/{contact_id}", json={"phone": "+1-000-000-0000"})
    assert response.status_code == 200
    assert response.json()["photo"] == PHOTO


def test_put_with_photo_keeps_it(client, payload):
    contact_id = client.post(BASE, json={**payload, "photo": PHOTO}).json()["id"]
    response = client.put(f"{BASE}/{contact_id}", json={**payload, "photo": PHOTO})
    assert response.status_code == 200
    assert response.json()["photo"] == PHOTO


def _contact_with_address(client, payload, **address) -> tuple[int, dict]:
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.post(f"{BASE}/{contact_id}/addresses", json={"type": "Home", **address})
    assert response.status_code == 201
    return contact_id, response.json()


def test_create_address(client, payload):
    contact_id, address = _contact_with_address(client, payload, street="1 Market St", city="San Francisco")
    assert address["contact_id"] == contact_id
    assert address["type"] == "Home"
    assert address["city"] == "San Francisco"
    assert address["state"] is None


def test_address_types_match_between_schema_and_database():
    # The allow-list lives in two places (Pydantic Literal, SQL CHECK); pin them together.
    from typing import get_args

    from app.models import ADDRESS_TYPES
    from app.schemas import AddressType

    assert get_args(AddressType) == ADDRESS_TYPES


def test_address_requires_known_type(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.post(f"{BASE}/{contact_id}/addresses", json={"type": "Vacation"})
    assert response.status_code == 422


def test_address_for_missing_contact_returns_404(client):
    assert client.post(f"{BASE}/9999/addresses", json={"type": "Home"}).status_code == 404


def test_contact_embeds_addresses_grouped_by_type(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    for kind in ("Work", "Other", "Home", "Work"):
        client.post(f"{BASE}/{contact_id}/addresses", json={"type": kind})

    types = [a["type"] for a in client.get(f"{BASE}/{contact_id}").json()["addresses"]]
    assert types == ["Home", "Other", "Work", "Work"]

    listed = client.get(f"{BASE}/{contact_id}/addresses").json()
    assert [a["type"] for a in listed] == types


def test_list_contacts_includes_addresses(client, payload):
    _contact_with_address(client, payload, city="London")
    items = client.get(BASE).json()["items"]
    assert items[0]["addresses"][0]["city"] == "London"


def test_replace_address(client, payload):
    contact_id, address = _contact_with_address(client, payload, street="Old St", city="London")
    response = client.put(
        f"{BASE}/{contact_id}/addresses/{address['id']}",
        json={"type": "Work", "street": "New St"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "Work"
    assert body["street"] == "New St"
    assert body["city"] is None  # omitted fields are cleared by PUT


def test_delete_address(client, payload):
    contact_id, address = _contact_with_address(client, payload)
    url = f"{BASE}/{contact_id}/addresses/{address['id']}"
    assert client.delete(url).status_code == 204
    assert client.delete(url).status_code == 404
    assert client.get(f"{BASE}/{contact_id}").json()["addresses"] == []


def test_address_is_scoped_to_its_contact(client, payload):
    _, address = _contact_with_address(client, payload)
    other_id = client.post(BASE, json={**payload, "email": "other@example.com"}).json()["id"]
    assert client.delete(f"{BASE}/{other_id}/addresses/{address['id']}").status_code == 404


def test_deleting_contact_deletes_its_addresses(client, payload):
    contact_id, address = _contact_with_address(client, payload)
    assert client.delete(f"{BASE}/{contact_id}").status_code == 204
    # A new contact must not inherit the orphaned row.
    new_id = client.post(BASE, json={**payload, "email": "new@example.com"}).json()["id"]
    assert client.get(f"{BASE}/{new_id}").json()["addresses"] == []
    assert client.delete(f"{BASE}/{new_id}/addresses/{address['id']}").status_code == 404


def test_put_omitting_photo_clears_it(client, payload):
    # PUT is a full replace: clients must carry the photo through an edit,
    # or it is wiped — the frontend edit form does exactly that.
    contact_id = client.post(BASE, json={**payload, "photo": PHOTO}).json()["id"]
    response = client.put(f"{BASE}/{contact_id}", json=payload)
    assert response.status_code == 200
    assert response.json()["photo"] is None
