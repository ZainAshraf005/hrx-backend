from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import settings

DataBase_Url = settings.DATABASE_URL

engine = create_async_engine(DataBase_Url, echo=False)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

async def get_db():
    async  with AsyncSessionLocal() as session:
        yield session
