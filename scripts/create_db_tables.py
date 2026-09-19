import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
import app.db.metadata  # Ensures all models (Store, IAM, Customers, Catalog) are loaded in Base.metadata
from app.db.base import Base


async def create_tables():
    print(f"Connecting to DB: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else '...'}")
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        print("Creating all missing tables from Base.metadata...")
        await conn.run_sync(Base.metadata.create_all)
        print("Successfully created/verified all database tables!")
        
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_tables())
