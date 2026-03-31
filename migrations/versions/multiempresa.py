"""multiempresa

Revision ID: multiempresa
Revises: 13da00781456
Create Date: 2026-03-31 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import Integer, String, Boolean


# revision identifiers, used by Alembic.
revision = "multiempresa"
down_revision = "13da00781456"
branch_labels = None
depends_on = None


def upgrade():
    # Crear tabla empresas
    op.create_table(
        "empresas",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("nombre", sa.String(length=200), nullable=False),
        sa.Column("cif", sa.String(length=32), nullable=True),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    with op.batch_alter_table("empresas") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_empresas_nombre"), ["nombre"], unique=True
        )
        batch_op.create_index(batch_op.f("ix_empresas_cif"), ["cif"], unique=True)

    # Añadir columnas empresa_id a usuarios y empleados (permite nulos inicialmente)
    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.add_column(
            sa.Column("empresa_id", sa.Integer(), nullable=True),
        )
        batch_op.create_index(
            batch_op.f("ix_usuarios_empresa_id"), ["empresa_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_usuarios_empresa_id_empresas",
            "empresas",
            ["empresa_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    with op.batch_alter_table("empleados") as batch_op:
        batch_op.add_column(
            sa.Column("empresa_id", sa.Integer(), nullable=True),
        )
        batch_op.create_index(
            batch_op.f("ix_empleados_empresa_id"), ["empresa_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_empleados_empresa_id_empresas",
            "empresas",
            ["empresa_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    # Crear empresa por defecto y asignarla a usuarios/empleados existentes (no superadmins)
    conn = op.get_bind()

    empresas_tbl = table(
        "empresas",
        column("id", Integer),
        column("nombre", String),
        column("cif", String),
        column("activa", Boolean),
    )

    # Insertar empresa por defecto
    conn.execute(
        empresas_tbl.insert().values(
            id=1,
            nombre="Empresa por defecto",
            cif=None,
            activa=True,
        )
    )

    # Asignar empresa_id=1 a usuarios no superadmin
    conn.execute(
        sa.text(
            """
            UPDATE usuarios
            SET empresa_id = 1
            WHERE rol <> :rol_superadmin
            """
        ),
        {"rol_superadmin": "superadministrador"},
    )

    # Asignar empresa_id=1 a todos los empleados existentes
    conn.execute(
        sa.text(
            """
            UPDATE empleados
            SET empresa_id = 1
            """
        )
    )

    # Hacer empresa_id obligatorio en empleados (usuarios puede seguir siendo NULL para superadmin)
    with op.batch_alter_table("empleados") as batch_op:
        batch_op.alter_column("empresa_id", existing_type=sa.Integer(), nullable=False)


def downgrade():
    # Quitar constraints e índices
    with op.batch_alter_table("empleados") as batch_op:
        batch_op.drop_constraint("fk_empleados_empresa_id_empresas", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_empleados_empresa_id"))
        batch_op.drop_column("empresa_id")

    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.drop_constraint("fk_usuarios_empresa_id_empresas", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_usuarios_empresa_id"))
        batch_op.drop_column("empresa_id")

    with op.batch_alter_table("empresas") as batch_op:
        batch_op.drop_index(batch_op.f("ix_empresas_cif"))
        batch_op.drop_index(batch_op.f("ix_empresas_nombre"))

    op.drop_table("empresas")

