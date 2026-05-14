"""zona horaria IANA por empresa

Revision ID: empresa_zona_h
Revises: tipo_empleado_col
Create Date: 2026-05-14 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "empresa_zona_h"
down_revision = "tipo_empleado_col"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "empresas",
        sa.Column("zona_horaria", sa.String(length=64), nullable=True),
    )


def downgrade():
    op.drop_column("empresas", "zona_horaria")
