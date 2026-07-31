from decimal import Decimal

from app.domain.schemas import Amounts, LineItem


def D(value: str | None) -> Decimal:
    return Decimal(value or "0")


def compute_line_total(quantity: str, unit_price: str | None, tax_pct: str | None) -> str:
    base = D(quantity) * D(unit_price)
    with_tax = base * (Decimal("1") + D(tax_pct) / Decimal("100"))
    return str(with_tax)


def compute_amounts(line_items: list[LineItem]) -> Amounts:
    subtotal = sum((D(li.quantity) * D(li.unit_price) for li in line_items), Decimal("0"))
    grand_total = sum((D(li.line_total) for li in line_items), Decimal("0"))
    tax_total = grand_total - subtotal
    return Amounts(subtotal=str(subtotal), tax_total=str(tax_total), grand_total=str(grand_total))
