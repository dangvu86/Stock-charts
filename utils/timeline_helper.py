"""
Timeline Helper - Shared logic for timeline calculation across pages
"""
from datetime import datetime, timedelta


def calculate_timeline_dates(timeline_option, interval='1D'):
    """
    Calculate start and end dates based on timeline option and interval

    Parameters:
    -----------
    timeline_option : str
        One of: "3 tháng", "6 tháng", "1 năm", "YTD", "Tùy chỉnh"
    interval : str
        One of: '1D', '1W', '1M'

    Returns:
    --------
    tuple : (display_start_default, display_end_default)
    """
    display_end_default = datetime.now()

    # Auto-adjust timeline based on interval for better visibility
    if interval == '1M' and timeline_option in ['3 tháng', '6 tháng']:
        # For monthly chart, show more data (minimum 1 year)
        if timeline_option == '3 tháng':
            display_start_default = display_end_default - timedelta(days=365)  # 1 year instead
        elif timeline_option == '6 tháng':
            display_start_default = display_end_default - timedelta(days=730)  # 2 years instead
    elif interval == '1W' and timeline_option == '3 tháng':
        # For weekly chart, 3 months is too short (only 12 candles)
        display_start_default = display_end_default - timedelta(days=180)  # 6 months instead
    elif timeline_option == "3 tháng":
        display_start_default = display_end_default - timedelta(days=90)
    elif timeline_option == "6 tháng":
        display_start_default = display_end_default - timedelta(days=180)
    elif timeline_option == "1 năm":
        display_start_default = display_end_default - timedelta(days=365)
    elif timeline_option == "YTD":
        display_start_default = datetime(display_end_default.year, 1, 1)
    elif timeline_option == "Tùy chỉnh":
        display_start_default = display_end_default - timedelta(days=180)  # Default fallback
    else:
        display_start_default = display_end_default - timedelta(days=180)

    return display_start_default, display_end_default


def get_default_timeline_index(interval):
    """
    Get default timeline option index based on interval

    Parameters:
    -----------
    interval : str
        One of: '1D', '1W', '1M'

    Returns:
    --------
    int : Index for timeline options ["3 tháng", "6 tháng", "1 năm", "YTD", "Tùy chỉnh"]
    """
    if interval == '1M':
        return 2  # 1 năm (12 nến) for monthly
    elif interval == '1W':
        return 2  # 1 năm (52 nến) for weekly
    else:
        return 1  # 6 tháng for daily


def get_expected_candles_info(interval, timeline_option):
    """
    Get expected number of candles for display info

    Parameters:
    -----------
    interval : str
        One of: '1D', '1W', '1M'
    timeline_option : str
        One of: "3 tháng", "6 tháng", "1 năm", "YTD", "Tùy chỉnh"

    Returns:
    --------
    str : Expected candle count info (e.g., "~126 nến")
    """
    expected_candles = {
        '1D': {
            '3 tháng': '~63 nến',
            '6 tháng': '~126 nến',
            '1 năm': '~252 nến',
            'YTD': f'~{(datetime.now() - datetime(datetime.now().year, 1, 1)).days} nến',
        },
        '1W': {
            '3 tháng': '~12 nến',
            '6 tháng': '~26 nến',
            '1 năm': '~52 nến',
            'YTD': f'~{(datetime.now() - datetime(datetime.now().year, 1, 1)).days // 7} nến',
        },
        '1M': {
            '3 tháng': '~3 nến',
            '6 tháng': '~6 nến',
            '1 năm': '~12 nến',
            'YTD': f'~{datetime.now().month} nến',
        }
    }

    return expected_candles.get(interval, {}).get(timeline_option, '')
