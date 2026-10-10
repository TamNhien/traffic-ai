# Traffic AI V0.5.71 — Giao diện bảo mật dọc + Kiểm tra độ mạnh mật khẩu

## Các cải tiến

- **Tài khoản của tôi**: ô mật khẩu hiện tại, mật khẩu mới, xác nhận mật khẩu và nút đổi mật khẩu xếp theo **chiều dọc**, có chiều rộng hợp lý thay vì kéo ngang toàn màn hình.
- **Quản lý người dùng & phân quyền**: các trường tên đăng nhập, họ tên, vai trò, mật khẩu tạm, xác nhận mật khẩu tạm và nút tạo tài khoản theo bố cục một cột, đáp ứng cả desktop/mobile.
- **Hiện / ẩn mật khẩu ngay trong ô nhập** bằng nút biểu tượng mắt, hỗ trợ bàn phím và trợ năng. Áp dụng cho đăng nhập, đổi mật khẩu, tạo tài khoản và đặt lại mật khẩu.
- **Độ mạnh mật khẩu (ước tính)**: thanh chỉ báo Yếu / Trung bình / Mạnh, danh sách điều kiện có dấu kiểm ngay khi nhập. Trạng thái này là thông tin hỗ trợ, không phải phép đo an toàn tuyệt đối.
- **Quy tắc bắt buộc cho MẬT KHẨU MỚI**: 12–128 ký tự, tối đa 512 byte UTF-8, có đủ chữ hoa, chữ thường, số và ký tự đặc biệt (Unicode thuộc nhóm Letter Uppercase, Letter Lowercase, Decimal Digit, Punctuation/Symbol). Dấu cách không được coi là ký tự đặc biệt. Giao diện **và backend** cùng kiểm tra, kể cả khi gọi API trực tiếp. Mật khẩu hiện có không bị vô hiệu hóa khi nâng cấp; sẽ được kiểm tra quy tắc mới lúc người dùng đổi mật khẩu.
- Khi đổi, tạo hoặc reset mật khẩu, người dùng cần **nhập lại mật khẩu xác nhận** trước khi nút thực hiện được kích hoạt. Đặt lại mật khẩu không còn dùng `window.prompt` để nhập mật khẩu, thay bằng form bảo mật ngay trong trang quản lý.
- Tiếp tục băm **Argon2id** (không lưu plaintext), cookie HttpOnly/Secure, CSRF, RBAC và thu hồi phiên cũ sau khi đổi / đặt lại mật khẩu. Không thay thuật toán đếm xe, AI, GT hoặc benchmark.
- Alembic migration `0085_password_policy_v0571` chỉ cập nhật `system_settings.schema_version`; **không đổi cấu trúc bảng hay xóa dữ liệu**. Thêm ba bài kiểm thử hồi quy backend V0.5.71 và contract kiểm tra UI/API trong `scripts/test.ps1`.

## Nâng cấp và chạy trên Windows

Giải nén full source V0.5.71 vào thư mục dự án (giữ `.env` hiện có, dữ liệu PostgreSQL và các video/model cũ nếu đã có), sau đó chạy PowerShell:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\test.ps1
.\scripts\start.ps1
# Khi chạy ổn và đã kiểm tra trực tiếp trên trình duyệt:
.\scripts\publish.ps1
```

Nếu `start.ps1` báo lỗi xác thực PostgreSQL, tham khảo hướng dẫn V0.5.70 **ở bên dưới**; không xóa volume và không tự ý đặt lại mật khẩu database. Khi triển khai, frontend cần được **build lại** từ source để nhận giao diện mới; có thể dùng Ctrl+F5 để bỏ cache trình duyệt.

## Kiểm chứng được trong môi trường phát triển

- Backend: **160/160 tests passed** (bao gồm 3 bài kiểm thử quy tắc mới, API create/change/reset và khả năng đăng nhập với hash cũ).
- AI Service: **631/631 tests passed**; thuật toán AI không sửa đổi.
- Frontend: parse cú pháp JSX qua TypeScript thành công. **Chưa chạy được `npm run build`** trong sandbox vì không kết nối được `registry.npmjs.org`; `scripts/test.ps1` trên máy Windows có Docker sẽ cài dependency, audit và build frontend thật. Chưa thử nghiệm Docker/PowerShell, PostgreSQL thật hoặc UI tương tác bằng trình duyệt trên máy người dùng.

---

# Traffic AI V0.5.70 — PostgreSQL Credential Recovery + Fail-fast Startup

## Vì sao PostgreSQL healthy nhưng Backend không thể start?

Log từ máy Windows xác nhận `FATAL: password authentication failed for user "traffic_admin"` (SQLSTATE 28P01). Cơ sở dữ liệu cũ tồn tại trong `traffic_ai_postgres_data` và có mật khẩu role đã lưu; thay đổi `POSTGRES_PASSWORD` trong `.env` / Docker Compose **không tự đổi mật khẩu role trong database đã khởi tạo**. `pg_isready` có thể báo ready khi authentication của Backend vẫn sai. Không liên quan Argon2id password cho người dùng Dashboard.

### Nâng cấp V0.5.70

1. Chặn startup ngay sau PostgreSQL stage nếu kết nối TCP/SCRAM bằng `POSTGRES_PASSWORD` hiện tại không thành công. Không đợi Backend restart 30 lần rồi timeout 180 giây.
2. Nếu `.env` còn mật khẩu mẫu nhưng đã có named database volume, **không tự sinh secret mới** đè lên cấu hình đang cần khôi phục.
3. Thêm `scripts/repair-postgres-auth.ps1`: dùng `psql \password <role>` nhập mật khẩu ẩn hai lần, không gửi plaintext qua CLI, history, hoặc SQL command. Sau đó xác thực lại bằng TCP/SCRAM. Cần sao chép mật khẩu từ `.env` tại máy cục bộ; không gửi mật khẩu qua chat.
4. Backend thoát sớm, log lý do rõ ràng nếu PostgreSQL từ chối password. Không chỉnh sửa dữ liệu, volume hay bảo mật PostgreSQL; không tắt SCRAM.
5. Thêm bốn regression `test_v0570_*`, contract PowerShell và migration `0084_postgres_auth_guard_v0570` (chỉ tăng `schema_version`). Không đổi AI counting, Gate, benchmark, database event, user Argon2id hoặc RBAC.

### Khôi phục database hiện tại (không xóa dữ liệu)

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
notepad .env
# Xác nhận POSTGRES_PASSWORD có mật khẩu mạnh; KHÔNG chia sẻ giá trị.
# PostgreSQL cần đang chạy:
docker compose up -d --no-deps postgres
.\scripts\repair-postgres-auth.ps1
# Khi được hỏi, dán POSTGRES_PASSWORD từ .env hai lần (ẩn ký tự).
.\scripts\test.ps1
.\scripts\start.ps1
# Khi đã kiểm tra thật sự hoạt động:
.\scripts\publish.ps1
```

Nếu kết nối psql qua Unix socket bị từ chối, **không** chuyển `pg_hba.conf` sang `trust`. Dừng lại và dùng tài khoản DB có quyền truy cập hợp lệ để khôi phục. Lưu ý việc thay đổi mật khẩu role có thể làm các ứng dụng khác dùng chung role mất kết nối; cấu hình của chúng cũng cần đồng bộ.

---

# Traffic AI V0.5.69 - Bounded PostgreSQL/Backend startup diagnostics

V0.5.68 could appear stuck after Docker image build while Compose waited
for backend `service_healthy` for multiple minutes. V0.5.69 stages startup:
PostgreSQL -> Backend/Alembic -> AI Service (GPU with CPU fallback) ->
Frontend/Gateway. Each stage has a finite health timeout and prints logs
when it fails. The system will stop waiting and report the real migration,
connection or healthcheck error instead of silently waiting.

**Important:** A screenshot of `backend Waiting` does not establish why
Backend is unhealthy. This release fixes endless waiting/observability;
it does not claim to fix an unknown database migration error without logs.
The Backend entrypoint avoids unconditional `ALTER TABLE alembic_version` on every boot and sets PostgreSQL lock/statement limits for migration diagnostics.
No destructive DB commands are issued: existing `traffic_ai_postgres_data`
volume, `.env`, model files, camera event data and GT are kept.

Run in PowerShell:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
# If backend still cannot become healthy:
.\scripts\diagnose-startup.ps1
# After startup and functional tests pass:
.\scripts\publish.ps1
```

The old `create-admin.ps1` workflow remains unchanged. Version 0.5.69 is
consistent across Frontend, Backend and AI Service. Alembic head is
`0083_bounded_startup_v0569` (updates schema version only).

---

# Traffic AI V0.5.68 — Quản lý người dùng & bảo mật Argon2id

## Mới: đăng nhập, phân quyền và audit thực sự hoạt động

**Lưu ý khi nâng từ V0.5.67:** Sau khi cập nhật source và chạy `start.ps1`, mọi API/UI dữ liệu (ngoại trừ health) yêu cầu đăng nhập. Không có mật khẩu mặc định và không có API đăng ký công khai. Chạy `scripts/create-admin.ps1` **một lần** trên máy quản trị sau khi backend đã healthy. Database, GT, sự kiện, mô hình và AI counting được giữ nguyên; Alembic revision `0082_security_auth_v0568` bổ sung trường `users.role`, `must_change_password`, `last_login_at` và ba bảng `auth_sessions`, `login_limits`, `security_audit`.

### Mật khẩu: băm chứ không mã hóa có thể giải ngược

Sử dụng **Argon2id** thông qua argon2-cffi 25.1.0, cấu hình `m=65536 KiB (64 MiB), t=3, p=2`, salt 16 byte riêng từng tài khoản, output 32 byte. Không ghi mật khẩu plaintext vào PostgreSQL/log và không cung cấp chức năng giải mã. Yêu cầu 12–128 ký tự, có chữ và số, tối đa 512 byte UTF-8; check_needs_rehash cho các hash Argon2id cũ. Quy tắc này đáp ứng mức tối thiểu Argon2id khuyến nghị trong OWASP Password Storage Cheat Sheet; không khẳng định mật khẩu yếu sẽ được bảo vệ tuyệt đối.

### Kiến trúc xác thực

- Session token ngẫu nhiên 256-bit, chỉ lưu SHA-256(token) trong `auth_sessions`; cookie `__Host-traffic_ai_session` có **Secure, HttpOnly, SameSite=Strict, Path=/** và hạn 8 giờ; không sử dụng localStorage, không JWT lưu client. Có thu hồi phiên khi logout, đổi mật khẩu, khóa tài khoản, thay vai trò, hoặc reset mật khẩu.
- CSRF token ràng buộc phiên, backend chỉ lưu SHA-256 của token đó. Mọi POST/PUT/PATCH/DELETE đã đăng nhập cần `X-CSRF-Token` và `Origin` phải trùng origin HTTPS hiện tại. Frontend `secureFetch` tự gắn header. Từ chối request thay đổi trạng thái thiếu token hoặc sai Origin.
- Khóa thử đăng nhập sai sau 5 lần trong 15 phút theo IP và tên tài khoản; phản hồi sai mật khẩu không tiết lộ tên tồn tại; phiên cookie không lưu plaintext trong DB.
- Auth middleware mặc định từ chối mọi `/api/*` chưa đăng nhập (trừ `/api/health` phục vụ Docker và `/api/auth/login`). `/api/internal/*` vẫn phải qua token AI riêng, nhưng **gateway không cho public gọi**. Video browser `/ai/streams/*` cần session hợp lệ; `/ai/media/video` còn cần Operator/Admin; các endpoint AI khác bị chặn tại Nginx.
- Nginx bật TLS, HSTS, CSP hạn chế script-origin, X-Frame-Options DENY, Referrer-Policy, nosniff. PostgreSQL chỉ bind **127.0.0.1:5445** ở host, không công khai trên LAN. Môi trường mới tự sinh mật khẩu PostgreSQL ngẫu nhiên từ template; **mật khẩu PostgreSQL đã tồn tại không tự đổi** để tránh làm mất kết nối với volume dữ liệu cũ. Nếu `.env` cũ vẫn dùng mật khẩu ví dụ, người quản trị nên chủ động đổi trong PostgreSQL và `.env` sau khi sao lưu. `.env` cũ có AI_SHARED_TOKEN ví dụ công khai sẽ được `start.ps1` thay bằng chuỗi ngẫu nhiên; các secret do người dùng tự đặt được giữ nguyên.

### Vai trò và hành vi

| Vai trò | Xem Dashboard/benchmark | Thay đổi camera, AI, GT, dataset, training | Tạo/khóa/sửa user và xem audit |
|---|---|---|---|
| Admin | Có | Có | Có |
| Operator | Có | Có | Không |
| Viewer | Có, chỉ đọc | Không | Không |

Viewer không nhận RTSP source URL từ `/api/cameras`, `/api/sessions` và benchmark JSON (trường `source_url` được che thành `restricted`); endpoint benchmark ZIP export, source inspection và raw ảnh dataset cần Operator trở lên. Các quyền được kiểm tra **tại backend**, không dựa vào ẩn nút UI. Admin không thể tự khóa hoặc tự hạ vai trò; hệ thống từ chối xóa quyền của Admin cuối cùng. Các thao tác đã xác thực (ngoại trừ reads) có audit action/path/HTTP outcome, không lưu body, mật khẩu hoặc query string; audit nhạy cảm (`users.*`, `auth.*`) ghi trong giao dịch. Với thao tác thông thường, audit sau response là best-effort nếu DB bị sự cố — xem giới hạn bên dưới.

### Khởi tạo Admin đầu tiên — không có tài khoản/mật khẩu cố định

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1

# Chạy trên máy chủ quản trị sau khi backend đã healthy.
# Mật khẩu được nhập ẩn, xác nhận 2 lần.
.\scripts\create-admin.ps1
```

Mở `https://traffic-ai.test:8443` và đăng nhập. Khi Admin tạo user mới, tài khoản phải **đổi mật khẩu tạm ngay lần đăng nhập đầu tiên**. Trên sidebar có **Tài khoản** (mọi vai trò) và **Người dùng** (chỉ Admin). Trong Người dùng: tạo user, tìm kiếm, sửa họ tên, phân vai, khóa/mở, reset mật khẩu, thu hồi phiên và xem nhật ký. Trong Tài khoản: tự đổi mật khẩu hoặc đăng xuất tất cả thiết bị. Mỗi lần đổi/reset mật khẩu hoặc đổi vai trò sẽ thu hồi toàn bộ session của user đó.

Sau khi chạy thử ổn, phát hành với **một lệnh**:

```powershell
.\scripts\publish.ps1
```

Tự động dùng `VERSION=0.5.68` tạo tag `v0.5.68` và GitHub Release. Nếu nâng cấp vào cài đặt cũ có user nhưng chưa có Admin, **không cấp Admin tự động**; thực hiện `create-admin.ps1`. Không upload `.env`, `gateway/certs/*.key`, database hoặc model weights vào ZIP/GitHub.

### Bảo mật và giới hạn đã biết

Argon2id dùng băm một chiều, không phải mã hóa đảo ngược. Chưa triển khai WebAuthn/passkeys hoặc MFA/TOTP, chưa có SIEM/tamper-proof external audit, chưa có ký riêng mỗi record audit; không gọi đây là bảo mật tuyệt đối. Logout/revocation kiểm tra trong PostgreSQL cho mỗi request. CSRF dựa vào cùng origin, nhưng phòng chống XSS cũng quan trọng. Kiểm thử thực tế hệ thống dùng Docker/PowerShell, cookies Nginx và chức năng video trên máy Windows vẫn cần thực hiện sau cài đặt. Không thay chính sách benchmark/GT và không khẳng định Recall/F1 cải thiện trong V0.5.68.

Tham khảo OWASP: <https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html> và <https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html>.

---

## Lịch sử phiên bản trước

# Traffic AI — lịch sử V0.5.67: Chẩn đoán cạnh tranh GT ↔ AI theo timecode

Nâng cấp trực tiếp từ **V0.5.66** do người dùng tải lên. Bản này bổ sung trạng thái sẵn sàng benchmark và giữ bản sửa van chở hàng thành **Xe tải**. Đơn vị đếm là lượt cắt vạch; một xe quay lại cắt vạch lần nữa được tính thêm một lượt.

## Nâng cấp V0.5.67 — giải thích "GT = AI nhưng vẫn có lọt/dư"

Ảnh benchmark #49/session #172: **GT 149, AI 149, khớp 135, lọt 14, dư 14, F1 90,6%, class đúng 98,5%**. Đây **không phải hồi quy mới so với benchmark #46/session #169 ở ảnh V0.5.63**: cả hai ảnh đều có 135/14/14. Tổng 149 bằng nhau chỉ là sai số số lượng bằng 0; báo cáo dùng global timestamp matching một-một trong cửa sổ ±0,75 giây nên có thể tồn tại GT không ghép và AI chưa ghép cùng lúc.

Trace trong `camera_1(20261009-124508).rar` có 23.650 observation frames, 195 event-delivery receipts: **149 created, 46 deduplicated**, drain thành công. Ví dụ mốc GT OUT 01:09.457 có event thực **69.4566 giây, track 20863, backend_event_id 10275, outcome created**. Nếu GT này vẫn hiện là chưa ghép, cần xem *AI event đã được sử dụng trong GT nào*, không được coi đây là bằng chứng AI không đếm.

**Backend `temporal_assignment_audit`:** báo cáo bổ sung số GT chưa ghép có event DB gần đó nhưng *đã gán cho GT khác*; số GT không có event DB trong cửa sổ; số AI chưa ghép có GT gần đó nhưng *đã gán AI khác*. Các record evidence kèm ID, chênh lệch thời gian, hướng và `identity_proven: false`. Tối đa 4 cạnh tranh gần nhất mỗi mục, tránh payload lớn.

**Giao diện:** Khi GT tổng bằng AI tổng mà vẫn có miss/FP, hiển thị giải thích cạnh tranh timecode và cảnh báo chỉ số GT chưa ghép không luôn đồng nghĩa xe thật bị AI bỏ sót. Từng thẻ mốc có chú thích phân biệt event đã được ghép GT khác hay hoàn toàn không có event DB trong cửa sổ. Điều chỉnh line-height/overflow để chữ không đè nhau.

**Bất biến quan trọng:** Không tự đổi GT, loại xe, hướng, timecode, tolerance, thuật toán ghép, event hoặc F1. Bản này **cải thiện tính minh bạch chẩn đoán**, không tự nhận tăng độ chính xác đếm. Muốn sửa chính xác 14 cặp vật lý cần ZIP **Tải hồ sơ benchmark** của đúng benchmark #49 (chứa toàn bộ `ground-truth.json`, `events.json`, `report.json`, manifest + trace). Chỉ RAR ảnh/trace không đủ quan hệ GT ↔ event để kết luận 14 pair đều là lỗi AI.

Riêng mốc GT 10:41.981 "Ô tô" nhưng AI "Xe tải" cần kiểm tra lại quy ước xe van chở hàng: V0.5.65/V0.5.66 đã chủ ý giữ nhãn TRUCK theo yêu cầu trước; không tự đổi Ground Truth thành xe tải.

## Kiểm thử V0.5.67

Đã chạy 140 backend + 631 AI pytest pass trong sandbox với SQLite memory và shim test-only `httpx2→httpx` do môi trường thiếu `httpx2`. Đã có 5 regression mới cho trường hợp tổng bằng nhau mà không match, GT cạnh tranh một AI, AI gần GT đã ghép, hướng sai không thay điểm và GT trống không chấm. Chưa chạy Docker/GPU/PowerShell/Vite đầy đủ trong sandbox; sau khi tải ZIP phải chạy `scripts/test.ps1` trên Windows trước khi publish.

## Vấn đề trong kết quả mới

Ảnh và trace V0.5.65, session 171 cho thấy 149 lượt được lưu: 146 xe máy, 1 xe đạp, 2 xe tải; IN 68 / OUT 81. Worker đề xuất 195 lượt, backend gộp 46, Human Guard loại 30. Có 195 terminal receipts, 149 created + 46 deduplicated; drain hoàn tất và pending/dropped đều 0.

Hai lượt van trước đây bị ghi thành Ô tô nay được lưu **TRUCK**:

| Lượt | Canonical | Source / observed frame | Backend event |
|---|---:|---:|---:|
| OUT10:41.931 (641.9311s) | 254023 | 16049 /16050 | 10212 |
| IN14:42.290 (882.2898s) | −22 | 22058 /22059 | 10254 |

Đây là kết quả người dùng đã chạy trên .65, không phải model replay của .66 trong môi trường kiểm tra. So với session 170, 195 receipts giữ tracking/time/frame/direction/method/geometry/outcome; hai class CAR đổi thành TRUCK, confidence IN lấy từ truck lock. Không dùng hai canonical để khẳng định danh tính cùng một xe vật lý.

**Benchmark #48 chưa có GT:** ảnh hiển thị GT 0 / AI 149 và có nút sao chép 149 GT từ benchmark #47. F1 = 0% / 149 đếm dư ở màn hình cũ chưa phải đánh giá hợp lệ về chất lượng AI. Không có GT/event assignment export của phiên mới để kết luận Recall/F1/class accuracy.

## Chức năng mới

### GT trống có trạng thái chuẩn bị riêng

Khi chưa có mốc Ground Truth, báo cáo hiển thị **Chưa có Ground Truth**. Vẫn xem được tổng AI, số AI theo loại xe, Integrity và tải hồ sơ benchmark. Khớp/lọt/dư/sai số/Recall/Precision/F1/class đúng hiển thị dấu **—**; không liệt kê 149 AI là 149 xe đếm dư hoặc gán nguyên nhân nội suy/rescue cho GT trống.

Thông báo hướng dẫn sao chép GT từ benchmark tương thích nếu có, với source/target ID và số GT rõ ràng, hoặc xem clip để đánh dấu. Việc sao chép dùng nút hiện có và yêu cầu bạn bấm; hệ thống không tự tạo hoặc sửa GT từ AI events. Nút Đối chiếu lại chỉ dùng khi benchmark có GT; Tải hồ sơ benchmark vẫn dùng được khi GT = 0.

Có GT nhưng AI = 0 vẫn là một báo cáo được chấm: xe GT chưa ghép là xe lọt, Recall/Precision/F1 bằng 0. Đây là trường hợp khác với thiếu GT. Có mốc GT chỉ xác nhận dữ liệu chấm đã tồn tại, không chứng minh người dùng đã đánh dấu đầy đủ toàn clip.

Hiện chưa có trường xác nhận riêng cho một clip đã được kiểm chứng không có xe. Vì vậy GT = 0 / AI = 0 cũng là chưa có dữ liệu chấm, không tự nhận điểm 100%.

### API và export thống nhất

GET /api/benchmarks/{id}/report và POST /api/benchmarks/{id}/reconcile có thêm:

```json
{"report_readiness":{"status":"needs_ground_truth","scoring_available":false,"reason":"no_ground_truth"}}
```

Với GT>0: status="ready", scoring_available=true, reason=null; trường ready bên ngoài thống nhất với scoring_available, kể cả AI0. Các field cũ của báo cáo có GT giữ nguyên, gồm global temporal matching, tolerance, missed matching audit và diagnostics.

Với GT0, các score/count-error fields là JSON null, các danh sách assignment/missed/false-positive/class-mismatch rỗng. ground_truth_total, ai_total, số GT/AI trong per_class và per_direction vẫn là counts thực; difference/correct_matches chưa chấm lànull. report.json xuất trong hồ sơ giữ đúng trạng thái này, còn events.json vẫn giữ AI events để review.

Client ngoài giao diện cần đọc report_readiness.scoring_available trước khi tính hoặc định dạng điểm; không chuyểnnull thành0%. Giao diện vẫn xử lý báo cáo API cũ qua ground_truth_total, không dùng ready cũ để loại bỏ trường hợp AI0.

## Giữ các chức năng đã nâng cấp

Giữ domain corroboration khi muốn đổi TRUCK semantic lock đang sống thành CAR: hai CAR wins theo source clock và ngưỡng hiện có, đồng thời đủ domain CAR proof; generic CAR đơn độc không tự vượt truck lock. Giữ deterministic all-frame crossing admission, source frame/time của event, refiner budgets/caches, terminal receipts và delivery drain.

Gate/Road Zone/cooldown, tracking, Human Guard, backend dedup, global temporal assignment và tolerance không đổi. Giữ matching audit tối đa4 event đã ghép, disclosure stack tránh chồng chữ và dashboard/GT–Report50/50. Không đổi model weights hoặc taxonomy để làm đẹp score.

## Chạy trên Windows

Giải nén toàn bộ ZIP và chép source vào thư mục dự án hiện tại. Chạy PowerShell:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.67 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443 và **Ctrl+F5**. Với benchmark48, bấm sao chép149GT từ **benchmark47** nếu clip/vạch tương thích. Review GT van quanh10:41.93OUT và14:42.29IN theo quy ước van chở hàng là Xe tải; giữ timecode/hướng theo clip đã kiểm tra. Đối chiếu lại rồi Tải hồ sơ benchmark để có cả GT và AI assignments cho lần phân tích tiếp theo.

Publisher lấy version từ VERSION, kiểm tra source trước khi commit/push/tag và tạo Release. Không force hoặc viết lại tag cũ. Muốn publish cần Git/GitHub CLI, tài khoản đã đăng nhập và quyền vào repository. Lệnh trên thực hiện xuất bản khi bạn chạy; quá trình kiểm tra bản này chỉ dùng Git cục bộ, chưa push hoặc tạo Release thật.

## Phiên bản công nghệ và kiểm tra

VERSION/frontend/API health/start message đồng bộ0.5.67. Alembic head 0081_temporal_audit_v0567, parent 0080_benchmark_ready_v0566; migration chỉ cập nhật schema_version0.5.67, downgrade về0.5.66, không thay GT/events/schema.

Docker/CI/packageManager giữ npm12.2.0 và Node26.10.0. npm12.2.0 được đối chiếu [official npm CLI latest](https://github.com/npm/cli/releases/latest) ngày09/10/2026. PowerShell scripts UTF-8 no-BOM/CRLF; source/config text khác LF.

Kết quả cụ thể và phạm vi thực thi nằm trong **VERIFICATION.md**. Offline assertions dùng algorithm modules thực và worker/backend helper trích AST; frontend kiểm bằng Babel/Node VM và JSX có kiểm soát. Môi trường hiện tại không chạy full dependency-pinned pytest, HTTP/ORM/database, native PowerShell, Docker, Vite/browser/GPU/model replay. Không có F1/class accuracy .66 được đo từ clip.
