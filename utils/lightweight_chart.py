"""
Lightweight Charts wrapper for Streamlit
Provides utility functions to convert DataFrame to Lightweight Charts format
and render charts with indicators (MA, MACD, Volume)
"""
from datetime import datetime
import pandas as pd
from lightweight_charts_v5 import lightweight_charts_v5_component


def convert_df_to_candlestick(df):
    """
    Convert DataFrame to Lightweight Charts candlestick format

    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with columns: time, open, high, low, close, volume

    Returns:
    --------
    list of dict
        Format: [{"time": "2024-01-01", "open": 100, "high": 105, "low": 95, "close": 102}]
    """
    data = []
    for _, row in df.iterrows():
        # Convert timestamp to string format "YYYY-MM-DD"
        time_str = pd.to_datetime(row['time']).strftime('%Y-%m-%d')
        data.append({
            "time": time_str,
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close'])
        })
    return data


def convert_series_to_line(time_series, value_series):
    """
    Convert pandas Series to Lightweight Charts line format

    Parameters:
    -----------
    time_series : pd.Series
        Time index series
    value_series : pd.Series
        Value series (e.g., MA, RSI)

    Returns:
    --------
    list of dict
        Format: [{"time": "2024-01-01", "value": 102.5}]
    """
    data = []
    for time, value in zip(time_series, value_series):
        # Skip NaN values
        if pd.isna(value):
            continue
        time_str = pd.to_datetime(time).strftime('%Y-%m-%d')
        data.append({
            "time": time_str,
            "value": float(value)
        })
    return data


def convert_volume_to_histogram(df):
    """
    Convert volume data to Lightweight Charts histogram format

    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with columns: time, open, close, volume

    Returns:
    --------
    list of dict
        Format: [{"time": "2024-01-01", "value": 1000000, "color": "#26a69a"}]
    """
    data = []
    for _, row in df.iterrows():
        time_str = pd.to_datetime(row['time']).strftime('%Y-%m-%d')
        # Color based on price movement (green if close >= open, red otherwise)
        color = "#26a69a" if row['close'] >= row['open'] else "#ef5350"
        data.append({
            "time": time_str,
            "value": float(row['volume']),
            "color": color
        })
    return data


def convert_macd_to_histogram(time_series, histogram_series):
    """
    Convert MACD histogram to Lightweight Charts histogram format

    Parameters:
    -----------
    time_series : pd.Series
        Time index series
    histogram_series : pd.Series
        MACD histogram values

    Returns:
    --------
    list of dict
        Format: [{"time": "2024-01-01", "value": 0.5, "color": "#26a69a"}]
    """
    data = []
    for time, value in zip(time_series, histogram_series):
        # Skip NaN values
        if pd.isna(value):
            continue
        time_str = pd.to_datetime(time).strftime('%Y-%m-%d')
        # Color based on histogram value (green if positive, red if negative)
        color = "#26a69a" if value >= 0 else "#ef5350"
        data.append({
            "time": time_str,
            "value": float(value),
            "color": color
        })
    return data


def render_chart_with_indicators(
    symbol,
    df,
    ma_list=None,
    macd_data=None,
    rsi_data=None,
    bb_data=None,
    show_volume=True,
    height=400,
    key=None
):
    """
    Render a stock chart with indicators using Lightweight Charts

    Parameters:
    -----------
    symbol : str
        Stock symbol (e.g., "HPG", "VNM")
    df : pd.DataFrame
        DataFrame with columns: time, open, high, low, close, volume
    ma_list : list of dict, optional
        List of MA indicators with format: [{"period": 20, "data": Series, "color": "#2962ff"}]
    macd_data : dict, optional
        MACD data with keys: "macd", "signal", "histogram" (all Series)
    rsi_data : pd.Series, optional
        RSI indicator data
    bb_data : dict, optional
        Bollinger Bands data with keys: "upper", "middle", "lower" (all Series)
    show_volume : bool
        Show volume bars
    height : int
        Chart height in pixels
    key : str, optional
        Unique key for Streamlit component

    Returns:
    --------
    None (renders chart)
    """
    # Prepare charts list (multi-pane support)
    charts = []

    # Main chart (Candlestick + MA)
    main_series = []

    # Add candlestick
    candlestick_data = convert_df_to_candlestick(df)
    main_series.append({
        "type": "Candlestick",
        "data": candlestick_data,
        "options": {
            "upColor": "#26a69a",
            "downColor": "#ef5350",
            "borderVisible": False,
            "wickUpColor": "#26a69a",
            "wickDownColor": "#ef5350"
        }
    })

    # Add Bollinger Bands (must be before MA to appear behind)
    if bb_data:
        # Upper band
        upper_data = convert_series_to_line(df['time'], bb_data['upper'])
        if upper_data:
            main_series.append({
                "type": "Line",
                "data": upper_data,
                "options": {
                    "color": "#bbbbbb",
                    "lineWidth": 1,
                    "lineStyle": 2,  # Dashed
                    "title": "BB Upper"
                }
            })

        # Middle band
        middle_data = convert_series_to_line(df['time'], bb_data['middle'])
        if middle_data:
            main_series.append({
                "type": "Line",
                "data": middle_data,
                "options": {
                    "color": "#999999",
                    "lineWidth": 1,
                    "title": "BB Middle"
                }
            })

        # Lower band
        lower_data = convert_series_to_line(df['time'], bb_data['lower'])
        if lower_data:
            main_series.append({
                "type": "Line",
                "data": lower_data,
                "options": {
                    "color": "#bbbbbb",
                    "lineWidth": 1,
                    "lineStyle": 2,  # Dashed
                    "title": "BB Lower"
                }
            })

    # Add MA lines
    if ma_list:
        ma_colors = ['#2962ff', '#ff6d00', '#9c27b0', '#00e676', '#ffd600']
        for i, ma_info in enumerate(ma_list):
            ma_data = convert_series_to_line(df['time'], ma_info['data'])
            if ma_data:  # Only add if there's valid data
                main_series.append({
                    "type": "Line",
                    "data": ma_data,
                    "options": {
                        "color": ma_info.get('color', ma_colors[i % len(ma_colors)]),
                        "lineWidth": 2,
                        "title": f"MA{ma_info['period']}"
                    }
                })

    # Add volume as overlay histogram (on same pane)
    if show_volume:
        volume_data = convert_volume_to_histogram(df)
        main_series.append({
            "type": "Histogram",
            "data": volume_data,
            "options": {
                "priceFormat": {
                    "type": "volume"
                },
                "priceScaleId": "volume",
                "scaleMargins": {
                    "top": 0.85,  # Volume takes bottom 15%
                    "bottom": 0
                }
            }
        })

    # Create main chart configuration
    main_chart = {
        "chart": {
            "layout": {
                "background": {"color": "#ffffff"},
                "textColor": "#131722"
            },
            "grid": {
                "vertLines": {"color": "#f0f0f0"},
                "horzLines": {"color": "#f0f0f0"}
            },
            "timeScale": {
                "borderColor": "#cccccc",
                "timeVisible": True
            }
        },
        "series": main_series,
        "height": height,
        "priceScale": [
            {"scaleId": ""},  # Default price scale
            {
                "scaleId": "volume",
                "scaleMargins": {
                    "top": 0.85,
                    "bottom": 0
                }
            }
        ]
    }

    charts.append(main_chart)

    # MACD chart (separate pane)
    if macd_data:
        macd_series = []

        # MACD line
        macd_line = convert_series_to_line(df['time'], macd_data['macd'])
        if macd_line:
            macd_series.append({
                "type": "Line",
                "data": macd_line,
                "options": {
                    "color": "#2962ff",
                    "lineWidth": 2,
                    "title": "MACD"
                }
            })

        # Signal line
        signal_line = convert_series_to_line(df['time'], macd_data['signal'])
        if signal_line:
            macd_series.append({
                "type": "Line",
                "data": signal_line,
                "options": {
                    "color": "#ff6d00",
                    "lineWidth": 2,
                    "title": "Signal"
                }
            })

        # Histogram
        histogram_data = convert_macd_to_histogram(df['time'], macd_data['histogram'])
        if histogram_data:
            macd_series.append({
                "type": "Histogram",
                "data": histogram_data,
                "options": {
                    "title": "Histogram"
                }
            })

        macd_chart = {
            "chart": {
                "layout": {
                    "background": {"color": "#ffffff"},
                    "textColor": "#131722"
                },
                "grid": {
                    "vertLines": {"color": "#f0f0f0"},
                    "horzLines": {"color": "#f0f0f0"}
                }
            },
            "series": macd_series,
            "height": int(height * 0.3)  # MACD pane is 30% of main chart height
        }

        charts.append(macd_chart)

    # RSI chart (separate pane)
    if rsi_data is not None:
        rsi_series = []

        # RSI line
        rsi_line = convert_series_to_line(df['time'], rsi_data)
        if rsi_line:
            rsi_series.append({
                "type": "Line",
                "data": rsi_line,
                "options": {
                    "color": "#9c27b0",
                    "lineWidth": 2,
                    "title": "RSI"
                }
            })

        # Add reference lines at 30 and 70
        # Note: Lightweight Charts doesn't support horizontal lines directly
        # We'll create constant data series for reference
        if rsi_line:
            time_points = [item['time'] for item in rsi_line]
            rsi_series.append({
                "type": "Line",
                "data": [{"time": t, "value": 70} for t in time_points],
                "options": {
                    "color": "#ff0000",
                    "lineWidth": 1,
                    "lineStyle": 2,  # Dashed
                    "title": "Overbought"
                }
            })
            rsi_series.append({
                "type": "Line",
                "data": [{"time": t, "value": 30} for t in time_points],
                "options": {
                    "color": "#00ff00",
                    "lineWidth": 1,
                    "lineStyle": 2,  # Dashed
                    "title": "Oversold"
                }
            })

        rsi_chart = {
            "chart": {
                "layout": {
                    "background": {"color": "#ffffff"},
                    "textColor": "#131722"
                },
                "grid": {
                    "vertLines": {"color": "#f0f0f0"},
                    "horzLines": {"color": "#f0f0f0"}
                }
            },
            "series": rsi_series,
            "height": int(height * 0.2)  # RSI pane is 20% of main chart height
        }

        charts.append(rsi_chart)

    # Calculate total height
    total_height = height
    if macd_data:
        total_height += int(height * 0.3)
    if rsi_data is not None:
        total_height += int(height * 0.2)

    # Render component
    lightweight_charts_v5_component(
        name=f"{symbol} Chart",
        charts=charts,
        height=total_height,
        key=key
    )
