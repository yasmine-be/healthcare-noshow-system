from alembic import op
from sqlalchemy import inspect

from database import Base
import models

revision = "20261109_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing_tables = set(inspect(bind).get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            table.create(bind=bind)
        for index in table.indexes:
            index.create(bind=bind, checkfirst=True)


def downgrade():
    raise RuntimeError(
        "The initial schema migration is intentionally irreversible to protect "
        "existing patient and appointment data."
    )
