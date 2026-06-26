from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal

from app.models.cover_request import CoverStatus, Neighborhood


class CoverRequestCreate(BaseModel):
    product_id: str = Field(..., description="UUID do produto")
    neighborhood: Neighborhood
    # target_price_cents calculado automaticamente no backend


class CoverRequestUpdate(BaseModel):
    status: Optional[CoverStatus] = None
    partner_response_at: Optional[datetime] = None
    checkout_url: Optional[str] = None
    notes: Optional[str] = None


class CoverRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    neighborhood: Neighborhood
    target_price_cents: int
    best_online_price_cents: int
    partner_id: Optional[str]
    status: CoverStatus
    partner_response_at: Optional[datetime]
    checkout_url: Optional[str]
    notes: Optional[str]
    created_at: datetime
    expires_at: datetime

    @property
    def target_price_reais(self) -> Decimal:
        return Decimal(self.target_price_cents) / 100

    @property
    def best_online_price_reais(self) -> Decimal:
        return Decimal(self.best_online_price_cents) / 100