from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import settings

DataBase_Url = settings.DATABASE_URL

# Disable asyncpg prepared statement cache to avoid InvalidCachedStatementError
# when the database schema changes between requests.
engine = create_async_engine(
    DataBase_Url,
    echo=False,
    connect_args={"prepared_statement_cache_size": 0},
    pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    async  with AsyncSessionLocal() as session:
        yield session
