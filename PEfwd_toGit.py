import os
import requests
import sqlite3
from datetime import datetime

# 1. 基礎設定
api_key = os.environ.get("FINNHUB_API_KEY") # 從 GitHub Secrets 安全讀取 API Key
current_date = datetime.now().strftime("%Y-%m-%d")
db_path = "sox_history.db"  # 資料庫檔案會保存在專案目錄下

# 2. 29 檔成分股 (已剔除 TSM)
sox_29_tickers = [
    "NVDA", "AVGO", "AMD", "QCOM", "INTC", "MU", "TXN", "AMAT", "LRCX", "ADI",
    "KLAC", "MRVL", "MCHP", "MPWR", "ON", "NXPI", "ASML", "ARM", "SWKS", "QRVO",
    "SLAB", "ALGM", "DIOD", "CRUS", "TER", "MKSI", "ENTG", "COHR", "AMKR"
]

# 3. 初始化 SQLite 資料庫與資料表
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 建立個股明細表
cursor.execute('''
    CREATE TABLE IF NOT EXISTS stock_daily_metrics (
        date TEXT, ticker TEXT, price REAL, marketcap REAL, pefwd REAL,
        PRIMARY KEY (date, ticker)
    )
''')
# 建立組合加權總覽表
cursor.execute('''
    CREATE TABLE IF NOT EXISTS portfolio_summary (
        date TEXT PRIMARY KEY, weighted_pefwd REAL
    )
''')
conn.commit()

# 4. 抓取 API 數據
raw_data = []
total_market_cap = 0.0

print("開始向 Finnhub API 請求數據...")
for ticker in sox_29_tickers:
    metric_url = f"https://finnhub.io/api/v1/stock/metric?symbol={ticker}&metric=all&token={api_key}"
    quote_url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={api_key}"
    
    try:
        metric_res = requests.get(metric_url).json()
        quote_res = requests.get(quote_url).json()
        
        metrics = metric_res.get("metric", {})
        price = quote_res.get("c")
        market_cap = metrics.get("marketCapitalization")
        pe_fwd = metrics.get("forwardPE")
        
        if market_cap:
            total_market_cap += float(market_cap)
            
        raw_data.append((current_date, ticker, price, market_cap, pe_fwd))
    except Exception as e:
        print(f"[{ticker}] 抓取失敗: {e}")

# 5. 寫入個股數據並計算加權 PEfwd
weighted_pefwd_sum = 0.0

for row in raw_data:
    # 寫入個股明細 (若當天重複執行會自動覆蓋)
    cursor.execute('''
        INSERT OR REPLACE INTO stock_daily_metrics (date, ticker, price, marketcap, pefwd)
        VALUES (?, ?, ?, ?, ?)
    ''', row)
    
    # 計算單檔加權貢獻
    mcap = row[3]
    pe_fwd = row[4]
    if mcap and pe_fwd and total_market_cap > 0:
        weight = float(mcap) / total_market_cap
        weighted_pefwd_sum += weight * float(pe_fwd)

# 6. 寫入組合總覽
if weighted_pefwd_sum > 0:
    cursor.execute('''
        INSERT OR REPLACE INTO portfolio_summary (date, weighted_pefwd)
        VALUES (?, ?)
    ''', (current_date, round(weighted_pefwd_sum, 4)))

conn.commit()
conn.close()
print("資料庫寫入成功，連線已關閉。")