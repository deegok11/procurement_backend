from decimal import Decimal
from typing import NamedTuple

from app.domain.errors import InvariantViolationError
from app.domain.schemas import Document, LineItem


def D(value: str | None) -> Decimal:
    return Decimal(value or "0")


def check_no_receipt_against_invalid_po(po: Document) -> None:
    """No GRN/SRN may be recorded against a cancelled or unissued PO."""
    if po.status != "ISSUED":
        raise InvariantViolationError(
            f"cannot record a receipt against PO {po.id} in status '{po.status}' "
            "(PO must be ISSUED)"
        )


def check_grn_tolerance(
    po_ordered_qty: str, cumulative_received_qty: str, tolerance_pct: float
) -> None:
    """Cumulative GRN quantity cannot exceed PO quantity beyond the configured tolerance."""
    max_allowed = D(po_ordered_qty) * (Decimal("1") + Decimal(str(tolerance_pct)) / Decimal("100"))
    if D(cumulative_received_qty) > max_allowed:
        raise InvariantViolationError(
            f"cumulative received quantity {cumulative_received_qty} exceeds PO quantity "
            f"{po_ordered_qty} plus {tolerance_pct}% tolerance (max {max_allowed})"
        )


def check_cumulative_billed_not_exceed_received(
    received_value: str, cumulative_billed_value: str
) -> None:
    """Cumulative invoiced/billed value cannot exceed received value. Hard cap, no tolerance."""
    if D(cumulative_billed_value) > D(received_value):
        raise InvariantViolationError(
            f"cumulative billed value {cumulative_billed_value} exceeds received value "
            f"{received_value}"
        )


def check_cumulative_paid_not_exceed_billed(billed_value: str, cumulative_paid: str) -> None:
    """Cumulative paid amount cannot exceed the bill's total. Hard cap, no tolerance."""
    if D(cumulative_paid) > D(billed_value):
        raise InvariantViolationError(
            f"cumulative paid amount {cumulative_paid} exceeds billed value {billed_value}"
        )


class LineMatchResult(NamedTuple):
    line_no: int
    ok: bool
    detail: str


class ThreeWayMatchResult(NamedTuple):
    status: str  # "MATCHED" | "MATCH_EXCEPTION"
    line_results: list[LineMatchResult]


def run_three_way_match(
    bill_lines: list[LineItem], grn_lines: list[LineItem], po_lines: list[LineItem]
) -> ThreeWayMatchResult:
    """Per bill line, compare against the PO line it (transitively) derives from,
    via ref_line_no -> GRN line -> extra['po_line_no'] -> PO line. Hard invariants
    (cumulative value <= received) are checked separately by the caller before this
    runs; this function only decides whether unit prices line up well enough to
    auto-clear (MATCHED) or need a human's eyes (MATCH_EXCEPTION)."""
    grn_by_line_no = {ln.line_no: ln for ln in grn_lines}
    po_by_line_no = {ln.line_no: ln for ln in po_lines}

    results: list[LineMatchResult] = []
    for bl in bill_lines:
        grn_line = grn_by_line_no.get(bl.ref_line_no) if bl.ref_line_no else None
        po_line_no = grn_line.extra.get("po_line_no") if grn_line else None
        po_line = po_by_line_no.get(po_line_no) if po_line_no else None

        if grn_line is None or po_line is None:
            results.append(LineMatchResult(bl.line_no, False, "no matching GRN/PO line found"))
            continue

        if bl.unit_price is not None and po_line.unit_price is not None and D(
            bl.unit_price
        ) != D(po_line.unit_price):
            results.append(
                LineMatchResult(
                    bl.line_no,
                    False,
                    f"unit price {bl.unit_price} does not match PO unit price {po_line.unit_price}",
                )
            )
            continue

        if D(bl.quantity) > D(grn_line.quantity):
            results.append(
                LineMatchResult(
                    bl.line_no,
                    False,
                    f"billed quantity {bl.quantity} exceeds received quantity {grn_line.quantity}",
                )
            )
            continue

        results.append(LineMatchResult(bl.line_no, True, "matched"))

    overall = "MATCHED" if all(r.ok for r in results) and results else "MATCH_EXCEPTION"
    return ThreeWayMatchResult(status=overall, line_results=results)
