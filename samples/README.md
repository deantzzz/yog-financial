# 样例数据生成指引

> 仓库禁止提交二进制 Excel 文件，因此示例通过脚本即时生成。

可参考以下命令即时构造工时与薪资示例工作簿：

```bash
python scripts/make_sample_timesheet.py --month 2025-01 --output /tmp/timesheet.xlsx
python scripts/make_sample_policy.py --month 2025-01 --output /tmp/policy.xlsx
```

生成的文件可直接通过前端上传页面或 `curl` 命令提交至后端进行调试。
