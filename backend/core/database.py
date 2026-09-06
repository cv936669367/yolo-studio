"""
YOLO Studio - Database Configuration
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """Dependency for getting database session"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Initialize database tables + 轻量列迁移（老库补新列）"""
    from models import project, image, annotation, train_run  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_columns)


def _ensure_columns(sync_conn):
    """为既有数据库补齐新版本新增的列（幂等）"""
    from sqlalchemy import text

    def col_exists(table: str, col: str) -> bool:
        rows = sync_conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return any(r[1] == col for r in rows)

    adds = {
        "train_runs": [("hyperparams", "TEXT")],     # 训练超参快照（JSON）
        "projects": [("class_colors", "TEXT")],      # 类别→颜色映射（JSON）
        "images": [("sha256", "VARCHAR(64)")],       # 内容哈希（同工程去重）
    }
    for table, cols in adds.items():
        for name, col_type in cols:
            if not col_exists(table, name):
                sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {col_type}"))
