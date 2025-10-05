# 📈 VN Stock Chart Analyzer ⚡

Web app Streamlit hiển thị biểu đồ nến và các chỉ báo kỹ thuật cho cổ phiếu Việt Nam.

**✨ Tối ưu hiệu suất: Parallel Loading + Session Cache → Nhanh gấp 3 lần!**

## ✨ Tính năng

### 📊 2 Chế độ xem:

#### 1. **Multi-Chart View** ([Home.py](Home.py)) ⭐ **HOMEPAGE - MẶC ĐỊNH**
- **6 charts cùng lúc** (3x2 grid)
- **Parallel Loading** - Tải 6 mã song song cực nhanh
- **Session Cache** - Lưu data tránh fetch lại
- Mỗi chart có dropdown riêng chọn mã
- **Mặc định**: 1 năm, MA20/50, MACD
- Light theme sáng đẹp

#### 2. **Single Chart Mode** ([pages/1_📊_Single_Chart.py](pages/1_📊_Single_Chart.py))
- Xem chi tiết 1 cổ phiếu
- Tùy chỉnh đầy đủ indicators
- Dark theme TradingView
- Cache tối ưu

### 📈 Chỉ báo kỹ thuật
- **Moving Average (MA)**: SMA/EMA (20, 50, 100, 200)
- **MACD**: Moving Average Convergence Divergence
- **RSI**: Relative Strength Index
- **Bollinger Bands**: Tùy chỉnh period và std dev
- **Volume**: Khối lượng giao dịch overlay

### ⚡ Tối ưu hiệu suất
- **Parallel Loading**: ThreadPoolExecutor cho 6 charts
- **Session State Cache**: Giảm API calls
- **Smart Caching**: TTL 5 phút tự động
- **Lazy Loading**: Chỉ load khi cần

## 🚀 Cài đặt

### 1. Clone repository hoặc tải về

### 2. Cài đặt dependencies
```bash
pip install -r requirements.txt
```

### 3. Chạy ứng dụng

```bash
streamlit run Home.py
```

**Trang chủ mặc định**: Multi-Chart View (6 charts)

**Chuyển page** qua sidebar:
- **📊 Single Chart** - Phân tích chi tiết 1 mã

### 4. Mở trình duyệt
Ứng dụng sẽ tự động mở tại: `http://localhost:8501`

## 📁 Cấu trúc Project

```
TA Signal/
├── Home.py                      # ⭐ HOMEPAGE: Multi-Chart View (6 charts)
├── pages/
│   └── 1_📊_Single_Chart.py     # Single chart detailed view
├── requirements.txt             # Dependencies
├── README.md                   # Documentation
├── data/
│   └── data_fetcher.py         # Parallel loading + vnstock API
├── indicators/
│   └── technical.py            # Technical indicators
├── utils/
│   ├── cache_manager.py        # ⚡ Session cache manager (NEW)
│   ├── tradingview_theme.py    # Dark theme
│   └── light_theme.py          # Light theme
└── charts/
    └── candlestick.py          # Candlestick charts
```

## ⚡ Tối ưu hiệu suất

### Before (Chậm):
- 6 API calls tuần tự
- Mỗi chart fetch riêng
- Không cache hiệu quả
- **Thời gian load: ~12-15s**

### After (Nhanh):
- ✅ Parallel loading với ThreadPoolExecutor
- ✅ Session state cache (TTL 5 phút)
- ✅ Smart caching strategy
- **Thời gian load: ~3-4s (Nhanh gấp 3 lần!)**

### Cách hoạt động:
```python
# Thay vì tuần tự:
for symbol in symbols:
    df = get_data(symbol)  # 2s x 6 = 12s

# → Song song:
with ThreadPoolExecutor(max_workers=6) as executor:
    futures = [executor.submit(get_data, sym) for sym in symbols]
    # Tổng: ~3s!
```

## 📚 Thư viện sử dụng

- **Streamlit** (1.31.1) - Web framework
- **vnstock** (1.0.30) - Dữ liệu cổ phiếu VN
- **Plotly** (5.18.0) - Biểu đồ interactive
- **Pandas** (2.1.4) - Xử lý dữ liệu
- **pandas-ta** (0.3.14b0) - Chỉ báo kỹ thuật

## 🎯 Hướng dẫn sử dụng

### 1. Chọn cổ phiếu
- Sử dụng dropdown trong sidebar
- Chọn mã cổ phiếu (VD: VNM, VCB, HPG)

### 2. Chọn khoảng thời gian
- Từ ngày - Đến ngày
- Khung thời gian: Ngày/Tuần/Tháng

### 3. Bật/tắt chỉ báo
- **Moving Average**: Chọn SMA/EMA và chu kỳ
- **Bollinger Bands**: Tùy chỉnh period và std
- **RSI**: Điều chỉnh period
- **MACD**: Hiển thị MACD, Signal, Histogram
- **Volume**: Hiển thị khối lượng

### 4. Tương tác với biểu đồ
- **Zoom**: Kéo chuột trên biểu đồ
- **Pan**: Click và giữ để di chuyển
- **Reset**: Double-click để reset zoom
- **Hover**: Di chuột để xem tooltip chi tiết

## 🔧 Tùy chỉnh

### Thêm mã cổ phiếu mới
Chỉnh sửa trong `data/data_fetcher.py`:
```python
def get_available_symbols():
    popular_stocks = [
        'VNM', 'VCB', 'HPG', # ... thêm mã ở đây
    ]
    return sorted(set(popular_stocks))
```

### Thêm chỉ báo mới
Tạo function trong `indicators/technical.py` và gọi trong `app.py`

## 🐛 Xử lý lỗi thường gặp

### Lỗi: "No module named 'vnstock'"
```bash
pip install vnstock
```

### Lỗi: "Cannot fetch data"
- Kiểm tra kết nối internet
- Đảm bảo mã cổ phiếu đúng
- Thử chọn khoảng thời gian khác

### Lỗi: pandas-ta
```bash
pip install pandas-ta --upgrade
```

## 📈 Nâng cấp tương lai

- [ ] Thêm nhiều chỉ báo (Stochastic, ATR, OBV)
- [ ] Watchlist lưu danh sách theo dõi
- [ ] Export chart (PNG/HTML)
- [ ] So sánh nhiều mã cổ phiếu
- [ ] Alerts/Notifications
- [ ] Backtest strategies

## 📄 License

MIT License - Tự do sử dụng và chỉnh sửa

## 🙏 Credits

- **vnstock** - Dữ liệu cổ phiếu VN
- **Plotly** - Biểu đồ interactive
- **Streamlit** - Web framework

---

**Happy Trading! 📊💰**
