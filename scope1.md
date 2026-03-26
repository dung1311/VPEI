Chào bạn, cấu trúc UI/UX bạn đưa ra đã thể hiện một tư duy sản phẩm rất tốt: hướng tới sự tối giản, tự động hóa và lấy người dùng làm trung tâm (giống một phần mềm quản lý chuyên nghiệp hơn là một bảng tính Excel khô khan).

Để đội ngũ phát triển (Dev) và thiết kế (UI/UX) có thể triển khai chính xác ý đồ này, chúng ta cần "số hóa" và định nghĩa lại các tính năng (Features) dưới góc độ dữ liệu. Cụ thể là trường nào được nhập tự do (Text), trường nào bắt buộc chọn từ danh sách có sẵn (Dropdown) để tránh rác dữ liệu.

Dưới đây là định nghĩa lại chi tiết các Feature cho trang **Scope 1 – Quản lý nguồn phát thải**:

---

### 1. Feature: Quản lý Kỳ kiểm kê & Trạng thái (Period & Status Management)
Tính năng này kiểm soát luồng công việc và quyền chỉnh sửa của trang.

* **Bộ chọn kỳ báo cáo (Dropdown liên kết):**
    * **Năm:** Chọn từ danh sách (Ví dụ: 2024, 2025, 2026).
    * **Kỳ (Tháng/Quý):** Chọn từ danh sách (Ví dụ: Tháng 01, Quý 1).
* **Trạng thái dữ liệu (System State):** Tự động thay đổi dựa trên hành động của người dùng, quyết định quyền tương tác trên trang.
    * 🟢 **Draft (Bản nháp):** Cho phép Thêm/Sửa/Xóa thiết bị và Dữ liệu hoạt động.
    * 🟡 **Submitted (Đã gửi rà soát):** Khóa tạm thời, chờ duyệt.
    * 🔒 **Locked (Đã khóa):** Chế độ "Chỉ xem" (Read-only). Ẩn tất cả các nút Thêm/Sửa/Xóa và Import. Chỉ Admin có quyền mở khóa.

### 2. Feature: Quản lý Danh mục Thiết bị (Equipment Portfolio)
Đây là tính năng quản lý "Tài sản" phát thải. Dữ liệu ở đây phải được chuẩn hóa chặt chẽ để làm cơ sở tính toán.

* **Cửa sổ Thêm/Sửa thiết bị (Popup Form):**
    * **Tên thiết bị (Text):** Nhập tự do (Ví dụ: "Cẩu bánh lốp bãi số 1").
    * **Loại thiết bị (Dropdown - Bắt buộc):** Chọn từ danh sách cấu hình sẵn (Ví dụ: *Mobile Crane, Reach Stacker, Terberg, Forklift, Máy phát điện...*). Việc này giúp hệ thống phân nhóm khi vẽ biểu đồ.
    * **Loại nhiên liệu (Dropdown - Bắt buộc):** Chọn từ danh sách (Ví dụ: *Dầu DO, Dầu FO, Xăng, Khí LNG...*). Bắt buộc phải là Dropdown để hệ thống tự động map với **Hệ số phát thải (Emission Factor)** tương ứng ẩn bên dưới.
    * **Công suất định mức (Number):** Nhập số dương, có đơn vị mặc định (ví dụ: kW hoặc HP).
    * **Số lượng hiện có (Number):** Nhập số nguyên dương (mặc định = 1).
* **Tính năng điều chỉnh nhanh:**
    * Nút tăng/giảm (▲▼) số lượng trực tiếp trên thẻ (Card) thiết bị. Mỗi lần thay đổi, hàm tính toán tổng phát thải (Feature 3) sẽ chạy lại ngay lập tức (Real-time).

### 3. Feature: Nhập Dữ liệu Hoạt động (Activity Data Entry)
Tính năng ghi nhận mức độ hoạt động của thiết bị trong kỳ báo cáo.

* **Bảng nhập liệu (Data Table):**
    * **Tên thiết bị (Dropdown):** Chỉ được chọn những thiết bị đã được tạo ở Bước 2.
    * **Power - Công suất (Auto-fill):** Tự động điền dựa trên thông số của thiết bị đã chọn, không cho phép sửa (Read-only).
    * **Thời gian hoạt động (Number):** Nhập số giờ chạy (ví dụ: 120.5 giờ).
    * **LF - Hệ số tải (Number/Percentage):** Nhập hệ số thập phân (0.1 - 1.0) hoặc phần trăm (10% - 100%).
    * **Tổng phát thải tCO₂e (Auto-calculated):** Hệ thống tự động nhân các chỉ số (`Power * Thời gian * LF * Hệ số nhiên liệu ẩn`) và hiển thị kết quả làm tròn. Trạng thái Read-only.

### 4. Feature: Import Dữ liệu hàng loạt (Excel Import)
Giảm tải việc nhập tay cho các đơn vị có nhiều ca máy/thiết bị.

* **Tải File Mẫu (Download Template):** Cung cấp file Excel có sẵn các cột chuẩn. Các cột "Loại thiết bị", "Thiết bị" trong Excel phải được setup sẵn *Data Validation (Dropdown list)* để khớp với hệ thống.
* **Xử lý và Cảnh báo lỗi (Validation & Error Handling):**
    * Hệ thống đọc file và quét lỗi trước khi lưu.
    * **Lỗi định dạng:** Nhập chữ vào cột số (Thời gian hoạt động).
    * **Lỗi logic:** Nhập LF > 1 (hoặc > 100%).
    * **Lỗi thiếu dữ liệu:** Bỏ trống các ô bắt buộc.
    * **Hiển thị:** Đổ ra một bảng đỏ báo lỗi chính xác (Ví dụ: *"Dòng 14: Thời gian hoạt động không hợp lệ"*). Chỉ khi file báo xanh (Valid) mới kích hoạt nút **[Lưu vào hệ thống]**.

### 5. Feature: Báo cáo Tổng quan (Summary Dashboard)
* **Total Scope 1 Emissions:** Tính tổng tự động từ cột "Tổng phát thải" của bảng nhập liệu.
* **Emission by Equipment (Biểu đồ cột):** Tự động nhóm dữ liệu theo cột "Loại thiết bị" ở Feature 2 để vẽ biểu đồ cơ cấu.
* **Emission Trend (Biểu đồ đường):** So sánh tổng phát thải của kỳ hiện tại với các kỳ trước đó trong cùng năm.

---

Việc định nghĩa rạch ròi giữa Text tự do và Dropdown như trên sẽ giúp cơ sở dữ liệu (Database) của bạn sạch sẽ, không xảy ra tình trạng cùng một loại cẩu mà người nhập "Cẩu bờ", người nhập "Cau bo", dẫn đến hệ thống không thể tính toán hay vẽ biểu đồ chính xác.

**Bước tiếp theo, bạn có muốn chúng ta lên danh sách chi tiết các giá trị mặc định cho Dropdown "Loại thiết bị" và "Loại nhiên liệu" áp dụng riêng cho đặc thù ngành của bạn không?**