#!/usr/bin/env bash
# 医智云·AI医疗协作平台 一键初始化
# 前置条件: PostgreSQL + Redis 已启动

set -e

echo "=== 1. 运行数据库迁移 ==="
cd "$(dirname "$0")/.."
alembic upgrade head

echo ""
echo "=== 2. 导入知识图谱初始数据 ==="
python -m app.scripts.seed_knowledge

echo ""
echo "=== 3. 启动开发服务器 ==="
echo "API 文档: http://localhost:8000/docs"
echo ""
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
