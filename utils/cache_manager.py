"""
Cache Manager - Optimized caching strategy with pre-calculated indicators
"""
import streamlit as st
from datetime import datetime, timedelta
import pandas as pd


def get_cache_key(symbol, start_date, end_date, resolution):
    """
    Tạo unique cache key với rounding để tăng cache hit rate

    Strategy: Round end_date về đầu ngày để tránh cache miss khi user
    truy cập cùng data trong ngày
    """
    # Normalize dates to string format
    if isinstance(start_date, datetime):
        start_date = start_date.strftime('%Y-%m-%d')
    if isinstance(end_date, datetime):
        end_date = end_date.strftime('%Y-%m-%d')
    elif isinstance(end_date, str) and len(end_date) > 10:
        # Truncate time part if present
        end_date = end_date[:10]

    return f"{symbol}_{start_date}_{end_date}_{resolution}"


def calculate_common_indicators(df):
    """
    Pre-calculate common indicators to cache with raw data

    Returns:
    --------
    dict : Dictionary of pre-calculated indicators
    """
    from indicators.technical import (
        calculate_sma, calculate_ema, calculate_rsi,
        calculate_macd, calculate_bollinger_bands
    )

    if df is None or df.empty:
        return {}

    indicators = {}

    # Moving Averages (most common periods)
    for period in [5, 10, 20, 50, 100, 200]:
        try:
            indicators[f'sma{period}'] = calculate_sma(df, period)
            indicators[f'ema{period}'] = calculate_ema(df, period)
        except:
            pass

    # RSI
    try:
        indicators['rsi14'] = calculate_rsi(df, 14)
    except:
        pass

    # MACD
    try:
        macd_data = calculate_macd(df)
        indicators['macd'] = macd_data['macd']
        indicators['macd_signal'] = macd_data['signal']
        indicators['macd_histogram'] = macd_data['histogram']
    except:
        pass

    # Bollinger Bands
    try:
        bb_data = calculate_bollinger_bands(df, 20, 2)
        indicators['bb_upper'] = bb_data['upper']
        indicators['bb_middle'] = bb_data['middle']
        indicators['bb_lower'] = bb_data['lower']
    except:
        pass

    return indicators


def get_cached_data(symbol, start_date, end_date, resolution):
    """
    Lấy data từ session_state cache (bao gồm cả indicators)

    Returns:
    --------
    tuple: (DataFrame, dict of indicators) hoặc (None, None) nếu không có cache
    """
    cache_key = get_cache_key(symbol, start_date, end_date, resolution)

    if 'stock_data_cache' not in st.session_state:
        st.session_state['stock_data_cache'] = {}

    cache_data = st.session_state['stock_data_cache'].get(cache_key)

    if cache_data:
        # Check if cache is still valid (5 minutes = 300 seconds)
        cache_time = cache_data.get('timestamp')
        if cache_time and (datetime.now() - cache_time).total_seconds() < 300:
            return cache_data.get('data'), cache_data.get('indicators', {})

    return None, None


def set_cached_data(symbol, start_date, end_date, resolution, data):
    """
    Lưu data + pre-calculated indicators vào session_state cache
    """
    cache_key = get_cache_key(symbol, start_date, end_date, resolution)

    if 'stock_data_cache' not in st.session_state:
        st.session_state['stock_data_cache'] = {}

    # Pre-calculate common indicators
    indicators = calculate_common_indicators(data)

    st.session_state['stock_data_cache'][cache_key] = {
        'data': data,
        'indicators': indicators,
        'timestamp': datetime.now()
    }


def clear_cache():
    """Xóa toàn bộ cache"""
    if 'stock_data_cache' in st.session_state:
        st.session_state['stock_data_cache'] = {}


def get_cache_stats():
    """Lấy thống kê cache"""
    if 'stock_data_cache' not in st.session_state:
        return {'total': 0, 'valid': 0}

    total = len(st.session_state['stock_data_cache'])
    valid = 0

    for key, cache_data in st.session_state['stock_data_cache'].items():
        cache_time = cache_data.get('timestamp')
        if cache_time and (datetime.now() - cache_time).total_seconds() < 300:
            valid += 1

    return {'total': total, 'valid': valid}


def get_indicator_from_cache(symbol, start_date, end_date, resolution, indicator_name):
    """
    Lấy 1 indicator cụ thể từ cache

    Parameters:
    -----------
    indicator_name : str
        Tên indicator (e.g., 'sma20', 'rsi14', 'macd')

    Returns:
    --------
    pd.Series or None
    """
    _, indicators = get_cached_data(symbol, start_date, end_date, resolution)

    if indicators:
        return indicators.get(indicator_name)

    return None
