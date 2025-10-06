"""
Module để lấy dữ liệu cổ phiếu từ vnstock với parallel loading
"""
import pandas as pd
from vnstock import Vnstock
from datetime import datetime, timedelta
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed


@st.cache_data(ttl=300, show_spinner=False)
def fetch_stock_data_raw(symbol, start_date, end_date, resolution='1D'):
    """
    Fetch data từ API with multi-source fallback
    Cached for 5 minutes using Streamlit's built-in cache
    """
    sources = ['TCBS']  # TCBS only - works on both local and cloud

    for source in sources:
        try:
            stock = Vnstock().stock(symbol=symbol, source=source)

            df = stock.quote.history(
                start=start_date,
                end=end_date,
                interval=resolution
            )

            if df is None or df.empty:
                print(f"[WARNING] No data from {source} for {symbol}, trying next...")
                continue

            # Đổi tên cột cho dễ sử dụng
            df.columns = df.columns.str.lower()

            # Đảm bảo có cột time (thử nhiều tên cột)
            if 'time' not in df.columns:
                if 'date' in df.columns:
                    df.rename(columns={'date': 'time'}, inplace=True)
                elif 'datetime' in df.columns:
                    df.rename(columns={'datetime': 'time'}, inplace=True)
                elif 'trading_date' in df.columns:
                    df.rename(columns={'trading_date': 'time'}, inplace=True)

            # Kiểm tra có đủ columns cần thiết không
            required_cols = ['time', 'open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                print(f"[WARNING] Missing columns from {source} for {symbol}: {df.columns.tolist()}")
                continue

            # Convert time to datetime
            df['time'] = pd.to_datetime(df['time'])

            # Sort by time
            df = df.sort_values('time').reset_index(drop=True)

            # Check for duplicates and remove if exists
            duplicates_before = len(df)
            df = df.drop_duplicates(subset=['time'], keep='last').reset_index(drop=True)
            duplicates_removed = duplicates_before - len(df)

            if duplicates_removed > 0:
                print(f"[WARNING] Removed {duplicates_removed} duplicate dates for {symbol} from {source}")

            # Log success with source info
            print(f"[SUCCESS] Fetched {symbol} from {source} ({len(df)} rows after dedup)")

            return df

        except Exception as e:
            print(f"[ERROR] {source} failed for {symbol}: {str(e)}")
            continue

    # All sources failed
    print(f"[ERROR] All sources failed for {symbol}")
    return None


def get_stock_data(symbol, start_date, end_date, resolution='1D', return_indicators=False):
    """
    Lấy dữ liệu cổ phiếu (sử dụng @st.cache_data decorator)

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
    # Fetch data (automatically cached by decorator)
    df = fetch_stock_data_raw(symbol, start_date, end_date, resolution)

    if return_indicators:
        # Calculate indicators on-the-fly (simple approach)
        from indicators.technical import (
            calculate_sma, calculate_ema, calculate_rsi,
            calculate_macd, calculate_bollinger_bands
        )

        if df is not None and not df.empty:
            indicators = {}
            try:
                # Common indicators
                for period in [5, 10, 20, 50, 100, 200]:
                    indicators[f'sma{period}'] = calculate_sma(df, period)
                    indicators[f'ema{period}'] = calculate_ema(df, period)

                indicators['rsi14'] = calculate_rsi(df, 14)

                macd_data = calculate_macd(df)
                indicators['macd'] = macd_data['macd']
                indicators['macd_signal'] = macd_data['signal']
                indicators['macd_histogram'] = macd_data['histogram']

                bb_data = calculate_bollinger_bands(df, 20, 2)
                indicators['bb_upper'] = bb_data['upper']
                indicators['bb_middle'] = bb_data['middle']
                indicators['bb_lower'] = bb_data['lower']
            except:
                pass

            return df, indicators
        else:
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


@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour
def get_available_symbols():
    """
    Lấy danh sách tất cả mã cổ phiếu từ 3 sàn (HOSE, HNX, UPCOM)
    Cached for 1 hour using Streamlit's built-in cache
    """
    try:
        stock = Vnstock().stock(symbol='ACB', source='VCI')

        # Lấy tất cả symbols (1700+ mã từ 3 sàn)
        df = stock.listing.all_symbols()

        if df is not None and not df.empty and 'symbol' in df.columns:
            all_symbols = df['symbol'].tolist()
            print(f"[SUCCESS] Loaded {len(all_symbols)} symbols from VCI")
            return sorted(set(all_symbols))

        # Fallback nếu API lỗi
        raise Exception("API error")

    except Exception as e:
        print(f"[WARNING] Failed to load symbols from VCI: {str(e)}")
        # Fallback: danh sách phổ biến
        return sorted(set([
            'VNM', 'VCB', 'HPG', 'VHM', 'VIC', 'MSN', 'FPT', 'SSI',
            'MBB', 'TCB', 'CTG', 'ACB', 'VPB', 'VRE', 'GAS',
            'PLX', 'POW', 'SAB', 'BVH', 'MWG', 'PNJ', 'HDB'
        ]))


def format_price(price):
    """Format giá theo định dạng VN với 2 số thập phân (VD: 120,000.50)"""
    if price is None:
        return "N/A"
    return f"{price:,.2f}"


def calculate_change(current, previous):
    """Tính % thay đổi"""
    if previous == 0 or previous is None or current is None:
        return 0
    return ((current - previous) / previous) * 100
