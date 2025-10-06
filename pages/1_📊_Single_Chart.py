"""
Single Chart View - Xem chi tiết 1 cổ phiếu (Optimized)
"""
import streamlit as st
from datetime import datetime, timedelta
import sys
import os
import pandas as pd

# Add modules to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from data.data_fetcher import get_stock_data, get_available_symbols, format_price, calculate_change
from utils.cache_manager import get_cache_stats
from indicators.technical import (
    add_rsi_subplot, add_macd_subplot, add_bollinger_bands,
    calculate_sma, calculate_ema
)
from utils.light_theme import (
    LIGHT_THEME, get_light_layout, get_light_axis_config, get_light_candlestick_config
)
from plotly.subplots import make_subplots
import plotly.graph_objects as go

# Page config
st.set_page_config(
    page_title="Single Chart View",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS - Light theme
st.markdown("""
    <style>
    .main {
        background-color: #f5f5f5;
    }
    .stSelectbox label {
        font-size: 12px;
        font-weight: bold;
        color: #131722;
    }
    /* Loading spinner */
    .stSpinner > div {
        border-top-color: #2962ff !important;
    }
    </style>
""", unsafe_allow_html=True)

# ===== SIDEBAR =====
st.sidebar.title("⚙️ Cài đặt")

# 1. Stock symbol
symbols = get_available_symbols()
symbol = st.sidebar.selectbox(
    "📊 Chọn mã cổ phiếu",
    options=symbols,
    index=symbols.index('HPG') if 'HPG' in symbols else 0
)

# 2. Timeline (Khoảng thời gian hiển thị)
st.sidebar.subheader("📅 Khoảng thời gian")
timeline_option = st.sidebar.radio(
    "Timeline:",
    options=["3 tháng", "6 tháng", "1 năm", "YTD", "Tùy chỉnh"],
    index=2,  # Mặc định 1 năm
    horizontal=True
)

# Tính toán display_start và display_end dựa trên timeline
display_end_default = datetime.now()
if timeline_option == "3 tháng":
    display_start_default = display_end_default - timedelta(days=90)
elif timeline_option == "6 tháng":
    display_start_default = display_end_default - timedelta(days=180)
elif timeline_option == "1 năm":
    display_start_default = display_end_default - timedelta(days=365)
elif timeline_option == "YTD":
    display_start_default = datetime(display_end_default.year, 1, 1)
elif timeline_option == "Tùy chỉnh":
    display_start_default = display_end_default - timedelta(days=365)

# Nếu chọn "Tùy chỉnh", hiển thị date picker
if timeline_option == "Tùy chỉnh":
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input(
            "Từ ngày",
            value=display_start_default,
            max_value=datetime.now(),
            key='custom_start_single'
        )
    with col2:
        end_date = st.date_input(
            "Đến ngày",
            value=display_end_default,
            max_value=datetime.now(),
            key='custom_end_single'
        )
else:
    start_date = display_start_default
    end_date = display_end_default

# 3. Timeframe
st.sidebar.subheader("📊 Khung thời gian")
timeframe = st.sidebar.radio(
    "Interval:",
    options=['1D', '1W', '1M'],
    format_func=lambda x: {'1D': 'Ngày', '1W': 'Tuần', '1M': 'Tháng'}[x],
    index=0,
    horizontal=True
)

st.sidebar.markdown("---")

# 4. Indicators
st.sidebar.subheader("📈 Chỉ báo kỹ thuật")

# Moving Averages
show_ma = st.sidebar.checkbox("Moving Average (MA)", value=True)
if show_ma:
    ma_type = st.sidebar.radio("Loại MA:", ["SMA", "EMA"], horizontal=True)
    ma_periods = st.sidebar.multiselect(
        "Chu kỳ:",
        options=[5, 10, 20, 50, 100, 200],
        default=[20, 50]
    )

# Bollinger Bands
show_bb = st.sidebar.checkbox("Bollinger Bands", value=False)
if show_bb:
    bb_period = st.sidebar.slider("BB Period", 10, 50, 20)
    bb_std = st.sidebar.slider("BB Std Dev", 1, 3, 2)

# RSI
show_rsi = st.sidebar.checkbox("RSI", value=True)
if show_rsi:
    rsi_period = st.sidebar.slider("RSI Period", 5, 30, 14)

# MACD
show_macd = st.sidebar.checkbox("MACD", value=True)

# Volume
show_volume = st.sidebar.checkbox("Volume", value=True)

st.sidebar.markdown("---")
st.sidebar.info("💡 Sử dụng chuột để zoom/pan trên biểu đồ")

# Cache stats
cache_stats = get_cache_stats()
st.sidebar.markdown(f"**Cache:** {cache_stats['valid']}/{cache_stats['total']} hits")

# ===== MAIN CONTENT =====
st.markdown("<h1 style='text-align: center; color: #131722;'>📊 VN STOCK CHART - SINGLE VIEW</h1>", unsafe_allow_html=True)

# Fetch data (with cache) - Load 3 years for accurate indicators
data_start = datetime.now() - timedelta(days=1095)  # 3 years
data_end = datetime.now()

with st.spinner(f"⚡ Đang tải dữ liệu {symbol}... (Cached indicators)"):
    df_full, indicators_cache = get_stock_data(
        symbol=symbol,
        start_date=data_start.strftime('%Y-%m-%d'),
        end_date=data_end.strftime('%Y-%m-%d'),
        resolution=timeframe,
        return_indicators=True  # Get pre-calculated indicators
    )

# Filter data for display based on sidebar date range
if df_full is not None and not df_full.empty:
    mask = (df_full['time'] >= pd.to_datetime(start_date)) & (df_full['time'] <= pd.to_datetime(end_date))
    df = df_full[mask].copy()
else:
    df = df_full

if df is not None and not df.empty:
    # Keep a copy of df_full for indicator filtering (like in Multi Chart)
    df_original = df_full.copy()

    # Display metrics - 52 week high/low/volume
    latest = df.iloc[-1]
    previous = df.iloc[-2] if len(df) > 1 else df.iloc[-1]
    current_price = latest['close']

    # Calculate 52-week metrics (364 days) - ALWAYS use df_full, not filtered df
    date_52w_ago = df_full['time'].max() - timedelta(days=364)
    df_52w = df_full[df_full['time'] >= date_52w_ago]

    if not df_52w.empty:
        highest_52w = df_52w['high'].max()
        lowest_52w = df_52w['low'].min()
        highest_vol_52w = df_52w['volume'].max()

        # Calculate % difference from current price
        diff_from_high = ((current_price - highest_52w) / highest_52w) * 100
        diff_from_low = ((current_price - lowest_52w) / lowest_52w) * 100
    else:
        highest_52w = latest['high']
        lowest_52w = latest['low']
        highest_vol_52w = latest['volume']
        diff_from_high = 0
        diff_from_low = 0

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="💰 Giá hiện tại",
            value=format_price(current_price),
            delta=f"{calculate_change(current_price, previous['close']):.2f}%"
        )

    with col2:
        st.metric(
            label="📈 Highest 52W",
            value=format_price(highest_52w),
            delta=f"{diff_from_high:.2f}%" if diff_from_high != 0 else None
        )

    with col3:
        st.metric(
            label="📉 Lowest 52W",
            value=format_price(lowest_52w),
            delta=f"{diff_from_low:.2f}%" if diff_from_low != 0 else None
        )

    with col4:
        st.metric(
            label="📊 Max Volume 52W",
            value=f"{highest_vol_52w:,.0f}"
        )

    st.markdown("---")

    # Determine number of subplots
    num_subplots = 1
    if show_volume:
        num_subplots += 1
    if show_rsi:
        num_subplots += 1
    if show_macd:
        num_subplots += 1

    # Create subplot heights
    heights = [0.5]  # Candlestick chart
    if show_volume:
        heights.append(0.2)
    if show_rsi:
        heights.append(0.15)
    if show_macd:
        heights.append(0.15)

    # Normalize heights
    total = sum(heights)
    heights = [h/total for h in heights]

    # Create subplots without titles
    fig = make_subplots(
        rows=num_subplots,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=heights
    )

    # Add candlestick with Light theme
    candle_config = get_light_candlestick_config()
    candlestick = go.Candlestick(
        x=df['time'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='OHLC',
        **candle_config
    )
    fig.add_trace(candlestick, row=1, col=1)

    # Add Moving Averages with Light theme colors (use cached indicators when available)
    if show_ma and ma_periods:
        colors = ['#2962ff', '#ff6d00', '#9c27b0', '#00e676', '#ffd600']
        for i, period in enumerate(ma_periods):
            # Try to get from cache first
            ma_key = f'{ma_type.lower()}{period}'
            ma_series = indicators_cache.get(ma_key)

            # If not in cache, calculate it
            if ma_series is None:
                if ma_type == "SMA":
                    ma_series = calculate_sma(df_full, period)
                else:
                    ma_series = calculate_ema(df_full, period)

            name = f'{ma_type}({period})'

            # Filter MA data to match display range - use df_original for alignment
            mask = (df_original['time'] >= pd.to_datetime(start_date)) & (df_original['time'] <= pd.to_datetime(end_date))
            ma_filtered = ma_series[mask].reset_index(drop=True)
            time_filtered = df_original['time'][mask].reset_index(drop=True)

            # Remove NaN values
            valid_mask = ma_filtered.notna()
            ma_clean = ma_filtered[valid_mask]
            time_clean = time_filtered[valid_mask]

            fig.add_trace(
                go.Scatter(
                    x=time_clean,
                    y=ma_clean,
                    name=name,
                    line=dict(color=colors[i % len(colors)], width=2),
                    mode='lines',
                    connectgaps=False
                ),
                row=1, col=1
            )

    # Add Bollinger Bands (calculate on full data)
    if show_bb:
        fig = add_bollinger_bands(fig, df_full, period=bb_period, std=bb_std, row=1)

    # Track current row for subplots
    current_row = 2

    # Add Volume with Light theme colors
    if show_volume and 'volume' in df.columns:
        colors = [LIGHT_THEME['volume_up'] if close >= open else LIGHT_THEME['volume_down']
                  for close, open in zip(df['close'], df['open'])]

        volume_bars = go.Bar(
            x=df['time'],
            y=df['volume'],
            name='Volume',
            marker_color=colors,
            showlegend=False
        )
        fig.add_trace(volume_bars, row=current_row, col=1)
        fig.update_yaxes(title_text="Volume", row=current_row, col=1)
        current_row += 1

    # Add RSI (calculate on full data)
    if show_rsi:
        fig = add_rsi_subplot(fig, df_full, period=rsi_period, row=current_row)
        current_row += 1

    # Add MACD (calculate on full data)
    if show_macd:
        fig = add_macd_subplot(fig, df_full, row=current_row)
        current_row += 1

    # Apply Light theme layout
    layout_config = get_light_layout(height=800)
    fig.update_layout(**layout_config)

    # Update all axes with Light theme style
    axis_config = get_light_axis_config()

    # Create rangebreaks to hide non-trading days (only for 1D interval)
    rangebreaks_list = []
    if timeframe == '1D':
        all_dates = pd.to_datetime(df['time']).dt.date.tolist()
        for i in range(len(all_dates) - 1):
            current_date = all_dates[i]
            next_date = all_dates[i + 1]
            if (next_date - current_date).days > 1:
                rangebreaks_list.append({
                    'bounds': [current_date + timedelta(days=1), next_date]
                })
        # Limit to 100 rangebreaks
        if len(rangebreaks_list) > 100:
            rangebreaks_list = rangebreaks_list[:100]

    # Turn off vertical grid lines
    x_axis_config = axis_config.copy()
    x_axis_config['showgrid'] = False

    # Set x-axis range to show only selected date range
    x_range = [pd.to_datetime(start_date), pd.to_datetime(end_date)]

    for i in range(1, num_subplots + 1):
        fig.update_xaxes(
            **x_axis_config,
            row=i, col=1,
            rangebreaks=rangebreaks_list if rangebreaks_list else None,
            range=x_range
        )
        fig.update_yaxes(**axis_config, row=i, col=1)

    # Display chart
    st.plotly_chart(fig, use_container_width=True)

    # Data table (optional)
    with st.expander("📋 Xem dữ liệu chi tiết"):
        st.dataframe(
            df[['time', 'open', 'high', 'low', 'close', 'volume']].tail(50),
            use_container_width=True
        )

else:
    st.error("❌ Không thể tải dữ liệu. Vui lòng thử lại!")

# Footer
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: #666;'>Powered by vnstock + Plotly | "
    "Data delayed ~15 minutes</p>",
    unsafe_allow_html=True
)
