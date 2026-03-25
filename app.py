import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from datetime import datetime, timedelta
import yfinance as yf
import time
import json
import os

# 嘗試導入富途 API
try:
    from futu import *
    FUTU_AVAILABLE = True
except ImportError:
    FUTU_AVAILABLE = False

# ==========================================
# LINE 配置信息
# ==========================================
LINE_CHANNEL_SECRET = "0ace01f20098b294c462404e079f3584"
LINE_CHANNEL_ACCESS_TOKEN = "4W6+YgAxXzVJhie/z1CquX6e4vhCQZ/ctHZJhp4+32EwDJdr3cAf9kfYEO9FTTPhpMb8AWCyVIsHuZxuCJKrcHb43sUV5mx9rHso1wCQNuDSBKc74eR9zdNviFGuoJcCLF2ZyQeG60jFjh2nsbsCUwdB04t89/1O/w1cDnyilFU="
LINE_USER_ID = "U80230c7dd330d8710c75da0b01f60c7d"

# ==========================================
# 股票名稱映射表 (中英對照)
# ==========================================
STOCK_NAMES = {
    "NVDA": {"en": "NVIDIA", "zh": "輝達"},
    "TSM": {"en": "Taiwan Semiconductor", "zh": "台積電"},
    "AAPL": {"en": "Apple", "zh": "蘋果"},
    "MSFT": {"en": "Microsoft", "zh": "微軟"},
    "AMZN": {"en": "Amazon", "zh": "亞馬遜"},
    "META": {"en": "Meta", "zh": "元宇宙"},
    "TSLA": {"en": "Tesla", "zh": "特斯拉"},
    "GOOGL": {"en": "Alphabet", "zh": "谷歌"},
    "AMD": {"en": "AMD", "zh": "超微半導體"},
    "NFLX": {"en": "Netflix", "zh": "網飛"},
    "00700.HK": {"en": "Tencent", "zh": "騰訊控股"},
    "09988.HK": {"en": "Alibaba", "zh": "阿里巴巴"},
    "03690.HK": {"en": "Meituan", "zh": "美團"},
    "01810.HK": {"en": "Xiaomi", "zh": "小米集團"},
    "09618.HK": {"en": "JD.com", "zh": "京東集團"},
    "00001.HK": {"en": "CK Hutchison", "zh": "長和"},
    "00005.HK": {"en": "HSBC Holdings", "zh": "滙豐控股"},
    "00388.HK": {"en": "HKEX", "zh": "香港交易所"},
    "02318.HK": {"en": "Ping An", "zh": "中國平安"},
    "01299.HK": {"en": "AIA Group", "zh": "友邦保險"},
}

# ==========================================
# 1. 基礎設定與 CSS
# ==========================================
st.set_page_config(page_title="AI 量化終端 (自動刷新版)", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .metric-card { background-color: #1e1e1e; padding: 10px; border-radius: 8px; border-left: 5px solid #00ffcc; }
    [data-testid="stMetricValue"] { font-size: 18px; color: #00ffcc; }
    [data-testid="stDataFrame"] { border: 1px solid #333; }
    .stAlert { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# 熱門股票清單
US_HOT = ["NVDA","TSM","AAPL","MSFT","AMZN"]
HK_HOT_CORE = ["00700.HK", "09988.HK", "03690.HK", "01810.HK", "09618.HK"]

# ==========================================
# 2. 數據提供者
# ==========================================
class DataProvider:
    def __init__(self, use_futu=False):
        self.use_futu = use_futu and FUTU_AVAILABLE
        self.ctx = None
        self.futu_connected = False
        
        if self.use_futu:
            try:
                self.ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
                self.futu_connected = True
            except Exception:
                self.futu_connected = False

    def close(self):
        if self.ctx:
            self.ctx.close()

    def get_data(self, symbol, interval, days_back):
        # 優先: Yahoo Finance
        try:
            max_lookback = 720 if interval in ['1h', '15m'] else 3650
            actual_days = min(days_back + 60, max_lookback)
            start_date = datetime.now() - timedelta(days=actual_days)
            df = yf.download(symbol, start=start_date, interval=interval, progress=False, timeout=10)
            if df is not None and not df.empty and len(df) > 50:
                return df
        except: pass
        return pd.DataFrame()

# ==========================================
# 3. LINE 推播
# ==========================================
def send_line_push(access_token, user_id, message):
    if not access_token or not user_id: return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}
    data = {"to": user_id, "messages": [{"type": "text", "text": message}]}
    try:
        requests.post(url, headers=headers, data=json.dumps(data), timeout=5)
    except: pass

# ==========================================
# 4. JSON 保存/讀取
# ==========================================
def save_results_to_json(results, filename="scan_results.json"):
    try:
        serializable_results = []
        for r in results:
            serializable_results.append({
                "symbol": r['symbol'],
                "name_zh": STOCK_NAMES.get(r['symbol'], {}).get('zh', r['symbol']),
                "name_en": STOCK_NAMES.get(r['symbol'], {}).get('en', r['symbol']),
                "price": float(r['price']),
                "time": r['time'],
                "status": r['status'],
                "intensity": r['intensity'],
                "score": r['score'],
                "final_ret_pct": float(r['final_ret'])
            })
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "results": serializable_results
            }, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

# ==========================================
# 5. 核心策略
# ==========================================
def calculate_indicators(df):
    if df.empty: return df
    df = df.copy()
    close = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
    vol = df['Volume'].iloc[:, 0] if isinstance(df['Volume'], pd.DataFrame) else df['Volume']
    
    df['DIF'] = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['HIST'] = df['DIF'] - df['DEA']
    df['H_MA'] = df['HIST'].rolling(50).mean()
    df['H_STD'] = df['HIST'].rolling(50).std()
    df['H_Lower'] = df['H_MA'] - (2 * df['H_STD'])
    
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    df['Vol_MA'] = vol.rolling(20).mean()
    return df

def run_strategy(data_provider, symbol, interval, days_back, capital, risk_pct, trail_pct, line_token, line_uid):
    try:
        df = data_provider.get_data(symbol, interval, days_back)
        if df is None or df.empty or len(df) < 50: return None
        df = calculate_indicators(df)
        
        close = df['Close'].values.flatten() if isinstance(df['Close'], pd.DataFrame) else df['Close'].values
        vol = df['Volume'].values.flatten() if isinstance(df['Volume'], pd.DataFrame) else df['Volume'].values
        vol_ma = df['Vol_MA'].values
        hist = df['HIST'].values
        h_lower = df['H_Lower'].values
        rsi = df['RSI'].values
        dates = df.index
        
        in_pos = False
        entry_price = 0.0
        last_idx = -1
        score = 0
        if rsi[last_idx] < 30: score += 2
        if hist[last_idx] < h_lower[last_idx]: score += 2
        if hist[last_idx] > hist[last_idx-1]: score += 2
        if vol[last_idx] > vol_ma[last_idx]: score += 1
        
        intensity_map = {0: "無", 1: "弱", 2: "中", 3: "強", 4: "極強", 5: "極強", 6: "極強"}
        intensity = intensity_map.get(min(score, 6), "弱")
        status = "觀望"
        
        is_buy_now = (hist[last_idx] < h_lower[last_idx] or rsi[last_idx] < 32) and (hist[last_idx] > hist[last_idx-1])
        if is_buy_now:
            status = "現價買入"
            intensity = "極強"

        return {
            "symbol": symbol,
            "price": close[-1],
            "time": dates[-1].strftime("%Y-%m-%d %H:%M:%S"),
            "final_ret": 0.0,
            "trade_logs": [],
            "df": df,
            "signals": [],
            "status": status,
            "intensity": intensity,
            "score": score + (100 if status == "現價買入" else 0),
            "shares_suggestion": 0
        }
    except Exception as e:
        return None

# ==========================================
# 6. Streamlit UI (包含自動刷新)
# ==========================================

with st.sidebar:
    st.header("🎛️ 系統中控台")
    
    st.subheader("⚙️ 自動掃描設定")
    auto_scan = st.checkbox("✅ 啟用自動掃描 (每 5 分鐘)", value=True)
    refresh_interval = st.number_input("刷新間隔 (秒)", min_value=60, max_value=3600, value=300, step=60, 
                                      help="Streamlit Cloud 建議設置 300 秒以上")
    
    st.divider()
    st.subheader("📝 自定義標的")
    custom_input = st.text_area("輸入股票代碼 (每行一個)", value="00700.HK\n09988.HK\nNVDA\nTSLA",
                                height=150)
    
    st.divider()
    st.subheader("📱 LINE 通知")
    line_token = st.text_input("Channel Access Token", type="password", value=LINE_CHANNEL_ACCESS_TOKEN)
    line_uid = st.text_input("Your User ID", type="password", value=LINE_USER_ID)

st.title("🚀 AI 量化終端 (自動刷新版)")

# 處理自定義標的
scan_list = [x.strip().upper() for x in custom_input.split("\n") if x.strip()]

# 狀態顯示
status_placeholder = st.empty()
last_run_placeholder = st.empty()

# 檢查上次運行時間
if 'last_run' not in st.session_state:
    st.session_state['last_run'] = None

if st.session_state['last_run']:
    last_run_placeholder.caption(f"🕐 上次掃描: {st.session_state['last_run']}")

# 手動運行按鈕
col1, col2 = st.columns(2)
with col1:
    run_now = st.button("🔄 立即手動掃描", use_container_width=True, type="primary")

# 自動刷新邏輯
if auto_scan or run_now:
    if auto_scan:
        status_placeholder.info(f"⏳ 自動模式已開啟，每 {refresh_interval} 秒自動刷新...")
    
    dp = DataProvider()
    results = []
    
    with st.spinner(f"正在分析 {len(scan_list)} 隻股票..."):
        prog_bar = st.progress(0)
        for i, sym in enumerate(scan_list):
            try:
                res = run_strategy(dp, sym, "1d", 120, 100000, 2.0, 5.0, line_token, line_uid)
                if res: results.append(res)
            except: pass
            prog_bar.progress((i+1)/len(scan_list))
    
    dp.close()
    
    if results:
        save_results_to_json(results)
        st.session_state['scan_results'] = results
        st.session_state['last_run'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_placeholder.success(f"✅ 掃描完成！成功: {len(results)}/{len(scan_list)} | 已保存 JSON")
        
        # 顯示結果
        st.subheader("🔔 即時買賣信號")
        monitor_data = []
        for r in results:
            sym = r['symbol']
            name_zh = STOCK_NAMES.get(sym, {}).get('zh', '')
            name_en = STOCK_NAMES.get(sym, {}).get('en', '')
            monitor_data.append({
                "代碼": sym,
                "名稱": f"{name_zh} / {name_en}",
                "狀態": r['status'],
                "強度": r['intensity'],
                "價格": f"{r['price']:.2f}",
                "_sort": r['score']
            })
        
        df_mon = pd.DataFrame(monitor_data)
        df_mon = df_mon.sort_values("_sort", ascending=False).drop(columns=["_sort"])
        
        def highlight(val):
            if "現價買入" in val: return 'background-color: #00cc00; color: white; font-weight: bold'
            if "持倉中" in val: return 'color: #00ffcc'
            return ''
            
        st.dataframe(df_mon.style.map(highlight, subset=["狀態"]), use_container_width=True, hide_index=True)

# 自動刷新 (僅在開啟自動模式時)
if auto_scan:
    time.sleep(refresh_interval)
    st.rerun()
