# Traffic AI V0.5.74 — PostgreSQL Backup & Restore / Migration Kit

## Mới trong V0.5.74

**Nền V0.5.73 được giữ nguyên** (Unicode users / security / counting). Không thay đổi thuật toán đếm hay tham số AI; benchmark Session #175 vẫn chưa có bằng chứng để kết luận đã giải quyết 10 lọt / 14 dư.

- Trang **Admin → Backup / Restore** (`#backups`): sao lưu thủ công, xem bản sao, tải `.dump` PostgreSQL 18, tải ZIP chuyển máy, tải ZIP/.dump lên máy mới, yêu cầu khôi phục, theo dõi tác vụ và lỗi.
- Service `backup-worker` riêng, xây từ `postgres:18.6`: dùng `pg_dump -Fc`, `pg_restore --list`, SHA-256, ghi tệp tạm rồi thay tên atomically; không cấp Docker socket cho backend.
- **Backup tự động** mặc định 24 giờ/lần, giữ 14 bản tự động; có thể chỉnh lịch trực tiếp trên web (1–720 giờ; giữ 1–365 bản). Chỉ bản tự động cũ bị dọn; không tự xóa backup thủ công/import.
- **Khôi phục thận trọng**: kiểm tra SHA-256 → tạo database tạm → `pg_restore --exit-on-error --single-transaction` → kiểm tra `alembic_version` → tạm khóa API và đổi tên database; database cũ được giữ dưới tên `traffic_old_<12 ký tự>` để có thể hoàn tác. Một khoảng gián đoạn kết nối là cần thiết. Sau khi thành công, chạy lại `start.ps1` để backend migration và AI khởi động trở lại.
- Gói ZIP chuyển máy chỉ chứa `database.dump`, `manifest.json`, `TRANSFER.txt`, **không chứa `.env`, khóa bí mật hoặc file model/video**. ZIP phải giữ kín vì dữ liệu PostgreSQL chứa thông tin người dùng và sự kiện camera.
- Migration `0088_backup_scheduler_v0574.py` tiếp nối V0.5.73, chỉ cập nhật schema version, không sửa bảng dữ liệu. Danh mục backup lưu độc lập trong Docker volume **`traffic_ai_backup_data`**; PostgreSQL tiếp tục dùng `traffic_ai_postgres_data`.

### Kiểm tra & chạy trên Windows

Giải nén lên `D:\LienThongDH\DoAn\traffic-ai` sau khi đã lưu bản sao của `.env`, volume database và các thư mục dữ liệu hiện có. **Không chạy `docker compose down -v`**. Docker Desktop cần ở chế độ Linux containers và đang chạy.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Kiểm tra backup worker và volume:

```powershell
docker compose ps
docker compose logs --tail 80 backup-worker
docker volume inspect traffic_ai_postgres_data
docker volume inspect traffic_ai_backup_data
```

Khi mọi bài test và các thao tác sao lưu/thử khôi phục thực tế đã ổn định, phát hành:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\publish.ps1
```

Không chạy `create-admin.ps1`: tài khoản Admin hiện tại đã có.

### Di chuyển sang máy khác

1. Máy cũ: dừng các phiên AI đang chạy để có ảnh chụp trạng thái nhất quán cho cả dữ liệu file ngoài PostgreSQL; vào **Backup / Restore → Sao lưu ngay**. Chờ tác vụ *Hoàn thành*, bấm **Tải ZIP chuyển máy**.
2. Sao lưu riêng **`.env`** (chứa mật khẩu PostgreSQL và token nội bộ), `models/`, `videos/`, `snapshots/`, `datasets/`, `training-runs/`, `gateway/certs/` nếu cần. Tránh chia sẻ các file nhạy cảm qua kênh công khai. Không nên ghi đè `.env` của máy đích khi đã có DB khác mà không kiểm tra mật khẩu.
3. Máy mới: cài Docker Desktop Linux containers, chép source V0.5.74 và các thư mục cần thiết, cấu hình `.env` hợp lệ, chạy `start.ps1` để khởi tạo PostgreSQL 18 và người dùng Admin ban đầu trên máy đích (nếu hoàn toàn mới có thể cần quy trình bootstrap Admin hiện hành). Tài khoản từ nguồn sẽ được đưa sang khi restore.
4. Trên máy đích, đăng nhập Admin → **Backup / Restore → Nhập bản sao lưu** → chọn ZIP. Hệ thống kiểm tra cấu trúc và checksum; *chưa thay dữ liệu*. Sau đó chọn bản mới nhập, nhập đúng `KHOI PHUC traffic_ai_db` (hoặc tên DB đang cấu hình), xác nhận cảnh báo và chờ trạng thái *Hoàn thành*.
5. Chạy lại `start.ps1` để áp dụng Alembic sau khi chuyển database. Đăng nhập bằng tài khoản Admin/mật khẩu từ máy nguồn, kiểm tra Camera / GT / Benchmark / người dùng / các thư mục video & model.

**Cảnh báo:** khôi phục khi người dùng hoặc AI còn đang ghi dữ liệu có thể làm mất các thay đổi kể từ thời điểm backup. Cần tạm dừng AI, sao lưu máy đích trước khi restore, đảm bảo đủ dung lượng cho cả database tạm và database cũ. Không có bảo đảm zero-downtime. Nếu job restore thất bại **trước lúc swap**, dữ liệu DB đang hoạt động không bị thay thế. Nếu restore thành công, database cũ vẫn còn trong PostgreSQL và có thể được quản trị viên phục hồi thủ công sau khi dừng dịch vụ; không tự động xóa database cũ.

**Giới hạn:** web upload tối đa 1 GiB; nếu dữ liệu lớn hơn, phải chuyển bằng `pg_dump/pg_restore` hoặc nâng đồng bộ giới hạn gateway/API sau khi đánh giá dung lượng. Các tệp model/video không nằm trong PostgreSQL và phải chuyển riêng. Hệ thống này chưa được kiểm thử phục hồi thực tế với Docker Desktop Windows trong môi trường đóng gói, vì vậy cần diễn tập backup/restore trên máy thử trước khi dùng với dữ liệu quan trọng.

### Kết quả kiểm thử mã nguồn

- Backend **171/171**; AI Service **635/635**; Node frontend unit **4/4**; backup-worker riêng **4/4**.
- Python compileall chạy thành công. Backend/AI suite trong môi trường đóng gói dùng shim chỉ phục vụ kiểm thử cho dependency `httpx2` vì không có gói chính xác trong môi trường; shim **không có trong source ZIP**.
- Chưa thực hiện được Docker PostgreSQL restore tích hợp và `npm run build` vì môi trường này không có Docker Engine và NPM registry không phản hồi. Trên máy Windows, `test.ps1` chạy build / test với Docker và npm theo đúng dependency pin của source.

---

## Lịch sử V0.5.73 và các bản trước

# Traffic AI V0.5.73 — Unicode Accounts + Reliable Creation Feedback

## Nguyên nhân tài khoản không được tạo trong V0.5.72

Ở trang Admin, tên đăng nhập **`Đạt`** có chữ `Đ`, trong khi backend phiên bản cũ khai báo regex `^[A-Za-z0-9_.-]+$`; FastAPI trả HTTP **422** vì đầu vào không hợp lệ, không lưu `users`. Frontend chuyển cấu trúc lỗi `detail: [{...}]` thành chuỗi **`[object Object]`** rồi trình bày trong hộp thông báo chung màu xanh. Đây không phải thông báo tạo thành công. **Không cần tạo lại Admin**.

## Nâng cấp V0.5.73

1. **Tạo tài khoản Unicode tiếng Việt**: chấp nhận `Đạt`, `Nhiên`, `Phạm-Vĩnh.Đạt`, chữ số, `_`, `.`, `-`; không cho khoảng trắng, emoji, ký tự vô hình/điều khiển, ký tự đặc biệt. Username dài 3–80 ký tự; họ tên có thể dùng dấu và khoảng trắng bình thường.
2. **Chuẩn hóa đăng nhập NFC + Unicode casefold**, lưu khóa `users.username_key` có **UNIQUE index** ở PostgreSQL. Chống tài khoản trùng do chữ hoa/chữ thường hoặc dấu Unicode tổ hợp; tên hiển thị vẫn giữ nguyên. `Đạt` / `đạt` / `ĐẠT` cùng một định danh. Rate limit đăng nhập dùng cùng khóa chuẩn hóa; giữ Argon2id, RBAC, CSRF và session cookie.
3. **Thông báo thao tác chính xác**: kiểm tra tên đăng nhập ngay khi gõ, phân biệt lỗi (đỏ), thành công (xanh), cần kiểm tra lại (vàng). Trích xuất thông báo FastAPI 422 theo trường, không hiện `[object Object]` và không làm lộ mật khẩu.
4. **Lưu là phải hiển thị**: khi server trả HTTP 201 kèm `id` và `username`, giao diện đưa người dùng vừa tạo vào danh sách, xóa bộ lọc tìm kiếm, tô viền tài khoản mới và tải lại danh sách bằng `cache: no-store`. Nếu GET thất bại, vẫn giữ tài khoản đã được server xác nhận và báo rõ lỗi tải danh sách; nếu bị từ chối POST, không xóa form hoặc thông báo tạo thành công.
5. **Migration** `0087_unicode_usernames_v0573`: backfill `username_key` từ toàn bộ tài khoản đã tồn tại, tạo chỉ mục duy nhất, nâng schema version lên `0.5.73`. Có kiểm tra xung đột canonical để **dừng migration thay vì xóa/đè tài khoản**. Vẫn giữ toàn bộ người dùng, hash mật khẩu, GT, event và session; Postgres khởi động sẽ áp dụng Alembic tự động.
6. Thêm regression backend cho Unicode/tên trùng/đăng nhập/tính bền vững, kiểm thử Node cho thông báo lỗi và regex, thêm contract V0.5.73 vào `scripts/test.ps1`. Gói giữ toàn bộ source V0.5.72.

**Session #175 ngày 11/10/2026:** GT 149 / AI lưu 153 / khớp 139 / lọt 10 / dư 14 / F1 92,1%. Trace 23.650 frame cho thấy worker đề xuất 192 crossing. Chưa có GT + database events đầy đủ trong RAR nên **không chỉnh ngưỡng thuật toán AI trong V0.5.73**; tuyệt đối không coi bản này đạt 0 lọt / 0 dư. Hãy xuất ZIP **Tải hồ sơ benchmark** để xác minh đủ từng lượt.

### Cập nhật source và chạy đúng thứ tự (Windows PowerShell)

Giải nén **full source ZIP** vào `D:\LienThongDH\DoAn\traffic-ai`, giữ file `.env`, các model/video cá nhân và **PostgreSQL volume**; nên sao lưu database trước migration, tuyệt đối không xóa volume hoặc tạo lại Admin. Docker Desktop phải ở trạng thái Engine running. Sau đó:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

# Mở khóa toàn bộ script PowerShell
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Kiểm tra source
.\scripts\test.ps1

# Khởi động hệ thống (tự chạy migration)
.\scripts\start.ps1
```

Sau khi trình duyệt đã tải phiên bản V0.5.73 (**Ctrl + F5** nếu còn cache), vào **Quản lý người dùng & phân quyền**, tạo lại tài khoản **`Đạt`** nếu yêu cầu trước đó đã bị HTTP 422 (tức chưa hề được lưu). Thông báo thành công phải có `@Đạt` và mã số `#id`; kiểm tra ngay trong danh sách và thử đăng nhập bằng mật khẩu tạm để buộc đổi mật khẩu lần đầu.

Nếu cần đánh giá benchmark trước khi phát hành, xuất ZIP hồ sơ benchmark và chạy:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\check-benchmark.ps1 -ExportZip .\benchmark-latest.zip -MaxMissed 0 -MaxExtra 0
```

Chỉ khi `test.ps1`, khởi động và benchmark đều đạt yêu cầu mới phát hành bằng:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\publish.ps1
```

### Giới hạn kiểm tra

Backend 163/163, AI Service 635/635, frontend Node 4/4 và benchmark gate 5/5 đạt trong sandbox tương thích. **Chưa build Vite/NPM thực tế, chưa thử migration với PostgreSQL thực tế hoặc chạy GPU với video gốc.** Kiểm tra Docker / PostgreSQL / browser thực tế bằng `scripts/test.ps1` trên máy Windows trước khi publish. Xem `VERIFICATION.md`.

---

# Traffic AI V0.5.72 — Stable Replay + Benchmark Regression Gate

## Căn cứ từ Session #174 (camera_1 ngày 10/10/2026)

- **GT 149, AI database 149, khớp 135, lọt 14, dư 14, F1 90,6%**. Tổng GT = AI **không** đồng nghĩa với benchmark đúng.
- Trace 23.650 frame: worker đề xuất 195 crossing; backend tạo 149 event và từ chối 46 event (22 `same-track-direction-flip`, 19 `same-track-repeat-jitter`, 3 `crossing-signature`, 1 `secondary-shadow-signature`, 1 `direct-secondary-shadow`). Đây là **telemetry**, không phải căn cứ tự khôi phục các mốc GT.
- So sánh source gốc V0.5.70 với V0.5.71: `ai-service/app/counting.py`, `worker.py`, `tracking.py`, `async_tasks.py` và `backend/app/benchmarking.py` **giống hệt từng byte**. Không thể kết luận giao diện mật khẩu V0.5.71 gây thay đổi thuật toán đếm. Có thể còn các biến đầu vào khác (model/clip/GT/geometry/runtime), chưa có hồ sơ xuất GT/events để xác nhận.

## Những thay đổi thực sự trong V0.5.72

1. **Deterministic MP4 replay — stable track order**: trước khi xử lý continuation/đếm, sắp xếp những detection **đã được ByteTrack gán ID** theo `(raw_track_id, bounding box)`, tránh kế thừa thứ tự mảng từ YOLO/NMS vốn có thể khác giữa các lần chạy. Chỉ áp dụng cho phát lại video với `AI_VIDEO_DETERMINISTIC=1`; không thay ngưỡng vạch, ROI, cứu track, class refinement, cooldown, không bỏ xe hay thêm crossing và không làm chậm camera RTSP. Với CAR/TRUCK/BUS xung đột và confidence **bằng nhau**, dùng tie-break cố định để quyết định ô giữ lại.
2. **Benchmark release quality gate**: thêm `scripts/benchmark-gate.py` và `scripts/check-benchmark.ps1`; nhận **ZIP “Tải hồ sơ benchmark”** từ giao diện (có `report.json`, `ground-truth.json`, `events.json`, `manifest.json`). Xác thực SHA-256/size, GT hiện diện, integrity backend, phương trình `matched + missed = GT` và `matched + extra = AI`; **FAIL nếu số lọt/dư lớn hơn giới hạn**, kể cả khi GT = AI. Không sửa số liệu hay GT.
3. **So sánh baseline đã đo**: baseline JSON ghi kết quả thực tế; khi có baseline chỉ so sánh nếu GT/tolerance/clip geometry tương thích. Không tự gán 0 lọt/0 dư. Có thể thêm `-MaxWrongClass` để chặn sai loại xe.
4. **Migration V0.5.72**: `0086_replay_guard_v0572` tăng duy nhất `system_settings.schema_version`, không đổi bảng, dữ liệu GT, lịch sử event, tài khoản hay mật khẩu. Duy trì bảo mật Argon2id và tính năng tài khoản V0.5.71.

### Lệnh PowerShell mặc định sau mỗi bản build (không tạo lại Admin)

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

# Mở khóa toàn bộ PowerShell scripts
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Kiểm tra source — yêu cầu Docker Desktop đang chạy
.\scripts\test.ps1

# Khởi động hệ thống
.\scripts\start.ps1
```

### Kiểm tra chất lượng trước khi phát hành (bổ sung)

Trong Benchmark Report, chọn **Tải hồ sơ benchmark** sau khi AI hoàn tất phát lại và đã có đủ GT. Sao chép ZIP xuất ra thành `D:\LienThongDH\DoAn\traffic-ai\benchmark-latest.zip` (hoặc dùng đường dẫn thực tế), rồi **mở cửa sổ PowerShell khác**:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\check-benchmark.ps1 -ExportZip .\benchmark-latest.zip -MaxMissed 0 -MaxExtra 0
```

Ví dụ V0.5.71 GT/AI 149/149, khớp 135, lọt 14, dư 14: lệnh trên sẽ **FAIL đúng**, không công nhận chất lượng chỉ bằng số tổng. Sau khi benchmark đạt 0 lọt/0 dư và test/run ổn, phát hành:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\publish.ps1
```

Nếu cần đo baseline của một phiên trước, dùng `python -X utf8 .\scripts\benchmark-gate.py --export .\benchmark-latest.zip --max-missed 14 --max-extra 14 --write-baseline .\benchmark-baseline.json`. Baseline là dữ liệu đã đo, **không** làm thay đổi AI hay việc chấm điểm.

### Giới hạn kiểm chứng

- Có thể test thuần code qua trace + unit test, **không thể xác nhận mức 0 lọt / 0 dư** của V0.5.72 khi chưa có **GT + danh sách event database + clip gốc** cho cùng benchmark và chưa chạy inference GPU Windows. Gói `.rar` của Session #174 chứa ảnh và trace chứ không có bộ GT/event đầy đủ.
- Đợt này hướng vào tính ổn định/tính trung thực của kết quả, **không nới rescue** chỉ để tăng tổng số đếm vì có nguy cơ tăng false positive.
- Xem `VERIFICATION.md` để biết bài nào được test thực tế và giới hạn môi trường.

---

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
