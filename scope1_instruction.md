### Nội dung file `Scope1_Requirements.md`


# YÊU CẦU XÂY DỰNG MODULE SCOPE 1 (DIRECT EMISSIONS)

## 1. Tổng quan dự án
Bạn là một Senior Fullstack Developer (FastAPI + SQLAlchemy + Jinja2 + Vanilla JS). Nhiệm vụ của bạn là xây dựng hoàn chỉnh module **Scope 1** cho hệ thống kiểm kê khí nhà kính (VPEI). Hệ thống sử dụng kiến trúc phân tầng: `Models -> Schemas -> Services -> Routers -> Templates`.

## 2. Tài nguyên đầu vào (Attached Files)
* **Database Models:** File `models/device.py` (Đã định nghĩa sẵn các bảng `DeviceCategory` và `ActivityData`).
* **Giao diện (Frontend):** Thư mục `raw_html/` chứa 2 file giao diện tĩnh cần được chuyển đổi thành Jinja2 template:
    * `scope_01_dashboard.html`: Màn hình Dashboard tổng quan.
    * `scope_01_emission_source.html`: Màn hình quản lý danh mục và nhập liệu.
* **File Excel mẫu:** Dùng cho chức năng Import dữ liệu. `test_data/import_test.xlsx`

## 3. Logic Cốt lõi (Core Business Logic)

### 3.1. Hệ số phát thải (Emission Factor - EF)
**TUYỆT ĐỐI KHÔNG TẠO BẢNG DATABASE CHO HỆ SỐ NÀY.** Hệ số phát thải phải là dạng tĩnh (hardcoded) nằm trong file `core/constants.py` hoặc ngay trong Service.
```python
STATIC_EF = {
    "Mobile Harbor Crane": 0.1420,
    "Reach Stacker": 0.1368,
    "Yard Tractor": 0.1373,
    "Empty Container Handler": 0.1563,
    "Forklift": 0.0814,
    "RTG crane": 0.0650,
    "Default": 0.1300
}
```

### 3.2. Công thức tính toán CO2e
Khi tạo hoặc cập nhật `ActivityData`, hệ thống phải tự động tính toán tổng phát thải theo công thức:
$Total\_CO2e = \frac{Power \times Hours \times LF_{input} \times EF_{static} \times Quantity}{1000}$
*(Trong đó LF - Load Factor do người dùng nhập vào qua UI hoặc file Excel, Power theo kW).*

### 3.3. Quản lý trạng thái theo kỳ (Period Status Management)
Dữ liệu được quản lý theo `year` và `month`. Có 3 trạng thái (Enum `RecordStatusEnum`):
* **Draft:** Mặc định. Cho phép Thêm, Sửa, Xóa, Import Excel.
* **Submitted:** Đã gửi rà soát. Khóa các thao tác chỉnh sửa nội dung.
* **Locked:** Đã khóa kỳ kiểm kê. Khóa hoàn toàn mọi thao tác chỉnh sửa và trạng thái.

**Logic chặn (Guardrail):** Mọi API `POST`, `PUT`, `DELETE` trong `ActivityDataService` phải kiểm tra trạng thái kỳ. Nếu kỳ đó có bản ghi nào là `LOCKED` (hoặc `SUBMITTED` tùy quy trình), phải `raise HTTPException(403)`.

## 4. Yêu cầu tính năng (Features Requirements)

### 4.1. Backend (FastAPI + SQLAlchemy)
* **Device Category Service:** CRUD cho nhóm thiết bị. Khi tạo mới, tự động lấy `device_type` để gán `emission_factor` ẩn phía sau.
* **Activity Data Service:**
    * CRUD nhập liệu thủ công (Nhập tay qua giao diện).
    * Cập nhật trạng thái kỳ (`update_period_status`): Đổi trạng thái hàng loạt cho tất cả bản ghi trong một tháng/năm.
* **Import Excel Service (Sử dụng Pandas):**
    * Cấu trúc cột bắt buộc: `Loại thiết bị`, `Số lượng`, `Power (kW)`, `Giờ hoạt động`, `LF (%)`.
    * Map cột `Loại thiết bị` trong Excel với trường `device_type` của bảng `DeviceCategory` trong Database để lấy ID. Nếu không khớp, bỏ qua và gom lại báo lỗi (HTTP 400).
    * Đọc giá trị LF từ Excel và áp dụng vào công thức tính toán.
* **Dashboard Service:**
    * Tính tổng nhiên liệu (Giả định: Tổng kW * h * LF * 0.25).
    * Tính tổng CO2e của tháng.
    * Tính % tăng trưởng (MoM Growth) so với tháng liền trước.
    * Trả về dữ liệu cho Biểu đồ cột (Top thiết bị) và Biểu đồ đường (12 tháng gần nhất).
    * Hỗ trợ xuất Dashboard ra Excel (Export Excel).

### 4.2. Frontend (Jinja2 + JS Fetch API)
* **Sidebar:** Đồng bộ `active` state đúng màn hình đang đứng. Liên kết mượt mà giữa Dashboard và trang Nhập liệu.
* **Dropdown Lọc thời gian:** Khi chọn `year` và `month` trên header, kích hoạt `window.location.href` kèm query params `?year=X&month=Y` để load lại dữ liệu.
* **UI Trạng thái (Status):** Nếu API trả về `status = Submitted` hoặc `Locked`, sử dụng JavaScript để `disabled` tất cả các nút Thêm, Sửa, Xóa, Import. Ẩn nút "Lưu dữ liệu", hiện nút "Khóa kỳ".
* **Charts:** Parse chuỗi JSON từ backend bằng `tojson | safe` và nhúng vào `Chart.js`.
* **AJAX:** Các form (Thêm thiết bị, Thêm hoạt động, Import Excel) phải được gửi qua JS `fetch()` (không dùng form submit thuần để tránh reload trắng trang khi báo lỗi), kèm popup `alert` rõ ràng nếu lỗi.

## 5. Kế hoạch thực thi cho Agent (Execution Steps) 
Vui lòng thực hiện theo thứ tự sau, hoàn thành bước trước mới làm bước sau bạn có thể tham khảo các file thuộc module scope2 `*scope2*` để thực hiện coding:
1.  **Bước 1: Schemas.** Tạo file `schemas/scope1.py` định nghĩa Pydantic models cho Create/Update và Dashboard Responses.
2.  **Bước 2: Services.** Xây dựng `services/scope1_device.py` và `services/scope1_dashboard.py` bao gồm toàn bộ logic tính toán, import/export excel, kiểm tra khóa kỳ.
3.  **Bước 3: Routers.** Tạo các Endpoint FastAPI trả về HTML (`TemplateResponse`) và xử lý API (POST/PUT/DELETE).
4.  **Bước 4: Templates.** Biến đổi 2 file HTML trong `raw_html` thành Jinja2 templates, bổ sung logic JavaScript xử lý gọi API, rồi lưu vào tệp template (giống scope2).
```



