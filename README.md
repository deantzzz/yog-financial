# 财务自动化结算系统（Yog Financial）

Yog Financial 是一个围绕“工作区/月度隔离”理念构建的工资核算自动化平台。系统聚合工时、工资口径、社保个税等多源数据，确保计算过程可审计、可重跑。本仓库当前处于 MVP 阶段，提供可运行的 FastAPI 后端、Next.js 控制台、最小化的解析流水线与规则引擎，并配套完整的测试与容器化配置，便于快速演示与二次开发。

## 功能概览

- **工作区管理**：按月份创建独立工作区，隔离原始文件与计算结果。
- **文件解析流水线**：支持对 CSV/JSON 以及常见 Excel 模板的自动识别与入库，完成上传 → 解析 → 标准化存储的端到端流程。
- **事实层与口径快照**：将解析结果写入内存状态与工作区目录，保留来源哈希与审计信息，为后续扩展到 DuckDB/Parquet 做好准备。
- **规则引擎 V1**：支持固定薪、计时薪两类模式，加班、津贴/扣款、社保个税等基础规则。
- **导出与审计**：生成银行发薪 CSV、税局导入 CSV，并保留每条结果对应的快照哈希与来源文件。

## 目录结构

```
repo/
  backend/
    app.py                  # FastAPI 入口
    routes/                 # 上传、工作区、计算等 API 路由
    core/                   # 规则引擎、校验、Parquet/CSV 工具
    extractors/             # 模板解析器（工时/口径/名册）与 LLM 兜底入口
    workers/                # 顺序任务编排器
    config/                 # 默认口径、税表配置
    exporters/              # 发薪/税局导出
  frontend/
    app/                    # Next.js App Router 页面
    components/             # 前端 UI 组件
    lib/                    # API 请求辅助函数
    package.json            # 前端依赖与脚本
    Dockerfile              # 前端容器构建脚本
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

> 提示：可使用 `samples/` 目录中的指引脚本即时生成示例 CSV/Excel，测试上传、解析与计算流程。

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
| `WORKSPACES_ROOT` | 工作区根目录，默认 `workspaces` |
| `LOG_LEVEL` | FastAPI 应用日志等级，可选 `INFO`/`DEBUG` |
| `API_CORS_ORIGINS` | 允许跨域访问的前端来源，逗号分隔，默认包含 `http://localhost:3000` |

> 当前仓库中的 `backend/extractors/generic_llm.py` 为预留入口，实际接入 Azure OpenAI 时请确保上述变量已配置，并在运行环境中可见（`.env` 或部署平台配置）。

## 工作流简介

1. **创建工作区**：调用 `POST /api/workspaces`，指定月份（`YYYY-MM`），系统将在 `WORKSPACES_ROOT` 下创建目录结构。
2. **上传文件**：调用 `POST /api/workspaces/{ws}/upload` 上传 CSV/JSON/Excel 文件。流水线会自动落盘原始文件并尝试识别模板类型。
3. **事实层合并**：识别为事实数据的记录会解析为统一字段，存放在内存状态与 `workspaces/{ws}/csv/`，并附带来源哈希。
4. **口径快照**：识别为口径数据的记录会生成 `PolicySnapshot` 并写入状态，同时保留原始行 JSON，方便追溯与调试。
5. **触发计算**：调用 `POST /api/workspaces/{ws}/calc`，规则引擎基于当前事实/口径数据计算工资结果，并持久化于工作区状态中。
6. **导出结果**：查询 `/api/workspaces/{ws}/results` 获取已计算的记录，或后续扩展导出模块生成银行/税务文件。

## 示例数据与模板格式

`samples/` 目录内提供了生成脚本，可用于快速体验：

- `facts_sample.csv`：包含 `employee_name`、`period_month`、`metric_code`、`metric_value` 等字段，上传后会生成事实记录；
- `policy_sample.csv`：包含 `employee_name_norm`、`mode`、`base_amount`、`ot_*` 等字段，上传后会生成口径快照；
- `scripts/make_sample_timesheet.py`：即时生成“月度工时汇总确认表”结构的 Excel；
- `scripts/make_sample_policy.py`：即时生成薪资口径 Excel，避免将二进制文件提交到仓库。

流水线当前支持以下格式：

- **事实数据 CSV/JSON**：必须包含 `employee_name`、`period_month`、`metric_code`、`metric_value`，可选列会自动透传至审计字段；
- **口径数据 CSV/JSON**：必须包含 `employee_name_norm`、`period_month`、`mode`，其余金额/倍率字段将自动转换为 `Decimal`；
- **Excel 工时模板**：自动识别“个人工时表”“月度工时汇总表”，并转写为事实记录；
- **Excel 工资口径模板**：识别“基本工资/时薪、加班倍率/费率、津贴/扣款、社保比例”等列并生成口径快照；
- **Excel 名册/社保模板**：提取社保个人/公司比例与基数上下限，补充到口径快照；
- **其他类型文件**：会被安全存储在 `raw/` 目录。若模板识别失败，将启用启发式 Excel 解析器提取可能的姓名、工时和金额字段；若仍无法解析，则生成占位记录提示人工介入。

如需扩展更多模板或解析器，可在 `backend/workers/pipeline.py` 中添加新的探测与解析逻辑，或编写专用的 extractor 模块。

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

   - Compose 将同时启动后端（`app` 服务，端口 `8000`）与前端（`frontend` 服务，端口 `3000`）。
   - 默认挂载仓库根目录下的 `workspaces/` 与 `logs/`，仓库内已提供空目录占位，便于持久化解析结果与审计日志。
   - 前端容器通过 `NEXT_PUBLIC_API_BASE_URL=http://app:8000` 与后端通信，若需自定义请调整 `infra/docker-compose.yml`。
   - 前端镜像使用 Next.js `standalone` 模式构建，入口命令为 `node server.js`，能够正确处理生产部署的运行参数。

## 数据与审计

- **原始文件**：保存在 `workspaces/{YYYY-MM}/raw/`，文件名会进行清洗避免目录穿越；
- **标准化副本**：CSV/JSON 会同步复制至 `csv/`、`json/` 子目录，方便进行二次处理；
- **解析记录**：在内存状态中保留字段齐全的事实与口径条目，附带 `source_file`、`source_sha256` 等追溯信息；
- **计算结果**：`POST /calc` 后会缓存最新结果，便于前端查询或导出扩展；
- **审计日志**：建议在真实场景中对 `state` 操作增加结构化日志，本仓库提供的 `logs/` 目录作为占位示例。

## 测试与自检

- 单元测试：建议针对解析器、规则引擎、校验器分别编写 Pytest 测试用例。
- 静态检查：可选用 `ruff`、`mypy` 等工具提高代码质量。
- 本仓库当前提供的命令示例：

  ```bash
  python -m compileall backend  # 快速检查语法错误
  pytest -q                     # 运行端到端 API 测试
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
