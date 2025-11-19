"""Initialize token tracking tables in existing database."""
import asyncio
import aiosqlite
from pathlib import Path
import os
import sys

# Add parent directory to path to import agent modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.database.token_schema import create_token_tracking_tables


async def main():
    """Initialize token tracking tables."""
    db_path = Path(os.getenv("DB_PATH", "./trading_data.db"))

    print(f"Initializing token tracking tables in {db_path}")

    async with aiosqlite.connect(db_path) as db:
        await create_token_tracking_tables(db)
        await db.commit()

    print("✅ Token tracking tables created successfully")


if __name__ == "__main__":
    asyncio.run(main())
