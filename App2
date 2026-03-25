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

# ==========================================
# 安全讀取 LINE 設定
# ==========================================
try:
    LINE_CHANNEL_ACCESS_TOKEN = st.secrets["LINE_CHANNEL_ACCESS_TOKEN"]
    LINE_USER_ID = st.secrets["LINE_USER_ID"]
except:
    LINE_CHANNEL_ACCESS_TOKEN = ""
    LINE_USER_ID = ""

# 嘗試導入富途 API
try:
    from futu import *
    FUTU_AVAILABLE = True
except ImportError:
    FUTU_AVAILABLE = False

# 股票名稱映射表 (中英對照)
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
    "TQQQ": {"en": "ProShares Ultra QQQ", "zh": "三倍做多納斯達克"},
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
st.set_page_config(page_title="AI 量化終端 (修復版)", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .metric-card { background-color: #1e1e1e; padding: 10px; border-radius: 8px; border-left: 5px solid #00ffcc; }
    [data-testid="stMetricValue"] { font-size: 18px; color: #00ffcc; }
    [data-testid="stDataFrame"] { border: 1px solid #333; }
    .stAlert { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# 熱門股票清單 (美股優先，Yahoo 穩定)
US_HOT = ["NVDA","TSM","AAPL","MSFT","AMZN","META","AMD","GOOGL","NFLX","TSLA","TQQQ"]

# ==========================================
# 2. 數據提供者 (修復 Yahoo 港股問題)
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
        # 修復：Yahoo Finance 港股代碼處理
        # 嘗試多種格式以提高成功率
        symbol_variants = [symbol]
        if ".HK" in symbol:
            # 港股嘗試不同格式
            symbol_variants.append(symbol.replace(".HK", ".HK")) # 保持原樣
            symbol_variants.append(symbol.replace(".HK", "")) # 嘗試不加 .HK
        
        for sym in symbol_variants:
            try:
                max_lookback = 720 if interval in ['1h', '15m'] else 3650
                actual_days = min(days_back + 60, max_lookback)
                start_date = datetime.now() - timedelta(days=actual_days)
                
                # 禁用進度條，增加重試
                df = yf.download(sym, start=start_date, interval=interval, 
                               progress=False, timeout=15, threads=False)
                
                if df is not None and not df.empty and len(df) > 50:
                    return df
            except Exception as e:
                continue
        
        return pd.DataFrame()

# ==========================================
# 3. LINE 推播函數
# ==========================================
def send_line_push(access_token, user_id, message):
    if not access_token or not user_id: return False
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}
    data = {"to": user_id, "messages": [{"type": "text", "text": message}]}
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=10)
        return response.status_code == 200
    except:
        return False

def send_line_summary(access_token, user_id, results, scan_time):
    if not access_token or not user_id or not results:
        return False

    buy_signals = []
    hold_signals = []
    watch_signals = []
    
    for r in results:
        sym = r['symbol']
        name_zh = STOCK_NAMES.get(sym, {}).get('zh', '')
        name_en = STOCK_NAMES.get(sym, {}).get('en', '')
        name_display = f"{name_zh}/{name_en}" if name_zh else name_en
        
        line = f"• {sym} ({name_display})\n  價格: {r['price']:.2f} | 狀態: {r['status']} | 強度: {r['intensity']}"
        
        if r['status'] == "現價買入":
            buy_signals.append(line)
        elif r['status'] == "持倉中":
            hold_signals.append(line)
        else:
            watch_signals.append(line)

    header = f"🚀 AI 量化掃描摘要\n📅 時間: {scan_time}\n📊 總計: {len(results)} 隻\n\n"
    
    if buy_signals:
        header += "🔥 【現價買入】\n" + "\n".join(buy_signals[:10]) + "\n\n"
    if hold_signals:
        header += "💼 【持倉中】\n" + "\n".join(hold_signals[:10]) + "\n\n"
    if watch_signals:
        header += "👀 【觀望】 (部分)\n" + "\n".join(watch_signals[:20])
    
    if len(header) > 1800:
        header = header[:1800] + "\n\n... (內容過長)"

    return send_line_push(access_token, user_id, header)

# ==========================================
# 4. JSON 保存
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

def run_strategy(data_provider, symbol, interval, days_back, capital, risk_pct, trail_pct):
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
        
        last_idx = -1
        score = 0
        if rsi[last_idx] < 30: score += 2
        if hist[last_idx] < h_lower[last_idx]: score += 2
        if hist[last_idx] > hist[last_idx-1]: score += 2
        if vol[last_idx] > vol_ma[last_idx]: score += 1
        
        # 修復：強度映射錯別字
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
# 6. Streamlit UI (全面修復 + 新增 LINE 測試)
# ==========================================

with st.sidebar:
    st.header("🎛️ 系統中控台")
    
    st.subheader("⚙️ 自動掃描設定")
    auto_scan = st.checkbox("✅ 啟用自動掃描 (每 5 分鐘)", value=True)
    refresh_interval = st.number_input("刷新間隔 (秒)", min_value=60, max_value=3600, value=300, step=60)
    send_line = st.checkbox("📱 掃描完成後發送 LINE 摘要", value=True)
    
    st.divider()
    st.subheader("📝 自定義標的 (去重)")
    # 修復：預設值去除重複 TSM
    default_input = "NVDA\nTSM\nAAPL\nMSFT\nAMZN\nMETA\nAMD\nGOOGL\nNFLX\nTSLA\nTQQQ"
    custom_input = st.text_area("輸入股票代碼 (每行一個)", value=default_input, height=150)
   
    st.divider()
    st.subheader("📱 LINE 設定")
    input_token = st.text_input("Channel Access Token", type="password", 
                               value=LINE_CHANNEL_ACCESS_TOKEN if LINE_CHANNEL_ACCESS_TOKEN else "")
    input_uid = st.text_input("Your User ID", type="password", 
                             value=LINE_USER_ID if LINE_USER_ID else "")
    
    # ================= 新增部分開始 =================
    st.divider()
    if st.button("🧪 測試 LINE 推播", type="secondary"):
        if not input_token or not input_uid:
            st.sidebar.error("❌ 請先填寫 Token 與 User ID")
        else:
            test_msg = f"🔧 連線測試成功！\n⏰ 時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            with st.spinner("正在發送..."):
                success = send_line_push(input_token, input_uid, test_msg)
            
            if success:
                st.sidebar.success("✅ 測試訊息已發送！")
            else:
                st.sidebar.error("❌ 發送失敗，請檢查設定")
    # ================= 新增部分結束 =================

st.title("🚀 AI 量化終端 (修復版)")

# 處理自定義標的 (去重)
scan_list = list(dict.fromkeys([x.strip().upper() for x in custom_input.split("\n") if x.strip()]))

# 狀態顯示
status_placeholder = st.empty()
last_run_placeholder = st.empty()

# 檢查上次運行時間
if 'last_run' not in st.session_state:
    st.session_state['last_run'] = None

if st.session_state['last_run']:
    last_run_placeholder.caption(f"🕐 上次掃描: {st.session_state['last_run']}")

# 手動運行按鈕 (修復：use_container_width -> width)
col1, col2 = st.columns(2)
with col1:
    run_now = st.button("🔄 立即手動掃描", width='stretch', type="primary")

# 掃描邏輯
if auto_scan or run_now:
    if auto_scan:
        status_placeholder.info(f"⏳ 自動模式已開啟，每 {refresh_interval} 秒自動刷新...")
    
    dp = DataProvider()
    results = []
    
    with st.spinner(f"正在分析 {len(scan_list)} 隻股票..."):
        prog_bar = st.progress(0)
        for i, sym in enumerate(scan_list):
            try:
                res = run_strategy(dp, sym, "1d", 120, 100000, 2.0, 5.0)
                if res: results.append(res)
            except Exception as e:
                pass
            prog_bar.progress((i+1)/len(scan_list))
    
    dp.close()
    
    if results:
        scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. 保存 JSON
        save_results_to_json(results)
        
        # 2. 發送 LINE 摘要
        line_sent = False
        if send_line:
            line_sent = send_line_summary(input_token, input_uid, results, scan_time)
        
        # 3. 更新 Session
        st.session_state['scan_results'] = results
        st.session_state['last_run'] = scan_time
        
        # 4. 顯示狀態
        msg = f"✅ 掃描完成！成功: {len(results)}/{len(scan_list)} | 已保存 JSON"
        if line_sent:
            msg += " | 📱 LINE 摘要已發送"
        status_placeholder.success(msg)
        
        # 5. 顯示結果表格 (修復：use_container_width -> width)
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
            
        st.dataframe(df_mon.style.map(highlight, subset=["狀態"]), width='stretch', hide_index=True)
    else:
        status_placeholder.error("❌ 沒有成功分析任何股票 (建議優先使用美股)")

# 自動刷新 (優化：避免 Event loop 錯誤)
if auto_scan:
    try:
        time.sleep(refresh_interval)
        st.rerun()
    except:
        # 捕獲 Event loop 錯誤，優雅退出
        pass
