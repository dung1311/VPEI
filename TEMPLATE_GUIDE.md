# VPEI Template Generation Guide

Tài liệu này mô tả các quy tắc bắt buộc khi sinh ra Jinja2 template cho dự án VPEI.
Mọi template mới phải tuân theo đúng những gì được định nghĩa ở đây — không được tự ý thay đổi màu sắc, font, cấu trúc block, hay CSS class names.

---

## 1. Kiến trúc template

### 1.1 Nguyên tắc kế thừa

Mọi page template (trừ `auth/login.html`) đều phải extend `base.html`:

```html
{% extends "base.html" %}
```

`base.html` cung cấp sẵn: navbar, flash message global, CSS variables, typography, button/badge/form/table styles.
**Không được copy lại những thứ đã có trong `base.html` vào child template.**

### 1.2 Cấu trúc thư mục

```
templates/
├── base.html               ← layout master, KHÔNG được sửa khi thêm module mới
├── auth/
│   └── login.html          ← standalone, KHÔNG extend base.html
├── dashboard/
│   └── index.html
├── admin/
│   ├── users.html
│   ├── create_user.html
│   └── reset_password.html
└── <module_mới>/           ← mỗi module có thư mục riêng
    ├── index.html
    ├── create.html
    └── detail.html
```

### 1.3 Các blocks có sẵn

| Block | Dùng để |
|---|---|
| `{% block title %}` | Tiêu đề tab trình duyệt (không cần suffix — base tự thêm) |
| `{% block extra_head %}` | CSS riêng của page, đặt trong `<style>` |
| `{% block content %}` | Nội dung chính của page |
| `{% block extra_scripts %}` | JavaScript riêng, đặt cuối body |

Template tối giản:

```html
{% extends "base.html" %}
{% block title %}Tên trang{% endblock %}

{% block extra_head %}
<style>
  /* CSS riêng của page này */
</style>
{% endblock %}

{% block content %}
<div class="page">
  <!-- nội dung -->
</div>
{% endblock %}

{% block extra_scripts %}
<script>
  /* JS riêng nếu có */
</script>
{% endblock %}
```

---

## 2. Design tokens — CSS variables

Tất cả màu sắc phải dùng CSS variable từ danh sách dưới đây.
**Không được hardcode màu hex trực tiếp trong child template** (trừ khi là màu hoàn toàn mới chưa có trong hệ thống).

```css
/* Brand colors */
--navy:         #0d1f3c   /* màu chủ đạo — nền navbar, button primary, tiêu đề */
--navy-mid:     #152850   /* gradient mid stop */
--navy-light:   #1e3a6e   /* gradient end stop, hover states */
--accent:       #2e7df7   /* link, focus border, accent elements */
--accent-light: #5a9bff   /* logo highlight, light accent */

/* Semantic colors */
--danger:       #e53e3e
--danger-light: #fff5f5
--success:      #38a169
--success-light:#f0fff4
--warning:      #d69e2e
--warning-light:#fffff0

/* Neutral */
--gray-soft:    #f4f6fb   /* page background, input background */
--gray-border:  #dde3ef   /* border, divider */
--text-muted:   #7a8aab   /* secondary text, placeholder */
--white:        #ffffff
```

---

## 3. Typography

Dự án dùng **2 font families** được load từ Google Fonts trong `base.html`:

```
'Sora'   → headings, brand name, button text, table header
'DM Sans' → body text, labels, general UI
```

Quy tắc:
- `font-family: 'Sora', sans-serif` — dùng cho: `h1`, `h2`, `h3`, `.page-title`, `.card-title`, `.btn`, `thead th`, `.stat-value`
- `font-family: 'DM Sans', sans-serif` — mặc định toàn bộ body
- **Không import font khác.** Nếu cần font mới, bổ sung vào `base.html`, không thêm vào child template.

---

## 4. Layout patterns

### 4.1 Page wrapper

Mọi page content đều bọc trong `.page`:

```html
<div class="page">
  <div class="page-header">
    <div>
      <div class="page-title">Tiêu đề trang</div>
      <div class="page-subtitle">Mô tả ngắn</div>
    </div>
    <!-- action button nếu có, ví dụ: nút Tạo mới -->
    <a href="/path/create" class="btn btn-primary">＋ Tạo mới</a>
  </div>

  <!-- nội dung -->
</div>
```

`.page` có `max-width: 1100px` và `margin: 0 auto` — không cần set lại.

### 4.2 Form page (create/edit)

Form đơn lẻ dùng `.form-card-wrap` + `.form-card`:

```html
<div class="form-card-wrap">   <!-- max-width: 560px, centered -->
  <div class="form-card">      <!-- white card, border-radius 16px -->
    <div class="card-title">Tiêu đề form</div>
    <div class="card-sub">Mô tả ngắn về form này.</div>

    {% if error %}<div class="error-msg">⚠ {{ error }}</div>{% endif %}

    <form method="POST" action="/path">
      <!-- form fields -->
    </form>
  </div>
</div>
```

### 4.3 Table page (list)

```html
<div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th>Cột 1</th>
        <th>Cột 2</th>
      </tr>
    </thead>
    <tbody>
      {% if items %}
        {% for item in items %}
        <tr>
          <td>{{ item.field1 }}</td>
          <td>{{ item.field2 }}</td>
        </tr>
        {% endfor %}
      {% else %}
        <tr>
          <td colspan="N">
            <div class="empty-state">
              <div class="icon">📋</div>
              Chưa có dữ liệu.
            </div>
          </td>
        </tr>
      {% endif %}
    </tbody>
  </table>
</div>
```

### 4.4 Stats bar

Dùng cho các trang list cần hiển thị tổng quan nhanh:

```html
<div class="stats">
  <div class="stat-card">
    <div class="stat-label">Nhãn</div>
    <div class="stat-value">{{ count }}</div>
  </div>
  <!-- thêm các stat-card khác -->
</div>
```

CSS của `stats`, `stat-card`, `stat-label`, `stat-value` khai báo trong `{% block extra_head %}` của từng page — không có trong `base.html`.

---

## 5. Components

Các class sau đã được định nghĩa trong `base.html` — dùng trực tiếp, không khai báo lại:

### 5.1 Buttons

```html
<a href="/path" class="btn btn-primary">Nút chính</a>
<a href="/path" class="btn btn-secondary">Huỷ</a>
<button class="btn btn-danger">Xoá</button>
<button class="btn btn-warning">Cảnh báo</button>

<!-- Size nhỏ (dùng trong table) -->
<button class="btn btn-sm btn-danger">🗑 Xoá</button>
<a href="/path" class="btn btn-sm btn-warning">🔑 Reset</a>
```

Biến thể màu:

| Class | Nền | Text | Dùng khi |
|---|---|---|---|
| `btn-primary` | navy gradient | white | Hành động chính của trang |
| `btn-secondary` | gray-soft | text-muted | Huỷ, quay lại |
| `btn-danger` | danger-light | danger | Xoá, hành động không thể hoàn tác |
| `btn-warning` | warning-light | warning | Cảnh báo, reset |

### 5.2 Badges

```html
<span class="badge badge-admin">Admin</span>
<span class="badge badge-user">User</span>
<span class="badge badge-active">Hoạt động</span>
<span class="badge badge-inactive">Bị khoá</span>
```

Để thêm badge type mới, khai báo trong `{% block extra_head %}`:

```css
.badge-custom { background: #ebf4ff; color: var(--accent); }
```

### 5.3 Flash messages

Flash toàn trang được xử lý tự động trong `base.html` qua query param:

```python
# Trong router — redirect kèm flash
return RedirectResponse(url="/path?flash=Thông báo&flash_type=success")
# flash_type: success | error | warning
```

Flash inline trong page (không qua redirect):

```html
{% if error %}
<div class="error-msg">⚠ {{ error }}</div>
{% endif %}
```

### 5.4 Forms

```html
<div class="form-group">
  <label class="field-label">
    Tên trường <span class="required">*</span>
  </label>
  <input type="text" name="field_name" placeholder="..." required>
  <div class="field-hint">Gợi ý hoặc ràng buộc của trường này.</div>
</div>
```

Quy tắc form:
- Dùng `label.field-label` (không phải `label` thông thường — đã bị override một phần bởi auth/login.html)
- Field bắt buộc: thêm `<span class="required">*</span>` sau label text
- Luôn có `name` attribute — SSR cần `name` để đọc form data
- Thêm `required`, `minlength`, `pattern` ở HTML để validate phía client trước khi submit

Checkbox đặc biệt (toggle style):

```html
<label class="toggle-group">
  <input type="checkbox" name="is_admin" value="true">
  <div>
    <div class="toggle-label">Tiêu đề lựa chọn</div>
    <div class="toggle-desc">Mô tả chi tiết về lựa chọn này</div>
  </div>
</label>
```

`.toggle-group` CSS khai báo trong `{% block extra_head %}` của page dùng nó.

### 5.5 Divider

```html
<hr class="divider">
```

---

## 6. Jinja2 conventions

### 6.1 Context variables

Mọi router phải truyền `request` vào context — Jinja2 cần để render `request.url.path`:

```python
return templates.TemplateResponse("module/page.html", {
    "request": request,
    # ... các biến khác
})
```

### 6.2 Navbar visibility

Navbar trong `base.html` chỉ hiện khi có `user` hoặc `admin` trong context:

```python
# Dashboard router — truyền user (JWT payload dict)
{"request": request, "user": current_user_payload}

# Admin router — truyền admin (JWT payload dict)
{"request": request, "admin": admin_payload, "users": users, ...}
```

Navbar dùng `_u.sub` (JWT payload) hoặc `_u.username` (ORM object) — cả hai đều hoạt động.

### 6.3 Active nav link

```html
<a href="/dashboard"
   class="nav-link {% if request.url.path == '/dashboard' %}active{% endif %}">
  Dashboard
</a>

<!-- Prefix match cho sub-routes -->
<a href="/admin"
   class="nav-link {% if '/admin' in request.url.path %}active{% endif %}">
  Admin
</a>
```

### 6.4 Flash qua query param

```html
<!-- Hiển thị flash từ query params (xử lý sẵn trong base.html) -->
<!-- Chỉ cần redirect với đúng format: -->
<!-- /path?flash=Nội dung thông báo&flash_type=success -->
```

### 6.5 Kiểm tra quyền trong template

```html
{# Dùng is_super_admin (bool) và super_admin_username (str) được truyền từ router #}
{% if is_super_admin %}
  <!-- Chỉ super admin thấy -->
{% endif %}

{% if u.username != super_admin_username %}
  <!-- Không hiện với super admin -->
{% endif %}
```

---

## 7. Error states

### 7.1 Form validation error

```html
{% if error %}
<div class="error-msg">⚠ {{ error }}</div>
{% endif %}
```

`.error-msg` CSS khai báo trong `{% block extra_head %}`:

```css
.error-msg {
  background: var(--danger-light);
  border: 1px solid #feb2b2;
  border-radius: 9px;
  padding: 10px 14px;
  color: var(--danger);
  font-size: .85rem;
  margin-bottom: 20px;
}
```

### 7.2 Empty state trong table

```html
{% else %}
  <tr>
    <td colspan="N">
      <div class="empty-state">
        <div class="icon">📋</div>
        Chưa có dữ liệu nào.
      </div>
    </td>
  </tr>
{% endif %}
```

---

## 8. Checklist trước khi submit template mới

- [ ] File extend `base.html` (trừ login)
- [ ] Có `{% block title %}` với tên trang ngắn gọn
- [ ] CSS riêng nằm trong `{% block extra_head %}`
- [ ] Nội dung nằm trong `{% block content %}`
- [ ] JS nằm trong `{% block extra_scripts %}`
- [ ] Không import font mới
- [ ] Không hardcode màu hex (dùng CSS variable)
- [ ] Không copy CSS đã có trong `base.html`
- [ ] Form có `method="POST"`, `action="/đường-dẫn"`, tất cả input có `name`
- [ ] Label dùng class `field-label`
- [ ] Button dùng đúng variant (`btn-primary` / `btn-secondary` / `btn-danger` / `btn-warning`)
- [ ] Table có `empty-state` khi không có dữ liệu
- [ ] Flash error dùng `{% if error %}<div class="error-msg">{% endif %}`
- [ ] Navbar nhận được `user` hoặc `admin` trong context
- [ ] `request` được truyền vào context từ router

---

## 9. Template mới cho module — ví dụ Emission

Khi thêm module `emission`, tạo thư mục `templates/emission/` với cấu trúc:

```
templates/emission/
├── index.html      ← danh sách emission records (dùng table pattern)
├── create.html     ← form nhập liệu (dùng form-card pattern)
└── detail.html     ← xem chi tiết record (dùng card pattern)
```

Skeleton `emission/index.html`:

```html
{% extends "base.html" %}
{% block title %}Emission Records{% endblock %}

{% block extra_head %}
<style>
  /* CSS riêng cho trang này */
</style>
{% endblock %}

{% block content %}
<div class="page">
  <div class="page-header">
    <div>
      <div class="page-title">Emission Records</div>
      <div class="page-subtitle">Quản lý dữ liệu phát thải cảng biển</div>
    </div>
    <a href="/emission/create" class="btn btn-primary">＋ Thêm mới</a>
  </div>

  {% if flash is defined and flash %}
  <div class="flash {{ flash_type | default('success') }}">{{ flash }}</div>
  {% endif %}

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Cảng</th>
          <th>Loại phát thải</th>
          <th>Giá trị</th>
          <th>Ngày ghi nhận</th>
          <th>Thao tác</th>
        </tr>
      </thead>
      <tbody>
        {% if records %}
          {% for r in records %}
          <tr>
            <td style="color:var(--text-muted);font-size:.8rem">{{ r.id }}</td>
            <td>{{ r.port_name }}</td>
            <td>{{ r.emission_type }}</td>
            <td>{{ r.value }} {{ r.unit }}</td>
            <td style="color:var(--text-muted);font-size:.85rem">
              {{ r.recorded_at.strftime('%d/%m/%Y') }}
            </td>
            <td>
              <div style="display:flex;gap:6px">
                <a href="/emission/{{ r.id }}" class="btn btn-sm btn-secondary">Xem</a>
                <form method="POST" action="/emission/delete/{{ r.id }}" style="display:inline">
                  <button type="submit" class="btn btn-sm btn-danger"
                          onclick="return confirm('Xoá record này?')">🗑</button>
                </form>
              </div>
            </td>
          </tr>
          {% endfor %}
        {% else %}
          <tr>
            <td colspan="6">
              <div class="empty-state">
                <div class="icon">📊</div>
                Chưa có dữ liệu phát thải nào.
              </div>
            </td>
          </tr>
        {% endif %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
```
