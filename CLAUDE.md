# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app (opens at http://localhost:8501)
streamlit run Home.py
```

## Architecture Overview

### Multi-Page Streamlit Application

This is a Vietnamese stock chart analyzer with two main views:

1. **Home.py** (Multi-Chart View - HOMEPAGE)
   - Displays 6 stock charts simultaneously in a 3x2 grid
   - Each chart has its own dropdown for symbol selection
   - Uses **parallel loading** with `ThreadPoolExecutor` to fetch 6 stocks concurrently
   - Implements **session state caching** with 5-minute TTL
   - Light theme (TradingView-style)

2. **pages/1_📊_Single_Chart.py** (Single Chart View)
   - Detailed analysis of a single stock
   - Full customization of indicators
   - Light TradingView theme (matches Multi-Chart)
   - Timeline selector: 3 tháng, 6 tháng, 1 năm (default), YTD, Tùy chỉnh
   - Loads 3 years of data for accurate MA calculations
   - Rangebreaks: Shows only trading days (hides weekends/holidays)
   - **52-Week Metrics**: Highest/Lowest price and Max volume in 52 weeks with % comparison to current price

### Key Performance Optimization

The app has been optimized through multiple iterations:

**Phase 1 (Initial):** ~12-15s → ~3-4s load time (3x faster)
- **Parallel Loading**: `ThreadPoolExecutor` with `max_workers=6`
- **Session Cache**: TTL-based caching (5 minutes)
- **Smart Data Strategy**: Fetch 3 years, calculate indicators on full data, display filtered range

**Phase 2 (Batched Lazy Loading):** First content visible in ~1.8s (50% faster perceived performance)
- **Batched Loading**: Load Row 1 (3 charts) first, then Row 2
- **Progressive Rendering**: User sees content while remaining charts load
- **Cached Indicators**: Pre-calculate 19 common indicators (SMA/EMA 5/10/20/50/100/200, RSI14, MACD, BB)

**Phase 3 (Optimized Cache):** Cache hit = 0.1ms (1600x faster than API call)
- **Smart Cache Keys**: Date rounding to increase hit rate
- **Indicator Caching**: Store pre-calculated indicators with raw data
- **Min Periods Fix**: Added `min_periods=1` to all rolling operations to handle NaN values correctly

**Phase 4 (Deployment Ready):** Removed unused dependencies
- **Removed Files**: parquet_cache.py, tradingview_theme.py (dark theme), charts/candlestick.py
- **Single Cache Layer**: Session state cache only (no parquet/external storage)
- **Streamlit Cloud Ready**: Uses ephemeral filesystem, no external dependencies

### Data Flow Pattern

**Multi-Chart (Home.py) - Batched Lazy Loading:**
```
User opens page
  ↓
BATCH 1: Load Row 1 (3 stocks parallel, max_workers=3)
  → get_stock_data() [check cache → fetch if miss → pre-calculate indicators]
  → Display Row 1 charts ← USER SEES CONTENT (~1.8s)
  ↓
BATCH 2: Load Row 2 (3 stocks parallel, max_workers=3)
  → get_stock_data() [check cache → fetch if miss → pre-calculate indicators]
  → Display Row 2 charts (~3.7s total)
```

**Single Chart - Cached Indicators:**
```
User changes settings (timeline/MA period)
  ↓
get_stock_data(return_indicators=True)
  → Cache HIT (0.1ms) → Return (data, indicators)
  → Cache MISS (1600ms) → Fetch → Calculate 19 indicators → Cache → Return
  ↓
Use cached indicators (ma20, ma50, rsi14, macd, etc.)
  → Filter for display range
  → Render chart (instant)
```

### Critical Implementation Details

#### 1. Data Fetching (data/data_fetcher.py)
- Uses `vnstock` library version ==3.2.6 with API: `Vnstock().stock(symbol, source='TCBS')`
- API method: `stock.quote.history(start, end, interval)`
- Intervals: `'1D'` (day), `'1W'` (week), `'1M'` (month)
- **Data Source**: TCBS (works consistently on both local and Streamlit Cloud)
  - VCI source fails on Streamlit Cloud due to network/firewall issues
  - TCBS API has a bug with ~247 duplicate dates (handled automatically)
  - Deduplication: `df.drop_duplicates(subset=['time'], keep='last')`
- **Stock List**: Fetches all symbols from 3 Vietnamese exchanges (HOSE, HNX, UPCOM) using `stock.listing.all_symbols()` - returns ~1719 stocks
- **Data Strategy**:
  - Multi-Chart (Home.py): Fetch 2 years (`timedelta(days=730)`)
  - Single Chart: Fetch 3 years (`timedelta(days=1095)`)
  - Always calculate indicators on full dataset, then filter for display
- **Caching**: Streamlit `@st.cache_data` with 5-minute TTL (ttl=300)

#### 2. Chart Creation (Home.py: create_single_chart)
- **Two-phase data strategy**:
  1. Calculate indicators (MA, MACD) on **full 2-year dataset** (`df_full`)
  2. Filter data for display based on sidebar date range (`display_start_date`, `display_end_date`)
  3. Keep `df_original` copy for proper index alignment when filtering indicators

- **Index alignment is critical**: After filtering with boolean masks, always:
  ```python
  ma_filtered = ma_series[mask].reset_index(drop=True)
  time_filtered = df_original['time'][mask].reset_index(drop=True)
  ```
  Then remove NaN values before plotting to avoid gaps in lines

- **Volume rendering**: Uses secondary Y-axis with range `[0, max_volume * 6.67]` to make volume occupy ~15% of chart height

- **Rangebreaks**: Only applied for interval='1D' to hide weekends/holidays. NOT used for weekly/monthly intervals to avoid candle overlapping

#### 3. Technical Indicators (indicators/technical.py)
- All indicators are implemented **manually without pandas-ta** dependency
- Functions: `calculate_sma()`, `calculate_ema()`, `calculate_rsi()`, `calculate_macd()`, `calculate_bollinger_bands()`, `calculate_stochastic()`
- MACD returns: `{'macd': Series, 'signal': Series, 'histogram': Series}`
- **CRITICAL**: All rolling operations use `min_periods=1` to handle NaN values correctly (holidays, missing data)
  - Without `min_periods=1`, NaN values propagate through entire rolling window
  - Example: Tet holiday NaN caused MA50 to show NaN for 36 weeks

#### 4. Theme Configuration
- **Light theme** (utils/light_theme.py): Used in both Multi-Chart and Single Chart pages
- TradingView-style color scheme with white background, subtle gridlines

### Single Chart Metrics (pages/1_📊_Single_Chart.py)

Displays 4 key metrics at the top of the page:

1. **💰 Giá hiện tại (Current Price)**
   - Latest closing price
   - Shows % change vs previous day

2. **📈 Highest 52W**
   - Highest price in last 52 weeks (364 days)
   - Shows % difference from current price
   - Formula: `((current - highest_52w) / highest_52w) * 100`

3. **📉 Lowest 52W**
   - Lowest price in last 52 weeks (364 days)
   - Shows % difference from current price
   - Formula: `((current - lowest_52w) / lowest_52w) * 100`

4. **📊 Max Volume 52W**
   - Highest trading volume in last 52 weeks
   - No percentage comparison (absolute value only)

**Calculation:** Uses `df_52w = df[df['time'] >= date_52w_ago]` where `date_52w_ago = max_date - 364 days`

### Sidebar Options (Home.py)

1. **Interval (Khung thời gian)**:
   - Ngày (1D) - default
   - Tuần (1W)
   - Tháng (1M)

2. **Timeline (Khoảng thời gian)**:
   - 3 tháng, 6 tháng (default), 1 năm, YTD, Tùy chỉnh (custom date picker)

3. **Indicators**:
   - Moving Average: MA20, MA50 (default), with options for MA5, 10, 100, 200
   - MACD (default on)
   - Volume (default on)

### Common Pitfalls & Solutions

1. **TCBS API returns duplicate dates** (NEW):
   - Issue: TCBS source returns ~247 duplicate dates (mostly from Sept-Oct 2024)
   - Fix: Automatic deduplication in `fetch_stock_data_raw()` using `df.drop_duplicates(subset=['time'], keep='last')`
   - After dedup: 497 rows (same as VCI clean data)

2. **MA lines breaking/gaps on weekly/monthly charts**:
   - Cause: Filtering indicators with wrong DataFrame reference or not resetting index
   - Fix: Use `df_original` for time filtering, reset index, remove NaN values, set `connectgaps=False`

3. **Charts overlapping on weekly/monthly intervals**:
   - Cause: Rangebreaks applied to non-daily intervals
   - Fix: Only apply rangebreaks when `interval == '1D'`

4. **Volume bars too tall/obscuring price**:
   - Fix: Adjust secondary Y-axis range (currently `max_volume * 6.67` for ~15% height)

5. **Slow loading**:
   - Check if parallel loading is working (should use `ThreadPoolExecutor`)
   - Verify `@st.cache_data` decorator is applied with ttl=300

6. **MA not showing on recent dates (showing only at start of chart)**:
   - Cause: Missing `min_periods=1` in rolling operations causes NaN propagation
   - Fix: All rolling operations in `indicators/technical.py` now have `min_periods=1`
   - Example error: Tet holiday NaN → MA50 shows NaN for last 36 weeks on weekly chart

7. **Cache not working after 1 hour**:
   - Cause: Using `.seconds` instead of `.total_seconds()` for timedelta comparison
   - Fix: Use `(datetime.now() - cache_time).total_seconds() < 300` in cache_manager.py

### vnstock API Notes

- Source: `'VCI'` (default)
- Data columns returned: `time, open, high, low, close, volume`
- Column names are lowercase after processing
- Always sort by time ascending and reset index
- API may return `None` or empty DataFrame for invalid symbols/dates

### Chart Customization Pattern

To add new indicators to Home.py:
1. Calculate on full data (`df_full`) in `create_single_chart()`
2. Filter using mask from `df_original['time']`
3. Reset index and remove NaN values
4. Add trace with `connectgaps=False`
5. Pass `interval` parameter to handle rangebreaks correctly

### Caching Strategy (utils/cache_manager.py)

**Session State Cache (5-minute TTL):**
```python
cache_key = f"{symbol}_{start_date}_{end_date}_{resolution}"
cache_data = st.session_state.cache.get(cache_key)
```

**Pre-calculated Indicators (19 total):**
- SMA: 5, 10, 20, 50, 100, 200
- EMA: 5, 10, 20, 50, 100, 200
- RSI: 14
- MACD: macd, signal, histogram
- Bollinger Bands: upper, middle, lower

**Cache Usage:**
- Multi-Chart: Automatically uses cached data/indicators on subsequent loads
- Single Chart: Pass `return_indicators=True` to get pre-calculated indicators
- Cache hit: 0.1ms (instant)
- Cache miss: 1600ms (API call + indicator calculation)

### Deployment Notes

**Streamlit Cloud:**
- Uses ephemeral filesystem (cache resets on restart)
- Session cache persists during active user session only
- No external storage dependencies (no parquet, no database)
- Memory limit: 1GB RAM

**Removed Features (for simplicity):**
- Parquet cache layer (not effective on ephemeral filesystem)
- Dark theme (consolidated to light theme only)
- Unused chart components

**Performance on Streamlit Cloud:**
- First load: ~3-4s (6 API calls with batched loading)
- Cached loads: ~0.5s (session cache hits)
- First content visible: ~1.8s (Row 1 loads first)
