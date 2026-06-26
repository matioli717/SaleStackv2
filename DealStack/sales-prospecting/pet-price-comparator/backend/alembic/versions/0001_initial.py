"""Initial migration

Revision ID: 0001
Revises:
Create Date: 2024-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums
    retailer_enum = postgresql.ENUM(
        "petlove", "cobasi", "petz", "amazon", "parceiro_local",
        name="retailer_enum",
        create_type=True
    )
    retailer_enum.create(op.get_bind(), checkfirst=True)

    cover_status_enum = postgresql.ENUM(
        "pending", "accepted", "rejected", "expired",
        name="cover_status_enum",
        create_type=True
    )
    cover_status_enum.create(op.get_bind(), checkfirst=True)

    neighborhood_enum = postgresql.ENUM(
        "jacarepagua", "barra_da_tijuca",
        name="neighborhood_enum",
        create_type=True
    )
    neighborhood_enum.create(op.get_bind(), checkfirst=True)

    # Products table
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("gtin", sa.String(14), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("brand", sa.String(100), nullable=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("subcategory", sa.String(100), nullable=True),
        sa.Column("weight_kg", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )

    op.create_index("ix_products_brand_category", "products", ["brand", "category"])
    op.create_index("ix_products_gtin_active", "products", ["gtin", "is_active"])

    # Prices table
    op.create_table(
        "prices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("retailer", retailer_enum, nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("in_stock", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )

    op.create_unique_constraint("uq_price_product_retailer", "prices", ["product_id", "retailer"])
    op.create_index("ix_prices_product_retailer_captured", "prices", ["product_id", "retailer", "captured_at"])

    # Cover requests table
    op.create_table(
        "cover_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("neighborhood", neighborhood_enum, nullable=False),
        sa.Column("target_price_cents", sa.Integer(), nullable=False),
        sa.Column("best_online_price_cents", sa.Integer(), nullable=False),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", cover_status_enum, nullable=False, server_default="pending"),
        sa.Column("partner_response_at", sa.DateTime(), nullable=True),
        sa.Column("checkout_url", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(), nullable=False, server_default=sa.text("now() + interval '24 hours'")),
    )

    op.create_index("ix_cover_requests_status_created", "cover_requests", ["status", "created_at"])
    op.create_index("ix_cover_requests_partner_status", "cover_requests", ["partner_id", "status"])


def downgrade() -> None:
    op.drop_table("cover_requests")
    op.drop_table("prices")
    op.drop_table("products")

    postgresql.ENUM(name="retailer_enum").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="cover_status_enum").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="neighborhood_enum").drop(op.get_bind(), checkfirst=True)