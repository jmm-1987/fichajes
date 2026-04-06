"""clasificacion dia laboral

Revision ID: clasif_dia
Revises: multiempresa
Create Date: 2026-04-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "clasif_dia"
down_revision = "multiempresa"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "clasificaciones_dia_laboral",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("empleado_id", sa.Integer(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("tipo", sa.String(length=32), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("creado_por_usuario_id", sa.Integer(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["empleado_id"],
            ["empleados.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["creado_por_usuario_id"],
            ["usuarios.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "empleado_id",
            "fecha",
            name="uq_clasificacion_dia_empleado_fecha",
        ),
    )
    op.create_index(
        "ix_clasificaciones_dia_laboral_empleado_id",
        "clasificaciones_dia_laboral",
        ["empleado_id"],
    )
    op.create_index(
        "ix_clasificaciones_dia_laboral_fecha",
        "clasificaciones_dia_laboral",
        ["fecha"],
    )


def downgrade():
    op.drop_index("ix_clasificaciones_dia_laboral_fecha", table_name="clasificaciones_dia_laboral")
    op.drop_index("ix_clasificaciones_dia_laboral_empleado_id", table_name="clasificaciones_dia_laboral")
    op.drop_table("clasificaciones_dia_laboral")
