# 财务自动化结算系统（Yog Financial）

Yog Financial 是一个围绕“工作区/月度隔离”理念构建的工资核算自动化平台。系统聚合工时、工资口径、社保个税等多源数据，确保计算过程可审计、可重跑。本仓库当前处于 MVP 阶段，重点提供后端服务骨架、规则引擎 V1、基础导出能力以及容器化部署配置。

## 功能概览

- **工作区管理**：按月份创建独立工作区，隔离原始文件与计算结果。
- **文件解析流水线**：基于模板解析器优先、LLM 兜底的原则，串联上传 → 解析 → CSV 标准化 → 事实层合并。
- **事实层与口径快照**：使用 DuckDB/Parquet 存储原子事实数据和当月口径，保障追溯能力。
- **规则引擎 V1**：支持固定薪、计时薪两类模式，加班、津贴/扣款、社保个税等基础规则。
- **导出与审计**：生成银行发薪 CSV、税局导入 CSV，并保留每条结果对应的快照哈希与来源文件。

## 目录结构

```
repo/
  backend/
    app.py                  # FastAPI 入口
    routes/                 # 上传、工作区、计算等 API 路由
    core/                   # 规则引擎、校验、Parquet/CSV 工具
    extractors/             # 模板解析与 LLM 兜底（占位）
    workers/                # 顺序任务编排器
    config/                 # 默认口径、税表配置
    exporters/              # 发薪/税局导出
  frontend/
    app/                    # Next.js App Router 页面
    components/             # 前端 UI 组件
    lib/                    # API 请求辅助函数
    package.json            # 前端依赖与脚本
  infra/
    docker-compose.yml      # 可选的容器化运行环境
  workspaces/               # 运行期生成的工作区目录（需提前创建或在配置中指定）
  requirements.txt          # Python 依赖
  Dockerfile                # 镜像构建脚本
  .env.example              # 环境变量示例（需复制为 .env）
```

## 环境依赖

- Python 3.11+
- DuckDB 或 PyArrow（随 `requirements.txt` 安装）
- 可选：Docker / Docker Compose（用于容器化部署）

## 快速开始

1. 克隆仓库并创建虚拟环境：

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. 复制环境变量示例并根据实际情况填充：

   ```bash
   cp .env.example .env
   ```

3. 启动本地开发服务：

   ```bash
   uvicorn backend.app:app --reload
   ```

4. 访问 `http://127.0.0.1:8000/docs` 查看自动生成的 OpenAPI 文档。

## 前端控制台

前端使用 Next.js + Tailwind CSS 实现最小可用界面，覆盖“上传/事实/口径/计算”四个核心页面，主要用于演示如何与后端交互。

1. 安装依赖：

   ```bash
   cd frontend
   npm install
   ```

2. 创建 `.env.local`（可选），用于覆盖默认的后端接口地址：

   ```env
   NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
   ```

3. 启动开发服务器：

   ```bash
   npm run dev
   ```

4. 访问 `http://127.0.0.1:3000`，即可查看控制台：

   - **上传与任务**：选择工作区并上传文件，查看解析状态；
   - **事实数据**：按姓名、指标过滤事实层数据，低置信度将高亮；
   - **口径快照**：查看当前口径参数，支持展开 JSON 详情；
   - **计算与导出**：触发计算并浏览结果，后续可在后端导出银行/税务文件。

构建与部署：

```bash
npm run build
npm start
```

Next.js 默认以 `NEXT_PUBLIC_API_BASE_URL` 指向 FastAPI 服务（默认 `http://127.0.0.1:8000`）。部署时请根据实际域名与 HTTPS 配置调整。

## 环境变量说明

| 变量名 | 说明 |
| --- | --- |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI Endpoint，形如 `https://xxx.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI 的 API Key，用于 LLM 兜底解析 |
| `AZURE_OPENAI_API_VERSION` | API 版本，默认 `2024-06-01` |
| `AZURE_OPENAI_DEPLOYMENT` | 部署名称，例如 `gp4o-json` |
| `TIMEZONE` | 系统默认时区，默认为 `Asia/Shanghai` |
| `WORKSPACE_ROOT` | 工作区根目录，默认 `workspaces` |
| `LOG_LEVEL` | FastAPI 应用日志等级，可选 `INFO`/`DEBUG` |

> 当前仓库中的 `backend/extractors/generic_llm.py` 为预留入口，实际接入 Azure OpenAI 时请确保上述变量已配置，并在运行环境中可见（`.env` 或部署平台配置）。

## 工作流简介

1. **创建工作区**：调用 `POST /api/workspaces`，指定月份（`YYYY-MM`），系统将在 `WORKSPACE_ROOT` 下创建目录结构。
2. **上传文件**：调用 `POST /api/workspaces/{ws}/upload` 上传 Excel/CSV/PDF 等原始文件。流水线会尝试自动识别模板类型并解析。
3. **事实层合并**：解析后的 CSV 会被写入 `fact/fact_records.parquet`，同时生成审计日志。
4. **口径快照**：工资口径、社保口径等信息会写入 `policy/payroll_policy_{month}.parquet`，支持跨月生效区间。
5. **触发计算**：调用 `POST /api/workspaces/{ws}/calc`，规则引擎根据事实层与口径快照生成 `results/payroll_{month}.parquet` 与导出文件。
6. **导出结果**：通过 `/api/workspaces/{ws}/export/bank`、`/api/workspaces/{ws}/export/tax` 生成标准导入文件，或查询 `/api/workspaces/{ws}/results` 查看结果。

## Docker 运行

1. 构建镜像：

   ```bash
   docker build -t yog-financial:latest .
   ```

2. 使用 Docker Compose（推荐开发/验收环境）：

   ```bash
   cp .env.example .env
   docker compose -f infra/docker-compose.yml up --build
   ```

   - Compose 默认挂载仓库根目录下的 `workspaces/` 与 `logs/`，仓库内已提供空目录占位，便于持久化解析结果与审计日志。
   - FastAPI 服务默认监听 `8000` 端口。

## 数据与审计

- **事实层**：`workspaces/{YYYY-MM}/fact/fact_records.parquet`
- **口径快照**：`workspaces/{YYYY-MM}/policy/payroll_policy_{YYYY-MM}.parquet`
- **计算结果**：`workspaces/{YYYY-MM}/results/`
- **审计日志**：`logs/ingestion_audit.log`

所有记录都包含 `source_file`、`source_sheet`、`source_row` 等字段，便于追溯原始数据来源。

## 测试与自检

- 单元测试：建议针对解析器、规则引擎、校验器分别编写 Pytest 测试用例。
- 静态检查：可选用 `ruff`、`mypy` 等工具提高代码质量。
- 本仓库当前提供的命令示例：

  ```bash
  python -m compileall backend  # 快速检查语法错误
  ```

## 常见问题（FAQ）

- **为什么没有直接看到 LLM 调用代码？**
  - 目前 `generic_llm.py` 仅保留函数入口，后续可根据实际业务接入 Azure OpenAI。README 中列出的环境变量用于该模块的配置。
- **工作区目录是否需要提前创建？**
  - 默认情况下，首次创建工作区时会自动生成。若以容器方式运行，请确保挂载目录具有写权限。
- **如何扩展其他导出格式？**
  - 在 `backend/exporters/` 目录中新增模块，并在路由层注册即可。

## 版本规划

- **MVP（当前版本）**：后端骨架、规则引擎 V1、导出 CSV、Docker 化部署。
- **后续迭代方向**：完善解析器、补充前端界面、引入消息通知与权限控制、多币种支持等。

如需进一步的实施方案与设计细节，请参考仓库内的设计文档或联系项目维护者。
