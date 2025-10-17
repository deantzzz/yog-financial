#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
from pathlib import Path


HEADER = [
    "姓名",
    "个人比例",
    "公司比例",
    "最低基数",
    "最高基数",
    "入职日期",
    "离职日期",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 roster_sheet 花名册 CSV 模板")
    parser.add_argument("--month", required=True, help="工作区月份，格式 YYYY-MM")
    parser.add_argument("--output", required=True, help="输出文件路径 (.csv)")
    parser.add_argument("--employee", default="张三", help="员工姓名")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(HEADER + ["月份"])
        writer.writerow([
            args.employee,
            0.08,
            0.12,
            5000,
            15000,
            "2023-01-01",
            "",
            args.month,
        ])

    print(f"roster_sheet CSV 模板已生成: {output}")


if __name__ == "__main__":
    main()
