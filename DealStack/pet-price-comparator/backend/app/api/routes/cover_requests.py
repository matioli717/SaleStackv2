from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime

from app.db.base import get_db
from app.models.product import Product
from app.models.cover_request import CoverRequest, CoverStatus, Neighborhood
from app.schemas.cover_request import CoverRequestCreate, CoverRequestRead, CoverRequestUpdate
from app.core.config import settings

router = APIRouter(prefix="/cover-requests", tags=["cover-requests"])

PARTNER_COMMISSION_PCT = settings.PARTNER_COMMISSION_PCT


@router.post("", response_model=CoverRequestRead, status_code=status.HTTP_201_CREATED)
async def create_cover_request(request: CoverRequestCreate, db: AsyncSession = Depends(get_db)):
    # Verifica produto existe
    result = await db.execute(select(Product).where(Product.id == request.product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Busca melhor preço online
    from app.models.product import Price, Retailer
    price_stmt = (
        select(Price)
        .where(Price.product_id == product.id, Price.in_stock == True, Price.retailer != Retailer.PARCEIRO_LOCAL)
        .distinct(Price.retailer)
        .order_by(Price.retailer, Price.captured_at.desc())
    )
    price_result = await db.execute(price_stmt)
    online_prices = price_result.scalars().all()

    if not online_prices:
        raise HTTPException(status_code=400, detail="No online prices available for comparison")

    best_online = min(online_prices, key=lambda p: p.price_cents)
    target_price_cents = int(best_online.price_cents * (1 - PARTNER_COMMISSION_PCT))

    # Cria cover request
    cover_request = CoverRequest(
        product_id=product.id,
        neighborhood=request.neighborhood,
        target_price_cents=target_price_cents,
        best_online_price_cents=best_online.price_cents,
    )
    db.add(cover_request)
    await db.commit()
    await db.refresh(cover_request)

    # TODO: Notificar parceiro via WhatsApp/webhook
    # await notify_partner(cover_request, product, best_online)

    return cover_request


@router.get("", response_model=list[CoverRequestRead])
async def list_cover_requests(
    status: CoverStatus | None = None,
    neighborhood: Neighborhood | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(CoverRequest).order_by(CoverRequest.created_at.desc())

    if status:
        stmt = stmt.where(CoverRequest.status == status)
    if neighborhood:
        stmt = stmt.where(CoverRequest.neighborhood == neighborhood)

    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{request_id}", response_model=CoverRequestRead)
async def get_cover_request(request_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CoverRequest).where(CoverRequest.id == request_id))
    cover_request = result.scalar_one_or_none()
    if not cover_request:
        raise HTTPException(status_code=404, detail="Cover request not found")
    return cover_request


@router.patch("/{request_id}", response_model=CoverRequestRead)
async def update_cover_request(
    request_id: UUID,
    update: CoverRequestUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CoverRequest).where(CoverRequest.id == request_id))
    cover_request = result.scalar_one_or_none()
    if not cover_request:
        raise HTTPException(status_code=404, detail="Cover request not found")

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cover_request, field, value)

    if update.status == CoverStatus.ACCEPTED and not cover_request.partner_response_at:
        cover_request.partner_response_at = datetime.utcnow()

    await db.commit()
    await db.refresh(cover_request)
    return cover_request


# Endpoint para parceiro aceitar/recusar via link único
@router.post("/{request_id}/accept", response_model=CoverRequestRead)
async def partner_accept(
    request_id: UUID,
    checkout_url: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CoverRequest).where(CoverRequest.id == request_id))
    cover_request = result.scalar_one_or_none()
    if not cover_request:
        raise HTTPException(status_code=404, detail="Cover request not found")

    if cover_request.status != CoverStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Request already {cover_request.status}")

    cover_request.status = CoverStatus.ACCEPTED
    cover_request.partner_response_at = datetime.utcnow()
    cover_request.checkout_url = checkout_url

    await db.commit()
    await db.refresh(cover_request)
    return cover_request


@router.post("/{request_id}/reject", response_model=CoverRequestRead)
async def partner_reject(
    request_id: UUID,
    notes: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CoverRequest).where(CoverRequest.id == request_id))
    cover_request = result.scalar_one_or_none()
    if not cover_request:
        raise HTTPException(status_code=404, detail="Cover request not found")

    if cover_request.status != CoverStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Request already {cover_request.status}")

    cover_request.status = CoverStatus.REJECTED
    cover_request.partner_response_at = datetime.utcnow()
    cover_request.notes = notes

    await db.commit()
    await db.refresh(cover_request)
    return cover_request