"""
Module để lấy dữ liệu cổ phiếu từ vnstock với parallel loading
"""
import pandas as pd
from vnstock import Vnstock
from datetime import datetime, timedelta
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import os

# Add utils to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.cache_manager import get_cached_data, set_cached_data


def fetch_stock_data_raw(symbol, start_date, end_date, resolution='1D'):
    """
    Fetch data từ API (không cache tại đây)
    Thử nhiều sources: TCBS (default) → VCI → MSN
    """
    sources = ['TCBS', 'VCI', 'MSN']

    for source in sources:
        try:
            stock = Vnstock().stock(symbol=symbol, source=source)

            df = stock.quote.history(
                start=start_date,
                end=end_date,
                interval=resolution
            )

            if df is None or df.empty:
                print(f"[WARNING] No data returned for {symbol} from {source}, trying next source...")
                continue

            # Đổi tên cột cho dễ sử dụng
            df.columns = df.columns.str.lower()

            # Đảm bảo có cột time
            if 'time' not in df.columns and 'date' in df.columns:
                df.rename(columns={'date': 'time'}, inplace=True)

            # Convert time to datetime
            df['time'] = pd.to_datetime(df['time'])

            # Sort by time
            df = df.sort_values('time').reset_index(drop=True)

            print(f"[SUCCESS] Fetched {symbol} from {source}")
            return df

        except Exception as e:
            print(f"[ERROR] Failed to fetch {symbol} from {source}: {str(e)}")
            continue

    # Tất cả sources đều fail
    print(f"[ERROR] All sources failed for {symbol}")
    return None


def get_stock_data(symbol, start_date, end_date, resolution='1D', return_indicators=False):
    """
    Lấy dữ liệu cổ phiếu với session cache (bao gồm pre-calculated indicators)

    Parameters:
    -----------
    symbol : str
        Mã cổ phiếu (VD: 'VNM', 'VCB', 'HPG')
    start_date : str
        Ngày bắt đầu (format: 'YYYY-MM-DD')
    end_date : str
        Ngày kết thúc (format: 'YYYY-MM-DD')
    resolution : str
        Khung thời gian: '1D' (ngày), '1W' (tuần), '1M' (tháng)
    return_indicators : bool
        Nếu True, return (df, indicators_dict). Nếu False, chỉ return df

    Returns:
    --------
    pd.DataFrame hoặc tuple(pd.DataFrame, dict)
        Nếu return_indicators=True: (DataFrame, dict of indicators)
        Nếu return_indicators=False: DataFrame
    """
    # Check cache trước
    cached_df, cached_indicators = get_cached_data(symbol, start_date, end_date, resolution)
    if cached_df is not None:
        if return_indicators:
            return cached_df, cached_indicators
        return cached_df

    # Fetch new data
    df = fetch_stock_data_raw(symbol, start_date, end_date, resolution)

    if df is not None:
        # Lưu vào cache (tự động tính indicators)
        set_cached_data(symbol, start_date, end_date, resolution, df)

        # Get cached indicators
        if return_indicators:
            _, indicators = get_cached_data(symbol, start_date, end_date, resolution)
            return df, indicators

    if return_indicators:
        return df, {}

    return df


def get_multiple_stocks_parallel(symbols, start_date, end_date, resolution='1D', max_workers=6):
    """
    Lấy dữ liệu nhiều cổ phiếu SONG SONG (parallel)

    Parameters:
    -----------
    symbols : list
        Danh sách mã cổ phiếu
    start_date : str
        Ngày bắt đầu
    end_date : str
        Ngày kết thúc
    resolution : str
        Khung thời gian
    max_workers : int
        Số thread tối đa

    Returns:
    --------
    dict : {symbol: DataFrame}
    """
    results = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_symbol = {
            executor.submit(get_stock_data, symbol, start_date, end_date, resolution): symbol
            for symbol in symbols
        }

        # Collect results as they complete
        for future in as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                df = future.result()
                results[symbol] = df
            except Exception as e:
                results[symbol] = None

    return results


def get_available_symbols():
    """
    Lấy danh sách tất cả mã cổ phiếu từ 3 sàn (HOSE, HNX, UPCOM)
    """
    try:
        stock = Vnstock().stock(symbol='ACB', source='VCI')

        # Lấy tất cả symbols (1700+ mã từ 3 sàn)
        df = stock.listing.all_symbols()

        if df is not None and not df.empty and 'symbol' in df.columns:
            all_symbols = df['symbol'].tolist()
            return sorted(set(all_symbols))

        # Fallback nếu API lỗi
        raise Exception("API error")

    except:
        # Fallback: danh sách phổ biến
        return sorted(set([
            'VNM', 'VCB', 'HPG', 'VHM', 'VIC', 'MSN', 'FPT', 'SSI',
            'MBB', 'TCB', 'CTG', 'ACB', 'VPB', 'VRE', 'BCM', 'GAS',
            'PLX', 'POW', 'SAB', 'BVH', 'MWG', 'PNJ', 'HDB'
        ]))


def format_price(price):
    """Format giá theo định dạng VN (VD: 120,000)"""
    if price is None:
        return "N/A"
    return f"{price:,.0f}"


def calculate_change(current, previous):
    """Tính % thay đổi"""
    if previous == 0 or previous is None or current is None:
        return 0
    return ((current - previous) / previous) * 100
