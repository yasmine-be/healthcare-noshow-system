from alembic import op
from sqlalchemy import inspect

revision = "20261109_02"
down_revision = "20261109_01"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if "appointments" not in inspector.get_table_names():
        return

    indexes = inspector.get_indexes("appointments")
    index_columns = {
        index["name"]: index.get("column_names") or [] for index in indexes
    }

    index_name = "ix_appointments_date_rdv"
    existing_columns = index_columns.get(index_name)
    if existing_columns == ["date_rdv"]:
        op.drop_index(index_name, table_name="appointments")
        existing_columns = None
    elif existing_columns not in (None, ["date_rdv", "id"]):
        raise RuntimeError(f"Index {index_name} exists with unexpected columns")

    if existing_columns is None:
        op.create_index(index_name, "appointments", ["date_rdv", "id"])


def downgrade():
    raise RuntimeError(
        "This forward-only migration is intentionally irreversible to protect "
        "existing appointment data."
    )
