"""
Module tính toán các chỉ báo kỹ thuật (không cần pandas_ta)
"""
import pandas as pd
import numpy as np
import plotly.graph_objects as go


def calculate_sma(df, period):
    """Tính Simple Moving Average"""
    return df['close'].rolling(window=period, min_periods=1).mean()


def calculate_ema(df, period):
    """Tính Exponential Moving Average"""
    return df['close'].ewm(span=period, adjust=False).mean()


def calculate_rsi(df, period=14):
    """
    Tính RSI (Relative Strength Index) thủ công

    Returns:
    --------
    pd.Series : RSI values
    """
    close = df['close']
    delta = close.diff()

    gain = (delta.where(delta > 0, 0)).rolling(window=period, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period, min_periods=1).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_macd(df, fast=12, slow=26, signal=9):
    """
    Tính MACD (Moving Average Convergence Divergence) thủ công

    Returns:
    --------
    dict : {'macd': Series, 'signal': Series, 'histogram': Series}
    """
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()

    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line

    return {
        'macd': macd,
        'signal': signal_line,
        'histogram': histogram
    }


def calculate_bollinger_bands(df, period=20, std=2):
    """
    Tính Bollinger Bands thủ công

    Returns:
    --------
    dict : {'upper': Series, 'middle': Series, 'lower': Series}
    """
    sma = df['close'].rolling(window=period, min_periods=1).mean()
    std_dev = df['close'].rolling(window=period, min_periods=1).std()

    upper_band = sma + (std_dev * std)
    lower_band = sma - (std_dev * std)

    return {
        'upper': upper_band,
        'middle': sma,
        'lower': lower_band
    }


def calculate_stochastic(df, k_period=14, d_period=3):
    """
    Tính Stochastic Oscillator thủ công

    Returns:
    --------
    dict : {'k': Series, 'd': Series}
    """
    low_min = df['low'].rolling(window=k_period, min_periods=1).min()
    high_max = df['high'].rolling(window=k_period, min_periods=1).max()

    k = 100 * (df['close'] - low_min) / (high_max - low_min)
    d = k.rolling(window=d_period, min_periods=1).mean()

    return {
        'k': k,
        'd': d
    }


def add_rsi_subplot(fig, df, period=14, row=2):
    """Thêm RSI subplot vào figure với TradingView style"""
    rsi = calculate_rsi(df, period)

    fig.add_trace(
        go.Scatter(
            x=df['time'],
            y=rsi,
            name=f'RSI({period})',
            line=dict(color='#7e57c2', width=2)
        ),
        row=row, col=1
    )

    # Thêm đường 70, 50, 30
    fig.add_hline(y=70, line_dash="dash", line_color="#787b86",
                  opacity=0.4, row=row, col=1)
    fig.add_hline(y=50, line_dash="dot", line_color="#787b86",
                  opacity=0.3, row=row, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="#787b86",
                  opacity=0.4, row=row, col=1)

    fig.update_yaxes(title_text="RSI", row=row, col=1, range=[0, 100])

    return fig


def add_macd_subplot(fig, df, row=3):
    """Thêm MACD subplot vào figure với TradingView style"""
    macd_data = calculate_macd(df)

    # MACD line
    fig.add_trace(
        go.Scatter(
            x=df['time'],
            y=macd_data['macd'],
            name='MACD',
            line=dict(color='#2962ff', width=2)
        ),
        row=row, col=1
    )

    # Signal line
    fig.add_trace(
        go.Scatter(
            x=df['time'],
            y=macd_data['signal'],
            name='Signal',
            line=dict(color='#ff6d00', width=2)
        ),
        row=row, col=1
    )

    # Histogram with TradingView colors
    colors = ['rgba(38, 166, 154, 0.5)' if val >= 0 else 'rgba(239, 83, 80, 0.5)'
              for val in macd_data['histogram']]

    fig.add_trace(
        go.Bar(
            x=df['time'],
            y=macd_data['histogram'],
            name='Histogram',
            marker_color=colors,
            showlegend=False
        ),
        row=row, col=1
    )

    fig.update_yaxes(title_text="MACD", row=row, col=1)

    return fig


def add_bollinger_bands(fig, df, period=20, std=2, row=1):
    """Thêm Bollinger Bands vào candlestick chart với TradingView style"""
    bb = calculate_bollinger_bands(df, period, std)

    # Upper band
    fig.add_trace(
        go.Scatter(
            x=df['time'],
            y=bb['upper'],
            name=f'BB Upper({period})',
            line=dict(color='#787b86', width=1, dash='dot'),
            mode='lines'
        ),
        row=row, col=1
    )

    # Middle band (SMA)
    fig.add_trace(
        go.Scatter(
            x=df['time'],
            y=bb['middle'],
            name=f'BB Basis({period})',
            line=dict(color='#787b86', width=1),
            mode='lines'
        ),
        row=row, col=1
    )

    # Lower band
    fig.add_trace(
        go.Scatter(
            x=df['time'],
            y=bb['lower'],
            name=f'BB Lower({period})',
            line=dict(color='#787b86', width=1, dash='dot'),
            fill='tonexty',
            fillcolor='rgba(120, 123, 134, 0.05)',
            mode='lines'
        ),
        row=row, col=1
    )

    return fig
