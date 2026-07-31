from decimal import Decimal

from app.domain.schemas import DocumentType
from app.storage.documents_repo import documents_repo


def D(value: str | None) -> Decimal:
    return Decimal(value or "0")


def cumulative_received_qty_for_po_line(po_id: str, po_line_no: int, *, exclude_grn_id: str | None = None) -> Decimal:
    """Sum of received quantity across every non-cancelled GRN/SRN against this
    PO, for the given PO line (matched via each GRN line's extra['po_line_no'])."""
    grns = documents_repo.list(document_type=DocumentType.GRN_SRN, parent_document_id=po_id)
    total = Decimal("0")
    for grn in grns:
        if grn.status == "CANCELLED" or grn.id == exclude_grn_id:
            continue
        for line in grn.line_items:
            if line.extra.get("po_line_no") == po_line_no:
                total += D(line.quantity)
    return total


def received_value_for_po_line(po_id: str, po_line_no: int) -> Decimal:
    """Sum of line_total across every non-cancelled GRN/SRN for this PO line —
    the ceiling that cumulative billed value must not exceed."""
    grns = documents_repo.list(document_type=DocumentType.GRN_SRN, parent_document_id=po_id)
    total = Decimal("0")
    for grn in grns:
        if grn.status == "CANCELLED":
            continue
        for line in grn.line_items:
            if line.extra.get("po_line_no") == po_line_no:
                total += D(line.line_total)
    return total


def cumulative_billed_value_for_po_line(po_id: str, po_line_no: int, *, exclude_bill_id: str | None = None) -> Decimal:
    """Sum of billed line_total across every non-cancelled BILL whose parent
    GRN belongs to this PO, for the given PO line."""
    grns = documents_repo.list(document_type=DocumentType.GRN_SRN, parent_document_id=po_id)
    grn_ids = {g.id for g in grns}
    total = Decimal("0")
    for grn_id in grn_ids:
        bills = documents_repo.list(document_type=DocumentType.BILL, parent_document_id=grn_id)
        for bill in bills:
            if bill.status == "CANCELLED" or bill.id == exclude_bill_id:
                continue
            for line in bill.line_items:
                if line.extra.get("po_line_no") == po_line_no:
                    total += D(line.line_total)
    return total


def cumulative_paid_for_bill(bill_id: str, *, exclude_transaction_id: str | None = None) -> Decimal:
    """Sum of amounts across every non-cancelled TRANSACTION against this bill."""
    txns = documents_repo.list(document_type=DocumentType.TRANSACTION, parent_document_id=bill_id)
    total = Decimal("0")
    for txn in txns:
        if txn.status == "CANCELLED" or txn.id == exclude_transaction_id:
            continue
        total += D(txn.amounts.grand_total)
    return total
