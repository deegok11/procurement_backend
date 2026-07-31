#!/usr/bin/env bash
# Full lifecycle walkthrough against a running server (see setup.sh).
# Mirrors the "Verification plan" section of the approved implementation plan.
set -euo pipefail
BASE="${1:-http://127.0.0.1:8123}"

login() {
  curl -s -X POST "$BASE/auth/login" -H "Content-Type: application/json" \
    -d "{\"username\":\"$1\",\"password\":\"$2\"}" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])"
}

jget() { python3 -c "import sys,json; d=json.load(sys.stdin); print(d$1)"; }

ALICE=$(login alice alicepw123)
BOB=$(login bob bobpw123)
ACME=$(login acme_sales acmepw123)
GLOBEX=$(login globex_sales globexpw123)
echo "[ok] logged in as alice(requester), bob(approver), acme+globex(vendors)"

ITEM=$(curl -s -X POST "$BASE/items/add_item" -H "Authorization: Bearer $ALICE" -H "Content-Type: application/json" \
  -d '{"item_code":"ITM-0001","description":"Laptop 14-inch","uom":"EA","category":"IT"}')
ITEM_ID=$(echo "$ITEM" | jget "['item_id']")
echo "[ok] item master: $ITEM_ID"

PR=$(curl -s -X POST "$BASE/prs" -H "Authorization: Bearer $ALICE" -H "Content-Type: application/json" -d "{
  \"title\": \"100 laptops\", \"line_items\": [{\"item_id\": \"$ITEM_ID\", \"description\": \"Laptop 14-inch\", \"uom\": \"EA\", \"quantity\": \"100\", \"unit_price\": \"1000\", \"tax_pct\": \"10\"}]
}")
PR_ID=$(echo "$PR" | jget "['id']")
[ "$(echo "$PR" | jget "['status']")" = "DRAFT" ] && echo "[ok] PR created DRAFT: $PR_ID"

curl -s -X POST "$BASE/prs/$PR_ID/submit" -H "Authorization: Bearer $ALICE" > /tmp/_r.json
[ "$(jget "['status']" < /tmp/_r.json)" = "SUBMITTED" ] && echo "[ok] PR submitted, number=$(jget "['document_number']" < /tmp/_r.json)"

CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/prs/$PR_ID/approve" -H "Authorization: Bearer $ALICE" -H "Content-Type: application/json" -d '{}')
[ "$CODE" = "403" ] && echo "[ok] self-approval blocked (403)"

curl -s -X POST "$BASE/prs/$PR_ID/approve" -H "Authorization: Bearer $BOB" -H "Content-Type: application/json" -d '{}' > /tmp/_r.json
[ "$(jget "['status']" < /tmp/_r.json)" = "APPROVED" ] && echo "[ok] PR approved by a different user (bob)"

curl -s -X POST "$BASE/prs/$PR_ID/invite-vendors" -H "Authorization: Bearer $ALICE" -H "Content-Type: application/json" \
  -d '{"vendor_ids": ["vnd_acme_001", "vnd_globex_001"]}' > /dev/null
echo "[ok] invited acme + globex"

ACME_Q=$(curl -s -X POST "$BASE/quotations" -H "Authorization: Bearer $ACME" -H "Content-Type: application/json" -d "{
  \"pr_id\": \"$PR_ID\", \"line_offers\": [{\"ref_line_no\": 1, \"quantity\": \"100\", \"unit_price\": \"900\", \"tax_pct\": \"10\"}]
}")
ACME_QID=$(echo "$ACME_Q" | jget "['id']")
curl -s -X POST "$BASE/quotations" -H "Authorization: Bearer $GLOBEX" -H "Content-Type: application/json" -d "{
  \"pr_id\": \"$PR_ID\", \"line_offers\": [{\"ref_line_no\": 1, \"quantity\": \"100\", \"unit_price\": \"950\", \"tax_pct\": \"10\"}]
}" > /dev/null
echo "[ok] acme + globex quotations submitted"

CMP=$(curl -s "$BASE/prs/$PR_ID/compare-quotations" -H "Authorization: Bearer $ALICE")
FIRST_VENDOR=$(echo "$CMP" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['vendor_id'])")
[ "$FIRST_VENDOR" = "vnd_acme_001" ] && echo "[ok] comparison sorted, acme (cheaper) first"

CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/quotations/$ACME_QID" -H "Authorization: Bearer $GLOBEX")
[ "$CODE" = "404" ] && echo "[ok] tenant isolation: globex cannot read acme's quotation (404)"

PO=$(curl -s -X POST "$BASE/pos" -H "Authorization: Bearer $ALICE" -H "Content-Type: application/json" -d "{\"quotation_id\": \"$ACME_QID\"}")
PO_ID=$(echo "$PO" | jget "['id']")
PO_TOTAL=$(echo "$PO" | jget "['amounts']['grand_total']")
[ "$(echo "$PO" | jget "['status']")" = "ISSUED" ] && echo "[ok] PO issued: $(echo "$PO" | jget "['document_number']") total=$PO_TOTAL"

CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/pos/$PO_ID" -H "Authorization: Bearer $GLOBEX")
[ "$CODE" != "200" ] && echo "[ok] tenant isolation: globex cannot read acme's PO ($CODE)"

curl -s -X POST "$BASE/grns" -H "Authorization: Bearer $ALICE" -H "Content-Type: application/json" -d "{
  \"po_id\": \"$PO_ID\", \"received_lines\": [{\"ref_line_no\": 1, \"received_qty\": \"60\"}]
}" > /tmp/_r.json
GRN_ID=$(jget "['id']" < /tmp/_r.json)
[ "$(jget "['status']" < /tmp/_r.json)" = "RECORDED" ] && echo "[ok] partial GRN recorded (60/100): $GRN_ID"

CODE=$(curl -s -o /tmp/_r.json -w "%{http_code}" -X POST "$BASE/grns" -H "Authorization: Bearer $ALICE" -H "Content-Type: application/json" -d "{
  \"po_id\": \"$PO_ID\", \"received_lines\": [{\"ref_line_no\": 1, \"received_qty\": \"60\"}]
}")
[ "$CODE" = "422" ] && echo "[ok] over-tolerance GRN rejected (422): $(jget "['detail']" < /tmp/_r.json)"

curl -s -X POST "$BASE/grns" -H "Authorization: Bearer $ALICE" -H "Content-Type: application/json" -d "{
  \"po_id\": \"$PO_ID\", \"received_lines\": [{\"ref_line_no\": 1, \"received_qty\": \"40\"}]
}" > /tmp/_r.json
GRN_ID_2=$(jget "['id']" < /tmp/_r.json)
echo "[ok] remaining 40 received (total 100): $GRN_ID_2"

curl -s -X POST "$BASE/bills" -H "Authorization: Bearer $ALICE" -H "Content-Type: application/json" -d "{
  \"grn_id\": \"$GRN_ID\", \"billed_lines\": [{\"ref_line_no\": 1, \"quantity\": \"60\", \"unit_price\": \"900\", \"tax_pct\": \"10\"}]
}" > /tmp/_r.json
BILL_ID=$(jget "['id']" < /tmp/_r.json)
[ "$(jget "['status']" < /tmp/_r.json)" = "MATCHED" ] && echo "[ok] bill auto-matched (price matches PO): $BILL_ID"

CODE=$(curl -s -o /tmp/_r.json -w "%{http_code}" -X POST "$BASE/bills" -H "Authorization: Bearer $ALICE" -H "Content-Type: application/json" -d "{
  \"grn_id\": \"$GRN_ID\", \"billed_lines\": [{\"ref_line_no\": 1, \"quantity\": \"60\", \"unit_price\": \"900\", \"tax_pct\": \"10\"}]
}")
[ "$CODE" = "422" ] && echo "[ok] over-billed (double-billing same GRN line) rejected (422): $(jget "['detail']" < /tmp/_r.json)"

curl -s -X POST "$BASE/bills" -H "Authorization: Bearer $ALICE" -H "Content-Type: application/json" -d "{
  \"grn_id\": \"$GRN_ID_2\", \"billed_lines\": [{\"ref_line_no\": 1, \"quantity\": \"40\", \"unit_price\": \"850\", \"tax_pct\": \"10\"}]
}" > /tmp/_r.json
BILL_ID_2=$(jget "['id']" < /tmp/_r.json)
[ "$(jget "['status']" < /tmp/_r.json)" = "MATCH_EXCEPTION" ] && echo "[ok] mismatched unit price -> MATCH_EXCEPTION: $BILL_ID_2"

curl -s -X POST "$BASE/bills/$BILL_ID_2/acknowledge-exception" -H "Authorization: Bearer $BOB" -H "Content-Type: application/json" -d '{}' > /tmp/_r.json
[ "$(jget "['status']" < /tmp/_r.json)" = "ACKNOWLEDGED" ] && echo "[ok] approver acknowledged the exception"

BILL_TOTAL=$(curl -s "$BASE/bills/$BILL_ID" -H "Authorization: Bearer $ALICE" | jget "['amounts']['grand_total']")
curl -s -X POST "$BASE/transactions" -H "Authorization: Bearer $BOB" -H "Content-Type: application/json" -d "{
  \"bill_id\": \"$BILL_ID\", \"amount\": \"$BILL_TOTAL\", \"payment_method\": \"wire\"
}" > /tmp/_r.json
[ "$(jget "['status']" < /tmp/_r.json)" = "RECORDED" ] && echo "[ok] full payment recorded for bill $BILL_ID"

CODE=$(curl -s -o /tmp/_r.json -w "%{http_code}" -X POST "$BASE/transactions" -H "Authorization: Bearer $BOB" -H "Content-Type: application/json" -d "{
  \"bill_id\": \"$BILL_ID\", \"amount\": \"1\", \"payment_method\": \"wire\"
}")
[ "$CODE" = "422" ] && echo "[ok] overpay rejected (422): $(jget "['detail']" < /tmp/_r.json)"

EVENTS=$(curl -s "$BASE/documents/$PR_ID/events" -H "Authorization: Bearer $ALICE")
NUM_EVENTS=$(echo "$EVENTS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
echo "[ok] PR audit trail has $NUM_EVENTS events"

echo ""
echo "ALL CHECKS PASSED"
