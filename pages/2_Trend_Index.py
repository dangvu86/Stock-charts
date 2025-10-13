import streamlit as st
import pandas as pd
import numpy as np
import requests
import io
import time
from io import StringIO
import warnings
from scipy.stats import linregress
import yfinance as yf
from vnstock import Vnstock
import sys
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Add path to use existing technical indicators module
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from indicators.technical import calculate_sma, calculate_rsi, calculate_macd, calculate_bollinger_bands
from indicators.adx import calculate_adx

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
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    /* Main background */
    .main {
        background-color: #f5f5f5;
    }

    /* Metric cards */
    .stMetric {
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        border: 1px solid #e1e3e6;
        background-color: #ffffff;
    }

    /* Headers */
    .main-title {
        text-align: center;
        color: #0d47a1;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }

    .sub-header {
        text-align: center;
        color: #4A4A4A;
        font-size: 1.2rem;
    }

    /* Dataframe styling */
    .dataframe {
        font-size: 0.9rem;
    }

    /* Loading spinner */
    .stSpinner > div {
        border-top-color: #2962ff !important;
    }
    </style>
""", unsafe_allow_html=True)

# =======================================================================================
# Data Loading & Caching (Multi-source support)
# =======================================================================================
@st.cache_data(ttl=3600)
def load_data_from_gdrive(gdrive_url):
    """Load single CSV file from Google Drive"""
    try:
        file_id = gdrive_url.split('/d/')[1].split('/')[0]
        download_url = f'https://drive.google.com/uc?export=download&id={file_id}'
        response = requests.get(download_url, timeout=15)
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
def load_combined_data_from_multiple_sources():
    """Load and combine data from multiple Google Drive files using parallel loading"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    gdrive_links = [
        "https://drive.google.com/file/d/1E0BDythcdIdGrIYdbJCNB0DxPHJ-njzc/view?usp=drive_link",  # Original
        "https://drive.google.com/file/d/1cb9Ef1IDyArlmguRZ5u63tCcxR57KEfA/view?usp=sharing",      # File 1
        "https://drive.google.com/file/d/1XPZKnRDklQ1DOdVgncn71SLg1pfisQtV/view?usp=sharing",      # File 2
        "https://drive.google.com/file/d/1op_GzDUtbcXOJOMkI2K-0AU9cF4m8J1S/view?usp=sharing"       # File 3
    ]

    all_dataframes = []
    successful_loads = 0
    load_status = []

    with st.spinner(f'⚡ Đang tải song song {len(gdrive_links)} nguồn dữ liệu...'):
        # Parallel loading with ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all tasks
            future_to_link = {
                executor.submit(load_data_from_gdrive, link): (i, link)
                for i, link in enumerate(gdrive_links, 1)
            }

            # Collect results as they complete
            for future in as_completed(future_to_link):
                i, link = future_to_link[future]
                try:
                    df = future.result()
                    if df is not None and not df.empty:
                        all_dataframes.append(df)
                        successful_loads += 1
                        load_status.append(f"✅ Nguồn {i}: {len(df)} dòng, {df['symbol'].nunique()} mã CP")
                    else:
                        load_status.append(f"⚠️ Nguồn {i}: Không có dữ liệu")
                except Exception as e:
                    load_status.append(f"❌ Nguồn {i}: Lỗi - {str(e)[:50]}")

    # Display load status (only errors and warnings, not success messages)
    for status in sorted(load_status):
        if "⚠️" in status:
            st.warning(status)
        elif "❌" in status:
            st.error(status)
        # Skip success messages (✅) to keep UI clean

    if not all_dataframes:
        st.error("❌ Không thể tải dữ liệu từ bất kỳ nguồn nào!")
        return None

    # Combine all dataframes
    combined_df = pd.concat(all_dataframes, ignore_index=True)

    # Remove duplicates (same symbol + date, keep latest)
    duplicates_before = len(combined_df)
    combined_df = combined_df.drop_duplicates(subset=['symbol', 'date'], keep='last')
    duplicates_removed = duplicates_before - len(combined_df)

    # Sort by symbol and date
    combined_df = combined_df.sort_values(by=['symbol', 'date']).reset_index(drop=True)

    st.info(f"📊 Tổng hợp: {len(combined_df):,} dòng từ {successful_loads}/{len(gdrive_links)} nguồn | "
            f"{combined_df['symbol'].nunique()} mã CP | Đã loại bỏ {duplicates_removed:,} bản ghi trùng")

    return combined_df

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
        # Base indicators - using manual calculation instead of pandas_ta
        group['SMA_20'] = calculate_sma(group, 20)
        group['SMA_50'] = calculate_sma(group, 50)
        group['SMA_100'] = calculate_sma(group, 100)
        group['SMA_200'] = calculate_sma(group, 200)
        group['RSI_14'] = calculate_rsi(group, 14)

        # MACD
        macd_data = calculate_macd(group, fast=12, slow=26, signal=9)
        group['MACD_12_26_9'] = macd_data['macd']
        group['MACDs_12_26_9'] = macd_data['signal']
        group['MACDh_12_26_9'] = macd_data['histogram']

        # Bollinger Bands
        bb_data = calculate_bollinger_bands(group, period=20, std=2)
        group['BBU_20_2.0'] = bb_data['upper']
        group['BBM_20_2.0'] = bb_data['middle']
        group['BBL_20_2.0'] = bb_data['lower']

        # Volume SMA
        group['VOL_SMA_20'] = group['volume'].rolling(window=20, min_periods=1).mean()

        # ADX calculation (real implementation)
        try:
            group['ADX_14'] = calculate_adx(group, period=14)
        except Exception as e:
            # Fallback to NaN if calculation fails
            group['ADX_14'] = np.nan
        
        raw_score = pd.Series(0, index=group.index)

        # --- BALANCED Scoring Logic (No Bias) ---
        # Price vs SMA200 (±3 points - long-term trend)
        if 'SMA_200' in group.columns:
            raw_score += np.where(group['close'] > group['SMA_200'], 3, -3)

        # Price vs SMA100 (±2 points - medium-term trend)
        if 'SMA_100' in group.columns:
            raw_score += np.where(group['close'] > group['SMA_100'], 2, -2)

        # SMA100 vs SMA200 alignment (±2 points - trend direction)
        if all(c in group.columns for c in ['SMA_100', 'SMA_200']):
            raw_score += np.where(group['SMA_100'] > group['SMA_200'], 2, -2)

        # Price vs SMA50 (±2 points - short-term trend)
        if 'SMA_50' in group.columns:
            raw_score += np.where(group['close'] > group['SMA_50'], 2, -2)

        # Price vs SMA20 (±1 point - immediate trend)
        if 'SMA_20' in group.columns:
            raw_score += np.where(group['close'] > group['SMA_20'], 1, -1)

        # SMA20 vs SMA50 alignment (±1 point)
        if all(c in group.columns for c in ['SMA_20', 'SMA_50']):
            raw_score += np.where(group['SMA_20'] > group['SMA_50'], 1, -1)

        # RSI (±2 points - momentum)
        if 'RSI_14' in group.columns:
            rsi_conditions = [group['RSI_14'] > 70, group['RSI_14'] > 50, group['RSI_14'] < 30, group['RSI_14'] < 50]
            rsi_scores = [2, 1, -2, -1]
            raw_score += np.select(rsi_conditions, rsi_scores, default=0)

        # MACD crossover (±2 points - trend change)
        if all(c in group.columns for c in ['MACD_12_26_9', 'MACDs_12_26_9']):
            macd_bullish = (group['MACD_12_26_9'] > group['MACDs_12_26_9']) & (group['MACD_12_26_9'].shift(1) <= group['MACDs_12_26_9'].shift(1))
            macd_bearish = (group['MACD_12_26_9'] < group['MACDs_12_26_9']) & (group['MACD_12_26_9'].shift(1) >= group['MACDs_12_26_9'].shift(1))
            raw_score += np.where(macd_bullish, 2, 0)
            raw_score += np.where(macd_bearish, -2, 0)

        # ADX (trend strength - NOT directional, so only penalize weak trends)
        if 'ADX_14' in group.columns:
            # ADX > 25 = strong trend (good), < 20 = weak trend (bad)
            # Don't add/subtract for direction, just measure trend strength
            adx_valid = ~group['ADX_14'].isna()
            adx_conditions = [
                adx_valid & (group['ADX_14'] > 40),  # Very strong trend
                adx_valid & (group['ADX_14'] > 25),  # Strong trend
                adx_valid & (group['ADX_14'] < 20)   # Weak/no trend
            ]
            adx_scores = [1, 0, -1]  # Neutral for strong trend, penalty for weak
            raw_score += np.select(adx_conditions, adx_scores, default=0)

        # Volume confirmation (±2 points)
        if 'VOL_SMA_20' in group.columns:
            strong_bullish_candle = (group['close'] > group['open']) & (group['volume'] > group['VOL_SMA_20'])
            strong_bearish_candle = (group['close'] < group['open']) & (group['volume'] > group['VOL_SMA_20'])
            raw_score += np.where(strong_bullish_candle, 2, 0)
            raw_score += np.where(strong_bearish_candle, -2, 0)

        # Bollinger Bands (±1 point - overbought/oversold)
        if all(c in group.columns for c in ['BBU_20_2.0', 'BBL_20_2.0']):
            raw_score += np.where(group['close'] > group['BBU_20_2.0'], 1, 0)  # Overbought
            raw_score += np.where(group['close'] < group['BBL_20_2.0'], -1, 0)  # Oversold
        
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

    # Scoring theo đúng logic từ hình (Tính tổng điểm)
    score_columns_to_create = {
        # % trên MA200: >70% (+2), 50-70% (+1), 30-50% (0), <30% (-2)
        'Score MA200': {
            'series': breadth_df['% > MA200'],
            'bins': [-np.inf, 0.30, 0.50, 0.70, np.inf],
            'labels': [-2, 0, 1, 2]
        },
        # % trên MA50: >80% (+2), 60-80% (+1), <60% (-1)
        'Score MA50': {
            'series': breadth_df['% > MA50'],
            'bins': [-np.inf, 0.60, 0.80, np.inf],
            'labels': [-1, 1, 2]
        },
        # U/D Ratio MA5: >1.75 (+2), 1.25-1.75 (+1), 0.75-1.25 (0), 0.5-0.75 (-1), <0.5 (-2)
        'Score UDV': {
            'series': breadth_df['U/D Ratio MA5'],
            'bins': [-np.inf, 0.5, 0.75, 1.25, 1.75, np.inf],
            'labels': [-2, -1, 0, 1, 2]
        },
        # % RSI > 50: >60% (+2), 40-60% (0), <40% (-2)
        'Score RSI': {
            'series': breadth_df['% RSI > 50'],
            'bins': [-np.inf, 0.40, 0.60, np.inf],
            'labels': [-2, 0, 2]
        },
        # MACD Crossover (3 ngày): >20% (+2), 10-20% (+1), <10% (0)
        'Score MACD': {
            'series': breadth_df['% MACD Crossover'].rolling(window=3).sum(),
            'bins': [-np.inf, 0.10, 0.20, np.inf],
            'labels': [0, 1, 2]
        },
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
    # ===== SIDEBAR =====
    st.sidebar.title("⚙️ Cài đặt")

    # Timeline (Khoảng thời gian hiển thị)
    st.sidebar.subheader("📅 Khoảng thời gian")

    timeline_option = st.sidebar.radio(
        "Timeline:",
        options=["3 tháng", "6 tháng", "1 năm", "YTD", "Tùy chỉnh"],
        index=1,  # Default: 6 tháng
        horizontal=True
    )

    # Calculate timeline dates
    from datetime import datetime, timedelta
    end_date = datetime.now()

    if timeline_option == "3 tháng":
        start_date = end_date - timedelta(days=90)
    elif timeline_option == "6 tháng":
        start_date = end_date - timedelta(days=180)
    elif timeline_option == "1 năm":
        start_date = end_date - timedelta(days=365)
    elif timeline_option == "YTD":
        start_date = datetime(end_date.year, 1, 1)
    else:  # Tùy chỉnh
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.sidebar.date_input(
                "Từ ngày",
                value=end_date - timedelta(days=180),
                max_value=datetime.now(),
                key='custom_start_trend'
            )
        with col2:
            end_date = st.sidebar.date_input(
                "Đến ngày",
                value=end_date,
                max_value=datetime.now(),
                key='custom_end_trend'
            )

    st.sidebar.markdown("---")

    # Page header
    st.markdown("<h1 class='main-title'>📊 XU HƯỚNG & BỀ RỘNG THỊ TRƯỜNG</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Phân tích toàn diện sức khỏe thị trường chứng khoán Việt Nam</p>", unsafe_allow_html=True)
    st.markdown("---")

    try:
        col1, col2, col3 = st.columns([2,3,2])
        with col2:
            st.image("header.gif")
    except FileNotFoundError:
        pass

    # Load combined data from all 4 sources
    master_df = load_combined_data_from_multiple_sources()
    if master_df is not None:
        with st.spinner('Đang tính toán toàn bộ chỉ báo và điểm sức khỏe nâng cao...'):
            df_with_indicators = calculate_all_indicators_advanced(master_df.copy())

        # ===== BỀ RỘNG THỊ TRƯỜNG - ĐẦU TRANG =====
        st.header("📈 Lịch sử Bề rộng Thị trường")
        breadth_history_df = calculate_market_breadth_history(df_with_indicators)
        breadth_start_date = breadth_history_df.index.min()
        breadth_end_date = breadth_history_df.index.max()
        vnindex_df = get_vnindex_data_robust(breadth_start_date, breadth_end_date)

        for col in ['% > MA50', '% > MA200', '% RSI > 50', '% MACD Crossover']:
             breadth_history_df[col] = breadth_history_df[col].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A")
        display_cols = ['A-D Line', 'TRIN', 'U/D Ratio MA5', '% > MA200', '% > MA50', '% RSI > 50', '% MACD Crossover', 'Tổng Điểm', 'Trạng thái']
        breadth_history_df['TRIN'] = breadth_history_df['TRIN'].map('{:,.2f}'.format)
        breadth_history_df['U/D Ratio MA5'] = breadth_history_df['U/D Ratio MA5'].map('{:,.2f}'.format)
        breadth_history_df['Tổng Điểm'] = breadth_history_df['Tổng Điểm'].map('{:,.0f}'.format)

        # Style dataframe with color coding for Trạng thái
        def style_status(val):
            if val == 'Tăng Mạnh':
                return 'background-color: #4CAF50; color: white; font-weight: bold;'
            elif val == 'Tăng Thận Trọng':
                return 'background-color: #C8E6C9; color: #1B5E20;'
            elif val == 'Trung Lập':
                return 'background-color: #FFF9C4; color: #F57F17;'
            elif val == 'Giảm Thận Trọng':
                return 'background-color: #FFCDD2; color: #B71C1C;'
            elif val == 'Giảm Mạnh':
                return 'background-color: #F44336; color: white; font-weight: bold;'
            return ''

        styled_df = breadth_history_df[display_cols].style.applymap(
            style_status,
            subset=['Trạng thái']
        )
        st.dataframe(styled_df, use_container_width=True, height=400)

        st.subheader("📊 Biểu đồ A-D Line & VN-Index")

        # Create Plotly chart with VN-Index as candlestick
        if vnindex_df is not None:
            breadth_history_df_reset = breadth_history_df.reset_index().rename(columns={'Date': 'date'})

            # Prepare VN-Index data
            vnindex_df_reset = vnindex_df.reset_index()
            vnindex_df_reset['date'] = pd.to_datetime(vnindex_df_reset['Date']).dt.normalize()

            # Merge with breadth data
            chart_df = pd.merge(breadth_history_df_reset, vnindex_df_reset, on='date', how='inner')

            if not chart_df.empty and all(col in chart_df.columns for col in ['Open', 'High', 'Low', 'Close']):
                # Create figure with secondary y-axis
                fig = make_subplots(specs=[[{"secondary_y": True}]])

                # Add A-D Line (primary y-axis)
                fig.add_trace(
                    go.Scatter(
                        x=chart_df['date'],
                        y=chart_df['A-D Line'],
                        name='A-D Line',
                        line=dict(color='#2962ff', width=2),
                        mode='lines'
                    ),
                    secondary_y=False
                )

                # Add VN-Index as candlestick (secondary y-axis)
                fig.add_trace(
                    go.Candlestick(
                        x=chart_df['date'],
                        open=chart_df['Open'],
                        high=chart_df['High'],
                        low=chart_df['Low'],
                        close=chart_df['Close'],
                        name='VN-Index',
                        increasing_line_color='#26a69a',
                        decreasing_line_color='#ef5350',
                        increasing_fillcolor='#26a69a',
                        decreasing_fillcolor='#ef5350',
                        showlegend=True
                    ),
                    secondary_y=True
                )

                # Update layout
                fig.update_layout(
                    height=500,
                    hovermode='x unified',
                    paper_bgcolor='#ffffff',
                    plot_bgcolor='#ffffff',
                    font=dict(family='Arial, sans-serif', size=12, color='#131722'),
                    legend=dict(
                        orientation='h',
                        yanchor='top',
                        y=1.1,
                        xanchor='left',
                        x=0
                    ),
                    margin=dict(l=50, r=50, t=30, b=30),
                    xaxis_rangeslider_visible=False
                )

                # Update axes
                fig.update_xaxes(
                    title_text="Ngày",
                    gridcolor='#e1e3e6',
                    showgrid=True,
                    linecolor='#e1e3e6'
                )
                fig.update_yaxes(
                    title_text="A-D Line (Tích lũy)",
                    gridcolor='#e1e3e6',
                    showgrid=True,
                    linecolor='#e1e3e6',
                    secondary_y=False
                )
                fig.update_yaxes(
                    title_text="VN-Index",
                    gridcolor='#e1e3e6',
                    showgrid=False,
                    linecolor='#e1e3e6',
                    secondary_y=True
                )

                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Không có dữ liệu OHLC cho VN-Index. Hiển thị A-D Line riêng lẻ.")
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=breadth_history_df.index,
                    y=breadth_history_df['A-D Line'],
                    name='A-D Line',
                    line=dict(color='#2962ff', width=2)
                ))
                fig.update_layout(height=400, hovermode='x unified')
                st.plotly_chart(fig, use_container_width=True)
        else:
            # VN-Index not available, show only A-D Line
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=breadth_history_df.index,
                y=breadth_history_df['A-D Line'],
                name='A-D Line',
                line=dict(color='#2962ff', width=2)
            ))
            fig.update_layout(
                height=400,
                hovermode='x unified',
                paper_bgcolor='#ffffff',
                plot_bgcolor='#ffffff',
                xaxis=dict(title='Ngày', gridcolor='#e1e3e6'),
                yaxis=dict(title='A-D Line', gridcolor='#e1e3e6')
            )
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # ===== PHÂN TÍCH CHI TIẾT NGÀY GẦN NHẤT =====
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
        # Sort by Đánh giá (Rất Tích cực first)
        trend_order = {"Rất Tích cực": 0, "Tích cực": 1, "Trung lập": 2, "Tiêu cực": 3, "Rất Tiêu cực": 4}
        latest_signals_df['sort_order'] = latest_signals_df['Đánh giá'].map(trend_order)
        latest_signals_df = latest_signals_df.sort_values('sort_order').drop('sort_order', axis=1)

        st.dataframe(latest_signals_df.style.applymap(style_trend, subset=['Đánh giá']), use_container_width=True)

        # Add charts for "Rất Tích cực" stocks
        very_positive_stocks = latest_signals_df[latest_signals_df['Đánh giá'] == 'Rất Tích cực']['Mã CP'].tolist()

        if very_positive_stocks:
            st.subheader(f"📊 Biểu đồ các cổ phiếu Rất Tích cực ({len(very_positive_stocks)} mã)")

            # Display charts in rows of 3
            for i in range(0, len(very_positive_stocks), 3):
                cols = st.columns(3)
                batch_stocks = very_positive_stocks[i:i+3]

                for idx, symbol in enumerate(batch_stocks):
                    with cols[idx]:
                        stock_data = df_with_indicators[df_with_indicators['symbol'] == symbol].copy()

                        if not stock_data.empty:
                            # Rename 'date' to 'time' for compatibility with multi-chart function
                            stock_data = stock_data.rename(columns={'date': 'time'})

                            # Filter data by timeline
                            mask = (stock_data['time'] >= pd.Timestamp(start_date)) & (stock_data['time'] <= pd.Timestamp(end_date))
                            stock_data_filtered = stock_data[mask].copy()

                            if not stock_data_filtered.empty:
                                # Create simple figure with secondary y-axis for volume
                                from plotly.subplots import make_subplots
                                fig = make_subplots(specs=[[{"secondary_y": True}]])

                                # Candlestick
                                fig.add_trace(go.Candlestick(
                                    x=stock_data_filtered['time'],
                                    open=stock_data_filtered['open'],
                                    high=stock_data_filtered['high'],
                                    low=stock_data_filtered['low'],
                                    close=stock_data_filtered['close'],
                                    name=symbol,
                                    increasing_line_color='#26a69a',
                                    decreasing_line_color='#ef5350',
                                    increasing_fillcolor='#26a69a',
                                    decreasing_fillcolor='#ef5350'
                                ), secondary_y=False)

                                # Add SMA20 and SMA50
                                if 'SMA_20' in stock_data.columns:
                                    ma20_filtered = stock_data.loc[mask, 'SMA_20'].reset_index(drop=True)
                                    time_filtered = stock_data_filtered['time'].reset_index(drop=True)
                                    valid_mask = ma20_filtered.notna()

                                    fig.add_trace(go.Scatter(
                                        x=time_filtered[valid_mask],
                                        y=ma20_filtered[valid_mask],
                                        name='MA20',
                                        line=dict(color='#2962ff', width=1.5),
                                        mode='lines',
                                        showlegend=False,
                                        connectgaps=False
                                    ), secondary_y=False)

                                if 'SMA_50' in stock_data.columns:
                                    ma50_filtered = stock_data.loc[mask, 'SMA_50'].reset_index(drop=True)
                                    time_filtered = stock_data_filtered['time'].reset_index(drop=True)
                                    valid_mask = ma50_filtered.notna()

                                    fig.add_trace(go.Scatter(
                                        x=time_filtered[valid_mask],
                                        y=ma50_filtered[valid_mask],
                                        name='MA50',
                                        line=dict(color='#ff6d00', width=1.5),
                                        mode='lines',
                                        showlegend=False,
                                        connectgaps=False
                                    ), secondary_y=False)

                                # Volume (secondary y-axis)
                                colors = ['#26a69a' if c >= o else '#ef5350'
                                          for c, o in zip(stock_data_filtered['close'], stock_data_filtered['open'])]
                                fig.add_trace(go.Bar(
                                    x=stock_data_filtered['time'],
                                    y=stock_data_filtered['volume'],
                                    name='Volume',
                                    marker_color=colors,
                                    showlegend=False,
                                    opacity=0.2
                                ), secondary_y=True)

                                # Update layout
                                fig.update_layout(
                                    title=f"{symbol}",
                                    height=300,
                                    hovermode='x unified',
                                    paper_bgcolor='#ffffff',
                                    plot_bgcolor='#ffffff',
                                    font=dict(family='Arial, sans-serif', size=10, color='#131722'),
                                    showlegend=False,
                                    margin=dict(l=40, r=20, t=40, b=30),
                                    xaxis_rangeslider_visible=False
                                )

                                # Update axes
                                fig.update_xaxes(
                                    gridcolor='#e1e3e6',
                                    showgrid=False,
                                    linecolor='#e1e3e6'
                                )
                                fig.update_yaxes(
                                    title_text="Giá (VNĐ)",
                                    gridcolor='#e1e3e6',
                                    showgrid=True,
                                    linecolor='#e1e3e6',
                                    secondary_y=False
                                )

                                # Secondary Y-axis (Volume) - ẩn, range để volume chiếm ~10%
                                max_volume = stock_data_filtered['volume'].max()
                                fig.update_yaxes(
                                    showgrid=False,
                                    showticklabels=False,
                                    range=[0, max_volume * 10],
                                    secondary_y=True
                                )

                                st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.header("🔬 Phân tích Chi tiết Từng Cổ phiếu (Hệ thống điểm Nâng cao)")
        all_symbols = sorted(df_with_indicators['symbol'].unique())
        selected_stock = st.selectbox("Chọn một mã cổ phiếu để phân tích:", all_symbols)
        if selected_stock:
            stock_history = df_with_indicators[df_with_indicators['symbol'] == selected_stock].copy()
            if not stock_history.empty and 'Trend Score' in stock_history.columns:
                st.subheader(f"📈 Biểu đồ Giá và Điểm Sức khỏe Xu hướng - {selected_stock}")
                chart_data = stock_history[['date', 'close', 'Trend Score']].copy()
                chart_data.dropna(inplace=True)

                if not chart_data.empty:
                    # Create figure with secondary y-axis
                    fig = make_subplots(specs=[[{"secondary_y": True}]])

                    # Add Price line (primary y-axis)
                    fig.add_trace(
                        go.Scatter(
                            x=chart_data['date'],
                            y=chart_data['close'],
                            name='Giá Đóng Cửa',
                            line=dict(color='#2962ff', width=2),
                            mode='lines',
                            fill='tonexty',
                            fillcolor='rgba(41, 98, 255, 0.1)'
                        ),
                        secondary_y=False
                    )

                    # Add Trend Score line (secondary y-axis)
                    fig.add_trace(
                        go.Scatter(
                            x=chart_data['date'],
                            y=chart_data['Trend Score'],
                            name='Điểm Sức khỏe',
                            line=dict(color='#ff6d00', width=2, dash='dot'),
                            mode='lines'
                        ),
                        secondary_y=True
                    )

                    # Add zero line for Trend Score
                    fig.add_hline(
                        y=0,
                        line_dash="dash",
                        line_color="#787b86",
                        opacity=0.5,
                        secondary_y=True
                    )

                    # Update layout
                    fig.update_layout(
                        height=500,
                        hovermode='x unified',
                        paper_bgcolor='#ffffff',
                        plot_bgcolor='#ffffff',
                        font=dict(family='Arial, sans-serif', size=12, color='#131722'),
                        legend=dict(
                            orientation='h',
                            yanchor='top',
                            y=1.1,
                            xanchor='left',
                            x=0
                        ),
                        margin=dict(l=50, r=50, t=30, b=30)
                    )

                    # Update axes
                    fig.update_xaxes(
                        title_text="Ngày",
                        gridcolor='#e1e3e6',
                        showgrid=True,
                        linecolor='#e1e3e6'
                    )
                    fig.update_yaxes(
                        title_text="Giá (VNĐ)",
                        gridcolor='#e1e3e6',
                        showgrid=True,
                        linecolor='#e1e3e6',
                        secondary_y=False
                    )
                    fig.update_yaxes(
                        title_text="Điểm Sức khỏe Xu hướng",
                        gridcolor='#e1e3e6',
                        showgrid=False,
                        linecolor='#e1e3e6',
                        secondary_y=True
                    )

                    st.plotly_chart(fig, use_container_width=True)

                    # Show latest metrics
                    latest_row = chart_data.iloc[-1]
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Giá Hiện Tại", f"{latest_row['close']:,.0f} VNĐ")
                    with col2:
                        trend_score = latest_row['Trend Score']
                        trend_color = "🟢" if trend_score > 0 else "🔴"
                        st.metric("Điểm Sức khỏe", f"{trend_score:.2f} {trend_color}")
                    with col3:
                        # Calculate price change
                        if len(chart_data) > 1:
                            price_change_pct = ((latest_row['close'] - chart_data.iloc[0]['close']) / chart_data.iloc[0]['close']) * 100
                            st.metric("Thay Đổi", f"{price_change_pct:+.2f}%")
                else:
                    st.warning(f"Không có đủ dữ liệu sau khi xử lý để vẽ biểu đồ cho {selected_stock}.")
            else:
                st.warning(f"Không có đủ dữ liệu lịch sử để vẽ biểu đồ cho {selected_stock}.")
    else:
        st.error("Không thể tải hoặc xử lý dữ liệu. Vui lòng kiểm tra lại file Google Drive.")

if __name__ == "__main__":
    main()