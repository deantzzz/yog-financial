# 样例与模板说明

仓库不包含任何二进制 Excel 文件，所有演示数据均通过 CSV 模板或脚本即时生成。以下内容帮助你快速找到 roster_sheet 等必备模板，并了解每个字段的含义。

## 现成 CSV 模板

`samples/templates/` 目录提供了系统支持的四类关键模板：

| 模板 | 适用上传节点 | 关键字段 | 文件路径 |
| --- | --- | --- | --- |
| `timesheet_aggregate_template.csv` | 月度工时汇总（timesheet_aggregate） | 姓名、标准工时、加班工时、确认工时 | `samples/templates/timesheet_aggregate_template.csv` |
| `timesheet_personal_template.csv` | 个人打卡明细（timesheet_personal） | 姓名、月份、日期、各类工时 | `samples/templates/timesheet_personal_template.csv` |
| `policy_sheet_template.csv` | 薪酬口径（policy_sheet） | 月薪、加班费率、社保比例、津贴/扣款 | `samples/templates/policy_sheet_template.csv` |
| `roster_sheet_template.csv` | 花名册/社保（roster_sheet） | 社保个人/公司比例、基数上下限、入离职信息 | `samples/templates/roster_sheet_template.csv` |

> 使用方式：直接下载或复制 CSV 内容，即可上传到前端「上传资料」步骤进行验证。所有模板均采用 UTF-8 编码，兼容 Excel、WPS、Numbers 等常见表格工具。

## 脚本生成带示例数据的 CSV

如果希望快速生成带有示例记录的模板，可使用 `scripts/` 下的辅助脚本。脚本默认写出 UTF-8 编码的 CSV 文件，你可以通过 `--output` 参数指定输出位置。

```bash
python scripts/make_sample_timesheet.py --month 2025-01 --output /tmp/timesheet_aggregate.csv
python scripts/make_sample_policy.py --month 2025-01 --output /tmp/policy_sheet.csv
python scripts/make_sample_roster.py --month 2025-01 --output /tmp/roster_sheet.csv
```

生成的 CSV 可直接用于工作区上传调试，也可根据需要复制到自定义目录进行编辑。脚本会额外写入月份信息，帮助你在多工作区场景下区分文件来源。

## FAQ

- **可以继续上传 Excel 吗？** 可以。后端解析器同时兼容 CSV 与常见 Excel 模板，因此你仍可在外部工具中导出 `.xlsx` 再上传。
- **如何新增字段？** 复制模板后即可按需增加列，解析器会自动忽略未知字段，只要保留表头关键字即可。
- **脚本是否依赖额外库？** 不需要。所有示例脚本仅使用 Python 标准库即可运行。
