"""ausencia tipos (reemplaza absentismo)

Revision ID: ausencia_tipos
Revises: clasif_dia
Create Date: 2026-04-06 12:00:00.000000
"""

from alembic import op


revision = "ausencia_tipos"
down_revision = "clasif_dia"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE clasificaciones_dia_laboral
        SET tipo = 'ausencia_no_justificada'
        WHERE tipo = 'absentismo'
        """
    )


def downgrade():
    # No revertir tipos: habría mezclado ausencias nuevas con datos antiguos.
    pass
