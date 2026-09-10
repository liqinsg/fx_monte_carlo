import json
from pathlib import Path

def generate_date_index(api_dir="api"):
    """扫描 api/ 目录下的 YYYY/MM/DD 结构，生成 api/dates.json"""
    api_path = Path(api_dir)
    dates = []

    for p in sorted(api_path.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]")):
        if p.is_dir():
            parts = p.parts[-3:]
            dates.append(f"{parts[0]}-{parts[1]}-{parts[2]}")

    dates.sort(reverse=True)

    index_file = api_path / "dates.json"
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump({"available_dates": dates, "total": len(dates)}, f, indent=2)

    print(f"✅ 已生成日期索引: {index_file} ({len(dates)} 个历史日期)")

if __name__ == "__main__":
    # 在 build_api 原有逻辑执行完后调用：
    generate_date_index()