"""
Light theme giống TradingView/chart truyền thống
"""

# Light Theme Colors
LIGHT_THEME = {
    'background': '#ffffff',
    'paper_bgcolor': '#ffffff',
    'plot_bgcolor': '#ffffff',
    'grid_color': '#e1e3e6',
    'text_color': '#131722',

    # Candle colors
    'candle_up': '#26a69a',      # Teal/Green
    'candle_down': '#ef5350',    # Red

    # Indicator colors
    'ma_colors': ['#2962ff', '#ff6d00', '#9c27b0', '#00e676', '#ffd600'],

    'macd': '#2962ff',
    'signal': '#ff6d00',
    'histogram_up': 'rgba(38, 166, 154, 0.5)',
    'histogram_down': 'rgba(239, 83, 80, 0.5)',

    'volume_up': 'rgba(38, 166, 154, 0.5)',
    'volume_down': 'rgba(239, 83, 80, 0.5)',
}


def get_light_layout(height=400):
    """
    Get light theme layout configuration
    """
    return {
        'height': height,
        'paper_bgcolor': LIGHT_THEME['paper_bgcolor'],
        'plot_bgcolor': LIGHT_THEME['plot_bgcolor'],
        'font': {
            'family': 'Arial, sans-serif',
            'size': 10,
            'color': LIGHT_THEME['text_color']
        },
        'hovermode': 'x unified',
        'hoverlabel': {
            'bgcolor': '#ffffff',
            'font_size': 10,
            'font_family': 'Arial',
            'font_color': '#131722',
            'bordercolor': '#e1e3e6'
        },
        'margin': dict(l=50, r=10, t=30, b=30),
        'xaxis_rangeslider_visible': False,
        'showlegend': True,
        'legend': {
            'orientation': 'h',
            'yanchor': 'top',
            'y': 0.99,
            'xanchor': 'left',
            'x': 0,
            'bgcolor': 'rgba(255, 255, 255, 0.8)',
            'font': {'color': LIGHT_THEME['text_color'], 'size': 9}
        },
    }


def get_light_axis_config(gridcolor=None):
    """
    Get light theme axis configuration
    """
    if gridcolor is None:
        gridcolor = LIGHT_THEME['grid_color']

    return {
        'gridcolor': gridcolor,
        'gridwidth': 1,
        'showgrid': True,
        'zeroline': False,
        'color': LIGHT_THEME['text_color'],
        'linecolor': gridcolor,
        'showline': True,
    }


def get_light_candlestick_config():
    """
    Get light theme candlestick configuration
    """
    return {
        'increasing_line_color': LIGHT_THEME['candle_up'],
        'decreasing_line_color': LIGHT_THEME['candle_down'],
        'increasing_fillcolor': LIGHT_THEME['candle_up'],
        'decreasing_fillcolor': LIGHT_THEME['candle_down'],
        'line': {'width': 1},
    }
