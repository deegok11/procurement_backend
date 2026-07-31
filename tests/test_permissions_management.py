from tests.conftest import auth_header


def test_non_admin_cannot_view_or_edit_permissions(client, tokens):
    req = auth_header(tokens["requester"])
    assert client.get("/permissions", headers=req).status_code == 403
    assert client.put("/permissions/vendor", headers=req, json={"permissions": ["item:read"]}).status_code == 403


def test_admin_can_view_permissions_matrix(client, tokens):
    admin = auth_header(tokens["admin"])
    resp = client.get("/permissions", headers=admin)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["matrix"].keys()) == {"requester", "approver", "vendor", "super_admin"}
    assert "permissions:manage" in body["matrix"]["super_admin"]
    assert "permissions:manage" in body["all_permissions"]
    assert "item:read" in body["all_permissions"]


def test_admin_can_grant_and_revoke_a_permission_and_it_takes_effect_immediately(client, tokens):
    admin = auth_header(tokens["admin"])
    vendor = auth_header(tokens["vendor"])

    # Vendor cannot create items by default.
    assert client.post(
        "/items/add_item", headers=vendor, json={"item_code": "PERM-TEST-1", "description": "x", "uom": "EA"},
    ).status_code == 403

    current = client.get("/permissions", headers=admin).json()["matrix"]["vendor"]
    granted = current + ["item:create"]
    resp = client.put("/permissions/vendor", headers=admin, json={"permissions": granted})
    assert resp.status_code == 200
    assert "item:create" in resp.json()["matrix"]["vendor"]

    # Now the same vendor can — no re-login needed, the check reads the store live.
    assert client.post(
        "/items/add_item", headers=vendor, json={"item_code": "PERM-TEST-1", "description": "x", "uom": "EA"},
    ).status_code == 200

    # Revoke it again — back to 403.
    resp = client.put("/permissions/vendor", headers=admin, json={"permissions": current})
    assert resp.status_code == 200
    assert "item:create" not in resp.json()["matrix"]["vendor"]
    assert client.post(
        "/items/add_item", headers=vendor, json={"item_code": "PERM-TEST-2", "description": "x", "uom": "EA"},
    ).status_code == 403


def test_unknown_permission_string_is_rejected(client, tokens):
    admin = auth_header(tokens["admin"])
    resp = client.put("/permissions/vendor", headers=admin, json={"permissions": ["not:a:real:permission"]})
    assert resp.status_code == 400


def test_cannot_remove_permissions_manage_from_super_admin(client, tokens):
    admin = auth_header(tokens["admin"])
    current = client.get("/permissions", headers=admin).json()["matrix"]["super_admin"]
    without_manage = [p for p in current if p != "permissions:manage"]

    resp = client.put("/permissions/super_admin", headers=admin, json={"permissions": without_manage})
    assert resp.status_code == 400

    # Unaffected — still has it.
    assert "permissions:manage" in client.get("/permissions", headers=admin).json()["matrix"]["super_admin"]


def test_admin_has_no_procurement_action_permissions_by_default(client, tokens):
    admin = auth_header(tokens["admin"])
    resp = client.post(
        "/prs", headers=admin,
        json={"title": "should be blocked", "line_items": [
            {"description": "x", "uom": "EA", "quantity": "1", "unit_price": "1"}
        ]},
    )
    assert resp.status_code == 403


def test_admin_can_read_across_document_types(client, tokens):
    admin = auth_header(tokens["admin"])
    assert client.get("/prs", headers=admin).status_code == 200
    assert client.get("/pos", headers=admin).status_code == 200
    assert client.get("/bills", headers=admin).status_code == 200
