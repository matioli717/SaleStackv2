from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.db.base import get_db
from app.models.product import Product, Price, Retailer
from app.schemas.product import ProductCreate, ProductRead, PriceRead

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(product: ProductCreate, db: AsyncSession = Depends(get_db)):
    db_product = Product(**product.model_dump())
    db.add(db_product)
    await db.commit()
    await db.refresh(db_product)
    return db_product


@router.get("", response_model=list[ProductRead])
async def list_products(
    category: str | None = Query(None),
    brand: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Product).where(Product.is_active == True)

    if category:
        stmt = stmt.where(Product.category == category)
    if brand:
        stmt = stmt.where(Product.brand == brand)
    if search:
        stmt = stmt.where(Product.name.ilike(f"%{search}%"))

    stmt = stmt.order_by(Product.name).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(product_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/{product_id}/prices", response_model=list[PriceRead])
async def get_product_prices(product_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Price)
        .where(Price.product_id == product_id)
        .order_by(Price.retailer, Price.captured_at.desc())
    )
    return result.scalars().all()