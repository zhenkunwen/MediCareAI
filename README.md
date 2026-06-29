# 🏥 MediCareAI — AI 多 Agent 医疗协作平台

> **多 Agent 自主医疗协作系统 | Multi-Agent Autonomous Medical Collaboration System**
>
> 不是聊天机器人，是一支专业医疗 Agent 团队。
> 患者驱动 + AI 辅助 + 医生验证，为 Agent 时代重新构想。

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python" alt="Python 3.12"/>
  <img src="https://img.shields.io/badge/FastAPI-0.115-teal?logo=fastapi" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react" alt="React 19"/>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License"/>
</p>

---

## 📦 项目信息

| 项目 | 说明 |
|------|------|
| 🔗 GitHub | https://github.com/zhenkunwen/MediCareAI |
| 🎯 定位 | 多 Agent 自主医疗协作平台 |
| 🧠 核心 | 自研 Agent 框架（非 LangChain） |
| 📋 角色 | 访客 / 患者 / 医生 / 管理员 |

---

## 🚀 快速启动

### 方式一：本地开发（SQLite 模式，推荐）

不需要 Docker、不需要 PostgreSQL，一条命令启动：

```bash
# 1. 克隆
git clone https://github.com/zhenkunwen/MediCareAI.git
cd MediCareAI

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 LLM API Key（如 OPENAI_API_KEY）

# 3. 安装并启动后端
cd backend
pip install -e ".[dev]"
python run_dev.py
# → http://localhost:8000
# → API 文档: http://localhost:8000/docs

# 4. 新终端，启动前端（可选）
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

### 方式二：Docker 生产部署

```bash
docker compose up -d
# → http://localhost:8000
# → API 文档: http://localhost:8000/docs
```

### 默认管理员账号

| 邮箱 | 密码 |
|------|------|
| `admin@medicareai.dev` | `admin123456`（首次登录需改密码） |

### 常见问题

| 问题 | 解决 |
|------|------|
| 端口 8000 被占用 | `netstat -ano \| findstr :8000` → `taskkill //F //PID <PID>` |
| `ModuleNotFoundError` | 运行 `pip install -e ".[dev]"` |
| 无 PostgreSQL/Redis/Celery | SQLite 模式自动降级，不影响核心功能 |
| LLM API Key | 启动后在管理后台 → LLM 配置页填写 |

---

## 🧠 核心模块设计

### 1. 多 Agent 架构

| 组件 | 职责 |
|------|------|
| **MasterAgent** | 意图分类。判断用户是想问诊、查知识还是闲聊 |
| **InterviewOrchestrator** | **核心决策引擎**。管理 InterviewState（23 个临床维度），通过 `decide_next()` 决定下一步动作 |
| **Track1：病史采集** | LLM 驱动的动态问诊，根据已收集信息生成下一个问题 |
| **Track2：搜索增强** | RAG 检索 + SearXNG 外部搜索 → 生成靶向问题 |
| **Track3：多模态解析** | 图片/文档 → 化验单结构化解析 |
| **DiagnosisAgent** | 综合所有信息，生成结构化诊断报告 |
| **PlanningAgent** | 生成治疗计划与随访方案 |
| **MonitoringAgent** | 病情监测与异常告警 |

### 2. 核心问诊流程

```
用户发主诉（SSE 流式入口）
  → MasterAgent 意图分类
  → interview() 创建 InterviewState（23 维度）
  → 三轨并行：
       Track1: 病史采集（LLM 驱动）
       Track2: 搜索增强（RAG + 外部搜索）
       Track3: 多模态解析（图片 → 化验单）
  → 三层去重（同轮互斥 / phase_key 前缀 / LLM 语义去重）
  → decide_next() 决策引擎：
       信息不足 → 继续问
       信息充足 → 调 DiagnosisAgent
  → DiagnosisAgent 生成结构化诊断报告
  → 自动创建 MedicalCase / CarePlan / 分配医生
  → 诊断后对话（parent_session_id 层级关联）
```

### 3. LLMService — 统一 AI 调用

封装所有 AI 调用，支持多提供商、Tool Call、结构化输出、流式输出、多模态。

**请求流**：
```
LLMService.chat()
  → TokenBudget.check()         # 24h 滑动窗口限流
  → SemanticCache.get()         # Level1: MD5 精确 / Level2: 余弦 >0.95
  → LLM API 调用
  → TokenBudget.deduct()        # 扣除 token
  → SemanticCache.set()         # 写入缓存
```

### 4. ToolRegistry — 工具注册表

所有工具的注册与调度中心。工具定义 → 自动生成 OpenAI Function Calling Schema → LLM 选择调用 → 执行并返回。

已注册工具：`query_patient_history`、`search_medical_knowledge` 等。

### 5. SemanticCache — 语义缓存

两级缓存，拦截点在 `LLMService.chat()`：

- **Level 1（精确匹配）**：`md5(messages + system_prompt + model + provider)` → Redis
- **Level 2（语义匹配）**：embedding 余弦相似度 > 0.95 命中
- Redis 不可用时静默降级

---

## 🛠 技术栈

| 层级 | 技术 |
|------|------|
| **后端** | Python 3.12 + FastAPI + SQLAlchemy 2.0 (async) |
| **前端** | React 19 + TypeScript + Vite + MUI 9 |
| **数据库** | PostgreSQL 17 + pgvector（生产）/ SQLite（开发） |
| **缓存** | Redis |
| **任务队列** | Celery |
| **AI/LLM** | OpenAI 兼容多提供商（OpenAI / DeepSeek / GLM / Qwen 等） |
| **认证** | JWT + 角色制（访客 / 患者 / 医生 / 管理员） |
| **搜索** | SearXNG（外部搜索）+ pgvector（向量检索）|
| **测试** | pytest + httpx |

---

## 📁 项目结构

```
MediCareAI/
├── backend/
│   ├── app/
│   │   ├── api/v1/              # REST + SSE 端点
│   │   │   ├── agents.py        # 核心：SSE 流式问诊
│   │   │   ├── auth.py          # JWT 登录/注册
│   │   │   ├── patient.py       # 患者端
│   │   │   ├── doctor.py        # 医生端
│   │   │   └── admin.py         # 管理后台
│   │   ├── services/            # ❤️ 核心业务逻辑
│   │   │   ├── agents.py        # MasterAgent, DiagnosisAgent...
│   │   │   ├── orchestrator.py  # decide_next() 决策引擎
│   │   │   ├── llm.py           # 统一 LLM 服务
│   │   │   ├── rag.py           # RAG 检索服务
│   │   │   └── semantic_cache.py  # 语义缓存
│   │   ├── models/              # SQLAlchemy 模型
│   │   ├── tools/               # 工具注册表（Function Calling）
│   │   ├── db/                  # 数据库会话 + 迁移
│   │   └── tasks/               # Celery 后台任务
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── components/          # ChatPage, DiagnosisCard 等
│   │   ├── api/                 # API 客户端 + SSE
│   │   └── theme/               # 设计 token
│   └── package.json
├── docs/
├── docker-compose.yml
└── README.md
```

---

## 💡 设计亮点

### 为什么不用 LangChain？

项目最初评估了 LangChain，结论是"过度复杂"，改为自研轻量框架：

| 对比 | LangChain | 本项目 |
|------|-----------|--------|
| 依赖 | 重量级，全量引入 | 零额外依赖 |
| 灵活性 | 受限于抽象层 | 完全可控 |
| 调试 | 黑盒链路 | 每步可打日志追踪 |
| Token 控制 | 无内置 | 滑动窗口预算控制 |
| 缓存 | 无内置 | 两级语义缓存 |
| 结构化输出 | 需额外配置 | Pydantic Schema 原生支持 |

---

## 📋 当前状态

| 功能 | 状态 |
|------|:----:|
| 三轨问诊（Track1 + Track2 + Track3） | ✅ |
| 自定义 Agent 框架（非 LangChain） | ✅ |
| 多提供商 LLM 支持 | ✅ |
| Function Calling 工具系统 | ✅ |
| 语义缓存（两级缓存） | ✅ |
| Token Budget 限流 | ✅ |
| RAG 检索 + 外部搜索 | ✅ |
| 诊断后对话 | ✅ |
| MedicalCase / CarePlan 自动创建 | ✅ |
| 患者端健康档案 + 随访计划 | ✅ |
| 医生端控制台 | 🔄 开发中 |
| MCP 协议支持 | 📋 计划中 |
| Android App | 📋 计划中 |

---

## 📝 License

[MIT](LICENSE) © 2026 zhenkunwen
