# Yog Financial 开发者指南

Yog Financial 是一套围绕“工作区/月度隔离”理念构建的工资核算自动化平台。项目提供 FastAPI 后端、Next.js 前端控制台、可扩展的文件解析流水线以及规则引擎，帮助团队快速完成工资计算、导出与审计。本文档面向开发者，汇总必要的架构背景、环境依赖、启动步骤与二次开发指引，力求在最短时间内让你完成一次端到端的开发迭代。

> 本仓库处于 MVP 阶段。以下说明基于当前代码结构撰写，若你在实测过程中发现偏差，请在提交前同步更新本文档。

---

## 1. 快速上手

### 1.1 准备环境

| 组件 | 版本/说明 |
| --- | --- |
| Python | 3.11 及以上 |
| Node.js | 18 LTS（Next.js 官方推荐版本） |
| 包管理 | `pip`（或 `uv`/`pip-tools`）、`npm`/`pnpm`/`yarn` 均可，示例使用 `pip` 与 `npm` |
| 可选 | Docker / Docker Compose（本地一键启动） |

### 1.2 克隆与安装依赖

```bash
# 克隆仓库
 git clone <REPO_URL>
 cd yog-financial

# 创建 Python 虚拟环境并安装依赖
 python -m venv .venv
 source .venv/bin/activate
 pip install -r requirements.txt

# 安装前端依赖
 cd frontend
 npm install
 cd ..
```

### 1.3 配置环境变量

1. 复制模板：`cp .env.example .env`
2. 至少确保以下字段填写正确：
   - `WORKSPACES_ROOT`：工作区根目录，默认指向仓库内 `workspaces/`。
   - `LOGS_ROOT`：日志目录，默认指向仓库内 `logs/`。
   - 若启用 OCR/LLM 等外部服务，请补充 `IFLYTEK_*`、`AZURE_OPENAI_*` 等变量。

> 如果只运行本地演示，可以保留 `.env.example` 内的默认值；需要调用第三方服务时再补齐凭据。

### 1.4 启动开发环境

#### 后端（FastAPI）

```bash
source .venv/bin/activate
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

- API 文档：访问 <http://localhost:8000/docs>
- 默认会在 `workspaces/` 下生成运行期目录，必要时提前创建并授予写权限。

#### 前端（Next.js App Router）

```bash
cd frontend
npm run dev
```

- 访问 <http://localhost:3000>
- 如需自定义后端地址，修改 `frontend/.env.local` 中的 `NEXT_PUBLIC_API_BASE_URL`，默认为 `http://localhost:8000`。

### 1.5 一键容器化（可选）

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up --build
```

- `app` 服务暴露 FastAPI，端口 `8000`。
- `frontend` 服务暴露 Next.js，端口 `3000`。
- Compose 会挂载仓库内 `workspaces/`、`logs/` 目录以持久化解析结果与审计信息。

---

## 2. 项目结构速览

```
repo/
├── backend/
│   ├── app.py                 # FastAPI 入口
│   ├── routes/                # 请求/响应映射与参数校验
│   ├── application/           # 用例服务（工作区、计算等）
│   ├── infrastructure/        # 仓储实现、持久化适配器（默认内存）
│   ├── domain/                # 领域实体、值对象
│   ├── workers/               # 顺序任务编排器（上传、解析、计算）
│   ├── core/                  # 规则引擎、校验、CSV/Parquet 工具
│   ├── extractors/            # Excel/CSV 模板解析器与兜底逻辑
│   └── exporters/             # 发薪/税务导出模块
├── frontend/
│   ├── app/                   # Next.js 页面与路由（App Router）
│   ├── components/            # UI 组件
│   ├── features/              # 业务服务（数据整形、状态管理）
│   ├── lib/                   # HTTP 客户端封装（`apiFetch`）
│   └── Dockerfile             # 前端容器构建脚本
├── infra/
│   └── docker-compose.yml     # 本地容器编排
├── samples/                   # 模板与标准化数据示例
├── tests/                     # Pytest 测试
├── workspaces/                # 运行时工作区输出（需可写）
├── logs/                      # 默认日志目录
└── requirements.txt           # Python 依赖清单
```

---

## 3. 核心概念与数据流

1. **工作区（Workspace）**：按月份隔离数据的逻辑空间，目录结构位于 `workspaces/<YYYY-MM>/`。
2. **上传流水线**：`backend/workers/pipeline.py` 将上传的文件清洗、识别 schema、调用相应 `extractors/` 写入标准化事实（facts）与口径（policy）。
3. **规则引擎 V1**：`backend/core/rules_v1.py` 支持固定薪、计时薪、加班、津贴/扣款、社保个税等计算。
4. **应用服务**：`backend/application/workspaces.py` 协调工作区状态更新、流水线执行与规则引擎调用。
5. **前端工作流**：`frontend/features/workspaces` 提供业务 API，`frontend/app/(dashboard)` 等页面负责交互展示。

典型流程：

1. 创建工作区 →
2. 上传工时表/口径表/名册 →
3. 流水线解析并写入 `facts`/`policy` →
4. 触发计算 →
5. 导出发薪 CSV 或通过 API 获取结果。

---

## 4. 关键代码定位

| 功能 | 入口 | 说明 |
| --- | --- | --- |
| FastAPI 启动 | `backend/app.py` | 创建应用实例、注册路由与中间件 |
| 工作区 API | `backend/routes/workspaces.py` | 提供创建、上传、计算、导出等 REST 接口 |
| 工作区服务 | `backend/application/workspaces.py` | 聚合仓储、流水线、规则引擎 |
| 流水线调度 | `backend/workers/pipeline.py` | 将文件解析为标准化记录并持久化 |
| 规则引擎 | `backend/core/rules_v1.py` | 核心计薪逻辑，支持多种薪资模式 |
| 模板解析器 | `backend/extractors/*.py` | 针对 Excel/CSV 模板的字段映射与校验 |
| 前端 API 封装 | `frontend/lib/api.ts` | 统一 fetch、错误处理、Base URL 管理 |
| 前端工作区服务 | `frontend/features/workspaces/services.ts` | 发起 API 调用并整形响应 |
| 前端页面 | `frontend/app/**/page.tsx` | 负责 UI 展示与交互 |

---

## 5. 常见开发场景

### 5.1 新增后端用例

1. 在 `backend/application/` 内编写服务函数或类，聚合所需仓储/规则模块。
2. 在 `backend/routes/` 中新增 API，将请求 DTO 转换为领域模型。
3. 如需持久化，扩展 `backend/infrastructure/`，例如实现数据库版 `WorkspaceRepository`。
4. 编写 `tests/` 内的 API 或服务层测试验证行为。

### 5.2 扩展文件解析或规则

- 新增模板：在 `backend/extractors/` 添加解析器并在 `pipeline.py` 注册探测逻辑。
- 新增指标：调整 `backend/core/rules_v1.py` 中的计算函数，并更新相关测试/样例。
- 引入异步任务：参考 `backend/workers/` 编写新的编排器或将现有流程接入消息队列。

### 5.3 增强前端页面

1. 在 `frontend/features/` 定义业务逻辑和类型，确保组件只消费清洗后的数据。
2. 在 `frontend/app/` 创建页面或路由段，复用 `components/` 中的基础组件。
3. 若涉及全局状态，可引入轻量状态管理或使用 React 上下文。

### 5.4 与外部系统对接

- 直接上传标准化 `facts`/`policy` CSV/JSON：字段格式见 `samples/facts_sample.csv`、`samples/policy_sample.csv`。
- 使用 REST API：参考 `/api/workspaces/*` 路由，确保请求体与响应 DTO 对齐。
- 若需批量导出：在 `backend/exporters/` 新增模块并在路由层挂载。

---

## 6. 测试与质量保障

```bash
# 语法检查
python -m compileall backend

# 运行 Pytest（包含端到端 API 用例）
pytest -q
```

推荐引入的附加工具：

- `ruff` / `flake8`：静态代码风格检查。
- `mypy`：类型检查（后端主要使用 dataclass 与 TypedDict）。
- `pytest --maxfail=1`：快速定位首个失败用例。

前端可按需引入 `eslint`、`prettier`、`jest`/`vitest`，目前仓库未预置单元测试脚本。

---

## 7. 数据与审计目录说明

| 目录 | 内容 |
| --- | --- |
| `workspaces/<YYYY-MM>/raw/` | 原始上传文件（已清洗文件名） |
| `workspaces/<YYYY-MM>/csv/`、`json/` | 标准化副本，便于调试与二次处理 |
| `workspaces/<YYYY-MM>/policy/` | 口径快照 JSON |
| 内存状态 | 由 `WorkspaceService` 管理，包含事实/口径记录及来源哈希 |
| 导出结果 | 通过 `/api/workspaces/{ws}/results` 获取，或使用 `exporters/` 生成文件 |
| `logs/` | 建议写入结构化审计日志，此目录已在仓库中创建 |

---

## 8. 示例数据与模板

- 查看 `samples/README.md` 获取所有模板字段说明。
- 常用模板位于 `samples/templates/`：
  - `timesheet_personal_template.csv`
  - `timesheet_aggregate_template.csv`
  - `policy_sheet_template.csv`
  - `roster_sheet_template.csv`
- 标准化示例：
  - `samples/facts_sample.csv`
  - `samples/policy_sample.csv`

上传这些文件即可完成一次完整的解析 → 计算 → 导出流程。

---

## 9. 常见问题

- **为什么没有看到 LLM 调用实现？** 当前 `backend/extractors/generic_llm.py` 仅提供函数占位，可按需接入 Azure OpenAI 或其他模型。
- **工作区目录需要手动创建吗？** 默认在首次调用创建工作区时自动生成，使用 Docker 时请确保宿主目录具有读写权限。
- **如何扩展导出格式？** 在 `backend/exporters/` 内新增模块并在路由层注册即可。
- **全部工资为 0 如何排查？** 确认口径中存在基本工资/时薪、上传花名册补充社保比例，并检查 `policy_sheet` 是否填写完整。

---

## 10. 已知限制与排查建议

- 当前仓储实现为内存版，如需持久化可扩展至数据库或 DuckDB。迁移时需同步更新 `application/workspaces.py` 与相关测试。
- 流水线在解析未知模板时采用启发式策略，可能生成占位记录提醒人工处理；上线前请确保关键模板已提供专用解析器。
- 前端未集成登录/权限控制，部署生产环境时需额外加固。

如在阅读代码时发现逻辑缺陷或潜在漏洞，请通过 Issue 或 PR 反馈；本文档未在撰写时发现明显逻辑问题。

