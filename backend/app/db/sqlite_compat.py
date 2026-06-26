"""SQLite 兼容性补丁：将 PostgreSQL 特有类型映射为 SQLite 兼容类型。

仅在开发环境（SQLite）下加载。生产环境（PostgreSQL）不受影响。
"""

from sqlalchemy import TypeEngine


class TSVECTOR(TypeEngine):
    """SQLite 兼容的 TSVECTOR 替代 — 使用 Text 存储。"""
    def get_col_spec(self, **kw):
        return "TEXT"


# 在 SQLite 下覆盖 SQLAlchemy 的 TSVECTOR 类型映射
from sqlalchemy.dialects import sqlite
from sqlalchemy import types as sa_types

# 注册 TSVECTOR 的 SQLite 处理器
@sqlite.base.ischema_names.register("tsvector")
def _visit_tsvector_sqlite():
    return TSVECTOR

# 让所有 TSVECTOR 列在 SQLite 下用 TEXT 渲染
from sqlalchemy.sql.compiler import SQLTypeCompiler

original_visit_TSVECTOR = getattr(SQLTypeCompiler, "visit_TSVECTOR", None)
if original_visit_TSVECTOR is None:
    def visit_TSVECTOR_sqlite(self, type_, **kw):
        return "TEXT"
    SQLTypeCompiler.visit_TSVECTOR = visit_TSVECTOR_sqlite
