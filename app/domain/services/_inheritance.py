from typing import Callable

from app.domain.schemas import Document, LineItem


def derive_line_items(
    parent: Document, quantity_mapper: Callable[[LineItem], str]
) -> list[LineItem]:
    """Copy each parent line into a fresh child scaffold, stamping ref_line_no
    and denormalizing po_line_no into extra so cumulative-quantity/value checks
    never need more than one hop back. This is the concrete mechanism behind
    "later stages reuse the parent document's fields" instead of redefining
    the schema per stage."""
    return [
        LineItem(
            line_no=pl.line_no,
            ref_line_no=pl.line_no,
            item_id=pl.item_id,
            description=pl.description,
            uom=pl.uom,
            quantity=quantity_mapper(pl),
            unit_price=pl.unit_price,
            line_total=None,
            tax_pct=pl.tax_pct,
            extra={**pl.extra, "po_line_no": pl.extra.get("po_line_no", pl.line_no)},
        )
        for pl in parent.line_items
    ]
