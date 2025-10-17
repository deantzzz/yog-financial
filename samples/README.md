# 样例与模板说明

仓库随附一套最小化的 CSV 模板，覆盖流水线当前正式支持的四类结构。通过这些模板即可快速验证上传 → 解析 → 计算的主流程，无需额外脚本。

## 官方模板

`samples/templates/` 目录内提供以下模板：

| 模板 | 适用上传节点 | 关键字段 | 文件路径 |
| --- | --- | --- | --- |
| `timesheet_personal_template.csv` | 个人工时明细（timesheet_personal） | 姓名、月份、日期、各类工时 | `samples/templates/timesheet_personal_template.csv` |
| `timesheet_aggregate_template.csv` | 月度工时汇总（timesheet_aggregate） | 姓名、标准工时、加班工时、确认工时 | `samples/templates/timesheet_aggregate_template.csv` |
| `policy_sheet_template.csv` | 薪酬口径（policy_sheet） | 薪资模式、月薪/时薪、加班倍率、津贴/扣款、社保配置 | `samples/templates/policy_sheet_template.csv` |
| `roster_sheet_template.csv` | 花名册/社保（roster_sheet） | 入离职日期、社保个人/公司比例、基数上下限 | `samples/templates/roster_sheet_template.csv` |

> 直接下载或复制上述 CSV 内容，即可在前端的「上传资料」步骤中进行调试。所有模板均采用 UTF-8 编码，兼容 Excel、WPS、Numbers 等常见表格工具。

## 自定义建议

- 若业务需要新增字段，可在复制模板后按需扩展列名；解析器会忽略未知列，只要保留关键字段即可。
- 模板内的演示数据仅用于提示字段含义，可在上传前替换为真实数值或留空。
- 若需批量生成数据，可在外部脚本或表格软件中引用这些表头；系统无需额外的生成脚本即可识别。
