#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
from pathlib import Path


HEADER = [
    "姓名",
    "模式",
    "基本工资",
    "平日加班费率",
    "周末加班费率",
    "社保个人比例",
    "社保公司比例",
    "社保基数下限",
    "社保基数上限",
    "餐补津贴",
    "缺勤扣款",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="生成薪酬口径 CSV 模板")
    parser.add_argument("--month", required=True, help="工作区月份，格式 YYYY-MM")
    parser.add_argument("--output", required=True, help="输出文件路径 (.csv)")
    parser.add_argument("--employee", default="张三", help="员工姓名")
    parser.add_argument("--base", type=float, default=10000, help="月薪")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(HEADER + ["月份"])
        writer.writerow(
            [
                args.employee,
                "SALARIED",
                f"{args.base:.2f}",
                50,
                80,
                0.1,
                0.12,
                5000,
                15000,
                200,
                0,
                args.month,
            ]
        )

    print(f"薪酬口径 CSV 模板已生成: {output}")


if __name__ == "__main__":
    main()
