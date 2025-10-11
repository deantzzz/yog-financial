#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

from openpyxl import Workbook


def main() -> None:
    parser = argparse.ArgumentParser(description="生成工时汇总示例工作簿")
    parser.add_argument("--month", required=True, help="工作区月份，格式 YYYY-MM")
    parser.add_argument("--output", required=True, help="输出文件路径 (.xlsx)")
    parser.add_argument("--employee", default="张三", help="员工姓名")
    args = parser.parse_args()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "工时汇总"
    sheet.append([
        "序号",
        "部门",
        "姓名",
        "工作日标准工时",
        "工作日加班工时",
        "周末节假日打卡工时",
        "当月工时（已公式加和）",
        "确认工时",
    ])
    sheet.append([1, "示例部门", args.employee, 160, 12, 8, 180, 180])

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output)
    print(f"工时示例已生成: {output}")


if __name__ == "__main__":
    main()
