from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal


class ProductBase(BaseModel):
    gtin: str = Field(..., min_length=13, max_length=14, description="EAN-13/GTIN")
    name: str = Field(..., max_length=255)
    brand: Optional[str] = Field(None, max_length=100)
    category: str = Field(..., max_length=100)
    subcategory: Optional[str] = Field(None, max_length=100)
    weight_kg: Optional[int] = Field(None, description="Peso em gramas")
    description: Optional[str] = None
    image_url: Optional[str] = None


class ProductCreate(ProductBase):
    pass


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PriceBase(BaseModel):
    retailer: str
    price_cents: int = Field(..., description="Preço final em centavos (frete incluso)")
    in_stock: bool = True
    url: Optional[str] = None


class PriceRead(PriceBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    captured_at: datetime


class PriceComparison(BaseModel):
    """Resultado da comparação para um produto"""
    product: ProductRead
    best_online_price: PriceRead
    all_prices: list[PriceRead]
    target_price_cents: int = Field(..., description="Preço alvo para o parceiro cobrir (melhor_online * 0.95)")
    savings_cents: int = Field(..., description="Economia estimada vs melhor online")
    savings_pct: float = Field(..., description="% de economia")
    partner_price_cents: Optional[int] = Field(None, description="Preço do parceiro local (se houver)")
    can_cover: bool = Field(..., description="Se o parceiro pode cobrir com margem mínima")

    @property
    def target_price_reais(self) -> Decimal:
        return Decimal(self.target_price_cents) / 100

    @property
    def savings_reais(self) -> Decimal:
        return Decimal(self.savings_cents) / 100