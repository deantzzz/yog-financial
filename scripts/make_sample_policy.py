#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

from openpyxl import Workbook


def main() -> None:
    parser = argparse.ArgumentParser(description="生成薪资口径示例工作簿")
    parser.add_argument("--month", required=True, help="工作区月份，格式 YYYY-MM")
    parser.add_argument("--output", required=True, help="输出文件路径 (.xlsx)")
    parser.add_argument("--employee", default="张三", help="员工姓名")
    parser.add_argument("--base", type=float, default=10000, help="月薪")
    args = parser.parse_args()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "薪资口径"
    sheet.append([
        "姓名",
        "月薪",
        "平日加班费率",
        "周末加班费率",
        "社保个人比例",
        "餐补津贴",
        "缺勤扣款",
    ])
    sheet.append([args.employee, args.base, 50, 80, 0.1, 200, 0])

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output)
    print(f"口径示例已生成: {output}")


if __name__ == "__main__":
    main()
