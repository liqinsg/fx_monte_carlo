import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import t, norm

# 1. 从雅虎财经抓取日元四维货币对历史日线数据 (以过去 3 年为例)
# 对应 yfinance 代码：USDJPY=X, EURJPY=X, AUDJPY=X, CHFJPY=X
tickers_yf = ['USDJPY=X', 'EURJPY=X', 'AUDJPY=X', 'CHFJPY=X']
raw_data = yf.download(tickers_yf, period="3y")['Close']
raw_data.columns = ['AUDJPY', 'CHFJPY', 'EURJPY', 'USDJPY']  # yfinance 会按字母重排序
df = raw_data[['USDJPY', 'EURJPY', 'AUDJPY', 'CHFJPY']].dropna()

# 2. 计算日对数收益率
returns = np.log(df / df.shift(1)).dropna()
n_assets = len(df.columns)
S0 = df.iloc[-1].values
dt = 1 / 252

# 3. 算法结合点：为每个资产拟合 Student-t 分布（捕捉肥尾），并转为 Copula 概率空间
u_data = np.zeros_like(returns.values)
t_params = []

for i in range(n_assets):
    # 拟合 t 分布参数：自由度 (df_t), 均值 (loc), 缩放因子 (scale)
    df_t, loc, scale = t.fit(returns.iloc[:, i])
    t_params.append((df_t, loc, scale))
    # 通过 t 分布的 CDF 将收益率映射到概率空间 [0, 1]
    u_data[:, i] = t.cdf(returns.iloc[:, i], df=df_t, loc=loc, scale=scale)

# 4. 在 Copula 空间计算高斯/t 隐式相关性矩阵并做 Cholesky 分解
# 将 [0,1] 的概率通过标准正态逆 CDF 反演为正态随机数提取相关性
gaussian_z = norm.ppf(np.clip(u_data, 1e-6, 1 - 1e-6))
corr_matrix = np.corrcoef(gaussian_z, rowvar=False)
L = np.linalg.cholesky(corr_matrix)

# 5. 多维 Student-t Copula Monte Carlo 路径模拟
n_days = 30
n_simulations = 10000
simulated_paths = np.zeros((n_simulations, n_days, n_assets))

np.random.seed(42)
for sim in range(n_simulations):
    # 生成相互独立的正态随机数并注入多维相关性
    Z_indep = np.random.normal(size=(n_days, n_assets))
    Z_corr = Z_indep @ L.T
    
    # 将相关随机数转回 [0,1] 空间，再通过各资产拟合好的 t 分布逆 CDF 映射回真实收益率
    U_sim = norm.cdf(Z_corr)
    sim_returns = np.zeros_like(U_sim)
    for i in range(n_assets):
        df_t, loc, scale = t_params[i]
        sim_returns[:, i] = t.ppf(np.clip(U_sim[:, i], 1e-6, 1 - 1e-6), df=df_t, loc=loc, scale=scale)
    
    # 还原生成 30 天价格路径
    path = np.zeros((n_days, n_assets))
    path[0] = S0
    for t_step in range(1, n_days):
        path[t_step] = path[t_step - 1] * np.exp(sim_returns[t_step])
    simulated_paths[sim] = path

# 6. 提取未来 30 天包含极端尾部风险的概率区间
print("\n=== 基于 yfinance 数据 + Student-t Copula 多维 MC 的日元走势包络线 ===")
for i, col in enumerate(df.columns):
    final_prices = simulated_paths[:, -1, i]
    p_low = np.percentile(final_prices, 5)     # 5% 极端下轨
    p_median = np.median(final_prices)         # 50% 中位中轴
    p_high = np.percentile(final_prices, 95)   # 95% 极端上轨
    print(f"{col:7s} | 当前价: {S0[i]:.2f} | 90%预测范围: {p_low:.2f} ~ {p_high:.2f} (中位数: {p_median:.2f})")