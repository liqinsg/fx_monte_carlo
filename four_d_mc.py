import numpy as np
import pandas as pd
from scipy.stats import norm
import yfinance as yf

# 1. 配置 日元 4 维货币对 (yfinance 用 Yahoo Finance 的 ticker 格式)
jpy_pairs = {
    "USD_JPY": "USDJPY=X",
    "EUR_JPY": "EURJPY=X",
    "AUD_JPY": "AUDJPY=X",
    "CHF_JPY": "CHFJPY=X",
}

# 2. 获取历史收盘价 (以最近 500 条日蜡烛图为例)
price_dict = {}

for pair_name, ticker in jpy_pairs.items():
    data = yf.download(ticker, period="3y", interval="1d", auto_adjust=False, progress=False)
    closes = data["Close"].dropna().tail(500)
    
    # yf.download 返回 DataFrame;若是多列则取唯一列
    if isinstance(closes, pd.DataFrame):
        closes = closes.iloc[:, 0]
    price_dict[pair_name] = closes.values

df = pd.DataFrame(price_dict)

# 3. 极简多维 Monte Carlo 拟合逻辑 (结合 Cholesky 分解)
returns = np.log(df / df.shift(1)).dropna()
S0 = df.iloc[-1].values
mu = returns.mean().values * 252
sigma = returns.std().values * np.sqrt(252)
dt = 1 / 252

# 动态提取包含 JPY 及其它 4 维货币的协方差/相关性矩阵
cov_matrix = returns.cov().values * 252
L = np.linalg.cholesky(cov_matrix)

n_days = 30
n_simulations = 10000
simulated_paths = np.zeros((n_simulations, n_days, len(jpy_pairs)))

np.random.seed(42)
for sim in range(n_simulations):
    Z = np.random.normal(size=(n_days, len(jpy_pairs)))
    Z_corr = Z @ L.T
    
    path = np.zeros((n_days, len(jpy_pairs)))
    path[0] = S0
    for t in range(1, n_days):
        drift = (mu - 0.5 * (sigma ** 2)) * dt
        shock = np.sqrt(dt) * Z_corr[t]
        path[t] = path[t-1] * np.exp(drift + shock)
    simulated_paths[sim] = path

# 4. 打印未来 30 天概率包络线 (Upper & Lower Bounds)
print("\n=== 基于 yfinance 数据的日元多维概率范围拟合 ===")
for i, pair in enumerate(df.columns):
    final_prices = simulated_paths[:, -1, i]
    p_low = np.percentile(final_prices, 5)
    p_high = np.percentile(final_prices, 95)
    print(f"{pair:7s} | 当前价格: {S0[i]:.2f} | 90%概率区间: {p_low:.2f} ~ {p_high:.2f}")