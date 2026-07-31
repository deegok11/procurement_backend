from typing import Optional

from pydantic import BaseModel, Field


class LineItemArg(BaseModel):
    item_id: Optional[str] = Field(default=None, description="item master ID, if known (use list_items to look one up)")
    description: str = Field(description="what the item is")
    uom: str = Field(description="unit of measure, e.g. EA, KG, HR")
    quantity: str = Field(description="quantity as a decimal string, e.g. '100'")
    unit_price: str = Field(description="unit price as a decimal string, e.g. '1000'")
    tax_pct: str = Field(default="0", description="tax percentage as a decimal string, e.g. '10'")


class LineOfferArg(BaseModel):
    ref_line_no: int = Field(description="the line_no on the PR this offer responds to")
    quantity: str = Field(description="offered quantity as a decimal string")
    unit_price: str = Field(description="offered unit price as a decimal string")
    tax_pct: str = Field(default="0", description="tax percentage as a decimal string")


class ReceivedLineArg(BaseModel):
    ref_line_no: int = Field(description="the line_no on the PO being received against")
    received_qty: str = Field(description="quantity received as a decimal string")


class BilledLineArg(BaseModel):
    ref_line_no: int = Field(description="the line_no on the GRN/SRN being billed")
    quantity: str = Field(description="billed quantity as a decimal string")
    unit_price: str = Field(description="billed unit price as a decimal string")
    tax_pct: str = Field(default="0", description="tax percentage as a decimal string")
