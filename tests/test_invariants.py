import pytest

from app.domain.errors import InvariantViolationError
from app.domain.invariants import (
    check_cumulative_billed_not_exceed_received,
    check_cumulative_paid_not_exceed_billed,
    check_grn_tolerance,
    check_no_receipt_against_invalid_po,
    run_three_way_match,
)
from app.domain.schemas import Document, DocumentType, LineItem
from app.domain.roles import Domain


def _po_line(line_no=1, quantity="100", unit_price="10", po_line_no=None):
    return LineItem(
        line_no=line_no, description="widget", uom="EA", quantity=quantity,
        unit_price=unit_price, line_total=str(int(quantity) * int(unit_price)),
        tax_pct="0", extra={"po_line_no": po_line_no if po_line_no is not None else line_no},
    )


def test_grn_tolerance_allows_within_bounds():
    check_grn_tolerance("100", "102", tolerance_pct=2.0)  # exactly at the boundary


def test_grn_tolerance_rejects_beyond_bounds():
    with pytest.raises(InvariantViolationError):
        check_grn_tolerance("100", "102.01", tolerance_pct=2.0)


def test_grn_tolerance_zero_tolerance_rejects_any_overage():
    with pytest.raises(InvariantViolationError):
        check_grn_tolerance("100", "100.01", tolerance_pct=0)
    check_grn_tolerance("100", "100", tolerance_pct=0)


def test_billed_value_cannot_exceed_received_hard_cap():
    check_cumulative_billed_not_exceed_received("1000", "1000")  # exact match ok
    with pytest.raises(InvariantViolationError):
        check_cumulative_billed_not_exceed_received("1000", "1000.01")


def test_paid_cannot_exceed_billed_hard_cap():
    check_cumulative_paid_not_exceed_billed("500", "500")
    with pytest.raises(InvariantViolationError):
        check_cumulative_paid_not_exceed_billed("500", "500.01")


def test_no_receipt_against_unissued_or_cancelled_po():
    def make_po(status):
        return Document(
            document_type=DocumentType.PO, series_code="PO", domain=Domain.INTERNAL,
            status=status, requester_id="u", title="t", created_by="u", updated_by="u",
        )

    check_no_receipt_against_invalid_po(make_po("ISSUED"))  # ok
    with pytest.raises(InvariantViolationError):
        check_no_receipt_against_invalid_po(make_po("CANCELLED"))


def test_three_way_match_all_lines_matched():
    po_lines = [_po_line(1, "100", "10")]
    grn_lines = [_po_line(1, "100", "10")]
    grn_lines[0].extra = {"po_line_no": 1}
    bill_lines = [LineItem(
        line_no=1, ref_line_no=1, description="widget", uom="EA", quantity="100",
        unit_price="10", line_total="1000", tax_pct="0", extra={"po_line_no": 1},
    )]
    result = run_three_way_match(bill_lines, grn_lines, po_lines)
    assert result.status == "MATCHED"
    assert all(r.ok for r in result.line_results)


def test_three_way_match_price_mismatch_is_exception():
    po_lines = [_po_line(1, "100", "10")]
    grn_lines = [_po_line(1, "100", "10")]
    grn_lines[0].extra = {"po_line_no": 1}
    bill_lines = [LineItem(
        line_no=1, ref_line_no=1, description="widget", uom="EA", quantity="100",
        unit_price="12", line_total="1200", tax_pct="0", extra={"po_line_no": 1},
    )]
    result = run_three_way_match(bill_lines, grn_lines, po_lines)
    assert result.status == "MATCH_EXCEPTION"
    assert not result.line_results[0].ok


def test_three_way_match_over_received_quantity_is_exception():
    po_lines = [_po_line(1, "100", "10")]
    grn_lines = [_po_line(1, "50", "10")]  # only 50 received
    grn_lines[0].extra = {"po_line_no": 1}
    bill_lines = [LineItem(
        line_no=1, ref_line_no=1, description="widget", uom="EA", quantity="60",  # billing more than received
        unit_price="10", line_total="600", tax_pct="0", extra={"po_line_no": 1},
    )]
    result = run_three_way_match(bill_lines, grn_lines, po_lines)
    assert result.status == "MATCH_EXCEPTION"
