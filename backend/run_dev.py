"""开发服务器启动脚本 — 自动建表（无需 PostgreSQL）。

使用方式：python run_dev.py
"""

import asyncio
import os
import sys

# 开发环境固定配置（encryption.py 使用 os.getenv，必须在此处设置）
os.environ["API_KEY_MASTER_KEY"] = "dev-master-key-32-chars-long-for-encryption!"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./medicareai.db"

from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

# 注册 PostgreSQL 类型 → SQLite 类型映射
SQLiteTypeCompiler.visit_TSVECTOR = lambda self, type_, **kw: "TEXT"
SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"
SQLiteTypeCompiler.visit_UUID = lambda self, type_, **kw: "VARCHAR(32)"
SQLiteTypeCompiler.visit_ARRAY = lambda self, type_, **kw: "JSON"
SQLiteTypeCompiler.visit_ENUM = lambda self, type_, **kw: "VARCHAR(20)"

from app.db.session import async_engine, Base
import app.models  # 加载所有模型
# 在 models 之后加载 conversations 表（避免循环导入）
from app.api.v1.conversations import Conversation, ConversationMessage  # noqa: F401, E402


async def init_db():
    """创建所有数据库表."""
    async with async_engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            try:
                await conn.run_sync(table.create)
                print(f"  [OK] {table.name}")
            except Exception as e:
                err = str(e)
                if "already exists" in err.lower():
                    print(f"  [-] {table.name} (已存在)")
                else:
                    print(f"  [!] {table.name}: {str(e)[:80]}")
    print("[OK] 数据库表创建完成")


async def _migrate():
    """安全迁移：已有表加新列（SQLite ALTER TABLE，不丢数据）。"""
    migrations = [
        ("medication_reminders", "lead_minutes", "INTEGER DEFAULT 15"),
        ("medication_reminders", "remind_enabled", "BOOLEAN DEFAULT 1"),
        ("medication_reminders", "last_reminded_at", "DATETIME"),
        ("medication_reminders", "reminded_count", "INTEGER DEFAULT 0"),
        ("health_profiles", "blood_type", "VARCHAR(20)"),
        ("agent_sessions", "title", "VARCHAR(200)"),
        ("medical_case_comments", "case_id", "VARCHAR(32)"),
        ("medical_case_comments", "author_id", "VARCHAR(32)"),
        ("medical_case_comments", "author_name", "VARCHAR(100)"),
        ("medical_case_comments", "content", "TEXT"),
        ("medical_case_comments", "created_at", "DATETIME"),
        ("medical_messages", "deleted_for_patient", "BOOLEAN DEFAULT 0"),
        ("medical_messages", "deleted_for_doctor", "BOOLEAN DEFAULT 0"),
        ("medical_conversations", "patient_deleted_at", "DATETIME"),
        ("medical_conversations", "doctor_deleted_at", "DATETIME"),
        ("users", "avatar_url", "VARCHAR(500)"),
    ]
    async with async_engine.connect() as conn:
        for table, col, col_type in migrations:
            try:
                result = await conn.execute(
                    __import__('sqlalchemy').text(f"PRAGMA table_info({table})")
                )
                existing = {row[1] for row in result.fetchall()}
                if col not in existing:
                    await conn.execute(
                        __import__('sqlalchemy').text(
                            f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"
                        )
                    )
                    print(f"  [MIGRATE] {table}.{col}")
            except Exception as e:
                print(f"  [!] {table}.{col}: {str(e)[:60]}")
        await conn.commit()
    print("[OK] 数据库迁移完成")


if __name__ == "__main__":
    asyncio.run(init_db())
    asyncio.run(_migrate())

    import subprocess, sys
    env = os.environ.copy()
    env["API_KEY_MASTER_KEY"] = "dev-master-key-32-chars-long-for-encryption!"
    env["DATABASE_URL"] = "sqlite+aiosqlite:///./medicareai.db"
    upload_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
    env["UPLOAD_DIR"] = os.path.abspath(upload_dir)
    print("[OK] 启动开发服务器: http://localhost:8000")
    print("[OK] API 文档: http://localhost:8000/docs")
    subprocess.run(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        env=env,
    )
