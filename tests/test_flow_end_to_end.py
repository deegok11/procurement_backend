from tests.conftest import auth_header


def test_full_lifecycle_pr_to_transaction(client, tokens):
    req = auth_header(tokens["requester"])
    apr = auth_header(tokens["approver"])
    vnd1 = auth_header(tokens["vendor"])
    vnd2 = auth_header(tokens["vendor2"])

    # Item master
    item = client.post(
        "/items/add_item", headers=req,
        json={"item_code": "E2E-ITM-1", "description": "Widget", "uom": "EA"},
    ).json()

    # PR lifecycle
    pr = client.post(
        "/prs", headers=req,
        json={
            "title": "E2E widgets",
            "line_items": [{
                "item_id": item["item_id"], "description": "Widget", "uom": "EA",
                "quantity": "10", "unit_price": "100", "tax_pct": "0",
            }],
        },
    ).json()
    assert pr["status"] == "DRAFT"

    pr = client.post(f"/prs/{pr['id']}/submit", headers=req).json()
    assert pr["status"] == "SUBMITTED"
    assert pr["document_number"] is not None

    # Self-approval blocked
    assert client.post(f"/prs/{pr['id']}/approve", headers=req, json={}).status_code == 403

    pr = client.post(f"/prs/{pr['id']}/approve", headers=apr, json={}).json()
    assert pr["status"] == "APPROVED"

    client.post(
        f"/prs/{pr['id']}/invite-vendors", headers=req,
        json={"vendor_ids": ["vnd_test_001", "vnd_test_002"]},
    )

    # Two competing quotations
    q1 = client.post(
        "/quotations", headers=vnd1,
        json={"pr_id": pr["id"], "line_offers": [{"ref_line_no": 1, "quantity": "10", "unit_price": "90"}]},
    ).json()
    client.post(
        "/quotations", headers=vnd2,
        json={"pr_id": pr["id"], "line_offers": [{"ref_line_no": 1, "quantity": "10", "unit_price": "95"}]},
    )

    # Comparison sorted cheapest-first
    cmp_ = client.get(f"/prs/{pr['id']}/compare-quotations", headers=req).json()
    assert cmp_[0]["vendor_id"] == "vnd_test_001"

    # Tenant isolation
    assert client.get(f"/quotations/{q1['id']}", headers=vnd2).status_code == 404

    # PO
    po = client.post("/pos", headers=req, json={"quotation_id": q1["id"]}).json()
    assert po["status"] == "ISSUED"
    assert po["amounts"]["grand_total"] == "900"

    # GRN with tolerance
    grn = client.post(
        "/grns", headers=req,
        json={"po_id": po["id"], "received_lines": [{"ref_line_no": 1, "received_qty": "10"}]},
    ).json()
    assert grn["status"] == "RECORDED"

    over = client.post(
        "/grns", headers=req,
        json={"po_id": po["id"], "received_lines": [{"ref_line_no": 1, "received_qty": "1"}]},
    )
    assert over.status_code == 422

    # Bill + 3-way match (matched, since price == PO price)
    bill = client.post(
        "/bills", headers=req,
        json={"grn_id": grn["id"], "billed_lines": [{"ref_line_no": 1, "quantity": "10", "unit_price": "90"}]},
    ).json()
    assert bill["status"] == "MATCHED"

    # Double-billing the same GRN line is rejected
    dup = client.post(
        "/bills", headers=req,
        json={"grn_id": grn["id"], "billed_lines": [{"ref_line_no": 1, "quantity": "10", "unit_price": "90"}]},
    )
    assert dup.status_code == 422

    # Transaction
    txn = client.post(
        "/transactions", headers=apr,
        json={"bill_id": bill["id"], "amount": bill["amounts"]["grand_total"]},
    ).json()
    assert txn["status"] == "RECORDED"

    overpay = client.post("/transactions", headers=apr, json={"bill_id": bill["id"], "amount": "1"})
    assert overpay.status_code == 422

    # Event log
    events = client.get(f"/documents/{pr['id']}/events", headers=req).json()
    event_types = [e["event_type"] for e in events]
    assert "CREATED" in event_types
    assert "STATUS_CHANGED" in event_types


def test_vendor_cannot_create_items(client, tokens):
    resp = client.post(
        "/items/add_item", headers=auth_header(tokens["vendor"]),
        json={"item_code": "NOPE", "description": "x", "uom": "EA"},
    )
    assert resp.status_code == 403


def test_only_owner_requester_can_submit_their_pr(client, tokens):
    req1 = auth_header(tokens["requester"])
    req2 = auth_header(tokens["requester2"])
    pr = client.post(
        "/prs", headers=req1,
        json={"title": "owner test", "line_items": [
            {"description": "x", "uom": "EA", "quantity": "1", "unit_price": "1"}
        ]},
    ).json()
    resp = client.post(f"/prs/{pr['id']}/submit", headers=req2)
    assert resp.status_code == 403
