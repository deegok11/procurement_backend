"""Regression coverage for the per-document-type read permissions
(pr:read / quotation:read / po:read / grn:read / bill:read / transaction:read)
that replaced the old blanket "document:read", and for the tenant-scoping
that PO/GRN/Bill/Transaction reads didn't previously apply at all (only
quotation reads did) — a second vendor could previously see another vendor's
PO/GRN/Bill/Transaction through the type-specific GET routes. Uses
membership assertions (not exact list contents) since JSON-file storage is
shared and accumulates documents across tests in the same session — other
tests' documents may already be present."""

import uuid

from tests.conftest import auth_header


def _build_chain(client, req, apr, vnd1):
    """PR -> APPROVED -> quotation (vnd1) -> PO -> GRN -> BILL -> TRANSACTION,
    all the way through, so every document type has a real, vendor-owned
    instance to test read access against."""
    item = client.post(
        "/items/add_item", headers=req,
        json={"item_code": f"READPERM-{uuid.uuid4().hex[:8]}", "description": "Widget", "uom": "EA"},
    ).json()
    pr = client.post(
        "/prs", headers=req,
        json={
            "title": "read-permission test",
            "line_items": [{
                "item_id": item["item_id"], "description": "Widget", "uom": "EA",
                "quantity": "5", "unit_price": "10", "tax_pct": "0",
            }],
        },
    ).json()
    pr = client.post(f"/prs/{pr['id']}/submit", headers=req).json()
    pr = client.post(f"/prs/{pr['id']}/approve", headers=apr, json={}).json()
    client.post(f"/prs/{pr['id']}/invite-vendors", headers=req, json={"vendor_ids": ["vnd_test_001"]})

    quotation = client.post(
        "/quotations", headers=vnd1,
        json={"pr_id": pr["id"], "line_offers": [{"ref_line_no": 1, "quantity": "5", "unit_price": "10"}]},
    ).json()
    po = client.post("/pos", headers=req, json={"quotation_id": quotation["id"]}).json()
    grn = client.post(
        "/grns", headers=req,
        json={"po_id": po["id"], "received_lines": [{"ref_line_no": 1, "received_qty": "5"}]},
    ).json()
    bill = client.post(
        "/bills", headers=req,
        json={"grn_id": grn["id"], "billed_lines": [{"ref_line_no": 1, "quantity": "5", "unit_price": "10"}]},
    ).json()
    txn = client.post(
        "/transactions", headers=apr, json={"bill_id": bill["id"], "amount": bill["amounts"]["grand_total"]},
    ).json()
    return {"pr": pr, "quotation": quotation, "po": po, "grn": grn, "bill": bill, "txn": txn}


def test_owning_vendor_can_read_their_own_documents(client, tokens):
    req, apr, vnd1 = auth_header(tokens["requester"]), auth_header(tokens["approver"]), auth_header(tokens["vendor"])
    docs = _build_chain(client, req, apr, vnd1)

    assert client.get(f"/pos/{docs['po']['id']}", headers=vnd1).status_code == 200
    assert client.get(f"/grns/{docs['grn']['id']}", headers=vnd1).status_code == 200
    assert client.get(f"/bills/{docs['bill']['id']}", headers=vnd1).status_code == 200
    assert client.get(f"/transactions/{docs['txn']['id']}", headers=vnd1).status_code == 200
    assert client.get(f"/prs/{docs['pr']['id']}", headers=vnd1).status_code == 200  # invited


def test_other_vendor_cannot_read_po_grn_bill_transaction(client, tokens):
    req, apr = auth_header(tokens["requester"]), auth_header(tokens["approver"])
    vnd1, vnd2 = auth_header(tokens["vendor"]), auth_header(tokens["vendor2"])
    docs = _build_chain(client, req, apr, vnd1)

    # Individual GETs: 404, not 403 — tenant scope hides existence entirely,
    # same as quotations already did.
    assert client.get(f"/pos/{docs['po']['id']}", headers=vnd2).status_code == 404
    assert client.get(f"/grns/{docs['grn']['id']}", headers=vnd2).status_code == 404
    assert client.get(f"/bills/{docs['bill']['id']}", headers=vnd2).status_code == 404
    assert client.get(f"/transactions/{docs['txn']['id']}", headers=vnd2).status_code == 404

    # List endpoints: 200, but vendor1's documents are absent from vendor2's view.
    assert docs["po"]["id"] not in [d["id"] for d in client.get("/pos", headers=vnd2).json()]
    assert docs["grn"]["id"] not in [d["id"] for d in client.get("/grns", headers=vnd2).json()]
    assert docs["bill"]["id"] not in [d["id"] for d in client.get("/bills", headers=vnd2).json()]
    assert docs["txn"]["id"] not in [d["id"] for d in client.get("/transactions", headers=vnd2).json()]

    # Not-invited vendor also can't see the PR itself.
    assert client.get(f"/prs/{docs['pr']['id']}", headers=vnd2).status_code == 404
    assert docs["pr"]["id"] not in [d["id"] for d in client.get("/prs", headers=vnd2).json()]


def test_generic_documents_route_enforces_the_same_type_permission(client, tokens):
    req, apr = auth_header(tokens["requester"]), auth_header(tokens["approver"])
    vnd1, vnd2 = auth_header(tokens["vendor"]), auth_header(tokens["vendor2"])
    docs = _build_chain(client, req, apr, vnd1)

    # Generic cross-type routes must match the type-specific ones exactly —
    # a document can't be reachable here under looser rules.
    assert client.get(f"/documents/{docs['bill']['id']}", headers=vnd1).status_code == 200
    assert client.get(f"/documents/{docs['bill']['id']}", headers=vnd2).status_code == 404
    assert client.get(f"/documents/{docs['bill']['id']}/events", headers=vnd2).status_code == 404

    # Untyped list narrows by permission/scope rather than 403ing outright.
    all_docs_vnd2 = client.get("/documents", headers=vnd2).json()
    assert docs["po"]["id"] not in [d["id"] for d in all_docs_vnd2]

    # Explicit document_type filter the caller can't read at all would 403;
    # every role here has read access to every type, so just confirm the
    # filtered call still succeeds and tenant-scopes correctly.
    typed = client.get("/documents", headers=vnd2, params={"document_type": "BILL"}).json()
    assert docs["bill"]["id"] not in [d["id"] for d in typed]


def test_requester_and_approver_can_read_across_all_types(client, tokens):
    req, apr = auth_header(tokens["requester"]), auth_header(tokens["approver"])
    vnd1 = auth_header(tokens["vendor"])
    docs = _build_chain(client, req, apr, vnd1)

    for role_header in (req, apr):
        assert client.get(f"/prs/{docs['pr']['id']}", headers=role_header).status_code == 200
        assert client.get(f"/quotations/{docs['quotation']['id']}", headers=role_header).status_code == 200
        assert client.get(f"/pos/{docs['po']['id']}", headers=role_header).status_code == 200
        assert client.get(f"/grns/{docs['grn']['id']}", headers=role_header).status_code == 200
        assert client.get(f"/bills/{docs['bill']['id']}", headers=role_header).status_code == 200
        assert client.get(f"/transactions/{docs['txn']['id']}", headers=role_header).status_code == 200
