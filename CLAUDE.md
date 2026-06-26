# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# 🫡 大佬指令集

每次回复开头必须叫我 **大佬**。
见到大佬先叫大佬，懂？

## 🧹 测试完立即清理无用测试代码
每次测试完成后，必须删除测试过程中产生的临时代码、调试数据、curl 残留、测试用户/计划等无用产物。不留垃圾。

## ☢️ 删库等危险操作必须先问再干
任何可能造成数据丢失的操作（删数据库、清表、重置数据、批量删除等），必须先向大佬说明原因和影响范围，**获得明确同意后才能执行**。不得擅自动手。

## 📋 每次完成代码后必须进行产品经理评审
每次写完代码（或完成一个可评审的原子任务）后，必须以**专业产品经理**的身份对代码进行评审：
1. 检查功能是否完整、符合用户预期
2. 检查边界情况（空数据、异常输入、并发冲突）
3. 检查代码质量和可读性
4. 检查是否引入了不需要的依赖或代码
5. 评审通过后方可结束任务或交付

# 项目规则（永久生效）

## 🚫 非必要不修改核心代码
不要改 framework / 库 / 基础设施代码。如果必须改，先问。

## 🎯 以最小代码完成任务（最少代码实现）
能改 1 行不改 2 行。不超前设计，不引入不用的依赖。

## ✨ 代码要保证可读性（整洁 + 清晰）
- 一致的缩写、命名、注释风格
- 命名要有意义，注释说"为什么"不说"是什么"
- 不留下注释掉的代码、console.log、调试语句
- 函数/组件职责单一，长度合理
- 删除无用 import 和变量

## ✅ 每完成一个小任务必须测试正常再进行下一步
改完一个功能点立即验证（编译 / 运行 / API 测试），确认通过再继续。

## 🧪 主动扫描邻近代码
每次修改一个功能后，不要等报错：
1. 主动扫描邻近功能、相关页面的代码，检查是否有同样的 bug 模式
2. 检查 `.catch(() => {})` 等静默吃错误的地方，加上 `console.error`
3. 检查 demo/dead 数据是否被错误地用作真实数据回退
4. 检查 API 响应格式是否与前端类型定义匹配
5. 发现潜在问题立即修，不要等用户报

**违反上述任何一条必须回退。**

## 📐 修改前必须画请求流图
涉及多个入口/路径的功能修改（如 SSE 双端点、角色双入口），先在注释或文档中画出完整的请求流向图，确认所有入口都覆盖后再动手。违反此条必须回退。

## 🔍 `except: pass` 零容忍
1. 严禁在关键路径（病例创建、消息发送、数据持久化）使用 `except: pass`
2. 非关键路径允许 `except: pass`，但前面必须加 `logger.exception()` 或 `logging.exception()`
3. 每次修改后搜索改动区域是否引入了新的 `except: pass`
违反此条必须回退。

## 🕐 时间字段统一 naive UTC 策略
1. 后端所有时间存储使用 naive UTC（`datetime.now(timezone.utc).replace(tzinfo=None)`）
2. API 返回给前端时加 `Z` 后缀
3. 前端用 `new Date(iso)` 自动转本地时间显示
4. 新增时间比较时统一用 naive UTC
违反此条必须回退。

## 🧪 验证必须用 pytest
1. API 测试写 `pytest` + `httpx` 用例到 `backend/tests/` 目录
2. 禁止用 `python -c` 一次性脚本做主要验证（调试排查除外）
3. 核心功能（消息系统、问诊链路）必须有自动化测试覆盖
违反此条必须回退。

# 🧠 导师审查指令

当我说"复盘"时，自动执行以下审查：

## 审查范围
1. 审计我的AI使用记录、项目文件、缓存数据与操作日志
2. 评估工作流程，剔除无效步骤
3. 定位效率瓶颈与思维误区

## 输出要求
1. 找出**无效堆积**与冗余环节
2. 点明**拖慢效率**的习惯
3. 分析思维卡点与认知盲区
4. 给出可落地的修正方案
5. 拒绝空泛赞美，只讲真话给干货

## 长期目标
持续迭代协作模式，提升我对AI的感知力与思维能力。

# 项目启动（无 Docker，SQLite 模式）

## 后端
```bash
cd backend && python run_dev.py
```
- SQLite 自动建表，http://localhost:8000，API 文档 /docs

## 前端
```bash
cd frontend && npm run dev
```
- Vite 在 http://localhost:3000，/api 代理到后端 8000

## 端口清理
```powershell
powershell -Command "Stop-Process -Id <PID> -Force"
```

## 已知限制
- 无 PostgreSQL/Redis/Celery（仅 SQLite 模式）
- LLM API 需在后台页面配置密钥
- MUI v9 + React 19 sx prop 警告不影响功能

# 架构总览

## 三轨问诊（核心诊断流程）

```
用户发主诉（SSE 流式入口）
  → MasterAgent 意图分类
  → interview() 创建 InterviewState
  → 三轨并行:
       Track1: 病史采集（LLM 驱动的 23 临床维度问诊）
       Track2: 搜索增强（SearXNG + RAG → 靶向问题）
       Track3: 多模态解析（图片/文档 → LabReport）
  → 三层去重（同轮互斥 / phase_key 前缀 / LLM 语义去重）
  → decide_next(): 无更多问题 + 无待答 + lab 完整 → synthesize
  → DiagnosisAgent 生成结构化诊断报告
  → 诊断后对话（parent_session_id 层级）
```

## 后端分层
```
backend/app/
├── main.py                  # FastAPI 入口（CORS、路由注册、lifespan）
├── api/v1/                  # REST + SSE 端点
│   ├── agents.py            # 核心：SSE 流式问诊 + /chat 诊断后对话 + lab-reports
│   ├── auth.py              # JWT 登录/注册
│   ├── doctor.py            # 医生端 API
│   ├── admin.py             # 管理员后台
│   ├── patient.py           # 患者端（随访/档案）
│   └── documents.py         # 文件上传+OCR
├── services/                # 业务逻辑层
│   ├── agents.py            # MasterAgent, DiagnosisAgent, PlanningAgent, MonitoringAgent
│   ├── orchestrator.py      # InterviewOrchestrator — decide_next() 核心决策引擎
│   ├── llm.py               # 统一 LLM 服务（多提供商、Tool Use、结构化输出）
│   ├── multimodal_parser.py # Track3 图片→化验单解析
│   ├── rag.py               # RAG 检索服务
│   └── external_search.py   # SearXNG 外部搜索
├── models/                  # SQLAlchemy 模型
│   ├── interview.py         # InterviewState, QuestionTemplate, 问诊相位定义
│   ├── agent.py             # AgentSession, AgentTask
│   ├── user.py              # 用户模型（患者/医生/管理员/访客）
│   ├── medical_case.py      # 病例模型（方案 C 分层）
│   └── patient_profile.py   # 健康档案
├── db/                      # 数据库管理
│   ├── session.py           # AsyncSession, async_engine
│   └── sqlite_compat.py     # PostgreSQL→SQLite 类型映射（开发环境）
├── tools/                   # 工具注册表（LLM Function Calling）
│   ├── registry.py          # GLOBAL_REGISTRY
│   └── medical.py           # query_patient_history, search_medical_knowledge 等
└── tasks/                   # Celery 后台任务
```

## 前端结构
```
frontend/src/
├── App.tsx                  # 路由定义（患者/医生/管理员三端）
├── components/              # 核心组件
│   ├── ChatPage.tsx         # 主聊天页（核心状态机 idle→consulting→diagnosed）
│   ├── PendingCardsPanel.tsx # 问诊卡片面板
│   ├── UploadReportCard.tsx # 上传报告卡片
│   ├── DiagnosisCard.tsx    # 诊断报告卡片
│   └── LabReportCard.tsx    # 化验单详情
├── api/                     # API 客户端
│   ├── client.ts            # Axios 实例 + 拦截器
│   ├── agent.ts             # SSE 流式问诊
│   └── patient.ts           # 患者端 API
├── patient/pages/           # 患者端页面
├── doctor/pages/            # 医生端页面
├── admin/pages/             # 管理员页面
├── theme.ts                 # MUI 主题（患者端）
└── themes/doctorTheme.ts    # 医生端蓝色主题
```

# 核心数据模型

## 用户角色体系
- **访客** — 无需登录，3 轮问诊限制后提示注册
- **患者 (Patient)** — 可问诊、查看健康档案、随访计划、病例
- **医生 (Doctor)** — 独立蓝色主题医生端，审核病例/开处方/随访
- **管理员 (Admin)** — 管理后台（LLM 配置、知识库、用户、审计日志）

## 诊断相关模型
| 模型 | 表 | 说明 |
|------|-----|------|
| `AgentSession` | `agent_sessions` | 一次问诊会话，含 context JSON（interview state, lab_reports）；诊断后对话用 parent_session_id 层级关联 |
| `AgentTask` | `agent_tasks` | 会话内的 Agent 任务记录（用于审计和调试） |
| `InterviewState` | (JSON embedded) | 问诊状态：23 个临床维度的 collected_info、phase 守卫（completed 不可降级） |
| `MedicalCase` | `medical_cases` | 诊断完成后自动创建的病例（Plan C），冗余字段供列表快速展示 |
| `PendingConsultation` | `pending_consultations` | 自动创建的待审核会诊（Plan D），预诊断数据在 pre_diagnosis JSON |

## 患者端数据模型
| 模型 | 表 | API 前缀 |
|------|-----|----------|
| `HealthProfile` | `health_profiles` | `GET/PATCH /patient/profile` — 基础信息、过敏史、慢性病、用药（JSON 字段） |
| `CarePlan` | `care_plans` | `GET/POST /patient/care-plans` — 随访计划，状态机 active↔paused→completed/cancelled |
| `CareTask` | `care_tasks` | `.../care-plans/{id}/tasks/{id}/complete\|skip` — 任务，状态 pending→completed/skipped/expired |
| `MedicalCase` (patient-facing) | `medical_cases` | `GET /patient/cases` — 患者可见的病例摘要 |

## 后端 API 路由一览（prefix 对应）
- `/api/v1/agents/*` — 核心诊断：SSE 流式问诊、/chat 诊断后对话、/plan 治疗计划、/monitor 监测
- `/api/v1/patient/*` — 患者端：健康档案 CRUD、随访计划 CRUD、病例列表
- `/api/v1/doctor/*` — 医生端：病例审核、处方、会诊（大部分空壳）
- `/api/v1/admin/*` — 管理后台：LLM 提供商、知识库、用户、审计日志
- `/api/v1/auth/*` — 认证：登录/注册/刷新令牌
- `/api/v1/medical-cases/*` — 病例管理
- `/api/v1/upload/*` + `/api/v1/documents/*` — 文件上传 + OCR 解析

# 开发命令

## 后端
- `cd backend && python run_dev.py` — 启动开发服务器（SQLite 自动建表）
- `cd backend && pip install -e ".[dev]"` — 安装开发依赖
- `cd backend && ruff check .` — 代码检查 (ruff)
- `cd backend && mypy app` — 类型检查
- `cd backend && pytest` — 运行测试
- `cd backend && pytest tests/test_file.py::test_name -v` — 运行单个测试
- `cd backend && alembic upgrade head` — 数据库迁移（PostgreSQL 生产环境）
- `cd backend && alembic revision --autogenerate -m "描述"` — 生成迁移

## 前端
- `cd frontend && npm run dev` — 启动 Vite 开发服务器
- `cd frontend && npm run build` — 生产构建
- `cd frontend && npm run lint` — ESLint 检查
- `cd frontend && npm run preview` — 预览构建产物

# 关键设计模式

## 问诊相位守卫
InterviewState 有 `phase` 字段，一旦变为 `completed`，不允许降级回 `interviewing`。`_update_interview_state()` 写入前会检查 DB 中已有 phase。

## SSE 流式协议
问诊和诊断后对话均通过 SSE（Server-Sent Events）流式返回，事件类型包括：
- `question` — 问诊卡片
- `structured` — 诊断报告（JSON）
- `action` — 动作指令
- `error` — 错误
- `done` — 流结束

## LLM 提供商配置
所有 API Key 加密存储在数据库 `llm_provider_configs` 表，支持多提供商（kimi / GLM / DeepSeek / Qwen 等），按 `model_type`（diagnosis / chat）区分模型用途。

## 状态机（前端）
```typescript
type ChatMode = 'idle' | 'consulting' | 'diagnosed';
// idle → consulting → diagnosed → idle
```
- `idle`: 初始态，显示快捷回复
- `consulting`: 问诊中，显示 PendingCardsPanel
- `diagnosed`: 诊断完成，可聊天追问

# 常见编码模式

## 患者端数据所有权模式
患者端 API 使用 router 级别 `require_role(UserRole.PATIENT)`，所有 service 函数通过 `patient_id` 参数在 WHERE 子句中过滤，保证数据隔离。

## JSON 字段处理
SQLite 兼容模式：JSON 列表字段（goals, allergies, medications）存为 `Text` 类型。
- **写**: `json.dumps(data, ensure_ascii=False)`
- **读**: `parse_json_field(value)`（见 `profile_service.py` — 兼容 PG JSONB 自动反序列化和 SQLite TEXT）

## 后端分页响应格式
所有列表接口返回统一结构 `{items: [...], total, page, size, pages}`。
前端需要提取 `.items`，不要直接当数组用。

## SSE 流式协议事件类型
- `question` — 问诊卡片
- `structured` — 诊断报告（JSON）
- `tool_call` / `tool_result` — 工具调用进度
- `thinking` — 中间状态提示
- `text` — Markdown 文本块
- `error` — 错误
- `complete` / `done` — 流结束

## 诊断后自动创建的 artifacts
`route_stream` 中诊断完成后自动创建（`agents.py:1065-1126`）：
1. **MedicalCase**（方案 C）— 含诊断摘要、严重程度
2. **PendingConsultation**（方案 D）— 预诊断数据 + 分配医生
3. **CarePlan**（方案 E）— 当 `follow_up_required` 为 true 时创建随访计划及任务

# 功能设计文档

## Semantic Cache（语义缓存）— `backend/app/services/semantic_cache.py`

两级缓存，拦截点在 `LLMService.chat()`：
- **Level 1（精确匹配）**：`md5(messages + system_prompt + model + provider)` → Redis GET/SETEX
- **Level 2（语义匹配）**：提取末条 user message 的 embedding（复用 `EmbeddingService`），余弦相似度 > 0.95 命中

**不缓存**：`chat_stream()`、`chat_vision()`、`chat_with_tools()`、`generate_structured()`

Redis 不可用时静默降级。缓存条目含原始 token 消耗以支持统计。

详见 `backend/app/services/semantic_cache.py` 和 `backend/tests/test_semantic_cache.py`。

## Session Token Budget — `backend/app/services/token_budget.py`

Redis ZSET 滑动窗口（复用 `rate_limit.py` 模式），按用户/访客维度跟踪 24h token 消耗。

### 请求流
```
LLMService.chat() → budget check → semantic cache check → LLM → budget deduct
```

### Redis Key
- `tb:user:{user_id}` — 用户 24h 滑动窗口 ZSET
- `tb:guest:{guest_id}` — 访客 24h 滑动窗口 ZSET
- ZSET member 格式: `{uuid}:{token_count}`

### 阈值
| 配置 key | 默认值 | 说明 |
|----------|--------|------|
| `token_budget.soft_limit` | 100000 | 用户软限(24h) |
| `token_budget.hard_limit` | 200000 | 用户硬限(24h) |
| `token_budget.guest_soft_limit` | 10000 | 访客软限 |
| `token_budget.guest_hard_limit` | 20000 | 访客硬限 |

超软限 → LLMResponse.budget_warning；超硬限 → raise TokenBudgetExceeded → API 429。
Redis 不可用时 fail-open。

# 可复用经验（复盘沉淀）

## 相似功能复用已有模式
当新功能与已有功能架构相似时：
- 跳过 Plan agent，直接参考已有实现写方案 + 代码
- Semantic Cache 和 Token Budget 共享：LLMService.chat() 注入点、Redis 操作、fire-and-forget 模式

## 配置项改动后检查副作用
改 `.env` 后检查会影响哪些启动流程：
- `DEFAULT_ADMIN_PASSWORD` → 影响 `_ensure_default_admin()` 启动钩子（只在无 admin 时创建）
- `password_change_required` 标志位影响前端 AdminLayout 的路由行为
- 改 `.env` 后必须重启后端才能生效

## 批量替换后必须验证
执行全局字符串替换（改色值、改字段名等）后：
- `grep` 确认无旧值残留
- 关键 UI 改动需启动前端确认
- sed 替换注意 `rgba()`、`boxShadow` 中的颜色、gradient 中的颜色可能不小心漏掉

## API 错误处理统一展示层
FastAPI Pydantic 422 返回的 `detail` 是数组格式：
```json
{"detail": [{"loc": ["body", "new_password"], "msg": "密码需包含字母"}]}
```
前端需要统一处理数组格式 `detail`，不能直接当字符串展示。
参考 `frontend/src/api/admin.ts` 中的 `changePassword` 处理方式：
```ts
const msg = Array.isArray(body.detail)
  ? body.detail.map(d => d.msg || '').filter(Boolean).join('；')
  : body.detail;
```

## 启动流程
- 后端：`cd backend && python run_dev.py`（默认 SQLite，自动建表，自动创建管理员）
- 前端：`cd frontend && npm run dev`（Vite，`/api` 代理到后端 8000 端口）
- 端口冲突：`netstat -ano | findstr ":8000 "` → `taskkill //F //PID <PID>`
- 管理员默认账号：`admin@medicareai.dev` / `admin123456`（首次登录需要改密码）

