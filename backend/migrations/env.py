from alembic import context
from sqlalchemy import create_engine
from models import Base

with create_engine(context.config.get_main_option("sqlalchemy.url")).begin() as conn:
    context.configure(connection=conn, target_metadata=Base.metadata)
    context.run_migrations()
