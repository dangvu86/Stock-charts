"""
ADX (Average Directional Index) calculation
Manual implementation without pandas_ta
"""
import pandas as pd
import numpy as np


def calculate_adx(df, period=14):
    """
    Calculate ADX (Average Directional Index) manually

    ADX measures the strength of a trend (0-100)
    - 0-25: Weak or no trend
    - 25-50: Strong trend
    - 50-75: Very strong trend
    - 75-100: Extremely strong trend

    Parameters:
    -----------
    df : pd.DataFrame
        Must have 'high', 'low', 'close' columns
    period : int
        ADX period (default 14)

    Returns:
    --------
    pd.Series : ADX values
    """
    high = df['high']
    low = df['low']
    close = df['close']

    # Calculate True Range (TR)
    high_low = high - low
    high_close = np.abs(high - close.shift(1))
    low_close = np.abs(low - close.shift(1))

    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

    # Calculate Directional Movement (+DM and -DM)
    high_diff = high - high.shift(1)
    low_diff = low.shift(1) - low

    plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
    minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)

    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)

    # Smooth TR, +DM, -DM using Wilder's smoothing (EMA with alpha = 1/period)
    tr_smooth = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    plus_dm_smooth = plus_dm.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    minus_dm_smooth = minus_dm.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    # Calculate Directional Indicators (+DI and -DI)
    plus_di = 100 * (plus_dm_smooth / tr_smooth)
    minus_di = 100 * (minus_dm_smooth / tr_smooth)

    # Calculate DX (Directional Index)
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)

    # Calculate ADX (smoothed DX)
    adx = dx.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    return adx


def calculate_adx_with_di(df, period=14):
    """
    Calculate ADX along with +DI and -DI

    Returns:
    --------
    dict : {'adx': Series, 'plus_di': Series, 'minus_di': Series}
    """
    high = df['high']
    low = df['low']
    close = df['close']

    # Calculate True Range (TR)
    high_low = high - low
    high_close = np.abs(high - close.shift(1))
    low_close = np.abs(low - close.shift(1))

    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

    # Calculate Directional Movement (+DM and -DM)
    high_diff = high - high.shift(1)
    low_diff = low.shift(1) - low

    plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
    minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)

    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)

    # Smooth using Wilder's smoothing
    tr_smooth = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    plus_dm_smooth = plus_dm.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    minus_dm_smooth = minus_dm.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    # Calculate Directional Indicators
    plus_di = 100 * (plus_dm_smooth / tr_smooth)
    minus_di = 100 * (minus_dm_smooth / tr_smooth)

    # Calculate DX and ADX
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    return {
        'adx': adx,
        'plus_di': plus_di,
        'minus_di': minus_di
    }
