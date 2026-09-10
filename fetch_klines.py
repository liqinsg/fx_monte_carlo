import requests

def get_klines(pair: str, timeframe: str = 'd') -> list[dict]:
    """
    获取 GitHub 上的 K线历史数据
    :param pair: 交易对名称 (如 'BTCUSDT', 'ETHUSDT')
    :param timeframe: 'd' (天) 或 'w' (周)
    :return: 包含 K线 字典的列表
    """
    pair = pair.upper()
    timeframe = timeframe.lower()
    
    url = f"https://raw.githubusercontent.com/AnandChowdhary/klines/main/data/{timeframe}/{pair}.txt"
    
    response = requests.get(url)
    if response.status_code != 200:
        raise ValueError(f"无法获取数据，请检查参数是否正确: {pair} ({timeframe})")
    
    klines = []
    # 逐行解析文本数据
    for line in response.text.strip().split('\n'):
        if not line:
            continue
        parts = line.split(',')
        if len(parts) >= 6:
            klines.append({
                "timestamp": int(parts[0]),
                "open": float(parts[1]),
                "high": float(parts[2]),
                "low": float(parts[3]),
                "close": float(parts[4]),
                "volume": float(parts[5])
            })
            
    return klines

# 使用示例
if __name__ == "__main__":
    # 参数只需给出 d 或 w，以及 pair
    d_or_w = "d"
    pair = "BTCUSDT"
    
    data = get_klines(pair=pair, timeframe=d_or_w)
    
    print(f"成功获取 {pair} ({d_or_w}) 数据，共 {len(data)} 条记录数据。\n")
    print("最新一根 K线数据:")
    print(data[-1])