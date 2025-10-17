# 样例与模板说明

仓库随附一套最小化的 CSV 模板与示例数据，覆盖流水线当前正式支持的结构。通过这些文件即可快速验证上传 → 解析 → 计算的主流程，无需额外脚本。

## 官方模板

`samples/templates/` 目录内提供以下模板（直接覆盖最常见的 4 种上传场景）：

| 模板 | 上传 `schema` | 生成数据 | 关键字段 | 文件路径 |
| --- | --- | --- | --- | --- |
| `timesheet_personal_template.csv` | `timesheet_personal` | `facts` | 姓名、月份、日期、各类工时 | `samples/templates/timesheet_personal_template.csv` |
| `timesheet_aggregate_template.csv` | `timesheet_aggregate` | `facts` | 姓名、标准工时、加班工时、确认工时 | `samples/templates/timesheet_aggregate_template.csv` |
| `policy_sheet_template.csv` | `policy_sheet` | `policy` | 薪资模式、月薪/时薪、加班倍率、津贴/扣款、社保配置 | `samples/templates/policy_sheet_template.csv` |
| `roster_sheet_template.csv` | `roster_sheet` | `policy` | 入离职日期、社保个人/公司比例、基数上下限 | `samples/templates/roster_sheet_template.csv` |

> 直接下载或复制上述 CSV 内容，即可在前端的「上传资料」步骤中进行调试。所有模板均采用 UTF-8 编码，兼容 Excel、WPS、Numbers 等常见表格工具。

完成 timesheet_personal →（可选）timesheet_aggregate → roster_sheet → policy_sheet 的四步上传后，系统会自动生成标准化的事实与口径记录，不需要再额外上传 `facts` 或 `policy` CSV。所有模板中的“月份”字段仅作备注，计算时会以当前工作区的月份为准；若结果仍为 0，可重新检查薪酬口径中的“基本工资/时薪”列以及 roster_sheet 是否填写社保比例。

## 示例数据

`samples/facts_sample.csv` 与 `samples/policy_sample.csv` 展示了流水线直接接收的两种标准化结构，可作为 API 调试或自动化测试的起点：

| 文件 | 类型 | 关键字段 | 适用场景 |
| --- | --- | --- | --- |
| `samples/facts_sample.csv` | `facts` 事实数据 | `employee_name`、`period_month`、`metric_code`、`metric_value`、`unit`、`confidence` | 直接模拟工时/金额等事实指标的批量上传 |
| `samples/policy_sample.csv` | `policy` 口径数据 | `employee_name_norm`、`period_month`、`mode`、`base_amount`、`ot_*`、`social_security_json` | 演示口径快照的最小字段组合，适合规则引擎调试 |

> 如果需要扩展字段，可在复制这些示例后按业务需求增加列名；解析器会保留未知列供后续审计。JSON 字段示例采用转义双引号，便于在表格软件中直接编辑。

### 与上传模板的关系

- 上传模板会在后台解析后生成与 `facts`/`policy` 相同的结构（参见 `backend/workers/pipeline.py` 中对 `_ingest_fact_rows`、`_ingest_policy_rows` 的调用）。
- 若已有外部系统输出标准化字段，可直接上传 `facts`/`policy`，系统会沿用同一套校验与规则引擎流程，无需再从 Excel 解析。

## 自定义建议

- 若业务需要新增字段，可在复制模板后按需扩展列名；解析器会忽略未知列，只要保留关键字段即可。
- 模板内的演示数据仅用于提示字段含义，可在上传前替换为真实数值或留空。
- 若需批量生成数据，可在外部脚本或表格软件中引用这些表头；系统无需额外的生成脚本即可识别。
