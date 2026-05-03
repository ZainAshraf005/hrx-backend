from logging.config import fileConfig
import os
import asyncio

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

from dotenv import load_dotenv

# load env
load_dotenv()

config = context.config

DATABASE_URL = os.getenv("DATABASE_URL")
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# IMPORTANT: import ALL models so metadata is populated
from app.core.database import Base
from app import models  # this must import everything (your __init__.py fix matters here)

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = create_async_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,
    )

    async def run():
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)

    asyncio.run(run())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()