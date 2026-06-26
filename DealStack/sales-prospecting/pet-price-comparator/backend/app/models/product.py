import enum
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, Enum, Index, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base


class Retailer(str, enum.Enum):
    PETLOVE = "petlove"
    COBASI = "cobasi"
    PETZ = "petz"
    AMAZON = "amazon"
    PARCEIRO_LOCAL = "parceiro_local"


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gtin = Column(String(14), unique=True, index=True, nullable=False)  # EAN-13
    name = Column(String(255), nullable=False)
    brand = Column(String(100), index=True)
    category = Column(String(100), index=True)  # racao, medicamento, antipulga, vermifugo, etc
    subcategory = Column(String(100), nullable=True)  # racao_cao, racao_gato, etc
    weight_kg = Column(Integer, nullable=True)  # peso em gramas
    description = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    prices = relationship("Price", back_populates="product", cascade="all, delete-orphan")
    cover_requests = relationship("CoverRequest", back_populates="product")

    __table_args__ = (
        Index("ix_products_brand_category", "brand", "category"),
        Index("ix_products_gtin_active", "gtin", "is_active"),
    )


class Price(Base):
    __tablename__ = "prices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    retailer = Column(Enum(Retailer), nullable=False, index=True)
    price_cents = Column(Integer, nullable=False)  # preço final com frete incluso
    in_stock = Column(Boolean, default=True, index=True)
    url = Column(Text, nullable=True)
    captured_at = Column(DateTime, default=datetime.utcnow, index=True)

    product = relationship("Product", back_populates="prices")

    __table_args__ = (
        UniqueConstraint("product_id", "retailer", name="uq_price_product_retailer"),
        Index("ix_prices_product_retailer_captured", "product_id", "retailer", "captured_at"),
    )