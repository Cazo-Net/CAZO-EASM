"""Persist SAN + shadow-asset inventory fields.

- ssl_certificates.san: store Subject Alternative Names for cert-overlap matching.
- assets.confirmed / assets.inventory_status: distinguish known vs discovered vs
  shadow assets for Shadow Asset Detection. Existing assets default to
  inventory_status='known' (they were already in the canonical inventory).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

revision = "k4l5m6n7o8p9"
down_revision = "j3k4l5m6n7o8"
branch_labels = None
depends_on = None


def upgrade():
    # SAN on certificates (JSON list of DNS names)
    with op.batch_alter_table("ssl_certificates") as batch_op:
        batch_op.add_column(sa.Column("san", sa.JSON(), nullable=True, server_default="[]"))

    # Confirmation / shadow-asset status on the canonical asset inventory
    with op.batch_alter_table("assets") as batch_op:
        batch_op.add_column(
            sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column(
                "inventory_status",
                sa.String(20),
                nullable=False,
                server_default="discovered",
            )
        )

    # Existing assets were ALL auto-discovered via scans (never manually
    # confirmed), so they seed as 'discovered' — NOT 'known'. Only a user
    # confirming an asset promotes it to 'known'. This avoids silently marking
    # unconfirmed discoveries as authoritative inventory.
    op.execute(
        "UPDATE assets SET inventory_status='discovered', confirmed=0 "
        "WHERE inventory_status IS NULL OR inventory_status=''"
    )


def downgrade():
    with op.batch_alter_table("assets") as batch_op:
        batch_op.drop_column("inventory_status")
        batch_op.drop_column("confirmed")

    with op.batch_alter_table("ssl_certificates") as batch_op:
        batch_op.drop_column("san")
