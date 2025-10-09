import streamlit as st
import pandas as pd
import pandas_ta as ta
import numpy as np
import requests
import io
import time
from io import StringIO
import warnings
from scipy.stats import linregress
import yfinance as yf
from vnstock import Vnstock

# Suppress specific pandas warnings
warnings.filterwarnings(
    "ignore",
    message="The behavior of DatetimeProperties.to_pydatetime is deprecated",
)

# =======================================================================================
# Configuration and Styling
# =======================================================================================
st.set_page_config(
    page_title="Xu hướng & Bề rộng Thị trường",
    page_icon="📜",
    layout="wide"
)

st.markdown("""
    <style>
    .stMetric {
        border-radius: 10px; padding: 15px; text-align: center; border: 1px solid #ddd;
    }
    .bullish { background-color: #e8f5e9; color: #1b5e20; }
    .bearish { background-color: #ffebee; color: #b71c1c; }
    .main-title { text-align: center; color: #0d47a1; }
    .sub-header { text-align: center; color: #4A4A4A; }
    div[data-testid="stSidebarNav"], div[data-testid="stSidebar"] {display: none;}
    </style>
""", unsafe_allow_html=True)

# =======================================================================================
# Data Loading & Caching (Unchanged)
# =======================================================================================
@st.cache_data(ttl=3600)
def load_data_from_gdrive(gdrive_url):
    try:
        file_id = gdrive_url.split('/d/')[1].split('/')[0]
        download_url = f'https://drive.google.com/uc?export=download&id={file_id}'
        response = requests.get(download_url)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.content.decode('utf-8')))
        df['date'] = pd.to_datetime(df['date']).dt.normalize()
        df.columns = [col.lower().strip() for col in df.columns]
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df.dropna(inplace=True)
        df.sort_values(by=['symbol', 'date'], inplace=True)
        return df
    except Exception as e:
        st.error(f"Lỗi khi tải dữ liệu từ Google Drive: {e}")
        return None

@st.cache_data(ttl=3600)
def get_vnindex_data_robust(start_date, end_date):
    start_date_str = pd.to_datetime(start_date).strftime('%Y-%m-%d')
    end_date_str = pd.to_datetime(end_date).strftime('%Y-%m-%d')
    try:
        vnstock = Vnstock()
        vnindex = vnstock.stock(symbol='VNINDEX', source='TCBS').quote.history(start=start_date_str, end=end_date_str)
        if not vnindex.empty:
            vnindex.rename(columns={'time': 'Date', 'close': 'Close'}, inplace=True)
            vnindex['Date'] = pd.to_datetime(vnindex['Date']).dt.normalize()
            vnindex.set_index('Date', inplace=True)
            return vnindex[['Close']]
    except Exception:
        pass
    end_date_adj = pd.to_datetime(end_date) + pd.Timedelta(days=1)
    for _ in range(3):
        try:
            vnindex_yf = yf.download('^VNINDEX', start=start_date_str, end=end_date_adj, progress=False, timeout=10)
            if not vnindex_yf.empty:
                vnindex_yf.index = vnindex_yf.index.tz_localize(None).normalize()
                return vnindex_yf
            time.sleep(2)
        except Exception:
            time.sleep(2)
    st.warning("Không thể tải dữ liệu VN-Index. Biểu đồ so sánh sẽ không được hiển thị.")
    return None

# =======================================================================================
# ADVANCED Indicator Calculation with ROBUST scoring
# =======================================================================================
@st.cache_data
def calculate_all_indicators_advanced(df):
    def apply_features(group):
        # Base indicators
        group.ta.sma(length=20, append=True)
        group.ta.sma(length=50, append=True)
        group.ta.sma(length=100, append=True)
        group.ta.sma(length=200, append=True)
        group.ta.rsi(length=14, append=True)
        group.ta.macd(fast=12, slow=26, signal=9, append=True)
        group.ta.adx(length=14, append=True)
        group.ta.bbands(length=20, append=True)
        group.ta.sma(close=group['volume'], length=20, prefix="VOL", append=True)
        
        raw_score = pd.Series(0, index=group.index)
        
        # --- FIX: Add safety checks for all indicator columns before scoring ---
        if 'SMA_200' in group.columns:
            raw_score += np.where(group['close'] > group['SMA_200'], 3, 0)
        if 'SMA_100' in group.columns:
            raw_score += np.where(group['close'] < group['SMA_100'], -2, 0)
        if all(c in group.columns for c in ['SMA_100', 'SMA_200']):
            raw_score += np.where(group['SMA_100'] > group['SMA_200'], 2, 0)
        
        if 'SMA_50' in group.columns:
            raw_score += np.where(group['close'] > group['SMA_50'], 2, 0)
        if 'SMA_20' in group.columns:
            raw_score += np.where(group['close'] < group['SMA_20'], -1, 0)
        if all(c in group.columns for c in ['SMA_20', 'SMA_50']):
            raw_score += np.where(group['SMA_20'] > group['SMA_50'], 1, 0)

        if 'RSI_14' in group.columns:
            rsi_conditions = [group['RSI_14'] > 70, group['RSI_14'] > 50, group['RSI_14'] < 30, group['RSI_14'] < 50]
            rsi_scores = [2, 1, -2, -1]
            raw_score += np.select(rsi_conditions, rsi_scores, default=0)
        
        if all(c in group.columns for c in ['MACD_12_26_9', 'MACDs_12_26_9']):
            macd_crossover = (group['MACD_12_26_9'] > group['MACDs_12_26_9']) & (group['MACD_12_26_9'].shift(1) <= group['MACDs_12_26_9'].shift(1))
            raw_score += np.where(macd_crossover, 2, 0)

        if 'ADX_14' in group.columns:
            adx_conditions = [group['ADX_14'] > 40, group['ADX_14'] > 25, group['ADX_14'] < 20]
            adx_scores = [2, 1, -1]
            raw_score += np.select(adx_conditions, adx_scores, default=0)

        if 'VOL_SMA_20' in group.columns:
            strong_bullish_candle = (group['close'] > group['open']) & (group['volume'] > group['VOL_SMA_20'])
            strong_bearish_candle = (group['close'] < group['open']) & (group['volume'] > group['VOL_SMA_20'])
            raw_score += np.where(strong_bullish_candle, 2, 0)
            raw_score += np.where(strong_bearish_candle, -2, 0)
        
        if 'BBU_20_2.0' in group.columns: # This was the column causing the error
            raw_score += np.where(group['close'] > group['BBU_20_2.0'], 1, 0)
        
        group['Raw Score'] = raw_score
        group['Trend Score'] = group['Raw Score'].rolling(window=10).mean()
        
        group['prev_close'] = group['close'].shift(1)
        group['MACD_Bull'] = group['MACD_12_26_9'] > group['MACDs_12_26_9'] if all(c in group.columns for c in ['MACD_12_26_9', 'MACDs_12_26_9']) else False
        group['MACD_Crossover'] = group['MACD_Bull'].diff()
        
        return group

    df_with_indicators = df.groupby('symbol', group_keys=False).apply(apply_features)
    return df_with_indicators

def generate_latest_day_signals_advanced(df_with_indicators):
    latest_signals = []
    latest_date = df_with_indicators['date'].max()
    latest_df = df_with_indicators[df_with_indicators['date'] == latest_date]
    for _, latest in latest_df.iterrows():
        score = latest['Raw Score']
        if score > 10: trend = "Rất Tích cực"
        elif score > 5: trend = "Tích cực"
        elif score < -5: trend = "Rất Tiêu cực"
        elif score < 0: trend = "Tiêu cực"
        else: trend = "Trung lập"
        latest_signals.append({
            "Mã CP": latest['symbol'], "Giá đóng cửa": f"{latest['close'] / 1000:.2f}",
            "Điểm Sức khỏe": f"{int(score)}", "Đánh giá": trend,
            "ADX (14)": f"{latest.get('ADX_14', 0):.1f}", "Volume": "Cao" if pd.notna(latest.get('VOL_SMA_20')) and latest['volume'] > latest.get('VOL_SMA_20', float('inf')) else "Thấp"
        })
    return pd.DataFrame(latest_signals)

@st.cache_data
def calculate_market_breadth_history(df_with_indicators):
    breadth_data = []
    # (The rest of this function is identical to the previous version)
    for date, daily_df in df_with_indicators.groupby('date'):
        if daily_df.empty: continue
        total_stocks = len(daily_df)
        advances = (daily_df['close'] > daily_df['prev_close']).sum()
        declines = (daily_df['close'] < daily_df['prev_close']).sum()
        up_volume = daily_df[daily_df['close'] > daily_df['prev_close']]['volume'].sum()
        down_volume = daily_df[daily_df['close'] < daily_df['prev_close']]['volume'].sum()
        ad_ratio = advances / declines if declines > 0 else (advances / 1)
        ud_vol_ratio = up_volume / down_volume if down_volume > 0 else (up_volume / 1)
        trin = ad_ratio / ud_vol_ratio if ud_vol_ratio > 0 else 0
        breadth_data.append({
            'Date': date, 'A-D Net': advances - declines,
            'Up Vol': up_volume, 'Down Vol': down_volume, 'TRIN': trin,
            '% > MA50': (daily_df['close'] > daily_df['SMA_50']).sum() / total_stocks if 'SMA_50' in daily_df.columns else 0,
            '% > MA200': (daily_df['close'] > daily_df['SMA_200']).sum() / total_stocks if 'SMA_200' in daily_df.columns else 0,
            '% RSI > 50': (daily_df['RSI_14'] > 50).sum() / total_stocks if 'RSI_14' in daily_df.columns else 0,
            '% MACD Crossover': (daily_df['MACD_Crossover'] == True).sum() / total_stocks if 'MACD_Crossover' in daily_df.columns else 0
        })
    breadth_df = pd.DataFrame(breadth_data).set_index('Date').sort_index()
    breadth_df['A-D Line'] = breadth_df['A-D Net'].cumsum()
    breadth_df['U/D Ratio'] = breadth_df['Up Vol'] / breadth_df['Down Vol'].replace(0, 1)
    breadth_df['U/D Ratio MA5'] = breadth_df['U/D Ratio'].rolling(window=5).mean()
    def get_trend_score(series):
        y = series.dropna()
        if len(y) < 5: return np.nan
        x = np.arange(len(y)); slope, _, _, _, _ = linregress(x, y)
        normalized_slope = slope / y.mean() if y.mean() != 0 else 0
        if normalized_slope > 0.05: return 2
        elif normalized_slope > 0.01: return 1
        elif normalized_slope < -0.05: return -2
        elif normalized_slope < -0.01: return -1
        else: return 0
    breadth_df['Score ADL'] = breadth_df['A-D Line'].rolling(window=10).apply(get_trend_score, raw=False)
    score_columns_to_create = {
        'Score MA200': {'series': breadth_df['% > MA200'], 'bins': [-np.inf, 0.15, 0.30, 0.50, 0.70, np.inf], 'labels': [-2, -1, 0, 1, 2]},
        'Score MA50': {'series': breadth_df['% > MA50'], 'bins': [-np.inf, 0.20, 0.40, 0.60, 0.80, np.inf], 'labels': [-2, -1, 0, 1, 2]},
        'Score UDV': {'series': breadth_df['U/D Ratio MA5'], 'bins': [-np.inf, 0.5, 0.75, 1.25, 1.75, np.inf], 'labels': [-2, -1, 0, 1, 2]},
        'Score RSI': {'series': breadth_df['% RSI > 50'], 'bins': [-np.inf, 0.25, 0.40, 0.60, 0.75, np.inf], 'labels': [-2, -1, 0, 1, 2]},
        'Score MACD': {'series': breadth_df['% MACD Crossover'].rolling(window=3).sum(), 'bins': [-np.inf, 0.10, 0.20, np.inf], 'labels': [0, 1, 2]},
    }
    for col_name, params in score_columns_to_create.items():
        breadth_df[col_name] = pd.cut(params['series'], bins=params['bins'], labels=params['labels'], right=False)
    score_columns = ['Score MA200', 'Score MA50', 'Score ADL', 'Score UDV', 'Score RSI', 'Score MACD']
    for col in score_columns:
        breadth_df[col] = pd.to_numeric(breadth_df[col], errors='coerce').fillna(0)
    breadth_df['Tổng Điểm'] = breadth_df[score_columns].sum(axis=1)
    bins_status = [-np.inf, -6, -2, 3, 8, np.inf]
    labels_status = ['Giảm Mạnh', 'Giảm Thận Trọng', 'Trung Lập', 'Tăng Thận Trọng', 'Tăng Mạnh']
    breadth_df['Trạng thái'] = pd.cut(breadth_df['Tổng Điểm'], bins=bins_status, labels=labels_status, right=False)
    return breadth_df.sort_index(ascending=False)

# =======================================================================================
# Main Application UI and Logic
# =======================================================================================
def main():
    st.markdown("<h1 class='main-title'>📜 Xu hướng & Bề rộng Thị trường (Nâng cao)</h1>", unsafe_allow_html=True)
    gdrive_link = "https://drive.google.com/file/d/1E0BDythcdIdGrIYdbJCNB0DxPHJ-njzc/view?usp=drive_link"
    master_df = load_data_from_gdrive(gdrive_link)
    if master_df is not None:
        with st.spinner('Đang tính toán toàn bộ chỉ báo và điểm sức khỏe nâng cao...'):
            df_with_indicators = calculate_all_indicators_advanced(master_df.copy())
        st.header(f"📊 Phân tích Chi tiết Ngày Gần Nhất ({df_with_indicators['date'].max().strftime('%Y-%m-%d')})")
        latest_signals_df = generate_latest_day_signals_advanced(df_with_indicators)
        trend_counts = latest_signals_df['Đánh giá'].value_counts()
        pos_count = trend_counts.get("Rất Tích cực", 0) + trend_counts.get("Tích cực", 0)
        neg_count = trend_counts.get("Rất Tiêu cực", 0) + trend_counts.get("Tiêu cực", 0)
        total_stocks = len(latest_signals_df)
        pos_pct = (pos_count / total_stocks) * 100 if total_stocks > 0 else 0
        neg_pct = (neg_count / total_stocks) * 100 if total_stocks > 0 else 0
        col1, col2 = st.columns(2); col1.metric("Tổng Tích cực", f"{pos_pct:.1f}%", f"{pos_count}/{total_stocks} cp"); col2.metric("Tổng Tiêu cực", f"{neg_pct:.1f}%", f"{neg_count}/{total_stocks} cp")
        def style_trend(val):
            if "Rất Tích cực" in val: return 'background-color: #4CAF50; color: white;';
            if "Tích cực" in val: return 'background-color: #C8E6C9;';
            if "Rất Tiêu cực" in val: return 'background-color: #F44336; color: white;';
            if "Tiêu cực" in val: return 'background-color: #FFCDD2;';
            return ''
        st.dataframe(latest_signals_df.style.applymap(style_trend, subset=['Đánh giá']), use_container_width=True)
        st.divider()
        st.header("📈 Lịch sử Bề rộng Thị trường")
        breadth_history_df = calculate_market_breadth_history(df_with_indicators)
        start_date = breadth_history_df.index.min(); end_date = breadth_history_df.index.max(); vnindex_df = get_vnindex_data_robust(start_date, end_date)
        for col in ['% > MA50', '% > MA200', '% RSI > 50', '% MACD Crossover']:
             breadth_history_df[col] = breadth_history_df[col].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A")
        display_cols = ['A-D Line', 'TRIN', 'U/D Ratio MA5', '% > MA200', '% > MA50', '% RSI > 50', '% MACD Crossover', 'Tổng Điểm', 'Trạng thái']
        breadth_history_df['TRIN'] = breadth_history_df['TRIN'].map('{:,.2f}'.format); breadth_history_df['U/D Ratio MA5'] = breadth_history_df['U/D Ratio MA5'].map('{:,.2f}'.format); breadth_history_df['Tổng Điểm'] = breadth_history_df['Tổng Điểm'].map('{:,.0f}'.format)
        st.dataframe(breadth_history_df[display_cols], use_container_width=True)
        st.subheader("Biểu đồ Phân kỳ A-D Line vs. VN-Index")
        if vnindex_df is not None:
            breadth_history_df_reset = breadth_history_df.reset_index().rename(columns={'Date': 'date'}); vnindex_df_reset = vnindex_df.reset_index().rename(columns={'Date': 'date', 'Close': 'VN-Index'}); chart_df = pd.merge(breadth_history_df_reset, vnindex_df_reset[['date', 'VN-Index']], on='date', how='inner')
            if not chart_df.empty:
                chart_df.set_index('date', inplace=True); chart_df['A-D Line (Scaled)'] = (chart_df['A-D Line'] - chart_df['A-D Line'].min()) / (chart_df['A-D Line'].max() - chart_df['A-D Line'].min()); chart_df['VN-Index (Scaled)'] = (chart_df['VN-Index'] - chart_df['VN-Index'].min()) / (chart_df['VN-Index'].max() - chart_df['VN-Index'].min())
                st.line_chart(chart_df[['A-D Line (Scaled)', 'VN-Index (Scaled)']].sort_index())
            else:
                st.warning("Không có ngày giao dịch chung. Hiển thị A-D Line riêng lẻ."); st.line_chart(breadth_history_df[['A-D Line']].sort_index())
        else:
            st.line_chart(breadth_history_df[['A-D Line']].sort_index())
        st.divider()
        st.header("🔬 Phân tích Chi tiết Từng Cổ phiếu (Hệ thống điểm Nâng cao)")
        all_symbols = sorted(df_with_indicators['symbol'].unique())
        selected_stock = st.selectbox("Chọn một mã cổ phiếu để phân tích:", all_symbols)
        if selected_stock:
            stock_history = df_with_indicators[df_with_indicators['symbol'] == selected_stock].copy()
            if not stock_history.empty and 'Trend Score' in stock_history.columns:
                st.subheader(f"Biểu đồ Giá và Đường Sức khỏe Xu hướng cho {selected_stock}")
                chart_data = stock_history[['date', 'close', 'Trend Score']].set_index('date')
                chart_data.dropna(inplace=True)
                if not chart_data.empty:
                    chart_data['Giá (Scaled)'] = (chart_data['close'] - chart_data['close'].min()) / (chart_data['close'].max() - chart_data['close'].min())
                    chart_data['Sức khỏe Xu hướng (Scaled)'] = (chart_data['Trend Score'] - chart_data['Trend Score'].min()) / (chart_data['Trend Score'].max() - chart_data['Trend Score'].min())
                    st.line_chart(chart_data[['Giá (Scaled)', 'Sức khỏe Xu hướng (Scaled)']].sort_index())
                else:
                    st.warning(f"Không có đủ dữ liệu sau khi xử lý để vẽ biểu đồ cho {selected_stock}.")
            else:
                st.warning(f"Không có đủ dữ liệu lịch sử để vẽ biểu đồ cho {selected_stock}.")
    else:
        st.error("Không thể tải hoặc xử lý dữ liệu. Vui lòng kiểm tra lại file Google Drive.")

if __name__ == "__main__":
    main()