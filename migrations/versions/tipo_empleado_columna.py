"""tipo empleado en empleados

Revision ID: tipo_empleado_col
Revises: ausencia_tipos
Create Date: 2026-04-06 14:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "tipo_empleado_col"
down_revision = "ausencia_tipos"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "empleados",
        sa.Column("tipo_empleado", sa.String(length=120), nullable=True),
    )


def downgrade():
    op.drop_column("empleados", "tipo_empleado")
