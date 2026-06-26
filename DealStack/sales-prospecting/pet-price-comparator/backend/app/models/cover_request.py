import enum
from datetime import datetime, timedelta
from sqlalchemy import Column, String, Text, Integer, DateTime, Enum, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base


class CoverStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class Neighborhood(str, enum.Enum):
    JACAREPAGUA = "jacarepagua"
    BARRA_DA_TIJUCA = "barra_da_tijuca"


class CoverRequest(Base):
    __tablename__ = "cover_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    neighborhood = Column(Enum(Neighborhood), nullable=False, index=True)
    target_price_cents = Column(Integer, nullable=False)  # preço alvo = melhor_online * 0.95
    best_online_price_cents = Column(Integer, nullable=False)  # referência
    partner_id = Column(UUID(as_uuid=True), nullable=True)  # futuro: múltiplos parceiros
    status = Column(Enum(CoverStatus), default=CoverStatus.PENDING, index=True)
    partner_response_at = Column(DateTime, nullable=True)
    checkout_url = Column(Text, nullable=True)  # link whitelabel se aceito
    notes = Column(Text, nullable=True)  # observações do parceiro
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(hours=24), index=True)

    product = relationship("Product", back_populates="cover_requests")

    __table_args__ = (
        Index("ix_cover_requests_status_created", "status", "created_at"),
        Index("ix_cover_requests_partner_status", "partner_id", "status"),
    )