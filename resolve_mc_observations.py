import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List

OBSERVATIONS_LOG = Path("observations.jsonl")


def fetch_historical_price(pair: str, target_time: datetime) -> float:
    """
    【对接交易所API】根据交易对和目标时间抓取历史 K 线或标记价格。
    例如调用 ccxt, Binance API, Coingecko 等。
    这里提供模拟实现，实际使用时替换为真实的 API 逻辑。
    """
    # 示例逻辑：直接返回一个模拟价格（实际开发中请替换为交易所 API 调用）
    # print(f"正在从交易所获取 {pair} 在 {target_time.isoformat()} 的价格...")
    return 100.0  # 替换为实际抓取到的 float 价格


def parse_iso_datetime(dt_str: str) -> datetime:
    """解析 ISO 8601 时间戳为带时区信息的 datetime 对象"""
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def update_and_evaluate_observations(log_path: Path = OBSERVATIONS_LOG) -> None:
    """读取日志，填充超过5天的记录，更新文件，并打印预测准确率 report。"""
    if not log_path.exists():
        print(f"日志文件不存在: {log_path}")
        return

    now = datetime.now(timezone.utc)
    records: List[Dict[str, Any]] = []
    updated_count = 0

    # 1. 读取所有日志行
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    # 2. 遍历检查是否满足 5 天结算条件
    for record in records:
        # 仅处理尚未结算的记录
        if record.get("actual_price_5d_later") is None:
            ts = parse_iso_datetime(record["timestamp"])
            target_time = ts + timedelta(days=5)

            # 如果当前时间已经超过了预测开始后的第 5 天
            if now >= target_time:
                pair = record.get("pair")
                start_price = record.get("forecast_start_price")

                if pair and start_price is not None:
                    actual_price = fetch_historical_price(pair, target_time)
                    is_up = actual_price > start_price

                    # 回填记录
                    record["actual_price_5d_later"] = actual_price
                    record["is_actual_up"] = is_up
                    updated_count += 1

    # 3. 如果有更新，覆盖写回原日志文件
    if updated_count > 0:
        with open(log_path, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"已成功结算并更新 {updated_count} 条记录。\n")
    else:
        print("暂无需要结算的 5 天前记录。\n")

    # 4. 统计准确率
    calculate_metrics(records)


def calculate_metrics(records: List[Dict[str, Any]]) -> None:
    """计算总体准确率以及按分类 Bucket 的准确率"""
    evaluated_records = [r for r in records if r.get("actual_price_5d_later") is None]
    settled_records = [r for r in records if r.get("actual_price_5d_later") is not None]

    print("================ 蒙特卡洛预测准确率统计 ================")
    print(f"总记录数: {len(records)}")
    print(f"已结算数: {len(settled_records)}")
    print(f"待结算数: {len(evaluated_records)}")

    if not settled_records:
        print("尚无已结算的数据，无法计算准确率。")
        return

    # 总体看涨预测准确度计算：
    # 如果模型的 p_up > 0.5 且实际涨了 (is_actual_up == True)，或者 p_up < 0.5 且实际没涨，视为预测正确。
    correct_predictions = 0
    bucket_stats: Dict[str, Dict[str, int]] = {}

    for r in settled_records:
        p_up = r.get("p_up")
        is_actual_up = r.get("is_actual_up")
        bucket = r.get("classification_bucket", "UNKNOWN")

        if p_up is None or is_actual_up is None:
            continue

        # 判断预测是否正确
        predicted_up = p_up >= 0.5
        is_correct = (predicted_up == is_actual_up)

        if is_correct:
            correct_predictions += 1

        # 按概率分类区间 (Bucket) 累计统计
        if bucket not in bucket_stats:
            bucket_stats[bucket] = {"total": 0, "correct": 0}
        bucket_stats[bucket]["total"] += 1
        if is_correct:
            bucket_stats[bucket]["correct"] += 1

    overall_accuracy = (correct_predictions / len(settled_records)) * 100
    print(f"\n总体方向准确率: {overall_accuracy:.2f}% ({correct_predictions}/{len(settled_records)})")

    print("\n--- 分类区间 (Bucket) 准确率分布 ---")
    for bucket, stats in bucket_stats.items():
        acc = (stats["correct"] / stats["total"]) * 100 if stats["total"] > 0 else 0
        print(f"区间 [{bucket}]: 准确率 {acc:.2f}% (正确 {stats['correct']} / 总数 {stats['total']})")


if __name__ == "__main__":
    update_and_evaluate_observations()