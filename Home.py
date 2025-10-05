"""
VN Stock Multi-Chart View - HOMEPAGE (Optimized with Parallel Loading)
Hiển thị 6 charts cùng lúc với tốc độ tải nhanh
"""
import streamlit as st
from datetime import datetime, timedelta
import sys
import os
import pandas as pd

sys.path.append(os.path.dirname(__file__))

from data.data_fetcher import get_multiple_stocks_parallel, get_available_symbols
from indicators.technical import calculate_sma, calculate_macd
from utils.light_theme import (
    LIGHT_THEME, get_light_layout, get_light_axis_config, get_light_candlestick_config
)
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Page config
st.set_page_config(
    page_title="VN Multi-Chart View",
    page_icon="📈",
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

# Get available symbols
symbols = get_available_symbols()

# 1. Interval (Khung thời gian)
st.sidebar.subheader("📊 Khung thời gian")
interval_options = {
    "Ngày": "1D",
    "Tuần": "1W",
    "Tháng": "1M"
}
interval_display = st.sidebar.radio(
    "Interval:",
    options=list(interval_options.keys()),
    index=0,
    horizontal=True
)
interval = interval_options[interval_display]

st.sidebar.markdown("---")

# 2. Timeline (Khoảng thời gian hiển thị)
st.sidebar.subheader("📅 Khoảng thời gian")
timeline_option = st.sidebar.radio(
    "Timeline:",
    options=["3 tháng", "6 tháng", "1 năm", "YTD", "Tùy chỉnh"],
    index=1,  # Mặc định 6 tháng
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
    display_start_default = display_end_default - timedelta(days=180)

# Nếu chọn "Tùy chỉnh", hiển thị date picker
if timeline_option == "Tùy chỉnh":
    col1, col2 = st.sidebar.columns(2)
    with col1:
        display_start = st.date_input(
            "Từ ngày",
            value=display_start_default,
            max_value=datetime.now(),
            key='custom_start'
        )
    with col2:
        display_end = st.date_input(
            "Đến ngày",
            value=display_end_default,
            max_value=datetime.now(),
            key='custom_end'
        )
else:
    display_start = display_start_default
    display_end = display_end_default

# Data range (luôn fetch 2 năm để có đủ data cho MA200 ở interval Tuần/Tháng)
data_start = datetime.now() - timedelta(days=730)  # 2 năm
data_end = datetime.now()

st.sidebar.markdown("---")

# 2. Indicators
st.sidebar.subheader("📈 Chỉ báo kỹ thuật")

# Moving Averages
show_ma = st.sidebar.checkbox("Moving Average (MA)", value=True)
if show_ma:
    ma_periods = st.sidebar.multiselect(
        "Chu kỳ MA:",
        options=[5, 10, 20, 50, 100, 200],
        default=[20, 50]
    )

# MACD
show_macd = st.sidebar.checkbox("MACD", value=True)

# Volume
show_volume = st.sidebar.checkbox("Volume", value=True)

st.sidebar.markdown("---")

# Cache management
from utils.cache_manager import clear_cache
if st.sidebar.button("🔄 Clear Cache"):
    clear_cache()
    st.sidebar.success("✅ Cache cleared!")
    st.rerun()

st.sidebar.info("💡 Chọn mã cổ phiếu ở dropdown trên mỗi chart")

# Title
st.markdown("<h1 style='text-align: center; color: #131722;'>📈 VN STOCK - MULTI CHART VIEW</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; color: #666;'>{interval_display} | {timeline_option} | MA20/MA50 | MACD</p>", unsafe_allow_html=True)
st.markdown("---")

# Initialize session state for symbols
if 'chart_symbols' not in st.session_state:
    # Default symbols to try (in order of preference)
    default_symbols = ['VNM', 'VCB', 'HPG', 'FPT', 'MBB', 'TCB']

    # Helper function to get symbol safely
    def get_safe_symbol(preferred_symbol, fallback_index):
        if preferred_symbol in symbols:
            return preferred_symbol
        elif fallback_index < len(symbols):
            return symbols[fallback_index]
        else:
            return symbols[0] if symbols else 'VNM'

    st.session_state['chart_symbols'] = {
        's1': get_safe_symbol(default_symbols[0], 0),
        's2': get_safe_symbol(default_symbols[1], 1),
        's3': get_safe_symbol(default_symbols[2], 2),
        's4': get_safe_symbol(default_symbols[3], 3),
        's5': get_safe_symbol(default_symbols[4], 4),
        's6': get_safe_symbol(default_symbols[5], 5),
    }


def create_single_chart(symbol, df, height=400, show_ma_list=None, show_macd_ind=True, show_volume_ind=True,
                        display_start_date=None, display_end_date=None, interval='1D'):
    """
    Tạo 1 chart với MA, MACD từ DataFrame có sẵn

    Parameters:
    -----------
    show_ma_list : list
        Danh sách chu kỳ MA cần hiển thị
    show_macd_ind : bool
        Hiển thị MACD
    show_volume_ind : bool
        Hiển thị Volume
    display_start_date : datetime
        Ngày bắt đầu hiển thị (filter data)
    display_end_date : datetime
        Ngày kết thúc hiển thị (filter data)
    interval : str
        Khung thời gian (1D, 1W, 1M)
    """
    if df is None or df.empty:
        return None

    # Filter data theo display range (nhưng tính MA trên full data trước)
    df_full = df.copy()  # Giữ toàn bộ data gốc
    df_original = df_full.copy()  # Copy để dùng cho filter MA sau

    # Determine rows based on MACD
    num_rows = 2 if show_macd_ind else 1
    row_heights = [0.7, 0.3] if show_macd_ind else [1.0]
    specs_list = [[{"secondary_y": True}]] if num_rows == 1 else [[{"secondary_y": True}], [{"secondary_y": False}]]

    # Create subplots: Price + MACD (với secondary y-axis cho volume)
    fig = make_subplots(
        rows=num_rows, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        specs=specs_list
    )

    # Tính các indicators trên full data trước
    # Moving Averages (tính trên full data)
    ma_data = {}
    if show_ma_list:
        for period in show_ma_list:
            ma_data[period] = calculate_sma(df_full, period)

    # MACD (tính trên full data)
    macd_data = None
    if show_macd_ind:
        macd_data = calculate_macd(df_full)

    # Filter data để hiển thị
    if display_start_date and display_end_date:
        mask = (df_full['time'] >= pd.Timestamp(display_start_date)) & (df_full['time'] <= pd.Timestamp(display_end_date))
        df = df_full[mask].copy()
    else:
        df = df_full

    if df.empty:
        return None

    # Candlestick (primary y-axis)
    candle_config = get_light_candlestick_config()
    candlestick = go.Candlestick(
        x=df['time'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Price',
        showlegend=False,
        **candle_config
    )
    fig.add_trace(candlestick, row=1, col=1, secondary_y=False)

    # Moving Averages (hiển thị data đã filter)
    if show_ma_list and ma_data:
        ma_colors = ['#2962ff', '#ff6d00', '#9c27b0', '#00e676', '#ffd600']
        for i, period in enumerate(show_ma_list):
            # Filter MA data theo display range - dùng df_original thay vì df_full
            ma_series = ma_data[period]
            if display_start_date and display_end_date:
                mask = (df_original['time'] >= pd.Timestamp(display_start_date)) & (df_original['time'] <= pd.Timestamp(display_end_date))
                # Reset index để đảm bảo alignment
                ma_filtered = ma_series[mask].reset_index(drop=True)
                time_filtered = df_original['time'][mask].reset_index(drop=True)
            else:
                ma_filtered = ma_series
                time_filtered = df_original['time']

            # Loại bỏ các giá trị NaN
            valid_mask = ma_filtered.notna()
            ma_filtered_clean = ma_filtered[valid_mask]
            time_filtered_clean = time_filtered[valid_mask]

            fig.add_trace(
                go.Scatter(
                    x=time_filtered_clean,
                    y=ma_filtered_clean,
                    name=f'MA{period}',
                    line=dict(color=ma_colors[i % len(ma_colors)], width=1.5),
                    mode='lines',
                    showlegend=False,
                    connectgaps=False  # Không nối các khoảng trống
                ),
                row=1, col=1, secondary_y=False
            )

    # Volume (secondary y-axis) - scale 5%
    if show_volume_ind:
        colors = [LIGHT_THEME['volume_up'] if close >= open else LIGHT_THEME['volume_down']
                  for close, open in zip(df['close'], df['open'])]

        fig.add_trace(
            go.Bar(
                x=df['time'],
                y=df['volume'],
                name='Volume',
                marker_color=colors,
                showlegend=False,
                opacity=0.3
            ),
            row=1, col=1, secondary_y=True
        )

    # MACD (nếu được bật) - filter MACD data theo display range
    if show_macd_ind and macd_data:
        # Filter MACD data - dùng df_original thay vì df_full
        if display_start_date and display_end_date:
            mask = (df_original['time'] >= pd.Timestamp(display_start_date)) & (df_original['time'] <= pd.Timestamp(display_end_date))
            # Reset index để đảm bảo alignment
            macd_filtered = macd_data['macd'][mask].reset_index(drop=True)
            signal_filtered = macd_data['signal'][mask].reset_index(drop=True)
            histogram_filtered = macd_data['histogram'][mask].reset_index(drop=True)
            time_filtered = df_original['time'][mask].reset_index(drop=True)
        else:
            macd_filtered = macd_data['macd']
            signal_filtered = macd_data['signal']
            histogram_filtered = macd_data['histogram']
            time_filtered = df_original['time']

        # Loại bỏ NaN values
        valid_mask = macd_filtered.notna() & signal_filtered.notna()
        macd_clean = macd_filtered[valid_mask]
        signal_clean = signal_filtered[valid_mask]
        time_clean = time_filtered[valid_mask]

        fig.add_trace(
            go.Scatter(
                x=time_clean,
                y=macd_clean,
                name='MACD',
                line=dict(color='#2962ff', width=1.5),
                showlegend=False,
                connectgaps=False
            ),
            row=2, col=1
        )

        fig.add_trace(
            go.Scatter(
                x=time_clean,
                y=signal_clean,
                name='Signal',
                line=dict(color='#ff6d00', width=1.5),
                showlegend=False,
                connectgaps=False
            ),
            row=2, col=1
        )

        # MACD Histogram - filter theo valid mask
        hist_filtered = histogram_filtered[valid_mask]
        hist_colors = [LIGHT_THEME['histogram_up'] if val >= 0 else LIGHT_THEME['histogram_down']
                       for val in hist_filtered]

        fig.add_trace(
            go.Bar(
                x=time_clean,
                y=hist_filtered,
                name='Histogram',
                marker_color=hist_colors,
                showlegend=False
            ),
            row=2, col=1
        )

    # Apply light theme
    layout_config = get_light_layout(height=height)
    fig.update_layout(**layout_config)

    # Bỏ legend và title
    fig.update_layout(showlegend=False)

    # Update axes
    axis_config = get_light_axis_config()

    # X-axis cho Price chart - tắt vertical grid
    x_axis_config = axis_config.copy()
    x_axis_config['showgrid'] = False  # Tắt vertical grid lines

    # Chỉ tạo rangebreaks cho interval Ngày (1D)
    rangebreaks_list = []
    if interval == '1D':
        # Tạo rangebreaks để ẩn các khoảng thời gian không có data
        # Lấy tất cả các ngày có data
        all_dates = pd.to_datetime(df['time']).dt.date.tolist()

        # Tạo rangebreaks cho các khoảng giữa các ngày không liên tiếp
        for i in range(len(all_dates) - 1):
            current_date = all_dates[i]
            next_date = all_dates[i + 1]
            # Nếu có khoảng cách > 1 ngày, tạo rangebreak
            if (next_date - current_date).days > 1:
                rangebreaks_list.append({
                    'bounds': [current_date + timedelta(days=1), next_date]
                })

        # Giới hạn số lượng rangebreaks để tránh quá nhiều (chỉ lấy 100 rangebreaks đầu)
        if len(rangebreaks_list) > 100:
            rangebreaks_list = rangebreaks_list[:100]

    fig.update_xaxes(**x_axis_config, row=1, col=1, rangebreaks=rangebreaks_list if rangebreaks_list else None)

    # Primary Y-axis (Price)
    fig.update_yaxes(**axis_config, row=1, col=1, secondary_y=False)

    # Secondary Y-axis (Volume) - ẩn, range để volume chiếm ~15%
    if show_volume_ind:
        max_volume = df['volume'].max()
        fig.update_yaxes(
            showgrid=False,
            showticklabels=False,
            range=[0, max_volume * 6.67],  # Range để volume chiếm ~15% (1/6.67 ≈ 15%)
            row=1, col=1,
            secondary_y=True
        )

    # MACD axis (nếu có)
    if show_macd_ind:
        macd_x_config = x_axis_config.copy()
        fig.update_xaxes(**macd_x_config, row=2, col=1, rangebreaks=rangebreaks_list if rangebreaks_list else None)
        fig.update_yaxes(**axis_config, row=2, col=1)

    # Bỏ subplot titles
    fig.update_annotations(text='')

    return fig


# Display charts with dropdown on top of each chart
chart_cols_1 = st.columns(3)
chart_cols_2 = st.columns(3)

# Collect symbols from dropdowns FIRST
selected_symbols = []

# Row 1 - Dropdowns
with chart_cols_1[0]:
    symbol_1 = st.selectbox(
        "Mã CP 1", symbols,
        index=symbols.index(st.session_state['chart_symbols']['s1']),
        key='select_s1',
        label_visibility='collapsed'
    )
    selected_symbols.append(symbol_1)

with chart_cols_1[1]:
    symbol_2 = st.selectbox(
        "Mã CP 2", symbols,
        index=symbols.index(st.session_state['chart_symbols']['s2']),
        key='select_s2',
        label_visibility='collapsed'
    )
    selected_symbols.append(symbol_2)

with chart_cols_1[2]:
    symbol_3 = st.selectbox(
        "Mã CP 3", symbols,
        index=symbols.index(st.session_state['chart_symbols']['s3']),
        key='select_s3',
        label_visibility='collapsed'
    )
    selected_symbols.append(symbol_3)

# Row 2 - Dropdowns
with chart_cols_2[0]:
    symbol_4 = st.selectbox(
        "Mã CP 4", symbols,
        index=symbols.index(st.session_state['chart_symbols']['s4']),
        key='select_s4',
        label_visibility='collapsed'
    )
    selected_symbols.append(symbol_4)

with chart_cols_2[1]:
    symbol_5 = st.selectbox(
        "Mã CP 5", symbols,
        index=symbols.index(st.session_state['chart_symbols']['s5']),
        key='select_s5',
        label_visibility='collapsed'
    )
    selected_symbols.append(symbol_5)

with chart_cols_2[2]:
    symbol_6 = st.selectbox(
        "Mã CP 6", symbols,
        index=symbols.index(st.session_state['chart_symbols']['s6']),
        key='select_s6',
        label_visibility='collapsed'
    )
    selected_symbols.append(symbol_6)

# Update session state
st.session_state['chart_symbols'] = {
    's1': symbol_1, 's2': symbol_2, 's3': symbol_3,
    's4': symbol_4, 's5': symbol_5, 's6': symbol_6
}

# Get MA periods from sidebar
ma_list = ma_periods if show_ma else []

# ===== BATCHED LAZY LOADING: Load Row 1 first, then Row 2 =====
# This improves perceived performance by showing content faster

# BATCH 1: Load Row 1 (3 stocks parallel)
with st.spinner(f'⚡ Đang tải hàng 1 ({interval_display})...'):
    stock_data_row1 = get_multiple_stocks_parallel(
        symbols=selected_symbols[:3],  # First 3 symbols
        start_date=data_start.strftime('%Y-%m-%d'),
        end_date=data_end.strftime('%Y-%m-%d'),
        resolution=interval,
        max_workers=3
    )

# Display Row 1 charts IMMEDIATELY (while Row 2 is loading next)
with chart_cols_1[0]:
    df1 = stock_data_row1.get(selected_symbols[0])
    if df1 is not None and not df1.empty:
        # Debug info
        st.caption(f"📊 {selected_symbols[0]}: {len(df1)} rows | {df1['time'].min().strftime('%Y-%m-%d')} → {df1['time'].max().strftime('%Y-%m-%d')}")
    fig1 = create_single_chart(
        selected_symbols[0], df1,
        height=350, show_ma_list=ma_list, show_macd_ind=show_macd, show_volume_ind=show_volume,
        display_start_date=display_start, display_end_date=display_end, interval=interval
    )
    if fig1:
        st.plotly_chart(fig1, use_container_width=True, key='chart1')
    else:
        st.error(f"❌ Không thể tải {selected_symbols[0]}")

with chart_cols_1[1]:
    fig2 = create_single_chart(
        selected_symbols[1], stock_data_row1.get(selected_symbols[1]),
        height=350, show_ma_list=ma_list, show_macd_ind=show_macd, show_volume_ind=show_volume,
        display_start_date=display_start, display_end_date=display_end, interval=interval
    )
    if fig2:
        st.plotly_chart(fig2, use_container_width=True, key='chart2')
    else:
        st.error(f"❌ Không thể tải {selected_symbols[1]}")

with chart_cols_1[2]:
    fig3 = create_single_chart(
        selected_symbols[2], stock_data_row1.get(selected_symbols[2]),
        height=350, show_ma_list=ma_list, show_macd_ind=show_macd, show_volume_ind=show_volume,
        display_start_date=display_start, display_end_date=display_end, interval=interval
    )
    if fig3:
        st.plotly_chart(fig3, use_container_width=True, key='chart3')
    else:
        st.error(f"❌ Không thể tải {selected_symbols[2]}")

# BATCH 2: Load Row 2 (3 stocks parallel)
with st.spinner(f'⚡ Đang tải hàng 2 ({interval_display})...'):
    stock_data_row2 = get_multiple_stocks_parallel(
        symbols=selected_symbols[3:6],  # Last 3 symbols
        start_date=data_start.strftime('%Y-%m-%d'),
        end_date=data_end.strftime('%Y-%m-%d'),
        resolution=interval,
        max_workers=3
    )

# Display Row 2 charts
with chart_cols_2[0]:
    fig4 = create_single_chart(
        selected_symbols[3], stock_data_row2.get(selected_symbols[3]),
        height=350, show_ma_list=ma_list, show_macd_ind=show_macd, show_volume_ind=show_volume,
        display_start_date=display_start, display_end_date=display_end, interval=interval
    )
    if fig4:
        st.plotly_chart(fig4, use_container_width=True, key='chart4')
    else:
        st.error(f"❌ Không thể tải {selected_symbols[3]}")

with chart_cols_2[1]:
    fig5 = create_single_chart(
        selected_symbols[4], stock_data_row2.get(selected_symbols[4]),
        height=350, show_ma_list=ma_list, show_macd_ind=show_macd, show_volume_ind=show_volume,
        display_start_date=display_start, display_end_date=display_end, interval=interval
    )
    if fig5:
        st.plotly_chart(fig5, use_container_width=True, key='chart5')
    else:
        st.error(f"❌ Không thể tải {selected_symbols[4]}")

with chart_cols_2[2]:
    fig6 = create_single_chart(
        selected_symbols[5], stock_data_row2.get(selected_symbols[5]),
        height=350, show_ma_list=ma_list, show_macd_ind=show_macd, show_volume_ind=show_volume,
        display_start_date=display_start, display_end_date=display_end, interval=interval
    )
    if fig6:
        st.plotly_chart(fig6, use_container_width=True, key='chart6')
    else:
        st.error(f"❌ Không thể tải {selected_symbols[5]}")

# Footer
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: #666;'>⚡ Batched Lazy Loading (Row by Row) | "
    "Cached Indicators + Session Cache | Optimized for Speed</p>",
    unsafe_allow_html=True
)
