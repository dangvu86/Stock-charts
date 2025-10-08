import streamlit as st
import pandas as pd
import pandas_ta as ta
import numpy as np
import requests
import io
from io import StringIO
import warnings
from scipy.stats import linregress

# Suppress specific pandas warnings
warnings.filterwarnings(
    "ignore",
    message="The behavior of DatetimeProperties.to_pydatetime is deprecated",
)

# =======================================================================================
# Configuration and Styling
# =======================================================================================
st.set_page_config(
    page_title="Hệ thống Phân tích Xu hướng & Bề rộng Thị trường",
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
    </style>
""", unsafe_allow_html=True)

# =======================================================================================
# Data Loading & Caching
# =======================================================================================
@st.cache_data(ttl=3600)
def load_data_from_gdrive(gdrive_url):
    try:
        file_id = gdrive_url.split('/d/')[1].split('/')[0]
        download_url = f'https://drive.google.com/uc?export=download&id={file_id}'
        response = requests.get(download_url)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.content.decode('utf-8')))
        df['date'] = pd.to_datetime(df['date'])
        df.columns = [col.lower().strip() for col in df.columns]
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df.dropna(inplace=True)
        df.sort_values(by=['symbol', 'date'], inplace=True)
        return df
    except Exception as e:
        st.error(f"Lỗi khi tải dữ liệu: {e}")
        return None

# =======================================================================================
# Indicator Calculation Functions
# =======================================================================================
@st.cache_data
def calculate_all_indicators(df):
    def apply_indicators(group):
        group.ta.sma(length=20, append=True)
        group.ta.sma(length=50, append=True)
        group.ta.sma(length=100, append=True)
        group.ta.sma(length=200, append=True)
        group.ta.rsi(length=14, append=True)
        group.ta.macd(fast=12, slow=26, signal=9, append=True)
        group.ta.adx(length=14, append=True)
        group.ta.bbands(length=20, append=True)
        group.ta.sma(close=group['volume'], length=20, prefix="VOL", append=True)
        group['MACD_Bull'] = group['MACD_12_26_9'] > group['MACDs_12_26_9']
        group['MACD_Crossover'] = group['MACD_Bull'].diff()
        return group

    df_with_indicators = df.groupby('symbol', group_keys=False).apply(apply_indicators)
    
    df_with_indicators['prev_close'] = df_with_indicators.groupby('symbol')['close'].shift(1)
    df_with_indicators['prev_high'] = df_with_indicators.groupby('symbol')['high'].shift(1)
    df_with_indicators['prev_low'] = df_with_indicators.groupby('symbol')['low'].shift(1)
    df_with_indicators['PIVOT'] = (df_with_indicators['prev_high'] + df_with_indicators['prev_low'] + df_with_indicators['prev_close']) / 3
    df_with_indicators['R1'] = (2 * df_with_indicators['PIVOT']) - df_with_indicators['prev_low']
    df_with_indicators['S1'] = (2 * df_with_indicators['PIVOT']) - df_with_indicators['prev_high']
    
    return df_with_indicators

def generate_latest_day_signals(df_with_indicators):
    latest_signals = []
    latest_date = df_with_indicators['date'].max()
    symbols_on_latest_day = df_with_indicators[df_with_indicators['date'] == latest_date]['symbol'].unique()
    for symbol in symbols_on_latest_day:
        full_history = df_with_indicators[df_with_indicators['symbol'] == symbol]
        if len(full_history) < 2: continue
        latest = full_history.iloc[-1]
        previous = full_history.iloc[-2]
        if pd.Timestamp(latest['date']) != latest_date: continue
        score = 0
        max_score = 17
        if 'SMA_20' in latest and pd.notna(latest['SMA_20']) and latest['close'] > latest['SMA_20']: score += 1
        if 'SMA_50' in latest and pd.notna(latest['SMA_50']) and latest['close'] > latest['SMA_50']: score += 1
        if 'SMA_100' in latest and pd.notna(latest['SMA_100']) and latest['close'] > latest['SMA_100']: score += 1
        if all(k in latest for k in ['SMA_20', 'SMA_50']) and pd.notna(latest['SMA_20']) and pd.notna(latest['SMA_50']) and latest['SMA_20'] > latest['SMA_50']: score += 1
        if all(k in latest for k in ['SMA_50', 'SMA_100']) and pd.notna(latest['SMA_50']) and pd.notna(latest['SMA_100']) and latest['SMA_50'] > latest['SMA_100']: score += 1
        if 'RSI_14' in latest and pd.notna(latest['RSI_14']) and latest['RSI_14'] > 50: score += 1
        if 'RSI_14' in previous and pd.notna(previous['RSI_14']) and 'RSI_14' in latest and pd.notna(latest['RSI_14']) and latest['RSI_14'] > 50 and previous['RSI_14'] <= 50: score += 1
        if all(k in latest for k in ['MACD_12_26_9', 'MACDs_12_26_9']) and pd.notna(latest['MACD_12_26_9']) and pd.notna(latest['MACDs_12_26_9']) and latest['MACD_12_26_9'] > latest['MACDs_12_26_9']: score += 1
        if all(k in previous for k in ['MACD_12_26_9', 'MACDs_12_26_9']) and all(k in latest for k in ['MACD_12_26_9', 'MACDs_12_26_9']) and latest['MACD_12_26_9'] > latest['MACDs_12_26_9'] and previous['MACD_12_26_9'] <= previous['MACDs_12_26_9']: score += 1
        if 'ADX_14' in latest and pd.notna(latest['ADX_14']) and latest['ADX_14'] > 25: score += 1
        if all(k in latest for k in ['DMP_14', 'DMN_14']) and pd.notna(latest['DMP_14']) and pd.notna(latest['DMN_14']) and latest['DMP_14'] > latest['DMN_14']: score += 1
        if 'BBM_20_2.0' in latest and pd.notna(latest['BBM_20_2.0']) and latest['close'] > latest['BBM_20_2.0']: score += 1
        if 'BBU_20_2.0' in latest and pd.notna(latest['BBU_20_2.0']) and latest['close'] > latest['BBU_20_2.0']: score += 1
        if 'VOL_SMA_20' in latest and pd.notna(latest['VOL_SMA_20']) and latest['volume'] > latest['VOL_SMA_20']: score += 1
        if 'VOL_SMA_20' in latest and pd.notna(latest['VOL_SMA_20']) and latest['close'] > latest['open'] and latest['volume'] > latest['VOL_SMA_20']: score += 1
        if 'PIVOT' in latest and pd.notna(latest['PIVOT']) and latest['close'] > latest['PIVOT']: score += 1
        if 'R1' in latest and pd.notna(latest['R1']) and latest['close'] > latest['R1']: score += 1
        if score >= 11: trend = "Rất Tích cực"
        elif score >= 8: trend = "Tích cực"
        elif score <= 4: trend = "Rất Tiêu cực"
        elif score <= 7: trend = "Tiêu cực"
        else: trend = "Trung lập"
        latest_signals.append({
            "Mã CP": latest['symbol'], "Giá đóng cửa": f"{latest['close'] / 1000:.2f}",
            "Điểm xu hướng": f"{score}/{max_score}", "Đánh giá": trend,
            "ADX (14)": f"{latest.get('ADX_14', 0):.1f}", "Volume": "Cao" if 'VOL_SMA_20' in latest and pd.notna(latest['VOL_SMA_20']) and latest['volume'] > latest['VOL_SMA_20'] else "Thấp"
        })
    return pd.DataFrame(latest_signals)

@st.cache_data
def calculate_market_breadth_history(df_with_indicators):
    breadth_data = []
    for date, daily_df in df_with_indicators.groupby('date'):
        if daily_df.empty: continue
        total_stocks = len(daily_df)
        advances = daily_df[daily_df['close'] > daily_df['prev_close']].shape[0]
        declines = daily_df[daily_df['close'] < daily_df['prev_close']].shape[0]
        up_volume = daily_df[daily_df['close'] > daily_df['prev_close']]['volume'].sum()
        down_volume = daily_df[daily_df['close'] < daily_df['prev_close']]['volume'].sum()
        
        # Calculate TRIN
        ad_ratio = advances / declines if declines > 0 else (advances / 1)
        ud_vol_ratio = up_volume / down_volume if down_volume > 0 else (up_volume / 1)
        trin = ad_ratio / ud_vol_ratio if ud_vol_ratio > 0 else 0
        
        breadth_data.append({
            'Date': date, 'A-D Net': advances - declines,
            'Up Vol': up_volume, 'Down Vol': down_volume, 'TRIN': trin,
            '% > MA50': (daily_df['close'] > daily_df['SMA_50']).sum() / total_stocks,
            '% > MA200': (daily_df['close'] > daily_df['SMA_200']).sum() / total_stocks,
            '% RSI > 50': (daily_df['RSI_14'] > 50).sum() / total_stocks,
            '% MACD Crossover': (daily_df['MACD_Crossover'] == True).sum() / total_stocks
        })
    
    breadth_df = pd.DataFrame(breadth_data).set_index('Date').sort_index()

    breadth_df['A-D Line'] = breadth_df['A-D Net'].cumsum()
    breadth_df['U/D Ratio'] = breadth_df['Up Vol'] / breadth_df['Down Vol'].replace(0, 1)
    breadth_df['U/D Ratio MA5'] = breadth_df['U/D Ratio'].rolling(window=5).mean()
    
    def get_trend_score(series):
        y = series.dropna()
        if len(y) < 5: return np.nan
        x = np.arange(len(y))
        slope, _, _, _, _ = linregress(x, y)
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
    st.markdown("<h1 class='main-title'>📜 Hệ thống Phân tích Xu hướng & Bề rộng Thị trường</h1>", unsafe_allow_html=True)
    st.sidebar.header("Cài đặt")
    gdrive_link = st.sidebar.text_input("🔗 Link Google Drive (file CSV):", "https://drive.google.com/file/d/1E0BDythcdIdGrIYdbJCNB0DxPHJ-njzc/view?usp=drive_link")
    
    if st.sidebar.button("Bắt đầu Phân tích"):
        master_df = load_data_from_gdrive(gdrive_link)
        if master_df is not None:
            with st.spinner('Đang tính toán toàn bộ chỉ báo...'):
                df_with_indicators = calculate_all_indicators(master_df.copy())
            
            st.header(f"📊 Phân tích Chi tiết Ngày Gần Nhất ({df_with_indicators['date'].max().strftime('%Y-%m-%d')})")
            with st.spinner('Đang tạo tín hiệu ngày gần nhất...'):
                latest_signals_df = generate_latest_day_signals(df_with_indicators)
            
            trend_counts = latest_signals_df['Đánh giá'].value_counts()
            pos_count = trend_counts.get("Rất Tích cực", 0) + trend_counts.get("Tích cực", 0)
            neg_count = trend_counts.get("Rất Tiêu cực", 0) + trend_counts.get("Tiêu cực", 0)
            total_stocks = len(latest_signals_df)
            pos_pct = (pos_count / total_stocks) * 100 if total_stocks > 0 else 0
            neg_pct = (neg_count / total_stocks) * 100 if total_stocks > 0 else 0
            col1, col2 = st.columns(2)
            with col1: st.markdown(f'<div class="stMetric bullish"><h4>Tổng Tích cực</h4><h1>{pos_pct:.1f}%</h1><p>({pos_count}/{total_stocks} cp)</p></div>', unsafe_allow_html=True)
            with col2: st.markdown(f'<div class="stMetric bearish"><h4>Tổng Tiêu cực</h4><h1>{neg_pct:.1f}%</h1><p>({neg_count}/{total_stocks} cp)</p></div>', unsafe_allow_html=True)
            def style_trend(val):
                if "Rất Tích cực" in val: return 'background-color: #4CAF50; color: white; font-weight: bold;'
                if "Tích cực" in val: return 'background-color: #C8E6C9; color: black;'
                if "Rất Tiêu cực" in val: return 'background-color: #F44336; color: white; font-weight: bold;'
                if "Tiêu cực" in val: return 'background-color: #FFCDD2; color: black;'
                return ''
            st.dataframe(latest_signals_df.style.applymap(style_trend, subset=['Đánh giá']), use_container_width=True)
            
            st.divider()

            st.header("📈 Lịch sử Bề rộng Thị trường")
            with st.spinner('Đang tổng hợp dữ liệu bề rộng...'):
                breadth_history_df = calculate_market_breadth_history(df_with_indicators)
            
            days_to_show = st.slider('Số ngày hiển thị:', min_value=10, max_value=len(breadth_history_df), value=min(60, len(breadth_history_df)), key="days_slider")
            
            for col in ['% > MA50', '% > MA200', '% RSI > 50', '% MACD Crossover']:
                 breadth_history_df[col] = breadth_history_df[col].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A")
            
            # --- FIX: Added TRIN to the display columns ---
            display_cols = ['A-D Line', 'TRIN', 'U/D Ratio MA5', '% > MA200', '% > MA50', '% RSI > 50', '% MACD Crossover', 'Tổng Điểm', 'Trạng thái']
            
            # Format some columns for better display
            breadth_history_df['TRIN'] = breadth_history_df['TRIN'].map('{:,.2f}'.format)
            breadth_history_df['U/D Ratio MA5'] = breadth_history_df['U/D Ratio MA5'].map('{:,.2f}'.format)
            breadth_history_df['Tổng Điểm'] = breadth_history_df['Tổng Điểm'].map('{:,.0f}'.format)

            st.dataframe(breadth_history_df[display_cols].head(days_to_show), use_container_width=True)
            
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                st.subheader("Biểu đồ A-D Line")
                st.line_chart(breadth_history_df[['A-D Line']].head(days_to_show).sort_index())
            with col_chart2:
                st.subheader("Biểu đồ Tổng Điểm Sức Khỏe")
                st.bar_chart(breadth_history_df[['Tổng Điểm']].head(days_to_show).sort_index())

if __name__ == "__main__":
    main()