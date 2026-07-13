# Vũ Yên Research — Nghiên cứu định lượng (bản tiếng Việt)

Dịch vụ backend + ứng dụng web di động để nghiên cứu **Vinhomes (VHM, HOSE)**
theo cách của một nhà phân tích định lượng, với điểm neo thực địa là
**Vinhomes Royal Island trên đảo Vũ Yên, Hải Phòng**.

> ⚠️ **Không phải lời khuyên đầu tư.** Công cụ chỉ phục vụ nghiên cứu và học
> tập: nó cho biết số liệu *đã* như thế nào, không dự báo và không khuyến
> nghị mua/bán. Quyết định tài chính cần chuyên gia có giấy phép.

## Có gì trong này

- **Dữ liệu thật, không cần API key**: giá cổ phiếu HOSE/HNX (VIC, VHM, VRE,
  VPL, VEF) từ nguồn công khai DNSE; ảnh vệ tinh Sentinel-2 thật của đảo
  Vũ Yên (độ phân giải 10 m, có mã cảnh để kiểm chứng độc lập).
- **Phát hiện thay đổi từ vệ tinh**: so sánh NDVI giữa hai thời điểm — ví dụ
  từ 1/2025 đến 5/2026 có **61,5 ha** bị san lấp dọc các trục đường mới.
- **Ứng dụng biểu đồ tương tác** (TradingView Lightweight Charts, tối ưu cho
  iPhone, tiếng Việt mặc định): nến thật + sự kiện + vùng kịch bản 2026–2029;
  tab USD/m² cho Vũ Yên và các dự án so sánh, mỗi điểm đều có nguồn dẫn.
- **Truy cập AI-native (MCP)**: Claude đọc và *chỉnh sửa* dữ liệu nghiên cứu
  qua Model Context Protocol — thêm điểm giá, thêm sự kiện, chỉnh giả định
  kịch bản; thay đổi hiện ngay trên ứng dụng.

## Chạy nhanh

```bash
pip install -r requirements.txt
uvicorn app.main:app        # mở http://127.0.0.1:8000/ — thêm vào Màn hình chính trên iOS
claude mcp add vuyen -- python -m app.mcp_server   # cho Claude đọc/sửa dữ liệu
```

## Lưu ý dữ liệu

- Giá HOSE tính bằng **nghìn VND**; điểm USD/m² quy đổi theo tỷ giá thời gian thực.
- Vùng kịch bản (xấu/cơ sở/tích cực) là **giả định minh hoạ** trong
  `data/outlook.json`, ai cũng xem và sửa được — không phải dự báo.
- Mã "VFS" trên sàn Việt Nam **không phải** VinFast (VinFast niêm yết NASDAQ
  bằng USD) — repo cố tình loại trừ để tránh nhầm lẫn.
