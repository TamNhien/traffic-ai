# Traffic AI V0.5.131 — Tài liệu duy nhất / Hướng dẫn sử dụng

## V0.5.131 — Sửa lỗi Dark Mode benchmark focus, chạy local trên Windows

- Khắc phục `scripts/test.ps1` dừng ở bài kiểm thử Dark Mode V0.5.125 do ba khai báo `!important` trong `.benchmark-focus-button` từ V0.5.130.
- Áp dụng `.panel button.benchmark-focus-button` với độ ưu tiên CSS phù hợp, giữ màu tối, viền, trạng thái focus và hành vi tua video tại timecode.
- Sửa bài kiểm thử xu hướng V0.5.130 không khóa cứng số phiên bản của những bản phát hành sau; bổ sung 4 bài kiểm thử chống tái phát cho V0.5.131.
- Đồng bộ frontend/backend/AI/backup-worker/VERSION và Alembic `0144_focus_css_v05131` (chỉ metadata). **Không thay đổi thuật toán đếm xe, PostgreSQL nghiệp vụ, Ground Truth, Docker volumes hoặc cấu hình GPU. Không thêm Google Drive/rclone.**
- Sau khi cài source mới, chạy `test.ps1`. Chỉ khi kiểm thử đạt mới chạy `start.ps1` và `publish.ps1`. Giữ nguyên `.env`, `.git`, models, datasets, videos, snapshots và training-runs hiện có.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
.\scripts\publish.ps1
```

---

## V0.5.130 — Local-only, không sử dụng Google Drive

**Nhánh này xây dựng trực tiếp từ V0.5.128.** V0.5.129 từng được phát hành riêng cho phương án Google Drive, nhưng người dùng đã quyết định giữ toàn bộ dữ liệu, Docker và RTX 3060 trên Windows. Để tránh trùng tag/phiên bản trên GitHub, bản local-only dùng **V0.5.130** và **KHÔNG** thêm rclone, kết nối Google, cloud backup hoặc lịch upload. Migration `0143_local_trend_v05130` nối tiếp Alembic `0142_repeatability_runner_v05128` và **chỉ cập nhật metadata**.

- Benchmark #88/#89/#90 (Session #248/#249/#250): cùng GT 149, AI 148, khớp 144, lọt 5, dư 4, sai hướng 2, sai loại 2. So sánh SHA-256 đã chứng thực cho thấy cả 148 chữ ký sự kiện AI và 13 chữ ký hồ sơ lỗi đều lặp cả ba lần. Không có cải thiện đo được; không can thiệp chính sách đếm bằng cách suy diễn từ ảnh tĩnh.
- **Mới:** `scripts/audit-benchmark-trend.py` + `.ps1` so sánh **3–12 benchmark** đã chấm GT, từ chối GT/nguồn/hình học không tương thích, kiểm tra SHA-256, nhận diện vấn đề tái diễn và phân nhóm: xe GT cạnh tranh thời gian, xe đạp lọt, rescue qua gap, nội suy qua vạch, khả năng trùng track, sai hướng và sai loại. Xuất `benchmark-trend.json`, `.csv`, `.md` (chỉ đọc).
- **Mới:** phần *Ưu tiên xem bằng chứng* trong màn hình Benchmark: gom mốc thời gian cần rà soát, bấm để tua video trước mốc 0,75 giây; không tự sửa GT, không cộng/trừ xe.
- Dữ liệu và mô hình không thay đổi; kiểm toán lỗi không chứng minh hai sự kiện gần thời gian thuộc cùng một xe. Cần xác nhận từ video liên tục trước khi thay đổi thuật toán trên clip kiểm tra độc lập.

**Chạy trên Windows (đã có Docker Desktop, không yêu cầu Python host):**

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1

.\scripts\audit-benchmark-trend.ps1 `
  -Exports @('.\traffic-ai-benchmark-88-session-248.zip', '.\traffic-ai-benchmark-89-session-249.zip', '.\traffic-ai-benchmark-90-session-250.zip') `
  -OutputDirectory '.\benchmark-trend-audit'

# Chi phat hanh khi test thanh cong
.\scripts\publish.ps1
```

Giữ nguyên `.env`, `.git`, `datasets`, `videos`, `models`, `training-runs`, snapshots và volumes PostgreSQL khi giải nén. Các kết quả báo cáo có thể được dọn riêng; không xóa PostgreSQL volume, không xóa VHDX Docker Desktop.

---

## Lịch sử: Traffic AI V0.5.128

> **Một `README.md`** ở thư mục gốc. Bản phân phối V0.5.126 đã hợp nhất
> nội dung của `VERIFICATION.md` và `DEPENDENCIES_V05122.md` vào cuối tệp này.
> Các thư mục nhật ký kiểm thử lịch sử `docs/` và `verification-logs/` **không đóng gói**;
> chúng không chứa mã ứng dụng cần thiết, nhưng nếu máy bạn còn các báo cáo đó
> thì chỉ nên tự xóa sau khi đã sao lưu những kết quả cần lưu trữ.

## Cập nhật V0.5.128 — khắc phục lỗi kiểm thử repeatability

- Khắc phục lỗi PowerShell `The expression after '&' ... was not valid` ở cuối `scripts/test.ps1`:
  kiểm thử hồi quy V0.5.127 trước đó gọi `$python.Source` dù không tạo biến `$python`.
- Cả bài kiểm thử repeatability V0.5.127 và bài kiểm tra mới V0.5.128 đều dùng
  **Python 3.14.10 trong Docker** với môi trường bytecode riêng, không phụ thuộc
  vào Python cài trên Windows; lỗi trả về dừng phát hành trước bước GitHub.
- Thêm `scripts/tests/test_repeatability_runner_v05128.py` để kiểm tra lỗi
  `$python.Source` không quay lại, có `docker run --rm`, lệnh unittest, mã trả về
  và việc kiểm thử được đưa lên trước các bộ test backend/AI tốn thời gian;
  vẫn giữ chế độ chỉ đọc benchmark.
- Đồng bộ version `0.5.128` và Alembic `0142_repeatability_runner_v05128`.
  **Không thay đổi thuật toán AI, Ground Truth, dữ liệu nghiệp vụ hay quyền truy cập.**
- Kết quả trên máy người dùng ở V0.5.127 trước khi gặp lỗi: **222 backend**,
  **898 AI**, **4 backup-worker** tests đạt. Cần chạy lại `test.ps1` trên Windows
  để xác nhận toàn bộ luồng và kiểm tra frontend/build thực tế.

## Cập nhật V0.5.127 — đối chiếu lỗi lặp lại

- Đối chiếu thực tế Benchmark #88 / Session #248 và #89 / Session #249 trên cùng clip/GT: **149 GT, 148 AI, khớp 144, lọt 5, dư 4, sai hướng 2, sai loại 2** ở cả hai.
- SHA-256 JSON và trace được xác minh: **148/148 chữ ký crossing AI trùng nhau, 13/13 hồ sơ sai lệch có chữ ký lặp, 0 hồ sơ mới, 0 hồ sơ được loại**, tham số thuật toán hiệu lực (`policy_metadata.configuration_sha256`) cũng giống nhau. Đây **không phải** một cải thiện về độ chính xác.
- Thêm `scripts/audit-benchmark-repeatability.py` và `scripts/audit-benchmark-repeatability.ps1` để so sánh hai ZIP đã chấm GT, phát hiện hồ sơ lỗi lặp và xuất **JSON, CSV, Markdown**. Tool dừng nếu GT/nguồn/geometry khác nhau, không dùng ID database để suy ra cùng một xe, không sửa số đếm.
- Bằng chứng camera RAR #249 được rà soát tại các mốc 54s, 59s, 289s, 293s, 642s, 754s, 760s, 882s. Ảnh tĩnh không đủ chứng minh trùng xe hoặc sai nhãn, do đó **không bật chặn bổ sung làm giảm Recall/Precision** trong bản này.
- Migration `0141_repeatability_v05127` chỉ cập nhật metadata phiên bản, **không thay đổi bảng dữ liệu, thuật toán hoặc model**.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\audit-benchmark-repeatability.ps1 `
  -Prior '.\traffic-ai-benchmark-88-session-248.zip' `
  -Current '.\traffic-ai-benchmark-89-session-249.zip' `
  -OutputDirectory '.\benchmark-repeatability-audit'
```

**Gợi ý thử nghiệm tiếp:** quay lại clip tại 13 timecode ghi trong báo cáo để xác nhận bằng video liên tục/GT; chỉ điều chỉnh chính sách đếm nếu có phản thực nghiệm trên chính bộ GT này và kiểm tra thêm clip độc lập.

## Mục lục nhanh

- [Cập nhật V0.5.128](#cập-nhật-v05128--khắc-phục-lỗi-kiểm-thử-repeatability)
- [Cập nhật V0.5.127](#cập-nhật-v05127--đối-chiếu-lỗi-lặp-lại)
- [Cập nhật V0.5.126](#cập-nhật-v05126)
- [Chạy thử và phát hành](#chạy-thử-và-phát-hành)
- [Dọn thư mục an toàn](#dọn-thư-mục-an-toàn)
- [Đọc báo cáo Benchmark #88](#đọc-báo-cáo-benchmark-88)
- [Lịch sử phát hành cũ](#lịch-sử-phát-hành-cũ)
- [Phụ lục dependency và xác minh](#phụ-lục-dependency-và-xác-minh)

## Cập nhật V0.5.126

- Phân tích đầy đủ bốn loại sai lệch GT/AI từ Benchmark #88 / Session #248:
  **GT 149, AI 148, khớp 144, lọt 5, dư 4, sai hướng 2, sai loại 2**.
  Có 13 mục review (một cặp đã khớp thời gian có thể vẫn sai hướng/loại).
- `scripts/audit-benchmark-quality.py` và `scripts/audit-benchmark-quality.ps1`
  **kiểm tra SHA-256 và footer trace**, xuất `benchmark-quality.json`/`.csv`.
  Tác vụ chỉ đọc, không sửa GT, không thay bằng chứng và không ép score lên 100%.
- `scripts/cleanup-generated.ps1` chỉ liệt kê trước (`dry-run`); cần `-Apply`
  mới thực sự xóa các thư mục báo cáo tạm được cho phép. Dữ liệu huấn luyện,
  video, model, snapshots, database/backup và Git **không nằm trong danh sách xóa**.
- Hợp nhất tài liệu phát hành và xác minh về một README gốc; giữ các script
  và migration cũ để tương thích và có thể nâng cấp/rollback. Migration
  `0140_quality_audit_v05126` chỉ cập nhật metadata `schema_version`.
- **Không chỉnh policy nhận diện/đếm xe trong bản này**: báo cáo không đủ bằng
  chứng nhận dạng cùng xe để bật rule chống dư hoặc rescue mới. Muốn đo hiệu quả
  thực sự, cần chạy lại **đúng clip nguồn và GT** sau khi có thay đổi thuật toán.

### Chạy thử và phát hành

Sao lưu `.env`, `.git` cùng dữ liệu cần thiết trước khi giải nén; không dùng
`docker compose down -v`, không xóa named volumes PostgreSQL, không ghi đè
model hay dữ liệu huấn luyện. Chỉ `publish` **sau khi** `test` thành công.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
.\scripts\publish.ps1
```

### Dọn thư mục an toàn

**Luôn giữ lại:** `.env`, `.git`, `scripts`, `frontend`, `backend`, `ai-service`,
`backup-worker`, `gateway`, `models`, `videos`, `datasets`, `training-runs`,
`snapshots`, `gateway/certs`, các Docker volumes (`traffic_ai_postgres_data`,
`traffic_ai_backup_data`). Các thư mục `models`, `videos`, `datasets`,
`training-runs`, `snapshots` có thể là dữ liệu trực tiếp từ người dùng hoặc
đầu ra tác nghiệp: **không tự xóa**.

**Có thể xóa sau khi đã lưu kết quả cần giữ:**

| Thư mục | Nội dung | Khuyến nghị |
|---|---|---|
| `crossing-cycle-audit` | Báo cáo phân tích chu kỳ cắt vạch | Xóa nếu đã sao lưu |
| `endpoint-precision-audit`, `endpoint-precision-audit-v108` | Audit endpoint lịch sử | Xóa nếu đã lưu |
| `gate-coverage-audit` | Báo cáo vùng/vạch | Xóa nếu đã lưu |
| `raw-id-audit-report` | Báo cáo chuyển động raw ID | Xóa nếu đã lưu |
| `replay-diff-report` | Báo cáo so sánh replay | Xóa nếu đã lưu |
| `benchmark-quality-audit`, `benchmark-forensics-report`, `passage-evidence-audit` | Báo cáo kiểm toán | Xóa nếu đã lưu |
| `verification-logs` | Log kiểm thử cũ | Có thể lưu trữ rồi xóa thủ công |
| `docs` | Nhật ký, tài liệu QA cũ | Chỉ xóa nếu không cần lịch sử điều tra |
| `dist-release` | Bản ZIP/TAR phát hành cục bộ | **Chỉ xóa nếu đã xác nhận GitHub Release và có bản sao** |

**Không xóa tự động** `docs`, `verification-logs`, `dist-release`, các ZIP
benchmark hoặc `camera_*.rar` trong thư mục dự án. Đặc biệt `dist-release`
chỉ được xem xét với tùy chọn riêng.

```powershell
# Chỉ xem những thư mục báo cáo tạm sẽ bị xóa
.\scripts\cleanup-generated.ps1
# Chỉ sau khi đã kiểm tra danh sách, cho phép xóa báo cáo tạm
.\scripts\cleanup-generated.ps1 -Apply
# Xem trước hai tài liệu gốc đã được hợp nhất vào README.md
.\scripts\cleanup-generated.ps1 -IncludeLegacyDocs
# Chỉ xóa hai tài liệu đó sau khi đã xác nhận README.md đầy đủ
.\scripts\cleanup-generated.ps1 -IncludeLegacyDocs -Apply
# Xem trước dist-release: CHỈ khi GitHub Release đã được xác minh
.\scripts\cleanup-generated.ps1 -IncludeReleaseArtifacts
```

Việc giải nén ZIP mới lên source cũ **không tự xóa** thư mục `docs` hay
`verification-logs` đang tồn tại trên Windows. Bạn tự quyết định sau khi kiểm
tra những tài liệu lịch sử cần giữ.

### Đọc báo cáo Benchmark #88

Nguồn: `traffic-ai-benchmark-88-session-248.zip` và ảnh camera trong RAR
Session #248; source FPS 25, GT/AI chấm theo cửa sổ 0,75 giây.

- **Lọt 5:** GT `12824` (59,446 s), `12854` (237,042 s),
  `12866` (289,824 s), `12888` (406,488 s), `12908` (591,091 s).
  Bốn ca đầu có event lân cận **đã được gán cho GT khác**, không thể xem như
  detector chưa phát hiện xe mà không đối chiếu video; ca cuối cần xem lại xe đạp.
- **Dư 4:** AI `16417` (54,294 s, rescued), `16459` (292,862 s, interpolated),
  `16524` (759,520 s, direct; gần event 16525), `16546` (882,291 s,
  interpolated truck). Không xóa tự động dù có `spatial_duplicate_near_gt`.
- **Sai hướng 2:** AI `16418` tại 58,894 s, `16521` tại 754,046 s.
- **Sai loại 2:** AI `16458` tại 289,617 s (GT bicycle/AI motorcycle),
  `16505` tại 641,930 s (GT car/AI truck).
- Ảnh JPG camera ở 591,091 s thiếu ảnh đủ gần (ảnh gần nhất lệch ~4,76 s),
  vì vậy không thể suy luận xe đạp tại thời điểm GT bằng ảnh tĩnh.

```powershell
# Báo cáo 13 mục review, kiểm tra hash trace đầy đủ
.\scripts\audit-benchmark-quality.ps1 `
  -Export '.\traffic-ai-benchmark-88-session-248.zip' `
  -OutputDirectory '.\benchmark-quality-audit'

# Nếu đã giải nén RAR ảnh camera ra thư mục camera_1:
.\scripts\audit-benchmark-quality.ps1 `
  -Export '.\traffic-ai-benchmark-88-session-248.zip' `
  -CameraImages '.\camera_1' `
  -OutputDirectory '.\benchmark-quality-audit'
```

Đầu ra có `benchmark-quality.json`, `benchmark-quality.csv` (UTF-8 BOM).
Kết quả mang tính **kiểm toán/ưu tiên xem lại**, không sửa số AI, GT, class,
hướng, benchmark matching, source video hay database.

## Lịch sử phát hành cũ
> **Lưu ý tư liệu lịch sử:** Những liên kết `docs/...` trong các ghi chú phiên bản cũ trỏ đến
> hồ sơ QA của bản phát hành lúc đó. Các hồ sơ này không còn nằm trong ZIP V0.5.126
> để giữ đúng yêu cầu chỉ một tài liệu Markdown; nếu cần điều tra lịch sử, hãy lưu
> trữ bản source cũ có đủ `docs` và `verification-logs`.



## V0.5.125 — Giao diện ô nhập liệu tối đồng bộ

Điều chỉnh nền trắng mặc định của form trong **Dataset Studio / Clean Retrain**,
**Fine-tune YOLO26**, các trường chọn dataset, và các trang **đăng nhập / đổi
mật khẩu / quản trị người dùng**, đồng thời áp dụng đồng bộ cho các form camera,
benchmark và báo cáo. Nền `#0b1a2f`, viền `#2d4a69`, chữ sáng `#edf5ff`.
Dropdown native và spinner số dùng `color-scheme: dark`; Chrome/Edge autofill
không đổi ô mật khẩu trở lại nền vàng/trắng. Nút bấm, checkbox, file upload,
placeholder và trạng thái focus vẫn tách biệt, bảo toàn khả năng dùng bàn phím.

Thay đổi chỉ ở CSS, bài kiểm thử UI (Node stdlib), runtime version và migration
metadata `0139`; không sửa AI detector, training pipeline, dữ liệu camera,
Ground Truth, database nghiệp vụ hay Docker volumes. Test `npm test` tự chạy
các bài hồi quy giao diện mới. Chạy `test.ps1` trước `publish.ps1` và giữ lại
`.env`, `.git`, videos, models, backups, Docker volumes khi giải nén ZIP.

# Traffic AI V0.5.124 — Sửa kiểm tra npm bị sót sau nâng cấp

Log Windows 29/10/2026 cho thấy `scripts/test.ps1` dừng tại
`Assert-ObservedPathCleanFrameV0552Contract` (line 1674): thông báo muốn
`npm@12.2.1` nhưng điều kiện cũ vẫn tìm `npm@12.2.0` (và loại `12.1.0`).
Trong source V0.5.123, frontend/Dockerfile và ba GitHub workflows đã dùng
đúng `npm@12.2.1`. Đây là false negative của preflight, không phải lỗi
`npm install` hay thuật toán AI.

V0.5.124 lấy npm version duy nhất từ `frontend/package.json` (`packageManager`),
kiểm tra bốn file installer có một pin duy nhất khớp tuyệt đối với manifest;
báo rõ file và pin tìm thấy nếu lệch. Đồng thời sửa kiểm tra NumPy cũ
`2.4.6`: file `requirements-test.txt` đã pin `2.5.4`. Thêm 6 bài regression stdlib trước Docker
build/frontend install; không bỏ `npm audit`, không thay `start.ps1`, không đổi
tracking/counting/GT/matching. Metadata Alembic `0138` chỉ cập nhật version,
không đụng bảng đếm xe hay Docker volumes.

Để cập nhật: giải nén ZIP đè source ở `D:\LienThongDH\DoAn\traffic-ai`,
**giữ `.env`, `.git`, videos, models, backups và Docker volumes**. Không giải nén
song song khi đang chạy `publish.ps1`. Chạy:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
.\scripts\publish.ps1
```

`publish.ps1` sẽ chạy lại test trước khi commit/tag/push. Nếu kiểm thử chưa qua
thì không phát hành, và không sửa tag GitHub cũ.

Giới hạn: kiểm thử offline trong môi trường đóng gói không thay thế test thực
tế trên Windows/Docker/GPU/GitHub Actions; xem phụ lục xác minh ở cuối README.md.

---

# Traffic AI V0.5.123 — Fix CI Node.js + ngăn phát hành sai tag

Nhật ký Windows 29/10/2026 xác nhận V0.5.122 khởi động thành công,
nhưng `scripts/test.ps1` báo workflow chưa dùng Node 26.13.0 vì **biểu thức
kiểm tra vẫn cố định ở 26.10.0**. Test nay đọc `.nvmrc`, đối chiếu cả ba
workflow `setup-node@v7` và Dockerfile frontend; không còn phải cập nhật một
literal cũ mỗi khi nâng Node.

Nhật ký GitHub cùng ngày cho thấy một lần chạy `publish.ps1` bắt đầu với
tag `v0.5.121` nhưng source được commit đã chứa `VERSION=0.5.122`.
GitHub Actions từ chối Release là **đúng** để tránh tag sai. Nguyên nhân
có thể là working tree thay đổi trong khi đợi bộ test lâu; log không đủ để
chứng minh thao tác cụ thể. V0.5.123 bổ sung kiểm tra version trước/sau test,
trước khi stage/commit/push và đối chiếu VERSION + package.json trong Git
index, HEAD và tag; phát hiện lệch thì dừng, không đẩy tag mới hoặc tạo Release
trực tiếp sai version. Tag `v0.5.121` đã có trên GitHub không bị sửa/đẩy lại.

Chỉ thay hạ tầng CI/phát hành và metadata version (migration `0137`); không
động thuật toán đếm, Ground Truth, mô hình AI, cấu hình tracking, hay dữ liệu
trong Docker volumes. Có thêm bốn kiểm thử stdlib về chốt phát hành.

**Chạy trên Windows (tránh vừa giải nén source vừa publish):**

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
.\scripts\publish.ps1
```

`publish.ps1` sẽ tự chạy lại toàn bộ test trước khi commit/push. Không sửa
hay force-push tag cũ để bỏ qua lỗi VERSION/tag; luôn dùng version mới.

**Phạm vi xác minh:** regression offline được chạy trong môi trường này;
PowerShell trên Windows, Docker/GPU thật và GitHub Release cần chạy/kiểm tra
trên máy người dùng. Xem phụ lục xác minh ở cuối `README.md`.

---

# Traffic AI V0.5.122 — Framework/Package upgrade

For new direct dependency pins, compatibility notes and installation verification limits see [phụ lục dependency trong README](#phụ-lục-dependency-và-xác-minh). Source based on V0.5.121.

---

# Traffic AI V0.5.121 — Sửa lỗi cài dependency Frontend (Rolldown E404)

Trong log `scripts/test.ps1` ngày 29/10/2026, backend (222 tests), AI service
(898 tests) và backup worker (4 tests) đã đạt; bước **Frontend build** dừng
trong `npm install` vì yêu cầu tải `rolldown-1.2.16.tgz` trả `E404`.

Vite `8.3.5` khai báo Rolldown `~1.2.14`; range này có thể chọn patch
`1.2.16` chưa tải được tại thời điểm log. V0.5.121 **giữ Vite 8.3.5** và
thêm `overrides.rolldown = "1.2.15"` (bản khả dụng đã đối chiếu trên npm),
để các đường cài đặt thông thường Docker, CI và test đều giải quyết dependency
qua package.json giống nhau. Không tắt `npm audit` và không downgrade Vite.

Bổ sung 5 kiểm thử regression stdlib chạy trước frontend build. Version ở
backend/AI/worker/frontend được đồng bộ; Alembic migration `0135` chỉ đổi
metadata phiên bản, không tác động dữ liệu đếm. Thuật toán đếm, báo cáo,
Ground Truth, matching và cấu hình tracking **không đổi so với .120**.

**Lưu ý xác minh:** Môi trường tạo bản ZIP này không có Docker/PowerShell và
không truy cập được npm registry (`EAI_AGAIN`), vì vậy chưa thể chứng nhận
`npm install` hay Vite build thật đã chạy thành công. Chạy `scripts/test.ps1`
trên máy Windows có Docker để xác nhận lỗi đã được giải quyết.

## Cập nhật và kiểm tra bản .121

Giải nén full source vào `D:\LienThongDH\DoAn\traffic-ai` (giữ nguyên
`.env`, model, video, dữ liệu, backup và Docker volumes). Không tạo lại Admin.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Nếu còn E404, kiểm tra proxy/cache/npm registry trên Docker; không dùng
`npm audit --force`, không bỏ kiểm tra audit và không sửa nguồn dữ liệu benchmark.

---

# Traffic AI V0.5.120 — Xem chuyển động riêng của từng raw ID

Trong các thẻ sai hướng, sai loại hoặc đếm dư, mở **Chuyển động theo raw ID**
để xem các đoạn quan sát liên tiếp của từng token ByteTrack. Mỗi đoạn có
frame, timecode, số mẫu, độ dịch tâm box, vận tốc đo từ box và vận tốc đã lọc
của canonical. Nút xem đầu/cuối đoạn đưa video tới đúng mốc để đối chiếu.

Khi có đổi raw ID, bước nhảy nối ID được hiển thị riêng với độ cùng chiều
so với chuyển động của raw mới. ID thay đổi hoặc frame bị thiếu luôn ngắt
đoạn; bước nhảy giữa hai ID không được tính là chuyển động riêng của một raw.
Dữ liệu xung đột, khác track hoặc không đủ hai mẫu liên tiếp không tạo đoạn.
Đây là bằng chứng để xem lại video, không tự xác nhận cùng xe, hướng cắt vạch
hay sửa điểm benchmark.

Tại ca754s của phiên214, raw312739 gần như đứng yên ở frame18834–18842;
raw331821 ở frame18860–18870 dịch tâm lên74,505px trong11 mẫu. Bước nối
ID có độ dịch xuống229,647px, được giữ riêng khỏi đoạn raw mới. Chức năng
mới giúp phân biệt bước nối canonical với chuyển động box đã quan sát.

## Hồ sơ chạy thực tế

Benchmark #87 chạy AI .119 ghi149GT,147AI,144khớp,5lọt,3dư,
2sai loại,2sai hướng,F1 **97,2973%**. GT/ghi chú/cấu hình và147 event
chuẩn hóa giống #86. Đây là điểm của .119; chưa có lần chạy video/GPU .120
mới để đo mức thay đổi. Bản .120 bổ sung chức năng xem bằng chứng, giữ
thuật toán đếm/nối ID, GT, matcher và tolerance. Van chở hàng vẫn là xe tải;
lượt quay lại hợp lệ tiếp tục được đếm.

## Cập nhật và sử dụng

Chép đè source nhưng giữ `.env`, `.git`, models, videos, snapshots, database,
Docker volumes và backups. Migration `0134_raw_motion_audit_v05120` chỉ cập
nhật metadata phiên bản; không cần tạo lại admin.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.120 và GitHub Release
.\scripts\publish.ps1
```

Nhấn Ctrl+F5, mở benchmark #87, bấm **Đối chiếu lại**, rồi xem thẻ sai hướng
quanh754s và mở **Chuyển động theo raw ID**. Chức năng đọc lại trace đã lưu;
không cần chạy detector mới nếu trace phiên214 vẫn còn.

Đã đạt **1.355 ca kiểm thử offline**; giữ nguyên 1.319 hàm kiểm thử Python
cũ và 10 tệp kiểm thử Node cũ. 64 ca HTTP/ORM chưa chạy và 1 ca PowerShell
bỏ qua; chưa chạy Docker, browser/Vite build hoặc video/GPU mới.

Xem phụ lục xác minh ở cuối `README.md` để biết phạm vi kiểm chứng và giới hạn.

---

## Ghi chú các bản trước

# Traffic AI V0.5.119 — Xem cấu hình thực tế của phiên benchmark

Màn hình benchmark có mục **Cấu hình thực tế của phiên**. Mở mục này để xem
phiên bản AI đã ghi trace, trạng thái cấu hình, các cờ bộ lọc và tham số đã
chạy. Phiên cũ không ghi cấu hình được hiển thị là chưa có dữ liệu; giá trị
thiếu không bị coi là tắt. Có thể tìm trong danh sách tham số và tải lại khi
AI tạm thời chưa phản hồi.

Dữ liệu lấy từ `policy_metadata` của đúng phiên đã chọn, được kiểm tra schema,
kiểu giá trị và digest. API chỉ đọc phần đầu trace theo giới hạn byte/dòng;
lỗi tệp hoặc AI không ngăn xem điểm benchmark. Việc này không thay cấu hình
đang chạy hay dùng môi trường hiện tại để đoán cấu hình cũ. Digest xác nhận
các tham số trong danh sách đã ghi, không xác nhận toàn bộ video/model/lần
chạy; phần đầu trace không thay chứng nhận đóng toàn bộ hồ sơ.

## Kết quả thực tế bạn vừa gửi

| Chỉ số | #85 / AI .117 | #86 / AI .118 |
|---|---:|---:|
| GT | 149 | 149 |
| AI lưu DB | 148 | 147 |
| Khớp | 144 | 144 |
| Lọt | 5 | 5 |
| Dư | 4 | 3 |
| Sai loại | 2 | 2 |
| Sai hướng | 2 | 2 |
| F1 | 96,9697% | 97,2973% |

GT chuẩn hóa và ghi chú giống nhau. 147 event còn lại giữ nguyên thời gian,
điểm cắt, loại, hướng, confidence và canonical ID; chỉ lượt OUT dư tại
812,5773 giây được bỏ. Đây là kết quả **.118**, chưa phải điểm .119.

Chính sách đếm/nối ID của .118 được giữ nguyên. Trường hợp sai hướng quanh
754 giây có bằng chứng xe đang OUT nhận ID của xe đỗ cũ; cần thêm kiểm chứng
để thay quy tắc nối ID mà vẫn bảo vệ xe dừng rồi đi tiếp. Các lượt gần GT
không tự động bị xóa/đổi loại. Van chở hàng vẫn là xe tải và lượt quay lại
hợp lệ tiếp tục được đếm. Không sửa GT, matcher hay tolerance.

## Cập nhật và chạy

Chép đè source nhưng giữ `.env`, `.git`, models, videos, snapshots, database,
Docker volumes và backups. Migration `0133_recorded_policy_v05119` chỉ cập
nhật metadata phiên bản. Không cần tạo lại admin. Nhấn Ctrl+F5 rồi kiểm tra
giao diện/AI đều .119; mở benchmark #86 để xem cấu hình của phiên213 (.118).

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.119 và GitHub Release
.\scripts\publish.ps1
```

Đã đạt **1.316 ca kiểm thử offline**; giữ nguyên toàn bộ 1.287 hàm kiểm
thử Python cũ và 9 tệp kiểm thử Node cũ. 64 ca HTTP/ORM chưa chạy và
1 ca PowerShell bỏ qua; chưa chạy Docker, trình duyệt, Vite build hoặc
video/GPU mới trong môi trường này.

Xem phụ lục xác minh ở cuối `README.md` để biết phạm vi kiểm tra và giới hạn thực tế.

---

## Ghi chú các bản trước

# Traffic AI V0.5.118 — Rescue đầu vạch và cấu hình phiên

Bản này tiếp tục từ đầy đủ source .117. Giữ bộ lọc ID mảnh, phân loại
van chở hàng là xe tải và cho phép xe quay lại cắt vạch được đếm tiếp.

- **Giảm đề xuất dư ở đầu vạch:** mở rộng kiểm tra tâm xe sang lượt
  `rescued` của xe hai bánh trong video. Dùng nguyên vùng đầu vạch 0,08
  và ngưỡng xác nhận tâm 0,04; lượt trực tiếp, xe bốn bánh và tâm đã qua
  đủ sâu giữ chính sách cũ. Khi loại đề xuất, trạng thái vạch tiếp tục đóng
  để tránh tạo lượt bù giả. Đây là chính sách bảo thủ cần chạy A/B video.
- **Ghi tham số thực tế của phiên:** trace có thêm `policy_metadata` sau
  `geometry_metadata`, lấy các thuộc tính thuật toán được cho phép từ
  đối tượng đã khởi tạo. Có SHA256 cấu hình, trạng thái đầy đủ/thiếu và tên
  trường không đọc được. Không ghi biến môi trường tùy ý, token hay URL.
  Digest chỉ nhận diện các tham số được liệt kê; không thay thế model,
  hình học, video hoặc fingerprint source.
- **Theo dõi riêng lượt rescue bị chặn:** Dashboard và trace thêm
  `endpoint_rescue_suppressed`, là một phần của `endpoint_precision_suppressed`.
  Đây là số đề xuất bị chặn tại worker, không phải số dư DB đã đo được.

Mặc định `AI_ENDPOINT_RESCUE_GUARD=1`, chỉ có hiệu lực trong video khi
`AI_FINITE_ENDPOINT_PRECISION_GUARD` cũng bật. Đặt cờ mới bằng `0` trong
`.env` và khởi động lại AI để so sánh với chính sách .117. Không thay GT,
matcher, tolerance hay loại bỏ xe khác chỉ vì hai lượt gần thời gian.

Hồ sơ #85/session212 chạy **AI .117** ghi GT149, AI148, khớp144,
lọt5, dư4, sai loại2, sai hướng2, F1 **96,9697%**. Đây là kết quả phiên
cũ, chưa phải điểm .118. Chưa có lần chạy detector/GPU mới để kết luận
đã hết lọt/dư.

Kiểm tra cố định trên trace #85: 42 đề xuất rescue, chỉ 1 đề xuất bị chặn
thêm; 41 rescue còn lại và 120 đề xuất phương thức khác giữ nguyên quyết
định của helper. Cần chạy phiên mới để đo tác động lên DB và F1.

Chép đè source và giữ `.env`, `.git`, models, videos, snapshots, database,
Docker volumes, backups. Migration `0132_runtime_policy_v05118` chỉ cập nhật
metadata phiên bản. Nhấn Ctrl+F5 sau khởi động, kiểm tra giao diện/AI đều .118.
Không cần tạo lại admin.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.118 và GitHub Release
.\scripts\publish.ps1
```

Đã đạt **1.276 ca kiểm thử offline**, giữ nguyên các hàm/assertion kiểm thử
cũ. Có 64 ca HTTP/ORM chưa chạy và 1 ca PowerShell bỏ qua trong môi trường
này; chưa chạy Docker/GPU/video mới hoặc build Vite.

`publish.ps1` đọc VERSION; mặc định chạy test trước khi commit/push, tạo tag
và chờ GitHub Release hoặc dùng GitHub CLI hoàn tất. Xem phụ lục xác minh ở cuối `README.md`
để biết phạm vi kiểm tra thực tế và giới hạn của bản này.

---

## Ghi chú các bản trước

# Traffic AI V0.5.117 — Fragment Ownership and Runtime Versions

## Nâng cấp chạy thực tế

- **Xử lý ID mảnh xe hai bánh:** kiểm tra một box mới, nhỏ, nằm trong box xe
  đang chạy qua nhiều khung liên tiếp. Chỉ dừng ID mảnh khi nó chưa có lượt
  đếm/chờ Human Guard và có bằng chứng hình học, chuyển động nhất quán với
  xe chủ. Không gộp heading hay bằng chứng phân loại của hai ID. Trạng thái
  đếm chưa hoàn tất được thu hồi đồng bộ để tránh các lượt giả nối tiếp.
- **Giữ xe tách riêng và lượt quay lại:** ID bị giữ phải có bằng chứng tách
  riêng an toàn hoặc kết thúc vòng đời trước khi được cấp lịch sử mới; không
  dùng lại canonical cũ còn cache ngữ nghĩa. Xe đi sau không bị loại chỉ vì
  gần thời gian với xe trước.
- **Hiện phiên bản thật:** Dashboard hiển thị riêng phiên bản giao diện đang
  mở và phiên bản AI đang phản hồi. Nếu hai bản khác nhau, có cảnh báo và nút
  tải lại thủ công. AI chưa sẵn sàng/thiếu thông tin không tạo cảnh báo lệch.
  Trang không tự reload khi người dùng đang thao tác.

Bộ lọc mảnh ID mặc định bật **chỉ với video**. Có thể đặt
`AI_TWO_WHEEL_FRAGMENT_GUARD=0` trong `.env` và khởi động lại AI để so sánh
với nhánh cũ. Các bộ đếm mới phản ánh ID/box được xử lý, không phải số event
DB đã được chứng minh loại dư. Đây là chính sách hình học bảo thủ; vẫn cần
kiểm tra video thật với các xe che khuất hoặc đi sát nhau.

## Kết quả đã xác minh từ lần chạy của bạn

| Chỉ số | #83 / AI .115 | #84 / AI .116 |
|---|---:|---:|
| GT | 149 | 149 |
| AI lưu DB | 148 | 149 |
| Khớp | 143 | 144 |
| Lọt | 6 | 5 |
| Dư | 5 | 5 |
| Sai loại | 3 | 2 |
| Khớp đủ loại/hướng | 138 | 140 |
| F1 | 96.2963% | 96.6443% |

Lượt OUT gần giây392 đã được khôi phục và xe đạp gần giây534 đã đúng loại.
GT/cấu hình chuẩn hóa của hai hồ sơ giống nhau. Đây là kết quả **AI .116**
đã chạy, chưa phải điểm của .117. Năm event dư trong báo cáo cũ vẫn giữ
nguyên. Không thay GT, matcher, tolerance hoặc loại xe để làm đẹp điểm.

Ảnh mới hiện badge .115 nhưng trace phiên211 ghi đúng runtime .116 và
fingerprint source đã giao. Chưa đủ bằng chứng phân biệt tab/cache cũ với
frontend container cũ. Dòng phiên bản mới giúp nhận ra tình trạng này;
`index.html` cũng được yêu cầu kiểm tra lại cache sau mỗi lần mở.

## Cập nhật và chạy trên Windows

Chép đè source nhưng giữ `.env`, `.git`, models, videos, snapshots, database,
Docker volumes và backups. Migration `0131_runtime_status_v05117` chỉ cập
nhật metadata phiên bản. Sau khởi động, nhấn **Ctrl+F5** một lần rồi kiểm tra
dòng phiên bản giao diện/AI trên Dashboard.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag và Release v0.5.117
.\scripts\publish.ps1
```

Chạy video trong phiên mới rồi tạo benchmark mới để đo kết quả .117. Thay
source không viết lại các phiên/benchmark đã lưu. Xem phụ lục xác minh ở cuối `README.md` để
biết các test đã chạy và những bước cần xác nhận trên máy Windows/GPU.
Phần dưới là lịch sử bản trước.

---

# Traffic AI V0.5.116 — Stationary Ownership and Repeated Target Evidence

## Thay đổi chạy thực tế

- **Giữ ID cho xe đang chạy:** bộ nối ID dùng lịch sử đứng yên của chính xe
  chủ để từ chối ghép một xe hai bánh mới, ở xa, vào ID xe đỗ. Cần ít nhất ba
  quan sát khác khung, kéo dài ít nhất 12 khung, cùng raw ID và không có chuyển
  động vượt giới hạn. Cả khoảng nhảy trực tiếp lẫn sai số dự đoán phải vượt
  giới hạn sẵn có. Không tạo sự kiện đếm thay cho bộ kiểm tra qua vạch.
- **Xác nhận xe đạp:** nhánh dự phòng tại lần qua vạch yêu cầu crop hẹp hiện
  tại và hai crop rộng khác khung của cùng nguồn đều ủng hộ xe đạp. Điểm crop
  rộng hiện tại còn phải thắng điểm detector chính. Bằng chứng xe máy đối
  nghịch trong lịch sử crop hẹp/rộng sẽ chặn nhánh này. Điểm tin cậy trả về
  giữ nguyên điểm crop rộng hiện tại, không cộng xác suất từ cùng mô hình.
- Hai bộ đếm chẩn đoán mới: `stationary_alias_rejections` và
  `bicycle_context_repeated_target_rescues`. Trace ghi cờ đang áp dụng và
  fingerprint bao gồm cả `tracking.py` lẫn `classification.py`.

Hai chức năng mặc định bật **chỉ với video**. Có thể tắt riêng bằng
`AI_STATIONARY_ALIAS_GUARD=0` hoặc `AI_BICYCLE_REPEATED_TARGET_CONTEXT=0` trong
`.env`, sau đó khởi động lại AI service. Các điều kiện cũ và chế độ stream
giữ nguyên. Không thay GT, matcher, tolerance, quy ước hướng hoặc chính sách
van hàng là truck. Một xe quay lại qua vạch vẫn có thể được đếm lần mới.

## Bằng chứng và giới hạn

Đầu vào là full source **V0.5.115** và hồ sơ **Benchmark #83 / Session #210**.
Điểm đã lưu của bản cũ: **GT149 / AI148 / khớp143 / lọt6 / dư5 / F1 96.3%**.
Đây chưa phải điểm của V0.5.116.

Phát lại bằng chứng crop trên trace cũ tìm được đúng một quyết định mới đủ
điều kiện trong 167 quyết định context: xe đạp track196223, frame13355.
Phát lại resolver/cổng đếm từ box đã ghi được dùng để kiểm tra việc mất ID
gần giây392. Đây là kiểm thử logic trên dữ liệu đã ghi; cần chạy lại AI trên
video gốc và tạo benchmark mới để đo lọt/dư/F1 của .116. Các trường hợp chưa
có bằng chứng an toàn, gồm mảnh ID quanh giây808, chưa được tự động bỏ đếm.

## Cập nhật và chạy trên Windows

Chép đè source, giữ `.env`, `.git`, models, videos, snapshots, database,
Docker volumes và backups. Migration `0130_target_evidence_v05116` chỉ cập
nhật metadata phiên bản. Giữ đủ test cũ; `test.ps1` chạy thêm regression .116.
`publish.ps1` đọc `VERSION`, chạy test rồi commit, push, tạo tag và GitHub
Release **v0.5.116** theo cấu hình repository có sẵn.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag và Release
.\scripts\publish.ps1
```

Xem phụ lục xác minh ở cuối `README.md` để phân biệt các test offline đã chạy và các bước
Windows/Docker/GPU/npm cần chạy trên máy đích. Phần dưới là lịch sử các bản cũ.

---

# Traffic AI V0.5.114 — Verified Review Export Docker Mount Fix

## Fix reported by user

Running `scripts/export-benchmark-review-frames.ps1` in V0.5.113 failed:
`[ERROR] Review frame export: [Errno 2] No such file or directory: '/opt/benchmark-gate.py'`.
The container was able to load the mounted `review-tool.py` and `benchmark-forensics.py`,
but `benchmark-forensics.py` dynamically imports a **second verifier** named
`benchmark-gate.py` from the same directory. This verifier was not mounted inside
`ai-service` and is not copied into that Docker image by its Dockerfile.

V0.5.114 changes the PowerShell exporter to explicitly mount
`scripts/benchmark-gate.py` at `/opt/benchmark-gate.py` **read-only**, alongside
`benchmark-forensics.py` and the frame exporter. A preflight check now refuses
missing verifier scripts **before starting Docker**. Both original benchmark and
video are read-only mounts; GT, AI events, database, count policy and source
video are unchanged. No extra host Python, OpenCV or `pip install` is required.

Four new regression tests cover the complete three-file dependency chain,
read-only mounts and native relative imports. `scripts/test.ps1` runs them
as a stdlib-only isolated Docker step. Migration `0128_review_mount_v05114`
is **metadata only**; it changes only the schema-version setting.

### Standard Windows commands

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

### Retry frame review export

Ensure the full benchmark ZIP and original video are located in the specified paths.
Check file existence with `Test-Path -LiteralPath ... -PathType Leaf` before running.
The exporter requires the source video from the benchmark; no JPG/RAR substitute
proves continuous crossing motion.

```powershell
.\scripts\export-benchmark-review-frames.ps1 `
  -Export ".\traffic-ai-benchmark-81-session-208.zip" `
  -Video ".\videos\clip1.mp4" `
  -ExpectedSession 208 `
  -OutputDirectory ".\benchmark-review-frames-81"
```

After checking output, compress `benchmark-review-frames-81` and share it for
manual review. Do not automatically relabel GT or treat extracted frames as
training labels. Publish using `.\scripts\publish.ps1` **only after** Windows
`test.ps1` and application checks succeed.

**Baseline, not a V0.5.114 score:** Benchmark #81 / Session #208: GT 149,
AI 148, matched 143, missed 6, extra 5, F1 96.3%. This update addresses an
exporter packaging error, **not** detector/tracker or crossing accuracy.

---

# Traffic AI V0.5.113 — Vite Security Maintenance

## Fix the failing Windows `scripts/test.ps1` pipeline

The provided V0.5.112 Windows test log completed backend (195 tests), AI service
(761 tests) and frontend unit tests (47 tests), but the frontend audit gate
failed on `vite@8.3.0` with a **high-severity** advisory related to
`launch-editor`. npm recommends upgrading to `vite@8.3.5`.

V0.5.113 updates the exact Vite devDependency to `8.3.5`, changes the pinned
version asserted by `Assert-TechnologyVersionsContract`, and adds five
stdlib-only regressions run by `scripts/test.ps1` **before** installing frontend
packages. `npm audit --audit-level=high` remains mandatory in `test.ps1`, the
frontend multi-stage Dockerfile and GitHub Actions CI. It is not bypassed.

The project ignores `frontend/package-lock.json` and generates one through
`npm install` during Windows/Docker test. No fictitious lockfile is included;
transitive dependencies and the registry's current advisories must be checked
by `npm audit` on the target machine. If the registry reports new advisories,
fix their causes instead of using `npm audit fix --force` blindly.

The release is **dependency/security maintenance only**. It changes no model,
detector, tracker, counting admission, GT, crossing time, database records,
backend APIs or PostgreSQL schema. Alembic migration
`0127_vite_security_v05113` updates the schema version metadata only.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Run `./scripts/publish.ps1` (PowerShell: `.\scripts\publish.ps1`) only after
the full Windows audit/build and application checks succeed. Keep `.env`, videos,
models, database volumes and backups when updating source.

---

# Traffic AI V0.5.109 — Road Zone / Finite-Gate Eligibility Evidence

## Why this update

At benchmark #79 / Session #206 the screenshot shows 149 GT, 148 AI, 143 matched,
6 missed, 5 unmatched, F1 96.3%. This is the user's already-completed V0.5.108 run,
not a measured V0.5.109 inference result. The supplied test/publish log for V0.5.108
is successful; there is no failing test to conceal or bypass.

Earlier trace analysis called `road_tracks=0` evidence of no roadway detections.
This conclusion was too strong: `road_tracks` is strict Road Zone polygon membership,
whereas actual primary counting decisions also consider a small configured anchor
margin, the observed path and corridor probes. This release repairs that telemetry
mismatch, without loosening the gate or adding synthetic vehicle events.

## V0.5.109 changes

- New `road_gate_diagnostics.py` computes strict Road Zone membership, anchor-only
  margin membership and normalized distance to the **finite** counting segment;
  it does NOT count vehicles.
- AI state + verified replay trace expose per-frame
  `road_margin_eligible_tracks`, `road_margin_only_tracks`, and
  `near_gate_eligible_tracks`. Per-track `road_gate_probe` evidence is optional
  and does not change `primary_gate_decision` or crossing clocks.
- Dashboard warnings use the **margin-aware** anchor indicator when present;
  older sessions safely fall back to the original `road_tracks_current_frame`.
  Diagnostic panel shows all counts separately. These numbers refer to currently
  observed anchors, not validated passage events.
- `audit-gate-coverage.ps1` appends margin/near-gate evidence when present.
  Older exports show `null` for absent fields, rather than misreporting `0`.
- Six new dependency-free AI unit tests, four source-integration tests and a
  Windows Docker stdlib step prevent regressions. Migration
  `0123_road_probe_v05109` updates release metadata only.

**No GT changes; no event/DB edits; no detector, tracker, model weights, Road Zone
geometry, time tolerance, gate admission, endpoint guard, HumanGuard or dedup
policy changes.** On an unchanged clip an identical count is expected.

## Run on Windows

Protect `.env`, `.git`, models, camera videos, PostgreSQL volumes and backups;
extract the ZIP over the source (or first stage it in a separate folder).

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

For the older #77 benchmark, the new fields are correctly unknown:

```powershell
.\scripts\audit-gate-coverage.ps1 `
  -Export ".\traffic-ai-benchmark-77-session-204.zip" `
  -ExpectedSession 204 `
  -OutputDirectory ".\gate-coverage-audit"
```

For **new** frame-level diagnostics, run AI with V0.5.109 first, export a
new benchmark ZIP for that session, and audit that ZIP instead.

After `test.ps1` and app validation succeed, publish by running:

```powershell
.\scripts\publish.ps1
```

The publisher tests, commits, pushes, tags and creates the GitHub Release.
The deliverable ZIP itself does not push or publish anything.

## Accuracy next steps

A matched/extra timecode alone does not identify a physical vehicle. In
particular the historical bicycle-IN GT near 591.091 seconds had zero **strict**
road tracks in a 1-second review window. Whether there were margin-eligible
anchors cannot be reconstructed from pre-V0.5.109 telemetry; do not assume
this is a detector failure or automatically insert a count. Continuous video
and verified new benchmark trace are required to calibrate targeted recovery
without increasing false positives. See phụ lục xác minh ở cuối README.md for evidence scope.

---

# Traffic AI V0.5.108 — Audit các lần chặn endpoint thực tế

Lệnh `audit-endpoint-precision.ps1` trước đây chỉ duyệt sự kiện **đã lưu vào DB**.
Vì đề xuất bị bộ lọc chặn không được lưu thành event, audit trên phiên mới có thể
báo `0 candidates` dù worker đã chặn hai đề xuất. Đây là lỗi báo cáo, không phải
bằng chứng bộ lọc không hoạt động.

Bản này đọc quyết định producer trực tiếp từ trace đã kiểm tra toàn vẹn, trình
bày riêng **đã chặn trong runtime** và **ứng viên mô phỏng từ event đã lưu**.
Bằng chứng gắn với từng lượt cắt vạch theo track, hướng, loại, phương pháp và
clock của event; trường hợp thiếu hoặc mâu thuẫn được ghi rõ, không đoán theo
mốc gần nhất rồi coi là xác nhận.

## Kết quả trên dữ liệu bạn gửi

Benchmark #78 / Session #205: GT **149**, AI **148**, khớp timecode **143**,
lọt **6**, dư **5**, F1 **96,30%**. Trace xác nhận runtime **0.5.107**, bộ lọc bật,
23.650 frame và fingerprint đúng source .107 đính kèm.

- Hai lần chặn thực tế: track 191795 tại **519,418s** và track 345897 tại
  **811,925s** (clock cắt vạch; frame xác nhận đến sau).
- Audit cũ báo 0 trên #78 vì cả hai không có event DB. Audit mới hiển thị hai
  quyết định này và số ứng viên còn lại riêng biệt.
- Trong 90 event nội suy hai bánh cần đối chiếu: 89 có clock chính xác;
  1 event (14901 tại 20,2295s) chỉ có bằng chứng proposal đang chờ HumanGuard,
  nên audit ghi **unknown**, không kết luận thiếu lượt đếm hay lỗi DB.
- Ảnh camera trong RAR thuộc Session #205, trace trùng hash với benchmark.
  Gần 812,577s có xe đang chạy cạnh xe đỗ và một lần đổi raw ID; bằng chứng
  này chưa đủ để tự xóa lượt xe đang chạy hoặc gộp các xe khác nhau.

**Phạm vi:** sửa audit, không thay detector/model, quy tắc đếm, GT, matcher,
ngưỡng ghép thời gian hoặc dữ liệu cũ. Van chở hàng vẫn là **xe tải**. Xe quay
lại cắt vạch vẫn được tính lượt mới. Không khẳng định F1 sẽ tăng với .108.
Migration `0122_endpoint_audit_v05108` chỉ cập nhật version metadata.

## Lệnh PowerShell

Giải nén full source vào thư mục dự án, giữ `.env`, `.git`, models, video,
snapshots, dữ liệu và Docker volumes đang có.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Audit lại phiên đã có (không cần chạy lại AI)
.\scripts\audit-endpoint-precision.ps1 `
  -Export ".\traffic-ai-benchmark-78-session-205.zip" `
  -OutputDirectory ".\endpoint-precision-audit-v108"

# Tự test, commit, push, tạo tag v0.5.108 và GitHub Release
.\scripts\publish.ps1
```

Kết quả kiểm thử thực tế và giới hạn môi trường ở đầu phụ lục xác minh ở cuối `README.md` và
`docs/verification-v05108/`. Cần chạy `test.ps1` trên Windows để kiểm tra Docker,
PostgreSQL và môi trường triển khai đầy đủ.

---

# Traffic AI V0.5.107 — Fix Windows Docker endpoint regression runner

**Bug fixed:** `scripts/test.ps1` launched `python -m pytest` inside a fresh
`python:3.14.7-slim` container with no installed pytest, causing a guaranteed
`No module named pytest` failure in V0.5.106 before backend/AI integration tests.

**Change:** the three existing endpoint-guard unit tests now use Python's built-in
`unittest` framework, and the dedicated Docker command uses `python -S -m unittest`
without installing third-party packages. Pytest still collects and runs these
`unittest.TestCase` tests during the AI service suite. New regression assertions
verify the slim runner's commands and execute the tests with site packages disabled.
This change is only to the testing workflow. The V0.5.106 endpoint precision
counting policy, the experiment toggle, and all persisted camera/GT/DB values remain
unchanged. Migration `0121_test_runner_v05107` updates only version metadata.

**Windows PowerShell** (after safely replacing source and preserving `.env`, models,
videos and PostgreSQL volumes):

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
# Publish only after validating the full test and runtime:
.\scripts\publish.ps1
```

**Limitations:** a host run of the full PowerShell/Docker/GPU suite must be
verified separately. No new inference or F1 improvement is claimed.

---

# Traffic AI V0.5.106 — Finite Endpoint Precision Experiment

## Why this version can change counts

Benchmark #77 / Session #204 was produced by **attested V0.5.105 runtime** (23,650 frames).
Ground Truth = 149, AI = 149, matches = 143, missed = 6, extra = 6, F1 = 96.0%.
Previous releases since V0.5.102 mostly changed audit/provenance, not the counting policy.

This version **changes the worker's submission decision** for one narrowly defined case on local VIDEO:
interpolated two-wheel crossings within the first 8% of the finite line, with an
unconfirmed destination-side body-center observation. Direct, rescued, truck,
car, bus, RTSP and crossings near the opposite line endpoint are unaffected.
The gate still closes its counted passage to prevent the same borderline frame
from being submitted repeatedly; no event is submitted for the rejected proposal.

**Experimental setting, enabled by default on local videos:**
`AI_FINITE_ENDPOINT_PRECISION_GUARD=1`. Set `=0` in `.env` and restart
with `./scripts/start.ps1` to restore V0.5.105 behavior; the existing `.env`
file is not overwritten by the source package. The selected setting is recorded
in the session metadata and the suppression count appears in the camera UI.

## Verified offline counterfactual, NOT a new inference score

A read-only replay of benchmark #77 identifies 2 *candidate* rejected events:
- **519.418s**, motorcycle OUT, interpolated, track 191795, projection 0.0551;
- **811.925s**, motorcycle OUT, interpolated, track 345897, projection 0.0763.

Both are unmatched under the supplied GT, while 0 previously matched events
are flagged by the narrow policy. A less cautious both-endpoint variant would
also flag 3 matched events and was rejected. This is a historical trace
counterfactual **only**: counts/score/identity are not modified and the real
F1 impact requires replaying the same clip under V0.5.106.

**Known limit:** the bicycle GT at 591.091s has zero road tracks in its 50-frame
window despite detections, so this precision filter will NOT repair that miss.
It may require inspecting video timestamps, road ROI, detector/GT annotation.
Do not silently add an event or change GT to inflate F1.

## Windows commands

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
# Read-only old benchmark counterfactual:
.\scripts\audit-endpoint-precision.ps1 `
  -Export '.\traffic-ai-benchmark-77-session-204.zip' `
  -OutputDirectory '.\endpoint-precision-audit'
# Compare new benchmark export after replay:
.\scripts\compare-benchmark-exports.ps1 `
  -Prior '.\traffic-ai-benchmark-77-session-204.zip' `
  -Current '.\traffic-ai-benchmark-78-session-205.zip' `
  -OutputDirectory '.\comparison-v106'
# Only after verification:
.\scripts\publish.ps1
```

The new file's benchmark/session ID must be replaced with the *actual* export
IDs; Session #205 is only an example. Keep `.env`, models, data, PostgreSQL
volumes and camera video when replacing the extracted source. Migration
`0120_endpoint_precision_v05106` changes schema-version metadata only.

---

# V0.5.105 — Runtime Trace Provenance & Session-Safe Audit

**Issue established:** Screenshot shows Benchmark #76 / Session #203 running V0.5.104,
but the uploaded ZIP is Benchmark #75 / Session #202 (created earlier). A gate
audit of #75 cannot diagnose V0.5.104's per-track decisions. The lack of
`primary_gate_decision` in #75 is expected and does not prove a stale container.

New worker traces include `ai_runtime_version`, SHA256 of the exact deployed
worker/counting/trace-identity source bytes, and a declared decision schema.
Every track emitted by the gate loop has an explicit primary/final reason,
including tracks skipped while HumanGuard is pending. The audit validates a
declared schema on every frame and can **fail closed** if a requested Session
ID does not match the ZIP or if provenance is missing. Old benchmark exports
remain readable without strict flags, clearly labeled `legacy-unattested`.

**No changes to detector/model weights, counting or GT/DB/scoring policies.**
No AI inference accuracy gain is claimed. This upgrade prevents misleading
comparisons and enables the next targeted logic correction when the #76 trace
is available. Migration 0119 changes schema-version metadata only.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
# Export Benchmark #76 / Session #203 from the application first.
.\scripts\audit-gate-coverage.ps1 `
  -Export ".\traffic-ai-benchmark-76-session-203.zip" `
  -ExpectedSession 203 `
  -OutputDirectory ".\gate-coverage-audit"
# For V0.5.105-generated sessions only, add -RequireProvenance.
# After Windows tests and replay are verified:
.\scripts\publish.ps1
```

---

# V0.5.104 — Per-track Gate Decision Provenance

This release adds a **read-only** primary gate decision reason for each canonical
track observation and propagates it to the benchmark trace, plus the final
secondary acceptance/rejection signal. Reasons include dead-band, missing an
opposite-side sample, road-zone rejection, finite-segment rejection, cooldown,
late confirmation, insufficient motion, long-gap rescue validation and cycles.

`scripts/audit-gate-coverage.ps1` now summarizes per-track gate reasons in
JSON/CSV/Markdown and reports the number of frames without road-zone tracks
around each mismatch. For old exports, reasons are explicitly marked
`not-recorded-in-export`; do not backfill or infer them from aggregate counters.

**No detector or counting thresholds changed.** No GT marks, historical events,
precision/recall scoring, and database data were altered. In particular, a
geometric span is insufficient evidence to automatically count a vehicle.
The 149 AI events in Benchmark #74 and #75 are identical, so F1 remains 96.0%
for the supplied runs. A new inference replay using this release is required
before concluding whether any policy change would improve 6 misses / 6 extras.

Database migration `0118_gate_decision_v05104` updates version metadata only.
Six new runtime and six new report regressions, with contract coverage.

## Windows commands

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1

.\scripts\audit-gate-coverage.ps1 `
  -Export ".\traffic-ai-benchmark-75-session-202.zip" `
  -OutputDirectory ".\gate-coverage-audit"

# When tests and inference are validated on Windows:
.\scripts\publish.ps1
```

**Safe update:** Back up `.env`, PostgreSQL volumes, model weights, videos and
user uploads before replacing the source. No admin creation required.

---

# V0.5.103 — Verified Finite-Gate Coverage Audit

## Release scope

Input: Benchmark #74 / Session #201 and camera images from `camera_1(20261018-131808).rar`. This release does not modify detector weights, crossing policy, database events, saved Ground Truth or benchmark score; no automatic re-counting or deleting vehicle events. The last two sessions #200/#201 have identical 149 event signatures (time, type, direction, method, canonical track) and identical 143 matched / 6 missed / 6 extra. A "zero net count error" is not perfect accuracy.

New `scripts/audit-gate-coverage.py` and `.ps1` verify the manifest and closed trace, inspect the finite counting segment at every frame near all 12 mismatch timecodes, and export JSON/CSV/Markdown with closest observed canonical tracks, normalized distance, finite-segment location, raw ID and sign-changing geometry witnesses. Geometric sign changes are *review candidates*, never proven physical passages. This lets reviewers distinguish missed nearby crossings from missing near-gate detections without increasing the matching window or fabricating counts. Only bounded per-case observations are retained; no full video decoding/model execution in the audit. Twelve regression tests and the test.ps1 contract are added. Alembic metadata-only revision `0117_gate_audit_v05103`.

To audit Benchmark #74 on Windows:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\audit-gate-coverage.ps1 -Export ".\traffic-ai-benchmark-74-session-201.zip" -OutputDirectory ".\gate-coverage-audit"
```

Always run `scripts/test.ps1` and `scripts/start.ps1` after installation, and `scripts/publish.ps1` only after confirming tests and runtime. Do not overwrite live `.env`, database volumes, models, source videos or prior audit exports during extraction.

# Traffic AI V0.5.102 — Admission-first HumanGuard + Verified Timecode Audit

**Nâng cấp từ V0.5.101; giữ nguyên GT và dữ liệu PostgreSQL.** Benchmark #73 / session #200 có **149 GT / 149 AI / 143 khớp / 6 lọt / 6 dư / F1 96,0%**. Đây là số đo của phiên chạy trước khi cập nhật .102, không phải đánh giá độ chính xác của bản .102. Một sự kiện AI dư bị loại so với #72 và số lọt vẫn 6, xác nhận trên export mới; không suy ra các ca còn lại đều là lỗi detector.

### Sửa lỗi chính: chỉ ghi nhận HumanGuard crossing sau khi hàng đợi nhận sự kiện

Nhánh `PipelineWorker._commit_guard_crossing` của .101 tăng `state.total_count`, biến đếm IN/OUT, ghi dấu context bicycle và đánh dấu transaction thành công **trước** lời gọi `EventDispatcher.submit`. Nếu queue đang đóng hoặc `submit` từ chối, worker vẫn đã tăng số và ghi audit "accepted" dù DB không có event. .102 dựng payload, gọi `submit` trước; chỉ sau khi lời gọi trả về thành công mới ghi state, bicycle rescue, raw handoff history, proposal audit và xóa pending. Lỗi submit tiếp tục nổi lên như cũ, pending được giữ nguyên. Admission ≠ backend persisted; receipt backend mới chứng minh lưu DB.

Ba test hồi quy kiểm tra dispatcher từ chối không tăng counter, không chấp nhận rescue khi lỗi, và submit phải diễn ra trước counter/handoff. Không thay thuật toán crossing, ngưỡng geometry, model weights, phân loại xe, bộ ghép GT hoặc hệ thống xác thực. Alembic revision `0116_queue_admit_v05102` chỉ cập nhật `schema_version`.

### Công cụ kiểm toán timecode

Mới có `scripts/audit-temporal-neighbors.ps1` (Python `.py` tương ứng). Chỉ chạy trên ZIP benchmark có manifest, trace hoàn chỉnh và hash đã được xác minh, xuất JSON/CSV/Markdown cho tất cả ca lọt/dư. Hiện rõ GT có event trong ngưỡng nhưng đã **được ghép với GT khác**, event cùng hướng **nằm ngoài cửa sổ 0,75 giây**, và GT **không có event trong ±2 giây**. Không tự ghép lại, sửa timestamp, thêm/xóa lượt hay suy đoán danh tính cùng xe.

Với #73: GT OUT lúc **392,179 s** có AI OUT gần nhất lúc **393,303 s** (trễ 1,124 s, ngoài tolerance; AI này đã ghép GT khác), GT xe đạp IN lúc **591,091 s** không có event AI trong ±2 giây; bốn GT còn lại có AI trong tolerance nhưng đã được gán mốc GT khác. Mốc 882,290 s là xe tải IN có ảnh vùng vạch: không tự loại chỉ vì báo dư.

Chạy trên Windows sau khi chép source, **giữ `.env`, `.git`, models, video, snapshot và Docker volume PostgreSQL**:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1

# Kiểm toán benchmark cũ, không chạy lại AI:
.\scripts\audit-temporal-neighbors.ps1 -Export ".\traffic-ai-benchmark-73-session-200.zip" -OutputDirectory ".\temporal-neighbor-audit"

# Chỉ sau khi test/chạy ổn định:
.\scripts\publish.ps1
```

Cần chạy clip trên bản .102 mới để biết hiệu quả thực tế; bản cập nhật này **không tuyên bố giảm thêm 6 lượt lọt hay 6 lượt dư**.

---

# Traffic AI V0.5.101 — Sửa HumanGuard deferred crossing / Raw-ID Guard

**Bản sửa lỗi kế thừa đầy đủ V0.5.100.** Khắc phục 6 bài kiểm thử AI thất bại trong `tests/test_guard_transaction.py`: test fixture dựng `PipelineWorker.__new__` mà không chạy `__init__`, vì vậy thuộc tính `_raw_handoff_guard_enabled` không tồn tại ở nhánh `_commit_guard_crossing`. Bản mới coi guard tùy chọn là tắt khi chưa khởi tạo, nhưng khi worker thực bật vẫn lưu passage đã xác nhận.

**An toàn giao dịch:** Raw-ID guard chỉ ghi lịch sử một crossing HumanGuard deferred sau khi `EventDispatcher.submit(...)` hoàn tất, tránh chặn nhầm lượt sau nếu dispatcher từ chối sự kiện. Thêm ba regression test: worker thiếu thuộc tính guard; guard bật và ghi đúng một passage sau admission; dispatcher lỗi không để lại ghi nhận giả. Không chỉnh GT, event lịch sử, thuật toán phân loại hoặc giá trị benchmark. Alembic `0115_guard_commit_v05101` chỉ cập nhật `schema_version`, không tạo/xóa bảng.

**Chạy Windows (giữ nguyên `.env`, data, models và PostgreSQL volumes):**

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
# Khi kiểm thử/chạy ổn và có gh: .\scripts\publish.ps1
```

**Kết quả chạy trên máy của bạn với V0.5.100:** backend 195 đạt, AI 729 đạt / 6 lỗi (log ngày 18-10). V0.5.101 được kiểm thử lại độc lập; xem phụ lục xác minh ở cuối `README.md` cho phạm vi và giới hạn môi trường. Không tuyên bố F1 thay đổi cho tới khi chạy một phiên video và xuất benchmark mới.

---

# Traffic AI V0.5.100 — Verified raw-ID handoff suppression

**Nâng cấp full source từ V0.5.99, lần này có thay đổi runtime worker**. Dữ liệu benchmark #72 / session #199 có 149 GT / 150 AI / 143 khớp / 6 lọt / 7 dư và giống hệt #71 / session #198 theo chữ ký crossing. Đây là số của phiên đã chạy, **không phải** kết quả inference mới với V0.5.100.

## Sửa lỗi đếm trùng khi raw tracker ID chuyển qua hai canonical

Trong trace cả hai phiên, frame 12304 có raw ID `182056` nằm dưới canonical `181574`; frame 12305 raw ID này chuyển sang canonical `182056` với box IoU 0.7003; hai canonical nhận OUT tại 491.920 và 492.200 giây, với điểm cắt cách nhau Δx=0.009272, Δy=0.002097. Dấu hiệu này đủ để tạo guard *rất hẹp* thay vì chặn các xe chỉ vì cùng timecode.

`app.raw_handoff_guard.RawHandoffCrossingGuard` quan sát trực tuyến raw/canonical ID, đòi hỏi tất cả điều kiện: **cùng raw ID được quan sát dưới hai canonical khác nhau** (đổi trong tối đa 3 frame), IoU box khi handoff ≥0.64, canonical cũ có passage thực sự được commit trong 12 frame, cùng hướng IN hoặc OUT, event mới là `direct`, thời gian sau handoff ≤10 frame, điểm cắt x lệch ≤0.025 và y lệch ≤0.018. Không dùng GT, tên video, session ID, danh sách track ID cố định hay matcher để sửa đầu ra; không chặn xe khác raw ID dù rất gần nhau. Chính sách áp dụng cho `video` với 2 bánh, giữ nguyên RTSP/stream và 4 bánh. Nếu cần A/B, đặt `AI_VERIFIED_RAW_HANDOFF_GUARD=0` trong `.env` rồi chạy lại. Mặc định `1` trên local video.

Bộ bảo vệ chỉ chặn ghi thêm event worker/DB khi có bằng chứng; canonical bị chặn vẫn giữ trạng thái gate đã xác nhận để không bắn lại cùng passage ngay sau đó. Trace lưu `producer_decision=verified_raw_handoff_duplicate_suppressed`, kèm raw/owner ID, IoU, Δframe, Δxy; Dashboard / Thông số kỹ thuật hiển thị **Raw-ID trùng được chặn**. Không thay đổi GT, benchmark matcher, rule class, Human Guard, dedup backend hay mật khẩu Admin.

**Replay shadow** `scripts/audit-raw-handoff.py` (`.ps1` trên Windows) xác minh manifest/CRC/SHA trace, quét đủ 23.650 frame và xuất JSON/Markdown; cả #71 và #72 cho **1 ứng viên** cùng vị trí 492.200s trong 167 đề xuất. Đây là mô phỏng offline từ dữ liệu track cũ, không phải xác nhận F1 mới. Chưa có mô phỏng lại full-video YOLO/tracker sau bản sửa, và có rủi ro hiếm khi raw ID bị ByteTrack tái sử dụng cho hai xe chồng lấp; có thể tắt guard để so đối chứng.

## Cập nhật, kiểm tra, chạy và xuất bản

Giữ nguyên `.env`, `.git`, models, MP4, ảnh camera, storage và PostgreSQL volumes; không khởi tạo lại Admin. Metadata schema `0114_raw_handoff_v05100` nối `0113_passage_evidence_v0599`, không chỉnh bảng hoặc record cũ.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1

# Phân tích lại export đã lưu; không chạy GPU và không tự sửa điểm:
.\scripts\audit-raw-handoff.ps1 -Export ".\traffic-ai-benchmark-72-session-199.zip" -OutputDirectory ".\raw-handoff-audit"

# Chỉ khi test/chạy ổn thì phát hành tự động:
.\scripts\publish.ps1
```

Chạy lại AI **một lần** với cùng `clip1.mp4` và cùng hình học vạch, tạo benchmark mới rồi sao chép GT từ #72 để so sánh. **Không khẳng định** trước rằng sẽ giảm từ 7 xuống 6 dư hoặc tăng F1: đây mới là counterfactual dựa trên trace cũ. Hai GT không có đề xuất crossing gần 392.179s và 591.091s vẫn phải rà detector/track riêng, không tự sinh lượt ảo.

---

# Traffic AI V0.5.99 - Verified Passage Evidence Review

**Nâng cấp từ V0.5.98; không tự chỉnh thuật toán counting/detector.** Phân tích benchmark mới #71 / session #198 bằng full export ZIP và 166 JPG trong RAR (giải nén riêng). 149 GT / 150 AI / 143 khớp / 6 lọt / 7 dư: dữ liệu từ lượt chạy V0.5.98, **không phải** kết quả inference sau khi nâng cấp. 4 trong 6 mốc GT chưa khớp có event AI đã được matcher ghép sang GT khác, không đủ bằng chứng nói detector bỏ sót; 2 GT còn lại không có event đã lưu tương ứng trong tolerance. 1 AI extra ở khoảng 491.920 giây có chỉ dấu hàng xóm hình học, nhưng chưa xác lập cùng xe. Van/xe tải tại 882.290 giây có snapshot ngay vùng vạch; không loại tự động.

**Giao diện:** trong báo cáo Benchmark thêm ghi chú V0.5.99 phân biệt số GT cạnh tranh ghép timecode với số GT chưa có event DB trong cửa sổ ghép, có kiểm tra phạm vi/chỉ số để không hiện dữ liệu thiếu nhất quán. 4 bài kiểm tra Node mới bảo vệ logic này.

**Tính năng mới:** `scripts/audit-error-evidence.py` / `audit-error-evidence.ps1`: xác minh CRC, manifest SHA256, SHA256 trace giải nén và delivery footer qua benchmark-forensics hiện có; tạo **13 hồ sơ rà soát** theo timecode với tình trạng matcher, event GT đã chiếm AI, khung hình/track hai phía, crossing proposal / delivery receipt gần thời điểm, cùng ảnh JPG gần nhất (nếu đã giải nén). Ảnh chỉ được liên kết khi cách source time tối đa **1 giây** và dùng FPS phiên từ snapshot đã xác minh. Kết quả xuất `passage-evidence.json`, `.csv`, `.md`; không ghi DB, không sửa GT, không tự gộp hoặc xóa event/track. Gần nhau về thời gian, xuất hiện ở hai phía vạch và JPG tĩnh đều **không chứng minh** cùng xe.

Ví dụ sau khi sao chép bản full source, export benchmark đã tải và (nếu cần) giải nén RAR vào thư mục ảnh:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1

# Đọc hồ sơ benchmark đã export, không cần chạy lại AI/benchmark.
.\scripts\audit-error-evidence.ps1 -Export ".\traffic-ai-benchmark-71-session-198.zip" -OutputDirectory ".\passage-evidence-audit"

# Có thể truyền ảnh JPG đã giải nén từ RAR để ghép hình theo frame/timecode.
.\scripts\audit-error-evidence.ps1 -Export ".\traffic-ai-benchmark-71-session-198.zip" -CameraImages ".\camera_1" -OutputDirectory ".\passage-evidence-audit"

# Chỉ publish khi đã test/kiểm tra trên máy thật thành công.
.\scripts\publish.ps1
```

Bản .99 có migration metadata `0113_passage_evidence_v0599`, parent `0112_clock_owner_v0598`; không thay đổi cấu trúc dữ liệu hay mật khẩu Admin. Hãy so benchmark của **phiên chạy mới** với GT có cùng video/vạch trước khi tuyên bố chỉ số AI thay đổi. Mục tiêu của công cụ mới là phân loại bằng chứng để nhắm đúng lỗi, không tuyên bố đã giảm từ 6/7.

---

# Traffic AI V0.5.98 — Giữ đúng lượt sở hữu mốc thời gian crossing

Sửa lỗi mốc thời gian của một đoạn quỹ đạo cũ còn đi theo alias sau khi gộp track vào một track đã nhận lượt cắt vạch mới hơn. Lỗi này có thể kéo timestamp của event về lượt trước và gây sai ghép benchmark. Bộ đếm không được tự tạo thêm event từ timestamp hint.

Ví dụ tái hiện bằng API thật: track 1 có hint IN tại frame 11.5 từ đoạn quỹ đạo kết thúc frame 13; track 2 đã nhận OUT ở frame 18. Bản cũ gộp 1→2 rồi vẫn trả hint 11.5 khi hỏi IN ở frame 22. Bản .98 loại hint đã hết vòng đời này.

Kiểm tra dựa vào frame **kết thúc đoạn quỹ đạo**, theo cùng điều kiện đang dùng cho pending span; không so thẳng timestamp nội suy với frame xác nhận. Vì vậy đoạn kết thúc frame 13 vẫn hợp lệ sau xác nhận frame 12, dù điểm cắt nội suy là frame 11.5. Hint hợp lệ và lượt xe quay lại vẫn có kiểm thử bảo vệ.

## Kiểm thử và dữ liệu mới

**1.002 kiểm thử offline/Node đạt, 0 lỗi**. Có 16 regression mới dùng hình học và các API rescuer thật: bản .97 đạt 12/sai 4; bản .98 đạt 16/16. Giữ nguyên toàn bộ test cũ và 79 contract Assert. Chỉ sửa ba hàm quản lý clock hint trong counting.py; các ngưỡng geometry, tracking, Human Guard, class policy, dedup và matcher được giữ nguyên.

Đã kiểm đầy đủ export #70/session 197 và đối chiếu #69/196: cùng 149 GT, config và đủ 150 event trên các trường source; cả hai đều **143 khớp / 6 lọt / 7 dư, F1 95.6522%**. Có thay đổi ở scheduling/class-refiner audit, nên không coi toàn bộ trace giống nhau. Lỗi hint vừa sửa được tái lập độc lập, chưa được chứng minh là nguyên nhân sáu lượt lọt hoặc bảy lượt dư trong clip này.

Chưa chạy Docker/PowerShell native hoặc inference đầy đủ .98 tại môi trường đóng gói. Chi tiết kiểm chứng và giới hạn nằm trong phụ lục xác minh ở cuối README.md.

## Cập nhật và đo bản .98

Giải nén chép đè source, giữ .env, .git, models, video, snapshots, volumes và dữ liệu hiện có. Migration metadata mới `0112_clock_owner_v0598`, parent `0111_count_review_v0597`. Không tạo lại Admin.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.98 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443 rồi Ctrl+F5. Để đo thay đổi timestamp .98, chạy AI **một lần**, tạo benchmark cho phiên mới rồi sao chép GT từ #70 nếu vẫn cùng clip/vạch. Đối chiếu lại #70 chỉ chấm dữ liệu đã lưu của phiên 197; thao tác đó không chạy lại AI. Các phần dưới là lịch sử giữ nguyên.

---

# Traffic AI V0.5.97 — Rà soát track chồng lấp và đổi ID

Bản này bổ sung bằng chứng quỹ đạo cho các ca AI đếm dư, sai hướng và sai loại. Sau khi cập nhật source và khởi động, chọn Benchmark #69, bấm **Đối chiếu lại**, rồi mở **Track chồng lấp và đổi ID** trong ca cần xem. Các nút Đầu/Cuối hoặc Trước/Sau đưa video tới đúng các quan sát đã lưu trong trace phiên 196; không cần tạo thêm benchmark để đọc lại bằng chứng này.

## Chức năng mới

- Hiện các track đồng thời có box lồng nhau, số frame cùng xuất hiện, mức phủ box nhỏ và mốc thời gian quan sát. Track của event gần nhất đã khớp GT được nhận diện từ event đã lưu, thay vì đoán từ ID gần nhau.
- Phân biệt dịch chuyển tâm box quan sát được với vận tốc đã lọc. Hai loại số đo có thể khác nhau đáng kể khi box rung hoặc ID ghép sai.
- Hiện lần đổi raw ID trong cùng canonical track, khoảng cách frame và dịch chuyển tâm box; có nút xem video trước/sau.
- Các ca dư và sai hướng có thêm dấu vết worker đề xuất crossing và phản hồi backend. Bằng chứng luôn gắn với track của event AI đang xem.

Các số đo chồng box và raw ID phục vụ rà soát, không tự kết luận hai track là cùng phương tiện. Bộ đếm, matcher và GT giữ nguyên; đặc biệt hai xe đi sát nhau có thể tạo hình học tương tự một xe bị tách box. Trace thiếu hình học không được bù bằng quan sát giả.

## Đối chiếu dữ liệu bạn gửi

Đã kiểm CRC, manifest SHA/size và gzip của cả hai bản export; 149 GT tương đương và config giống từng byte. Toàn bộ 149 event cũ không đổi, chỉ thêm xe máy IN track 143399 tại 397.0209 s, khớp GT 397.288 s.

| Chỉ số | #68 / 195 | #69 / 196 |
|---|---:|---:|
| GT | 149 | 149 |
| AI đã lưu | 149 | 150 |
| Khớp / lọt / dư | 142 / 7 / 7 | 143 / 6 / 7 |
| F1 đếm | 95.3020% | 95.6522% |
| Khớp cả thời gian, loại và hướng | 137 | 138 |

Ảnh giao diện phiên 196 bạn gửi hiển thị V0.5.96; số liệu #69 là kết quả export của phiên đó, không phải điểm inference mới của .97. Trace không ghi build hash/version nên không độc lập xác minh được chính xác bytes runtime. Cặp 181574/182056 quanh 492 s có ảnh một xe máy với hai box lồng nhau. Track 296297 quanh 754 s có lần đổi raw ID qua gap 18 frame cần xem lại. Các trường hợp này được đưa vào kiểm thử và bằng chứng rà soát; không xóa event theo timecode để làm giảm số dư.

Ảnh van chở hàng tại 641.98 s phù hợp quy ước xe tải của dự án dù GT ghi ô tô; van quay lại tại 882.29 s cũng có ảnh cắt vạch IN thật. Hãy đối chiếu GT bằng video trước khi sửa nhãn. Không tự đổi hai trường hợp này. 6 lượt lọt và 7 lượt dư trong export vẫn là số liệu được giữ để kiểm tra.

## Cập nhật và chạy

Giải nén chép đè source vào thư mục dự án, giữ .env, .git, models, video, snapshots và các volume/dữ liệu hiện có. Không tạo lại tài khoản Admin. Migration metadata mới: `0111_count_review_v0597`, parent `0110_pycache_v0596`.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.97 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443 rồi Ctrl+F5. Chi tiết kiểm thử và giới hạn xem phụ lục xác minh ở cuối README.md. Các mục dưới đây là lịch sử giữ nguyên.

---

# Traffic AI V0.5.96 — Sửa cache Python khi chạy test Docker

Bản này xử lý lỗi trong log .95: kiểm tra source báo đúng version mới, nhưng ba test backend vẫn nhận `0.5.94` thay vì `0.5.95`.

## Nguyên nhân đã tái hiện

Hai ZIP .94/.95 trước đó đóng các file với cùng thời gian 00:00 ngày 17/10. Riêng `backend/app/main.py` đổi version nhưng vẫn cùng kích thước 1181 byte. Python có thể xem bytecode `.pyc` cũ là hợp lệ vì timestamp và kích thước đều khớp, dù nội dung source đã đổi. `compileall` mặc định cũng có thể bỏ qua cache này.

Đã tái hiện bằng chính bytes `main.py` của hai ZIP và loader CPython thật: source .95 nhưng code cache còn .94; dùng cache prefix mới đọc đúng .95. Chỉ thêm `-B` hoặc `PYTHONDONTWRITEBYTECODE=1` không đủ để ngăn đọc cache cũ.

## Sửa trong .96

- Cả **20 lệnh Docker Python** của `test.ps1` dùng `PYTHONPYCACHEPREFIX=/tmp/traffic-ai-test-pycache` và `PYTHONDONTWRITEBYTECODE=1`. Prefix nằm trong filesystem riêng của container `--rm`, không nằm trong source bind mount. Mỗi container có cache riêng; `compileall` cũng ghi cache vào prefix này.
- Bổ sung pattern cache đệ quy trong `.dockerignore` của backend/AI để không đưa `.pyc` lồng trong thư mục vào image. Pattern `**` theo [Docker Docs](https://docs.docker.com/build/concepts/context/).
- ZIP .96 dùng timestamp build UTC mới; audit kiểm tra các Python file đã thay đổi có timestamp khác ZIP .95.
- Thêm 8 regression dùng tiến trình Python thật cho trường hợp cùng mtime/kích thước, no-write flag, cache prefix mới/cũ và compileall. Giữ nguyên các test phiên bản hiện có.

**955 kiểm thử offline/Node đạt.** Source gồm đủ các chức năng .95: khôi phục rider có bằng chứng trực tiếp, Docker readiness, điểm neo ổn định, báo cáo Excel/CSV/PDF, phân quyền, backup và benchmark. Bản này không thay thuật toán AI hoặc điểm benchmark.

Log Windows bạn gửi đã xác nhận harness Docker readiness **26 assertions đạt**; backend có 186 đạt/3 lỗi version trong hai lần chạy .95. Đây không phải log chạy .96. Kiểm chứng .96 ở môi trường hiện tại chưa có Docker/PowerShell/HTTP ORM đầy đủ; chi tiết xem phụ lục xác minh ở cuối README.md.

## Test, chạy và tự động phát hành

Chép full source vào dự án hiện có, giữ `.env`, `.git`, models, video và volumes. Các lệnh dưới không yêu cầu xóa cache trên máy hoặc tạo lại Admin.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.96 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443 rồi Ctrl+F5. Migration `0110_pycache_v0596`, parent `0109_docker_guard_v0595`, chỉ đồng bộ schema_version .96. Các mục bên dưới là lịch sử giữ nguyên.

---

# Traffic AI V0.5.95 — Khôi phục rider có bằng chứng và kiểm tra Docker

Tiếp tục từ full source V0.5.94. Giữ điểm neo ổn định, báo cáo Excel/CSV/PDF, dashboard, phân quyền, backup, benchmark và toàn bộ chức năng cũ.

## Sửa HumanGuard giữ trạng thái chặn khi đã có bằng chứng xe

Trace session 195 xác định track 143399 bị chặn từ frame 9806. Tại frame 9822, model kiểm tra cùng crop đã cho xe trực tiếp 0.700684, PERSON 0.672363; nhưng box PERSON không đủ chiếm ưu thế hình học nên hàm trả neutral trước khi xét bằng chứng xe. Neutral giữ nguyên trạng thái rejected, làm các candidate quanh 397 s tiếp tục bị loại.

Bản .95 xét **bằng chứng xe trực tiếp cạnh tranh** trong đúng nhánh hình học PERSON chưa đủ chiếm ưu thế, dùng nguyên comparator có sẵn `direct >= max(0.20, person - confidence_margin - 0.03)`. Confidence phải là giá trị hợp lệ trong `[0,1]`. Bằng chứng đủ mạnh trả `rider_supported`, để chính sách hiện có khôi phục rider; không hạ ngưỡng, tăng inference hay sửa số lần xác nhận.

Xe lân cận hoặc chuyển động riêng lẻ không được dùng để khôi phục ở nhánh này. Các điều kiện thiếu PERSON, box không giống người, class khác và nhánh hình học PERSON đã chiếm ưu thế giữ cách xử lý cũ. Cùng frame vẫn dùng một quyết định cache; toàn bộ `HumanGuardTrackPolicy`, tracking, counter, rescuer và backend dedup giữ nguyên.

Tái lập có kiểm soát 26 quan sát thật bằng các ý kiến/IoU/coverage đã ghi, với predicate/policy/cache thật: .94 giữ rejected; .95 khôi phục tại frame 9822 và rider tại candidate frame 9929/9938. Trace không có PERSON rectangle nên phép kiểm tra dùng các chỉ số hình học đã ghi, **không phải inference lại ảnh hoặc benchmark toàn clip**. Fixture số liệu cùng các kiểm tra người đứng cạnh xe/score không hợp lệ được đóng gói trong source.

## Sửa lỗi Docker chưa chạy trong log Windows

Log bạn gửi báo thiếu pipe `dockerDesktopLinuxEngine`. Lỗi gốc là Docker Linux engine chưa kết nối được; thông báo không tạo được PostgreSQL volume chỉ là lỗi theo sau.

- `start.ps1` kiểm tra engine trước khi sửa `.env`, tạo secret/chứng chỉ hoặc query volume. Query volume thất bại dừng rõ ràng, không coi đó là volume chưa tồn tại.
- `test.ps1` kiểm tra engine trước test đầu tiên cần Docker. Engine Linux sẵn sàng trả ngay, không có thời gian ngủ cố định.
- Khi xác minh đúng Windows/context `desktop-linux`/pipe cục bộ, script có thể mở Docker Desktop một lần và chờ engine trong thời hạn 120 giây. Mỗi lệnh probe có deadline riêng và đọc stdout/stderr đồng thời. Desktop đã mở chỉ được chờ, không mở lại.
- Docker CLI chưa cài, Windows containers, endpoint/context khác chưa sẵn sàng hoặc hết thời gian sẽ có thông báo xử lý rõ. Không tự đổi Docker context, restart service/WSL, xóa volume hay thay dữ liệu.
- Bộ kiểm tra PowerShell độc lập daemon được chạy trên host trước preflight trong `test.ps1`; môi trường kiểm chứng hiện tại chưa có PowerShell nên phần native này chưa chạy tại đây. Kết quả chi tiết xem phụ lục xác minh ở cuối README.md.

## Kết quả input mới

Benchmark #68/session 195 chạy bản .94: **149 GT / 149 AI / 142 khớp / 7 lọt / 7 dư / F1 95,302%**. So với session 194, hết lọt tại 525.21028 s và 816.964611 s, không thêm GT lọt mới. Tổng AI bằng GT vẫn còn 7 lọt và 7 dư, không phải đếm đúng hoàn toàn.

Ba sai loại vẫn giữ nguyên. Hướng startup 0.16 s được sửa nhưng có một assignment sai hướng mới quanh 754.558486 s. Số lần refiner/model phụ cũng khác nên không gán toàn bộ cải thiện cho riêng thay đổi điểm neo. Không tự sửa GT, quy ước van chở hàng là Xe tải hay matcher.

**Chưa có điểm full pipeline của .95.** Cần chạy lại cùng clip/vạch/model với GT đã review để đo hiệu quả sửa rider.

## Test, chạy và tự động phát hành

Chép full source vào dự án hiện có, giữ `.env`, `.git`, models, video và volumes. Không tạo lại Admin.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.95 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl+F5. Nếu Docker Desktop không ở thư mục/context thông thường, mở ứng dụng thủ công và chờ Engine running trước khi chạy lệnh. Sau replay .95, sao chép GT sang benchmark mới rồi Tải hồ sơ benchmark sau khi có GT.

Migration metadata `0109_docker_guard_v0595`, parent `0108_guard_audit_v0594`; không thay GT/events. Các mục bên dưới là lịch sử được giữ nguyên.

---

# Traffic AI V0.5.94 — Ổn định điểm neo và chẩn đoán Human Guard

Tiếp tục từ đúng full source V0.5.93. Giữ báo cáo giờ/ngày/tháng, Excel/CSV/PDF, phân quyền, backup, dashboard, huấn luyện, benchmark, công cụ audit và quy trình GitHub Release hiện có. Không cần tạo lại tài khoản Admin.

## Sửa dao động hướng ở xe hai bánh

Trace session 194 cho thấy track 345897 có box lớn nhưng tâm chỉ dao động vài pixel; heading đổi mạnh làm điểm neo đi qua vạch và tạo các lượt sớm. Hai event thực được lưu là IN 811.64 s và OUT 815.2484 s; GT IN 816.964961 s còn lọt.

Bản này giới hạn góc đổi hướng của **điểm neo hai bánh** theo quãng đường tâm thực sự di chuyển và bán kính box (nửa đường chéo lớn hơn của box trước/hiện tại, sàn 1.5 px). Khi bước di chuyển nhỏ hơn bán kính, góc đổi tối đa là `travel / radius` radian; độ cong nhỏ có đủ chuyển động hỗ trợ vẫn cập nhật ngay. Bước di chuyển từ một bán kính trở lên cập nhật ngay theo vận tốc mới, như nhánh xử lý trước. Không thay vận tốc đo/dự đoán dùng để nối identity.

Xe bốn bánh, thiếu rect, chưa có heading, khoảng mất dấu dài và chế độ rollback giữ cách xử lý heading của .93. Điểm neo giữ độ lớn ở ngưỡng full-heading, tránh vector bằng 0 khi quay ngược 180°. Không nới Gate, cửa sổ matching, backend dedup, Human Guard hay đổi quy ước van chở hàng là Xe tải. Có thể đối chiếu với .93 bằng `AI_TWO_WHEEL_HEADING_INERTIA=0` trong `.env`; mặc định bật. Guard nối nhầm ID gap 1–12 của .93 vẫn được giữ.

Tái lập có kiểm soát trên 677 hàng của track 345897 bằng heading/counter/rescuer thật còn OUT 811.925 s và IN 816.922 s, loại chu kỳ dao động quanh 815 s. OUT sớm vẫn chưa có GT tương ứng nên không tuyên bố đã hết dư. Kiểm tra mở rộng trên 271.208 observations giữ toàn bộ 142 GT từng khớp thời gian; đây là kiểm tra hình học, không phải số event DB của ứng dụng. Một thay đổi ghép hướng do hai proposal cạnh tranh quanh 606 s được ghi rõ trong phụ lục xác minh ở cuối README.md.

## Xem bằng chứng Human Guard trên web

Ở **Benchmark Report**, mở **Bằng chứng Human Guard** dưới lượt lọt hoặc sai loại xe. Phiên mới ghi PERSON, xe trực tiếp/xe lân cận, IoU/độ phủ khi đã tính, frame kiểm tra gốc, tuổi cache, số lần xác nhận từ các frame riêng biệt và trạng thái track.

- Phân biệt quan sát mới, cùng frame, chờ chu kỳ kiểm tra, frame cũ, model chưa sẵn sàng và không có kết quả. Thiếu bằng chứng hiển thị `—`, không biến thành confidence 0.
- Nếu GT chưa có identity AI đã ghép, UI ghi rõ đây là **các track gần timecode**, cần xem video để xác định xe GT. Không gán một track lân cận thành xe bị lọt.
- Chỉ giữ tối đa 8 bản ghi chẩn đoán; danh sách ghi trong mỗi frame có giới hạn. Không ghi ảnh crop, đường dẫn nội bộ hoặc response model vào audit. Trace có thể lớn hơn do thêm bằng chứng; chưa đo dung lượng gzip của một lần inference mới.
- Hàm quyết định và chính sách Human Guard giữ nguyên. Dùng lại cache không tạo thêm strike; lỗi ghi audit không chặn quá trình đếm. Trace cũ chưa có trường này không được dựng thêm bằng chứng.

## Kết quả input đã xác minh

Benchmark #67/session 194: **149 GT / 151 AI / 140 khớp / 9 lọt / 11 dư / F1 93,33%**. So với #66/session 193: khớp thêm mốc 534.086505 s và 640.140782 s, hết dư 638.12 s; không có signature lọt/dư mới. Cùng 149 GT theo thứ tự và cấu hình byte giống nhau; chưa chứng minh weights và toàn bộ môi trường inference giống nhau nên không gán mọi cải thiện cho một thay đổi source.

Đính chính mô tả ảnh trong ghi chú .93 bên dưới: track 255061 ở frame 15954/15968 của phiên mới là **box phần thân trên của người đang đi xe máy**, không phải người đi bộ. .93 tách identity này khỏi 251681: OUT 638.6037 s và IN 639.7107 s đều khớp GT. Lỗi đã chứng minh là ghép nhầm hai phương tiện.

**Chưa có điểm benchmark toàn clip của V0.5.94.** Các kiểm tra tái lập dùng observations đã ghi và thuật toán thật, không thay thế một lần chạy detector/tracker/models/Guard/dispatcher/backend toàn pipeline. Kết quả và giới hạn cụ thể xem phụ lục xác minh ở cuối README.md. Human Guard ở 397 s vẫn cần crop-model opinions của lần chạy mới trước khi quyết định thay ngưỡng. Source không tự sửa GT, class hay timecode.

## Test, chạy và tự động phát hành

Chép đầy đủ source vào `D:\LienThongDH\DoAn\traffic-ai`, giữ `.env`, `.git`, models, video và volumes hiện có.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.94 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443 rồi Ctrl+F5. Chạy lại cùng clip/vạch/model, sao chép GT đã review sang benchmark mới rồi **Tải hồ sơ benchmark** sau khi có GT. Bằng chứng Human Guard mới xuất hiện từ trace của lần chạy .94. Báo cáo thống kê vẫn có thể đọc phiên 194 đang lưu; chọn đúng phiên để không cộng nhiều lần chạy lại video.

Migration `0108_guard_audit_v0594`, parent `0107_reports_guard_v0593`, chỉ đồng bộ schema_version 0.5.94; không chỉnh dữ liệu GT/events. `publish.ps1` đọc VERSION và giữ quy trình kiểm thử → commit/push → tag → Release, không ghi đè tag cũ. Các mục bên dưới là lịch sử của những bản trước.

---

# Traffic AI V0.5.93 — Báo cáo thống kê và sửa nối ID cự ly ngắn

Bản này tiếp tục từ đúng full source V0.5.92 được cung cấp. Giữ toàn bộ chức năng đăng nhập/phân quyền, backup, huấn luyện, dashboard 50/50, benchmark và công cụ audit cũ.

## Báo cáo thống kê nâng cao

Mở **Báo cáo** trên thanh điều hướng. Chọn camera, một phiên đếm, khoảng ngày và loại xe; nhóm theo **giờ / ngày / tháng** rồi bấm **Xem báo cáo**. Có tổng lượt, IN/OUT/chưa rõ hướng, biểu đồ lưu lượng, bảng theo camera/loại xe và các giờ cao điểm. Phiên mặc định là phiên gần nhất của camera; ngày được điền từ thời điểm bắt đầu/kết thúc phiên.

Báo cáo tính trên **event đã lưu trong PostgreSQL**, không phải số đề xuất worker. Đồng hồ dùng thời điểm hệ thống ghi nhận event theo **UTC+7**, không suy diễn ngày quay video từ hình overlay. Chạy lại cùng video tạo phiên mới; chọn một phiên để tránh cộng nhiều lần replay. Giờ cao điểm là từng khoảng một giờ có lưu lượng cao nhất trong khoảng ngày, không phải trung bình giờ trong ngày.

- Xuất **Excel .xlsx thật**, CSV UTF-8 BOM và PDF tiếng Việt có font nhúng, phân trang. Export có cùng bộ lọc với báo cáo đang xem; đổi bộ lọc phải xem lại trước khi tải.
- Viewer được đọc; Admin/Operator được tải. API mới vẫn qua authentication/RBAC hiện có.
- Giao diện chọn ngày cuối bao gồm cả ngày; API chuyển thành khoảng `[start, end)` theo UTC+7. Tối đa 366 ngày, báo cáo theo giờ tối đa 31 ngày. Query SQL tổng hợp có giới hạn 100.000 nhóm và báo lỗi khi vượt, không trả tổng thiếu.
- API: `GET /api/reports/traffic`, `GET /api/reports/traffic/export?format=xlsx|csv|pdf`, `GET /api/reports/sessions`.

## Sửa một nguyên nhân đếm dư và che mất lượt thật

Trace session 193 cho thấy raw 255061 được ghép vào canonical 251681 chỉ một frame 15954. Ảnh tại cửa sổ này cho thấy box người đi bộ nhận lịch sử track xe; event IN 638.12 s được lưu trước, còn proposal của track 251681 tại 639.7107 s bị backend gộp. GT 9635 nằm 640.1409 s. Không nới cửa sổ dedup để giữ thêm cả event sớm lẫn event sau.

V0.5.93 mở điều kiện kiểm tra mâu thuẫn nối ID hai bánh có sẵn từ gap 4–12 xuống gap 1–12 frame. Chỉ chặn khi đủ hai bounding box và đồng thời khoảng cách trực tiếp lẫn vị trí dự đoán đều vượt ngưỡng footprint hiện có. Xe nhanh khớp dự đoán, bốn bánh, gap > 12, raw ID đã có mapping và chế độ tắt guard giữ đường xử lý cũ. Gate, heading, Human Guard, backend dedup, class/taxonomy và matching/tolerance không đổi.

Reproducer dùng resolver và primary counter thật trên 158 dòng đo mục tiêu: .92 ghép raw 255061 vào 251681 và tạo crossing sớm; .93 giữ identity riêng và track 251681 tạo IN tại 639.7106917 s. Đây là tái lập có kiểm soát trên đoạn đo, chưa phải detector/tracker/HumanGuard/dispatcher replay toàn clip.

**Chưa có F1 mới của .93.** Benchmark #66/session 193 hiện tại vẫn 149 GT / 150 AI / 138 khớp / 11 lọt / 12 dư / F1 92,3%. Session 192 và 193 có cùng crossing signatures và kết quả dedup; bản .92 chủ yếu thêm audit nên không giải quyết hết các lỗi này. Case anchor dao động quanh 815–817 s và Human Guard ở 397 s vẫn cần thêm bằng chứng; không tự thay ngưỡng để ép điểm.

GT đang có 0 Xe tải, 1 Ô tô; van OUT 641.981 s vẫn được gán GT Ô tô trong khi AI là Xe tải. Van IN 882.2898 s chưa có GT gần trong cửa sổ ±0,75 s. Giữ quy ước van chở hàng là Xe tải và review nhãn/thời điểm trên clip; source không tự sửa GT.

## Kiểm thử, chạy và phát hành

Chép source vào dự án hiện tại, giữ `.env`, `.git`, volumes, models và video của bạn. Không cần tạo lại tài khoản Admin.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.93 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl+F5. Chạy lại cùng clip/vạch/model để đo kết quả bản mới; benchmark mới sao chép GT đã review rồi **Tải hồ sơ benchmark** sau khi có GT. Báo cáo thống kê có thể dùng phiên 193 hiện có để kiểm tra 150 lượt theo thời điểm ghi nhận thực tế. Trong dữ liệu được gửi, các event thuộc 15/10 theo UTC+7 dù file được gửi 16/10; chọn phiên sẽ điền ngày tương ứng.

Migration `0107_reports_guard_v0593`, parent `0106_cycle_witness_v0592`, chỉ đồng bộ schema_version 0.5.93; không sửa dữ liệu GT/events. ReportLab 5.0.1 được thêm vào dependencies cho PDF; font DejaVuSans và giấy phép được đóng gói. Kết quả kiểm tra cụ thể/giới hạn môi trường xem phụ lục xác minh ở cuối README.md.

---

# Traffic AI V0.5.92 — Verified Crossing-Cycle and Raw-ID Evidence Audit

- **Phân tích chu kỳ cắt vạch trên cùng canonical tracking ID** với cửa sổ tối đa 30 giây (mặc định 12 giây). Đối chiếu cả `matched_items` và `false_positive_items`, kèm bằng chứng raw ByteTrack ID từ trace JSONL đã xác thực manifest/hash.
- **Web Benchmark Report:** phần mở rộng "Các lượt dùng chung tracking ID" cho phép bấm vào cả hai timecode; phân biệt cặp có AI dư. Không tự xem các lượt IN→OUT là đếm trùng, vì một xe quay lại là một lượt hợp lệ.
- **Lệnh CLI/PowerShell `scripts/audit-crossing-cycles.ps1`** xuất `crossing-cycles.json`, `crossing-cycles.csv` (UTF-8 BOM) và Markdown để xem từng cặp; kiểm tra trace nguồn đóng, checksum và uncompressed size, không cần chạy inference.
- **Benchmark #65 / Session #192**: GT 149, AI 150, khớp 138, lọt 11, dư 12, F1 92,3%. Phát hiện 5 cặp cùng canonical trong 12 giây, 2 cặp liên quan AI dư, 3 cặp raw ID khác nhau gần event. **Không tự xóa lượt AI hoặc thay GT.** Xem `docs/benchmark-65-cycle-audit-v0592.md`.
- **Tăng phiên bản `0.5.92`**, migration metadata `0106_cycle_witness_v0592`; kiểm thử hồi quy CLI và JavaScript, PowerShell contract; giữ toàn bộ security, PostgreSQL, dashboard, benchmark, GitHub publication của các bản trước.
- **Giới hạn:** chỉ nâng cấp truy vết và trình duyệt lỗi, thuật toán đếm không đổi; chưa chạy lại GPU/video với V0.5.92 nên không có cơ sở nói F1 tăng. Source ZIP không bao gồm dữ liệu camera/video, model weights hoặc `.env` thật.

**Chạy trên Windows:** `cd D:\LienThongDH\DoAn\traffic-ai` → `Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File` → `.\scripts\test.ps1` → `.\scripts\start.ps1`. Khi kiểm thử thành công, dùng `.\scripts\publish.ps1` với tag mới `v0.5.92` (không ghi đè tag cũ).

**Xuất báo cáo chu kỳ:** `.\scripts\audit-crossing-cycles.ps1 -Export '.\traffic-ai-benchmark-65-session-192.zip' -OutputDirectory '.\crossing-cycle-audit'`.

---

# Traffic AI V0.5.91 — Benchmark Timecode Review Navigator

- **Rà soát 23 mốc lỗi ngay trên web:** sau khi benchmark đã có GT, phần Benchmark Report có bộ lọc `Tất cả / Lọt / Dư / Gần-cạnh tranh timecode` và điều hướng `← Trước / Sau →`. Chọn mốc sẽ **tạm dừng clip** và đưa video đến **0,4 giây trước** timecode; có thể bấm frame-by-frame bằng các nút cũ.
- **Tách trình xem với thuật toán đếm:** không thay đổi Ground Truth, sự kiện AI đã lưu, threshold, Gate, dedup, tracker hay kết quả F1. Điều hướng chỉ dùng report được backend trả về; khi GT = 0 thì không giả tạo danh sách lỗi.
- **Benchmark #64 / Session #191** (ZIP đã xác thực): GT 149, AI 150, khớp 138, lọt 11, dư 12, F1 92,3%. Đối chiếu benchmark #62: cùng 150 crossing, không có lượt AI được sửa hoặc khôi phục. Xem `docs/benchmark-64-review-v0591.md`.
- **7 test frontend mới** cho thứ tự mốc, lọc, timecode không hợp lệ, trường hợp GT trống và không thay đổi báo cáo. Bổ sung PowerShell UI contract và metadata migration `0105_review_nav_v0591`.
- **Không khẳng định cải thiện AI** trước khi chạy lại clip bằng model thật và xác minh từng trường hợp với GT đã duyệt. Nếu không có cảnh video đủ sát, chỉ ghi `cần xem clip`, không tự xóa event.

**Cài và chạy:** `cd D:\LienThongDH\DoAn\traffic-ai` → `Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File` → `.\scripts\test.ps1` → `.\scripts\start.ps1`. Khi chạy ổn và rà soát Git: `.\scripts\publish.ps1` (tag `v0.5.91`, không ghi đè tag cũ).

---

# Traffic AI V0.5.90 — Verified AI-only Replay Comparison + GT Export Freshness

- **Sửa quy trình đối chiếu khi ZIP được xuất trước lúc chép Ground Truth:** vẫn xác thực checksum JSON/trace, session, geometry và so sánh chính xác sự kiện AI đã lưu; KHÔNG tính hoặc suy ra F1/lọt/dư nếu một trong hai ZIP chưa có GT.
- **Sau khi sao chép GT trên web**, thông báo hướng dẫn xuất hồ sơ ZIP mới; ZIP đã tải trước đó không tự cập nhật.
- **Benchmark #63 / Session #190:** ảnh mới cho thấy 149 GT / 150 AI / khớp 138 / lọt 11 / dư 12 / F1 92.3%, nhưng ZIP #63 cũ vẫn có GT 0. So sánh AI-only với ZIP #62 đã xác minh 150 chữ ký sự kiện giống nhau, không có lượt crossing được thêm hoặc xóa.
- Thêm công cụ `scripts/review-benchmark-errors.ps1` xuất `review-queue.csv`, `.md`, `.json` để duyệt tất cả **11 lượt lọt / 12 lượt dư** của benchmark #62 theo timecode, kèm dấu hiệu cạnh tranh; không tự gộp xe hay thay GT.
- Thêm **11 hồi quy** cho GT-free comparison, từ chối hash/nguồn/điểm số không nhất quán. Migration metadata `0104_ai_export_v0590`; giữ các chức năng, quản trị, bảo mật và script cũ.
- Thuật toán AI không thay đổi, chưa có bằng chứng nâng Precision / Recall. Muốn so sánh hiệu quả sau khi đủ GT, xuất lại ZIP #63.

**Lấy danh sách review:** `.\scripts\review-benchmark-errors.ps1 -Export ".\traffic-ai-benchmark-62-session-188.zip" -OutputDirectory ".\benchmark-review"`.

**Chạy:** `cd D:\LienThongDH\DoAn\traffic-ai` → `Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File` → `.\scripts\test.ps1` → `.\scripts\start.ps1`. Sau khi kiểm tra ổn: `.\scripts\publish.ps1` (tag mới `v0.5.90`, không ghi đè tag cũ).

---

# Traffic AI V0.5.89 — Release EOL Preflight + Immutable Tag Diagnostics

**Sửa quy trình phát hành từ log Windows V0.5.88:** `scripts/test.ps1` và
`start.ps1` thành công, nhưng `publish.ps1` dừng ở bước 4 vì tag `v0.5.88` đã tồn
tại trong khi working tree còn thay đổi. Đây là bảo vệ cần giữ nguyên: tuyệt đối
không tự ghi đè hay dời tag cũ.

- **Full-source chuẩn hóa CRLF ngay khi đóng gói** cho toàn bộ `*.ps1`; các file
  code/config khác giữ LF theo `.gitattributes`. `normalize-line-endings.ps1`
  sẽ không tạo biến đổi file khi chạy trên bản ZIP này, nếu không có chỉnh sửa mới.
- **Kiểm thử hồi quy trên package** (`scripts/tests/test_release_eol_v0589.py`):
  kiểm CRLF mọi PowerShell, Git EOL policy, cảnh báo tag có chẩn đoán,
  và LF ở source/config. `scripts/test.ps1` chạy bộ test này trước bước build.
- **Publish diagnostics**: khi tag đã có và Git còn thay đổi, in `git status --short`
  và `git diff --cached --name-status`, không lộ nội dung file; vẫn dừng an toàn.
- **Git ignore an toàn:** bỏ qua ZIP benchmark, RAR camera và thư mục kết quả so sánh
  trong thư mục dự án; không tự đưa dữ liệu lớn vào `git add -A`. Nếu các tệp
  đã bị stage từ lần publish trước, script dừng và hướng dẫn bỏ stage an toàn.
- **Phiên bản mới `0.5.89`**, migration `0103_release_eol_v0589` chỉ đồng bộ
  `schema_version`. Không sửa thuật toán AI, benchmark hay dữ liệu phương tiện.

**Lưu ý quan trọng:** log cho biết 9 file `.ps1` đã được chuyển line endings,
nhưng không cung cấp `git diff` nên chưa thể khẳng định *chỉ* các file đó làm
Git dirty; `.gitattributes` có thể chuẩn hóa nội dung khi stage. Nếu có thay đổi
khác trên máy Windows, nên rà soát trước khi phát hành. Bản mới dùng tag
`v0.5.89`, không ghi đè `v0.5.88`.

## Kiểm thử, khởi chạy và phát hành

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
# Khi đã kiểm tra chạy ổn định:
.\scripts\publish.ps1
```

Giữ nguyên `.git`, `.env`, PostgreSQL volumes, `models/`, `videos/` và dữ liệu
runtime khi cập nhật source. Nếu Git báo có file chỉnh sửa, sử dụng
`git status --short` để kiểm tra; không force tag, không hard reset dữ liệu.

---

# Traffic AI V0.5.88 — Temporal Review Contract Compatibility Fix

**Sửa lỗi thực tế từ Windows `scripts/test.ps1` tại V0.5.67:** test trước đó phụ thuộc nguyên văn
`Tổng GT = AI`, trong khi V0.5.87 đã thay UI để luôn cho review các trường hợp cạnh tranh
timecode **kể cả khi 149 GT khác 150 AI**. Đây là lỗi kiểm thử hồi quy lỗi thời, không phải
lỗi tính toán benchmark.

- Tách chính sách hiện cảnh báo `shouldShowTemporalCompetitionReview()` vào
  `frontend/src/benchmark-review.js`, có thể kiểm thử độc lập bằng Node.
- UI vẫn hiện cạnh tranh thời gian khi audit có bằng chứng, bất kể GT = AI hay GT != AI;
  vẫn ẩn khi không có bằng chứng hoặc GT chưa đủ để chấm điểm. Không chạm logic ghép
  timecode, nhãn GT, điểm số, DB events hay thuật toán AI.
- `scripts/test.ps1` kiểm tra sự hiện diện của chính sách và test cả hai trường hợp,
  không phụ thuộc câu chữ giao diện. Bổ sung 4 unit tests frontend.
- Tăng phiên bản đồng bộ lên `0.5.88` và Alembic migration `0102` chỉ cập nhật
  `schema_version`; không đổi dữ liệu nghiệp vụ.

## Chạy trên Windows

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Sau khi test và chạy thực tế ổn định mới phát hành bằng ` .\scripts\publish.ps1 `.
Không chạy lại tạo tài khoản Admin. Khi cập nhật nguồn, giữ nguyên `.env`, volumes
PostgreSQL, video, trọng số mô hình. Không thay đổi số liệu Benchmark #62:
GT 149 / AI 150 / khớp 138 / lọt 11 / dư 12 (F1 92,3%).

---

# Traffic AI V0.5.87 — Verified Cross-Benchmark Regression + Temporal Competition Review

Tiếp tục từ **V0.5.86**. Benchmark #62 / Session #188: GT **149**, AI **150**, khớp **138**, lọt **11**, dư **12**, sai hướng **2**, sai loại **2** (F1 **92,3%**). Công cụ so sánh bằng chứng đã xác nhận 150 chữ ký crossing và 149 mốc GT trong #61 và #62 giống nhau (ngoại trừ các ID/metadata phiên chạy). **V0.5.86 chưa cải thiện F1 trên clip kiểm chứng này.**

- **Verified Cross-Benchmark Regression** (`scripts/compare-benchmark-exports.py`): so sánh trực tiếp hai ZIP `Tải hồ sơ benchmark` mà không cần đăng nhập hay kết nối DB; kiểm tra SHA-256 JSON/trace, session, cùng video/vạch/FPS/GT/cửa sổ ghép, so sánh chữ ký sự kiện AI độc lập với ID tracker và DB. Từ chối so sánh khi dữ liệu nguồn/GT không tương thích.
- **Báo cáo JSON + Markdown tiếng Việt**: thể hiện tất cả delta Recall/Precision/F1/lọt/dư, số event thêm/bớt và GT lỗi xuất hiện/hết; chỉ coi ghép timecode là bằng chứng thời gian, không chứng minh danh tính vật lý hay tự sửa GT. Có lệnh PowerShell `scripts/compare-benchmark-exports.ps1` để kiểm tra các phiên trong tương lai.
- **Sửa lỗi hiển thị review benchmark:** trước đây khối cạnh tranh thời gian chỉ hiện khi tổng GT = tổng AI (`count_totals_equal`). Ở #62 (149 ≠ 150), khối bị ẩn dù có 4 mốc lọt bị event DB khác nhận và 2 AI dư sát GT đã ghép. V0.5.87 luôn cho phép mở `Đối chiếu GT/AI có trường hợp cạnh tranh thời gian` khi có chứng cứ, bất kể tổng GT/AI khác nhau, nhưng mặc định thu gọn để tránh kéo dài giao diện.
- **7 unit tests** mới và contract PowerShell cho so sánh 2 ZIP, từ chối GT khác, phát hiện sửa file sau khi xuất, cùng hiệu ứng GUI. Thêm migration `0101` chỉ cập nhật `schema_version`, không sửa data DB, GT hoặc thuật toán counting.

**Không tinh chỉnh Gate/Tracker theo những cặp chỉ gần thời gian:** trong ảnh camera 519–520s có nhiều xe gần vạch, 638s có nhiều sự kiện cạnh nhau. Việc xóa event mà chưa chứng minh cùng xe có thể tăng lọt. Để nâng độ chính xác AI thực tế cần chạy inference toàn bộ clip cùng trọng số và kiểm chứng từng instance. Phiên bản này cải thiện quy trình chẩn đoán và tính minh bạch, không cam kết giảm lọt/dư.

## Chạy sau giải nén trên Windows

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

## So sánh 2 hồ sơ benchmark

```powershell
.\scripts\compare-benchmark-exports.ps1 -Prior ".\traffic-ai-benchmark-61-session-187.zip" -Current ".\traffic-ai-benchmark-62-session-188.zip" -OutputDirectory ".\benchmark-comparison"
```

Khi test và chạy AI ổn định, phát hành một lệnh: `.\scripts\publish.ps1`. Tài khoản Admin đã tồn tại, không chạy tạo lại.

---

# Traffic AI V0.5.86 — Visible-Incumbent Reservation + Benchmark #61 Forensics

Tiếp tục từ **V0.5.85**. Baseline thực tế Benchmark #61 / Session #187: GT **149**, AI **150**, khớp timecode **138**, lọt **11**, dư **12**, sai loại **2**, sai hướng **2** (Recall **92,6%**, Precision **92,0%**, F1 **92,3%**). Đây là kết quả **V0.5.85**, không phải replay V0.5.86.

- **Visible-Incumbent Reservation (4–12 frame):** nếu xe hai bánh trước đó bị che trong 4–12 frame, raw tracker cũ và raw tracker mới **cùng hiện diện trong cùng một frame**, và raw cũ nằm gần hơn đáng kể vị trí canonical cuối, bảo lưu canonical cho raw cũ. Chặn raw mới chiếm sai danh tính do thứ tự xử lý; không tạo lượt đếm mới và không mở rộng Gate/Road Zone/cooldown.
- Chỉ hoạt động khi có bằng chứng đủ từ `visible_raw_centers`, không ảnh hưởng trường hợp xe thật trở lại bằng raw mới nhưng raw cũ không hiện diện. Xe 4 bánh vẫn giữ ngưỡng 3 frame. Có thể A/B rollback bằng `AI_SHORT_GAP_ALIAS_GUARD=0` rồi khởi động lại dịch vụ.
- **Vehicle Count dễ đọc:** tổng lượt DB/IN/OUT và số lượng theo từng loại xe được giữ trên cùng. Các chỉ số worker, bộ lọc, refiner chuyển vào mục mở rộng **Thông số kỹ thuật**; nhắc rõ những giá trị Trực tiếp/Nội suy/Rescue là đề xuất worker, có thể cao hơn tổng đã lưu ở backend do dedup/Human Guard.
- **Session #187 forensics:** kiểm tra SHA256 trace và hồ sơ benchmark, đọc ảnh camera xuất kèm tại frame 7243 (người dắt xe đạp và xe máy cùng khu vực), frame 16050/22059 (van chở hàng). Tại 641,931s GT hiện gán Ô tô nhưng AI gán Xe tải; phải kiểm tra quy ước GT, không tự sửa GT. Khác biệt khớp timecode không chứng minh AI đã nhận đúng đối tượng.
- Thêm **5 test** cho khả năng giữ raw incumbent, xe quay lại thật, incumbent ở xa, rollback và xe 4 bánh. Migration `0100` metadata-only, không chạm events/GT, giữ cơ chế backup/restore.

**Giới hạn:** không có môi trường Docker/GPU và trọng số model để chạy lại 23.650 frame. Chưa thể khẳng định F1/Recall mới đã tăng hoặc lọt/dư mới đã giảm. Sau khi chạy lại clip, xuất ZIP benchmark mới để đánh giá đối chứng.

## Lệnh PowerShell

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Sau khi xác nhận chạy ổn và các kiểm tra đạt, dùng ` .\scripts\publish.ps1 ` để test → commit/push → tag → GitHub Release. Tài khoản Admin đã có, không cần tạo lại.

---

# Traffic AI V0.5.85 — Short-Gap Alias Handoff Evidence Guard

Nâng cấp từ **V0.5.84**. Benchmark #60 / Session #186 cho thấy GT 149 / AI 151 / khớp timecode 138 / lọt 11 / dư 13. Thay đổi bộ ghép danh tính dựa trên quỹ đạo, không đọc GT lúc chạy.

- **Short-Gap Alias Evidence Guard:** chặn ByteTrack token mới chiếm nhầm danh tính xe máy/xe đạp cũ sau mất 4–12 frame nếu cả khoảng cách thực tế (>1,75 lần đường chéo hộp xe) và lệch dự đoán vận tốc (>1,50 lần) đều lớn.
- **Fast motion preservation:** xe chạy nhanh vẫn được nối nếu phù hợp hướng chuyển động, không chặn chỉ vì quãng đường lớn; không thay guard cho xe 4 bánh.
- Có thể đặt `AI_SHORT_GAP_ALIAS_GUARD=0` trong `.env` để A/B so sánh nếu có hồi quy, nhưng cần khởi động lại AI Service.
- Dashboard/trace có chỉ số `short_gap_alias_rejections`, tách khỏi `raw_id_discontinuities`.
- Bài test tái hiện frame 15143→15152 từ Session #186, xe chạy nhanh và xe bốn bánh.
- Migration 0099 chỉ cập nhật schema_version; không đổi cấu trúc PostgreSQL. Giữ Backup/Restore, phân quyền và model.

**Chưa chạy GPU replay.** Không thể kết luận đã giảm 11 lượt lọt / 13 dư trước khi chạy lại video. Nếu benchmark hồi quy, giữ source/backup trước và gửi ZIP benchmark mới.

## Lệnh PowerShell

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Sau khi chạy và kiểm thử ổn: `.\scripts\publish.ps1`. Không tạo lại tài khoản Admin.

---

## Lịch sử nâng cấp trước

# Traffic AI V0.5.84 — Per-Raw Provenance for ByteTrack Aliases

Nâng cấp từ full source V0.5.83. V0.5.84 xử lý trường hợp **Raw ID
thực sự bị tái sử dụng nhưng vị trí Canonical ID đã được alias khác cập nhật
nên che khuất bước nhảy**. Bộ kiểm tra mới dùng lịch sử theo từng Raw ID
**và** bảo vệ gián đoạn lớn của Canonical ID khi đổi alias. Trường hợp
hai ID cùng lái một danh tính qua hai vị trí không thể liên tục vẫn bị
tách để tránh crossing ảo. Không thay ngưỡng chuyển động Gate/rescue.

- Lưu raw-token position/rect/frame độc lập với Canonical ID; phát hiện
  teleport cả khi bị vị trí alias khác che khuất, đồng thời giữ quy tắc
  an toàn chống nối quỹ đạo Canonical vượt quãng đường bất thường.
- Xóa quan sát raw khi canonical hết TTL. Không đổi ngưỡng Gate, rescue,
  cooldown, thời gian giao sự kiện hoặc GT.
- `audit-raw-id.ps1` phân biệt số reset cộng dồn trên **toàn bộ frame** với
  jump tìm thấy trong `gate_tracks` (chỉ các track được trace quanh vạch).
  Ghi timecode và frame khi counter tăng, hỗ trợ đối chiếu video.
- Thêm 5 bài test cho alias có/không có lịch sử đo, teleport bị che, teleport thật và TTL;
  đồng bộ metadata, migrations, script test và hợp đồng CI.
- Benchmark #59 Session #185 (GT 149, AI 151, khớp timecode 138,
  strict 134, lọt 11, dư 13, sai hướng 2, sai loại 2) là **baseline**.
  **Chưa có GPU replay để khẳng định V0.5.84 cải thiện các con số này.**

## Chạy/kiểm thử sau nâng cấp

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Sau khi chạy ổn định, phát hành GitHub bằng `.\scripts\publish.ps1`.
Tài khoản Admin đã tồn tại, **không chạy** `create-admin.ps1`.

---

# Traffic AI V0.5.83 — Direction-aware Benchmark + Replay Regression Witness

Nâng cấp từ **V0.5.82**. Bổ sung chỉ số đánh giá đúng timecode + hướng + loại xe,
giao diện hiển thị các cặp GT/AI sai hướng và công cụ chứng cứ sự kiện biến mất
khi chạy lại cùng clip. Không sửa GT, không thay ngưỡng thuật toán AI và không
can thiệp dữ liệu PostgreSQL.

## V0.5.83 — Những thay đổi

- `strict_matches`, `strict_precision`, `strict_recall`, `strict_f1` chỉ công nhận
  các cặp timecode khớp **đồng thời đúng IN/OUT và loại phương tiện**.
- `direction_mismatches` và `direction_mismatch_items` chỉ rõ từng GT/AI sai hướng;
  nút timecode trên giao diện cho phép xem lại video. Các chỉ số `matched`,
  `missed`, `false_positives`, `counting_recall` truyền thống không đổi.
- `scripts/compare-gt-replays.ps1`: so sánh reference ZIP benchmark với trace
  chạy mới, báo những event mất/xuất hiện và chứng cứ hướng GT đã ghép trước đó.
  Sử dụng `-Strict` để fail khi có thay đổi; không dùng PASS làm chứng nhận accuracy.
- Benchmark #57 / Session #182: 139 cặp khớp timecode; **3 sai hướng**, **2 sai loại**,
  **134 cặp khớp đủ 3 điều kiện**. Trace Session #183 giảm còn 151 event, mất
  một event OUT tại 290.064s; baseline event này đã từng ghép GT IN tại 289.824s.
- `test.ps1`, GitHub Actions và migration `0097_direction_audit_v0583` tích hợp
  kiểm tra mới. Chỉ nâng metadata schema version; không sửa bảng DB.

### Kiểm tra chênh lệch Session #182 và #183

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\compare-gt-replays.ps1 `
  -ReferenceBenchmark .\traffic-ai-benchmark-57-session-182.zip `
  -CurrentTrace .\session_183_benchmark-trace.jsonl `
  -OutputDirectory .\gt-replay-witness-report `
  -Strict
```

Trace Session #183 là file JSONL trong bộ camera RAR, cần giải nén trước; hoặc
sử dụng ZIP “Tải hồ sơ benchmark” #183 và truyền trực tiếp làm `-CurrentTrace`.
Với trace hiện tại, `-Strict` **dự kiến FAIL** vì một event biến mất.

> **Chưa có kết quả GPU replay chứng minh 11 lọt / 13 dư được giảm.**
> Bản này cải thiện đo lường, phát hiện hồi quy và bằng chứng chấm điểm,
> không âm thầm điều chỉnh thuật toán đếm dựa trên giả định về GT.

---

# Traffic AI V0.5.82 — Raw ID Reuse Guard + Gate Trace Audit 10.1

**Nâng cấp từ full source V0.5.81.** Tập trung ngăn ByteTrack tái sử dụng cùng Raw Track ID cho xe khác ngay gần vạch đếm, gây kế thừa nhầm quỹ đạo, class và trạng thái crossing. Không thay đổi các ngưỡng Gate, cooldown, rescue hoặc chống trùng đã có.

- **Same-Raw Identity Discontinuity Guard:** Nếu cùng Raw Track ID bất ngờ nhảy rất xa trong tối đa 3 frame, đồng thời vượt 18% đường chéo toàn ảnh **và** hơn 3 lần đường chéo hai hộp detection, hệ thống tách danh tính mới. Chỉ tách khi có đủ hai hộp và tọa độ quan sát; không đoán danh tính bằng nhãn GT hay tổng đếm.
- **Chống tái ghép sai:** Raw ID vừa được tách không thể lập tức stitch lại Canonical ID đã bị loại. Các canonical track còn tồn tại được giữ riêng để tiếp tục theo dõi nếu đối tượng thật xuất hiện trở lại.
- **Telemetry:** Bổ sung số `Raw ID reset` trên dashboard, trạng thái phiên AI và benchmark trace để xác nhận bảo vệ có kích hoạt khi phát video. Mặc định 0 nếu không phát hiện lỗi.
- **Audit độc lập:** `scripts/audit-raw-id.ps1` đọc ZIP **Tải hồ sơ benchmark** đã đóng, xác minh SHA-256 của trace và tạo `raw-id-audit.json` / `raw-id-audit.md` với các frame nghi ngờ, không sửa GT/event.
- Có thể chỉnh `AI_STITCH_RAW_REUSE_JUMP_RATIO` trong `.env` (mặc định `0.18`; `0` tắt guard) nhưng không nên giảm ngưỡng khi thiếu bằng chứng, vì nguy cơ chặt đứt đường đi xe nhanh.
- **Phân tích Benchmark #57 Session #182** (23.650 frame): GT 149 / AI 152 / khớp 139 / lọt 10 / dư 13. Audit mới cho **0 sự kiện nhảy Raw ID cực đoan gần vạch** theo ngưỡng trên. Điều này **không có nghĩa đã sửa 10 lọt / 13 dư**; cần phát lại để đo. Nhiều sự kiện gap/ID đổi đã có hướng di chuyển hợp lý nên không thể áp quy tắc loại theo khoảng cách chung.
- Migration `0096_raw_id_reuse_v0582` chỉ cập nhật `schema_version` sang `0.5.82`. PostgreSQL, tài khoản, backup/restore, video/model và GT không bị sửa.

## Lệnh PowerShell đầy đủ

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

.\scripts\test.ps1
.\scripts\start.ps1
```

Audit sau khi tải ZIP từ giao diện Benchmark:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\audit-raw-id.ps1 -ExportZip .\benchmark-182.zip -OutputDirectory .\raw-id-audit-report
```

Sau khi kiểm tra máy Windows/Docker và benchmark ổn định, phát hành GitHub bằng ` .\scripts\publish.ps1 `. **Không chạy `create-admin.ps1`** vì Admin đã tồn tại.

---

# Traffic AI V0.5.81 — Quiet Startup + Backup Worker pip Test Hygiene

**Nâng cấp trực tiếp từ V0.5.80**, không thay đổi thuật toán đếm AI, model, mật khẩu, database hoặc hành vi Backup/Restore. Bản này sửa hiển thị khi chạy test và khởi động.

- Trong `scripts/test.ps1`, chỉ riêng bước Backup Worker unit test được thêm biến môi trường `PIP_ROOT_USER_ACTION=ignore` và `PIP_DISABLE_PIP_VERSION_CHECK=1` vào **container Docker dùng một lần**. Tránh cảnh báo pip cài bằng root trong container; **không** tắt cảnh báo/lỗi của Docker, PowerShell, pytest hoặc quy trình vận hành thật.
- Trong `scripts/start.ps1`, bỏ log thời gian chờ `Waiting for ... (starting, Xs/Ys)` và `healthy after Ns`; khi thành công chỉ hiển thị `[OK] <container> healthy.`.
- **Vẫn chờ container ready và giữ các giới hạn an toàn 120/180/240 giây** cùng healthchecks, thông báo timeout, trạng thái failed và log chẩn đoán khi lỗi. Không thay đổi độ trễ hoặc cho phép khởi động bỏ qua service lỗi.
- Thêm 4 bài kiểm thử hợp đồng console/startup. Chạy trong `scripts/test.ps1` và GitHub Actions, ngăn lần nâng cấp sau vô tình đưa bộ đếm thời gian chờ trở lại.
- Đồng bộ `VERSION=0.5.81`, API, frontend, AI Service, Backup Worker, favicon cache; migration `0095_quiet_startup_v0581` chỉ cập nhật `schema_version`, không thay đổi bảng dữ liệu.
- Benchmark #57 / Session #182 từ máy người dùng: GT 149 / AI 152 / khớp 139 / lọt 10 / dư 13. **V0.5.81 không sửa lỗi đếm**; không dùng việc tắt log để tuyên bố cải thiện Recall/Precision.

## Chạy trên Windows (tài khoản Admin đã tồn tại)

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Kiểm tra source
.\scripts\test.ps1

# Khởi động hệ thống
.\scripts\start.ps1
```

Sau khi chạy và kiểm thử ổn định, xuất bản bằng ` .\scripts\publish.ps1 `. Nếu timeout hoặc service unhealthy, `start.ps1` vẫn thông báo lỗi và in log chẩn đoán; chỉ ẩn dòng đếm giây trong lúc chờ.

---

# Traffic AI V0.5.80 — Incumbent Identity Protection (Cross-ID Anti-Swap)

**Nâng cấp từ V0.5.79; giữ nguyên PostgreSQL, tài khoản, Backup/Restore và chính sách chống đếm trùng V0.5.78.**

- Từ benchmark #56 / Session #180: 149 GT / 152 AI / khớp 139 / lọt 10 / dư 13. Cải thiện so với #179 là giảm 1 dư; số lượt lọt vẫn 10.
- Trace quanh 606 giây thể hiện hai raw ByteTrack cùng hiện diện nhưng canonical identities đổi chỗ khi một raw ID mới được xét trước raw ID đã hiện diện. Chỉ dùng khoảng cách crossing để xóa một event có thể gộp nhầm hai xe thật.
- **V0.5.80** thêm snapshot vị trí Raw Track ID của toàn frame trước khi ghép canonical: một canonical có incumbent vừa xuất hiện ở gần vị trí trước đó được bảo vệ khỏi các raw ID mới có điểm ở xa hơn rõ rệt. Không giữ chỗ cho incumbent đã biến mất, không thay ngưỡng vạch đếm/rescue. Có bài test cho chủ sở hữu quay lại, ID mới, ID cũ mất và trường hợp tracker nhảy quá xa.
- Đường tracking hiện có giữ tương thích khi không cung cấp snapshot; snapshot chỉ thêm xác thực quyền ưu tiên chủ ID và không dựa trên nhãn GT để đếm.
- **Kết quả cần kiểm chứng:** thay đổi danh tính có thể làm khác crossing. Chưa chạy GPU trên clip gốc; **không cam kết giảm từ 10 lọt / 13 dư** trước khi phát lại. Report của phiên #180 là baseline, không phải kết quả V0.5.80.
- Migration `0094_incumbent_identity_v0580` chỉ cập nhật schema_version, không thay đổi bảng. Đồng bộ VERSION/frontend/backend/AI/backup và kiểm tra hợp đồng phát hành.

## Lệnh chạy PowerShell (Admin đã tồn tại)

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Khi vận hành/benchmark được kiểm tra ổn định: ` .\scripts\publish.ps1 `.

---

# Traffic AI V0.5.79 — Release Version Consistency Hotfix

**Sửa lỗi chặn `scripts/test.ps1` khi `VERSION=0.5.78` nhưng contract vẫn cố định 0.5.77.** Bản sửa tăng release lên V0.5.79, dựa hoàn toàn trên source V0.5.78.

- Thay so sánh version cứng bằng so khớp file `VERSION` với frontend, backend, AI Service, backup worker và metadata sao lưu; kiểm tra các query cache favicon/manifest.
- Quét Alembic revision graph để xác nhận chỉ một head, đầy đủ parent và `schema_version` trong head trùng `VERSION`. Bảo toàn migration và dữ liệu cũ. Migration mới `0093_version_contract_v0579` chỉ sửa metadata phiên bản.
- Thêm `scripts/version-contract.py`, bài test tái hiện hardcode/stale package và kiểm tra trong cả `scripts/test.ps1`, `.github/workflows/ci.yml` và `ci-release-reusable.yml`.
- Đồng bộ API/health version, frontend, AI Service, backup worker và file icon cache; **không thay đổi logic AI crossing, các ngưỡng chống trùng, mật khẩu, quyền truy cập hoặc dữ liệu PostgreSQL**.
- Vẫn chưa chứng minh 0 lọt/0 dư. Kết quả Benchmark #179 mới nhất: GT 149, AI 153, khớp 139, lọt 10, dư 14. V0.5.78 dự đoán offline loại được 1 dư nhưng chưa replay thực tế.

## Chạy thử và khởi động Windows

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Sau khi test và chạy ổn, phát hành bằng ` .\scripts\publish.ps1 `; không chạy `create-admin.ps1` vì tài khoản Admin đã tồn tại.

---

# Traffic AI V0.5.78 — Bounded Direct Shadow Closure + GT-Verified Counterfactual

**Nâng cấp từ V0.5.77; giữ nguyên cấu hình camera, AI model, PostgreSQL, tài khoản và Backup/Restore.**

### V0.5.78 thay đổi gì?

- Sửa **một lỗi đếm trùng đã có bằng chứng ảnh và GT** của Session #179: tại t=491.920/492.200 giây, cùng xe máy có hai hộp/track ID khác nhau ở cùng vị trí crossing, đều là `direct`, `out`, `motorcycle`. Khoảng cách crossing chuẩn hóa 0.008587, dt 0.28 s. Bản cũ không loại vì giới hạn 0.006.
- Backend nâng **duy nhất** DIRECT/DIRECT cùng lớp/hướng khác ID lên **dt ≤ 0.32 giây và khoảng cách ≤ 0.009** cho đuôi mới; **giữ nguyên** guard cũ dt ≤ 0.42 giây, khoảng cách ≤ 0.006. Không thay điều kiện các crossing `rescued/interpolated` hoặc các trường hợp khác hướng/khác loại; thêm module thuần `backend/app/shadow_guard.py` để source và phân tích offline dùng chung đúng một quy tắc.
- Thêm `scripts/evaluate-direct-shadow.ps1` đọc `Tải hồ sơ benchmark` để **giả lập** bộ lọc từ AI events, không đọc GT trước khi chọn ứng viên, đối chiếu lại GT bằng thuật toán benchmark hiện có. Kiểm tra manifest SHA-256; không ghi vào PostgreSQL hay thay đổi GT.
- Thêm kiểm thử hồi quy cho hai track chồng nhau, giữ xe khác vị trí, hướng/loại khác nhau, guard thời gian chặt và checksum hỏng. Migration Alembic `0092_direct_shadow_v0578.py` chỉ tăng `system_settings.schema_version`; không thay bảng dữ liệu.

### Benchmark #179 (từ ZIP người dùng cung cấp)

| Dữ liệu | Trước | Giả lập V0.5.78 trên events cũ |
|---|---:|---:|
| Ground Truth | 149 | 149 |
| AI | 153 | 152 |
| Khớp | 139 | 139 |
| Lọt | 10 | 10 |
| Dư | 14 | 13 |

**Cảnh báo về chất lượng:** số cột giả lập chỉ chứng minh tác động có thể có trên event snapshot có sẵn; không phải kết quả replay model GPU với thuật toán mới. 10 lượt lọt và 13 lượt dư khác vẫn chưa được chứng minh khắc phục. Không ghép lại các event theo GT lúc chạy AI, không ép tổng AI = 149, không thay ảnh/trace/GT. Các dạng lọt do anchor/Gate/track loss và dư do cứu gap cần được kiểm chứng riêng trước khi thay đổi ngưỡng lớn.

### Lệnh chạy và kiểm tra

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Không cần `create-admin.ps1`. Để đánh giá offline:

```powershell
.\scripts\evaluate-direct-shadow.ps1 -ExportZip .\benchmark-179.zip -OutputDirectory .\shadow-report
```

Chỉ phát hành sau khi kiểm thử chạy tốt tại máy người dùng bằng `.\scripts\publish.ps1`.

---

# Traffic AI V0.5.77 — Startup Path Fix + Verified GT Case Forensics

**Khắc phục blocker V0.5.76:** `scripts/start.ps1` dùng biến `$root` chưa khai báo khi đọc `VERSION`, khiến PowerShell dừng ở bước Gateway với `Cannot bind argument to parameter 'Path' because it is null`. Đã sửa thành `$ProjectRoot`, biến được khởi tạo ngay đầu script. Có contract kiểm tra để tránh tái phát.

**Phân tích GT–AI từng sự kiện (chỉ đọc):** thêm `scripts/benchmark-forensics.py` và `scripts/analyze-benchmark.ps1`. Nhận **ZIP Tải hồ sơ benchmark** đã đối chiếu, xác minh `manifest.json`, SHA-256 của từng thành phần, kiểm tra đúng các số đếm bảo toàn `matched + missed = GT`, `matched + extra = AI`, và xuất `cases.json` / `cases.md` liệt kê chính xác từng GT bị lọt và từng AI event bị dư. Nếu ZIP có trace đóng đầy đủ, đối chiếu cửa sổ ±1 giây quanh từng timecode với quan sát track hai phía vạch, event được backend ghi, phương pháp crossing. Kiểm tra SHA-256 của cả trace nén và dữ liệu giải nén, giới hạn dung lượng, từ chối trace thiếu metadata/geometry/footer. Nếu không có trace, báo thiếu rõ ràng và chỉ cung cấp bằng chứng từ báo cáo backend.

**Phạm vi thay đổi:** không chỉnh Ground Truth, không xóa/ép event AI, không thay thuật toán đếm, model, vạch đếm, Road Zone, ngưỡng rescue hoặc cơ chế backend dedup. Giữ nguyên Backup/Restore, tài khoản, dữ liệu DB. Migration `0091_gt_forensics_v0577.py` chỉ đổi `system_settings.schema_version`, nối từ V0.5.76.

**Quan trọng về độ chính xác:** Session #177/#178 ổn định 153→153 nhưng vẫn GT=149 / matched=139 / missed=10 / extra=14. Bộ RAR của camera có 196 MB/frame trace nhưng **không chứa toàn bộ 149 GT đã đánh dấu**, vì vậy chưa thể sửa 10/14 có kiểm chứng. Kết quả của tool mới là chẩn đoán, **không phải** bản AI đã đạt 0 lọt/0 dư. Cần ZIP benchmark đầy đủ (có `ground-truth.json`, `events.json`, `report.json`) để triển khai/tối ưu thuật toán đúng các sự kiện sai và so sánh hồi quy sau đó.

### Cách chạy chuẩn

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Sau khi hoàn thành benchmark của Session #178, nhấn **Tải hồ sơ benchmark**, lưu vào thư mục source với tên `benchmark-178.zip`, chạy:

```powershell
.\scripts\analyze-benchmark.ps1 -ExportZip .\benchmark-178.zip -OutputDirectory .\benchmark-forensics-report
.\scripts\check-benchmark.ps1 -ExportZip .\benchmark-178.zip -MaxMissed 0 -MaxExtra 0
```

Lệnh `check-benchmark.ps1` phải báo FAIL khi còn 10 lượt lọt / 14 lượt dư. Đây là fail đúng theo chất lượng, không phải lỗi script. Gửi ZIP `benchmark-178.zip` để đối chiếu từng GT với event, sửa thuật toán mà không tạo false positive mới. Sau khi test/chạy tốt, xuất bản bằng ` .\scripts\publish.ps1 ` (không cần tạo lại Admin).

---

# Traffic AI V0.5.76 — GitHub Actions AI token regression fix

- **Fix GitHub Actions backend test (18 failures):** workflows now provide a **test-only** `AI_SHARED_TOKEN` (previously only `scripts/test.ps1` supplied it).
- `backend/tests/test_app.py` uses a temporary, per-test fixture to configure the internal RPC token even on standalone pytest machines without `.env`. After each test the original setting is restored.
- New negative regression test asserts missing, empty, wrong tokens and blank server secret all **fail with HTTP 401**. Production `_assert_ai_token` is unchanged and fail-closed.
- No change to detection/tracking/crossing or Gate, no count threshold change. Sessions #177 and #178 replay identically (153 events; removed 0, introduced 0, decision flips 0), **but** GT=149, matches=139, missed=10, extra=14; replay stability is not GT accuracy.
- Alembic `0090_ci_token_v0576`: updates only `system_settings.schema_version`; the source retains backup/restore and all previous features.
- For a true GT-accuracy fix, export a full **Tải hồ sơ benchmark** ZIP with ground-truth, event list and report. RAR frames/trace alone cannot establish which of the 10/14 cases are genuine algorithm errors versus matching issues.

## PowerShell sau khi nâng cấp

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

Nếu mọi kiểm tra đạt, phát hành qua `./scripts/publish.ps1` trong PowerShell (lệnh thực tế: `.\scripts\publish.ps1`). Không cần tạo lại Admin.

---

# Traffic AI V0.5.75 — Replay Drift Audit / Stability Gate

## V0.5.75 bổ sung chức năng gì?

**Kế thừa nguyên vẹn V0.5.74**: Backup/Restore PostgreSQL, lịch sao lưu, chuyển máy, tài khoản Unicode, Argon2id, phân quyền, camera, dataset và benchmark. Thuật toán đếm, ngưỡng Gate/ROI/rescue/cooldown/FP closure **không bị tự động nới hoặc chỉnh** trong phiên bản này vì chưa có file ZIP đối chiếu GT/AI hoàn chỉnh cho Session #175.

- **Replay Drift Audit** (`scripts/replay-diff.py`): phát hiện chênh lệch của hai lần chạy cùng video theo **source timecode, hướng IN/OUT và tọa độ crossing**; không phụ thuộc raw tracker ID hoặc mã event database (có thể đổi qua lần chạy).
- Nhận đầu vào dạng **ZIP “Tải hồ sơ benchmark”** từ giao diện (nếu chứa `benchmark-trace.jsonl.gz`/`.jsonl`), hoặc file `session_<id>_benchmark-trace.jsonl`/`.jsonl.gz` trong thư mục camera. Với ZIP, bắt buộc manifest đúng schema và SHA-256 của trace phải khớp.
- **Kiểm tra tương thích chặt**: session phải khác nhau, camera ID, FPS, số frame và Road Zone/đường đếm phải giống nhau; trace đủ tất cả frame, delivery đã drain, không rơi acknowledgement. ZIP thiếu trace, lỗi dữ liệu hoặc checksum → FAIL thay vì đưa ra kết quả giả.
- **Ghép 1–1 toàn cục** trong cửa sổ 0,75 giây và 0,025 đơn vị tọa độ chuẩn hóa (thay đổi được), phân biệt crossing mới, crossing mất, **backend thay đổi quyết định lưu/loại**, timecode dịch >2 frame. Xuất `replay-diff.json` và `replay-diff.md` với những timecode cần xem lại.
- **Chế độ strict** dành cho regression: FAIL (exit 1) khi event DB chỉ còn ở một run hoặc quyết định dedup đổi; lỗi dữ liệu không hợp lệ trả exit 2. Mặc định chỉ tạo báo cáo, không tự đổi tham số AI hay GT.
- Thêm PowerShell `scripts/compare-replays.ps1`, 15 unit tests stdlib mới tích hợp `scripts/test.ps1`, migration Alembic `0089_replay_drift_v0575` tiếp nối V0.5.74 (chỉ thay `system_settings.schema_version`). Không sửa bảng người dùng, dữ liệu hoặc restore.
- Kèm báo cáo thực tế `docs/replay-session-174-vs-175.md` từ hai trace gốc do người dùng gửi; **không kèm trace 196 MB/video/ảnh cá nhân** trong source.

### Kết quả Replay Audit thực tế (hai trace 23.650 frame)

| Chỉ số | Session #174 | Session #175 |
|---|---:|---:|
| Worker đề xuất crossing | 195 | 192 |
| Backend ghi event | 149 | 153 |
| Backend từ chối trùng | 46 | 39 |

Trong cửa sổ so sánh mặc định: **187 đề xuất ghép gần nhau, 8 đề xuất chỉ có ở #174, 5 đề xuất chỉ có ở #175, 6 đề xuất đổi trạng thái/reason; 1 event DB chỉ có ở #174 và 5 event DB chỉ có ở #175**. Kết quả strict trả FAIL đúng. Đây là **dao động giữa hai lần phát lại, không phải số xe lọt/dư xác định**; các ghép chỉ dựa timecode/vị trí, không xác minh danh tính vật lý. Trace hiện chưa chứa hash nội dung clip nên vẫn phải tự xác nhận sử dụng cùng video.

### Kiểm tra, chạy trên Windows PowerShell

Dùng source ZIP mới, giữ nguyên `.env`, volumes PostgreSQL và Backup, model/video/dataset. Không chạy `docker compose down -v`, không tạo lại Admin.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

### So sánh hai phiên và xuất báo cáo

Trong trang Ground Truth Benchmark của mỗi session đã hoàn tất, bấm **Tải hồ sơ benchmark** để có hai ZIP. Nếu ZIP bị thiếu trace, hãy lấy file `session_XXX_benchmark-trace.jsonl` đã được lưu cùng ảnh camera, hoặc export lại sau khi chạy xong; tool từ chối ZIP thiếu trace.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

# Thay đường dẫn bằng hai ZIP tải thực tế từ web
.\scripts\compare-replays.ps1 -PreviousTrace .\benchmark-174.zip -CurrentTrace .\benchmark-175.zip -OutputDirectory .\replay-diff-report

# Kiểm tra nghiêm ngặt: chủ động báo lỗi nếu các lần phát lại không nhất quán
.\scripts\compare-replays.ps1 -PreviousTrace .\benchmark-174.zip -CurrentTrace .\benchmark-175.zip -OutputDirectory .\replay-diff-report -Strict
```

Mở `replay-diff-report/replay-diff.md` để xem timecode, hoặc xem `replay-diff.json` cho công cụ xử lý tiếp. Có thể thay đường dẫn ZIP bằng `.jsonl`/`.jsonl.gz`. Tool yêu cầu Python >=3.10 trên Windows, không cần Ultralytics/GPU để phân tích.

**Điểm Ground Truth bắt buộc kiểm riêng** (không thay bằng Replay Drift Audit):

```powershell
.\scripts\check-benchmark.ps1 -ExportZip .\benchmark-175.zip -MaxMissed 0 -MaxExtra 0
```

Chỉ khi đã kiểm tra/test ổn định mới phát hành GitHub với `./scripts/publish.ps1` hoặc trong PowerShell:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\publish.ps1
```

### Giới hạn kiểm thử / chất lượng AI

- **Backend 171/171**, **AI 635/635**, **frontend unit 4/4**, **backup worker 4/4**, **benchmark gate 5/5** và **Replay Audit 15/15** đạt trong môi trường kiểm thử. Backend/AI cần lớp tương thích `httpx2` ở môi trường hiện tại; lớp đó **không đóng gói vào source**. Đã thử công cụ mới trực tiếp với hai file trace 196 MB (không chứa GT toàn bộ). 
- Chưa chạy `npm run build` với Node v26/Vite v8, Docker Compose/PostgreSQL thật, migration và GPU/replay video thực tế trên Windows ở môi trường đóng gói. Hãy chạy `test.ps1` trên máy của bạn trước khi publish.
- **Không cam kết giảm 10 lượt lọt / 14 lượt dư** của Session #175; chỉ sau khi cung cấp ZIP benchmark hoàn chỉnh mới có thể đối chiếu GT–AI và hiệu chỉnh thuật toán một cách có căn cứ.

---

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

Backend 163/163, AI Service 635/635, frontend Node 4/4 và benchmark gate 5/5 đạt trong sandbox tương thích. **Chưa build Vite/NPM thực tế, chưa thử migration với PostgreSQL thực tế hoặc chạy GPU với video gốc.** Kiểm tra Docker / PostgreSQL / browser thực tế bằng `scripts/test.ps1` trên máy Windows trước khi publish. Xem phụ lục xác minh ở cuối `README.md`.

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
- Xem phụ lục xác minh ở cuối `README.md` để biết bài nào được test thực tế và giới hạn môi trường.

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

Kết quả cụ thể và phạm vi thực thi nằm trong **phụ lục xác minh ở cuối README.md**. Offline assertions dùng algorithm modules thực và worker/backend helper trích AST; frontend kiểm bằng Babel/Node VM và JSX có kiểm soát. Môi trường hiện tại không chạy full dependency-pinned pytest, HTTP/ORM/database, native PowerShell, Docker, Vite/browser/GPU/model replay. Không có F1/class accuracy .66 được đo từ clip.

## V0.5.110 — Closed trace recovery and complete benchmark evidence

The Benchmark #80 / Session #207 diagnostic ZIP omitted its trace (`too_large`), although the camera RAR still contained a 413 MB closed JSONL. Version 0.5.110 adds **two integrity-preserving recovery paths**:

1. **Automatic:** the AI Service gzip download route can atomically rebuild a missing compressed artifact from a session's already completed JSONL. It requires the exact session header, a complete terminal delivery footer, a stable file signature, a raw input at most 512 MiB and compressed transport at most 128 MiB. It does not run on an active/incomplete trace. Set `AI_TRACE_LAZY_RECOVERY=0` in `.env` to disable on-demand recovery. If the trace is unavailable on the AI Service or compression still fails, use the second path.
2. **Offline:** `scripts/recover-benchmark-trace.ps1` reconstructs a **derived** benchmark ZIP from the original export plus a matching camera RAR (7-Zip required), or an extracted `session_<ID>_benchmark-trace.jsonl`. The tool verifies the original manifest, matching session, complete consecutive frames, metadata, terminal delivery, SHA-256, size caps and ZIP CRC. It copies the original `report.json`, `ground-truth.json`, `events.json`, `session.json` and `config.json` **byte for byte** and refuses overwriting the original export. The manifest explicitly labels the result *derived evidence*, not a certificate issued by the AI Service.

Example after placing the benchmark and camera RAR beside the source:

```powershell
.\scripts\recover-benchmark-trace.ps1 `
  -Export '.\traffic-ai-benchmark-80-session-207.zip' `
  -CameraRar '.\camera_1(20261020-145251).rar' `
  -Output '.\traffic-ai-benchmark-80-session-207-recovered.zip'

.\scripts\audit-gate-coverage.ps1 `
  -Export '.\traffic-ai-benchmark-80-session-207-recovered.zip' `
  -ExpectedSession 207 -RequireProvenance `
  -OutputDirectory '.\gate-coverage-audit'
```

For an already extracted JSONL, substitute `-TraceJsonl '.\session_207_benchmark-trace.jsonl'` for `-CameraRar`. Windows requires Python 3 on PATH; RAR extraction requires 7-Zip on PATH or installed under Program Files. No Python RAR package is installed or bundled by this release.

**Accuracy:** this update **does not alter** detector/tracker/road-zone/crossing logic or GT assignment. Session #207 remains GT 149 / AI 148 / matched 143 / missed 6 / extra 5 / F1 96.3%. Recovered evidence enables trustworthy case-specific diagnosis; it does not add or suppress counts. Review `docs/verification-v05110/benchmark80-analysis.md` and compare a future full-clip replay before changing any gate policy.


## V0.5.111 — Local benchmark ZIP path diagnostics

V0.5.111 fixes ambiguous input errors from `audit-gate-coverage.ps1` and
`scripts/benchmark-gate.py`. A missing file, a folder instead of a ZIP,
an invalid or partially downloaded ZIP, permission errors, and read I/O errors
now have distinct actionable messages. The PowerShell wrapper resolves
`-Export` to the actual local file and prevents a missing path from being
passed through to the Python verifier. This is a **read-only CLI diagnostics**
release: detector, matching window, tracker, counting and ground truth
are unchanged.

On Windows after downloading the attached ZIP into the Traffic AI project:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
$zip = '.\traffic-ai-benchmark-80-session-207-recovered-v110.zip'
Test-Path -LiteralPath $zip -PathType Leaf
Get-Item -LiteralPath $zip | Select-Object FullName, Length
.\scripts\audit-gate-coverage.ps1 -Export $zip -ExpectedSession 207 -RequireProvenance -OutputDirectory '.\gate-coverage-audit'
```

If the ZIP is in Downloads, supply its **absolute path** via `-Export` or copy
it to the project first. The original recovered archive has 11 unmatched
cases and 23,650 trace frames (runtime 0.5.109); this release does not claim
new inference or change the benchmark.

## V0.5.112 — Verified benchmark error-frame review pack

This release adds `scripts/export-benchmark-review-frames.ps1` and a Python
review-frame exporter. The previously verified GT and AI results from
Benchmark #81 / Session #208 remain **149 GT / 148 AI / 143 matched / 6 missed /
5 extra / F1 96.3%**. This update does not change detector weights, tracking,
counting admission, or benchmark matching.

The exporter checks the complete benchmark trace and validates the supplied
**original continuous video** against the attested FPS, frame count and source
aspect ratio. These metadata checks do **not** establish byte-level video
identity: the user must confirm that the chosen video is the source used by
the benchmark. It exports five near-event images for each of the 11 unmatched
cases (unless clamped at the beginning/end of the video), with the counting
line superimposed and a JSON review manifest. No automatic GT correction,
training annotation, YOLO label, or new count is generated.

Run this from the project root, with Docker Desktop using the Linux engine:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\export-benchmark-review-frames.ps1 `
  -Export '.\traffic-ai-benchmark-81-session-208.zip' `
  -Video '.\videos\clip1.mp4' `
  -ExpectedSession 208 `
  -OutputDirectory '.\benchmark-review-frames-81'
```

Adjust `-Video` if the original MP4 is in a different directory. Output
contains `review-manifest.json`, `README.md`, and `missed_*`/`extra_*`
folders with sampled JPG frames. **Manual review is required before using any
frames for model fine-tuning.** Verify identity, direction and actual crossing
by watching the surrounding continuous video. A saved JPEG is not proof of
physical identity or an independent crossing. There is no reason to re-run
inference just to extract review frames.

The exporter runs in the existing AI Service Docker image, so Windows does not
need another Python/OpenCV installation. Use a fresh output folder for each
attempt to prevent accidental mixing of evidence across sessions.


## V0.5.115 — Verified review-track overlays, no inference policy change

Use the **existing** 55 review frames exported from Benchmark #81 / Session #208.
V0.5.115 adds `scripts/annotate-benchmark-review-frames.ps1`, which joins those
images to the complete, integrity-checked trace by **exact frame index**, draws
up to ten nearest observed tracker bounding boxes and their gate-decision labels,
and writes `review-tracks-upload.zip` to the new output folder. This avoids
rerunning the 946-second video to generate diagnostic overlays.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\annotate-benchmark-review-frames.ps1 `
  -Export ".\traffic-ai-benchmark-81-session-208.zip" `
  -ReviewDirectory ".\benchmark-review-frames-81" `
  -ExpectedSession 208 `
  -OutputDirectory ".\benchmark-review-frames-81-annotated"
```

Then upload `benchmark-review-frames-81-annotated/review-tracks-upload.zip`
for manual case-by-case analysis. The tool requires the existing original
`review-manifest.json` and refuses mismatched sessions/SHA-256, missing
frames, path traversal, duplicate frames or overwriting previous output.
Input JPEGs and benchmark ZIP are mounted read-only in Docker.

**Provenance limitation:** a trace box or `primary-accepted` state is a worker
observation, not proof of vehicle identity or a GT match. The original 149
GT, 148 AI, 143 matched, 6 missed, 5 extra and F1 96.3% are reference
numbers from Session #209; there is **no claimed accuracy gain** in 0.5.115.
The detector, model weights, crossing policy, GT and PostgreSQL data are
unchanged. Annotation is review-only and generates no YOLO training labels.


---

## Phụ lục dependency và xác minh

### Phiên bản package từ V0.5.122 (nội dung gốc)

# Traffic AI V0.5.122 — Dependency & Framework Refresh

Release date: 2026-10-29. Base: the user's V0.5.121 full-source archive.
This is a dependency/runtime upgrade. It is not an improved AI-counting benchmark release.

## Upgraded direct dependencies

| Layer | From V0.5.121 | V0.5.122 |
| --- | --- | --- |
| React / React DOM | 19.3.0 | 19.3.1 |
| @vitejs/plugin-react | 6.1.1 | 6.1.2 |
| FastAPI (backend + AI) | 0.141.1 | 0.162.0 |
| Uvicorn | 0.53.0 | 0.54.0 |
| SQLAlchemy | 2.0.54 | 2.1.6 |
| Alembic | 1.20.0 | 1.20.1 |
| Pydantic | 2.13.5 | 2.14.1 |
| pydantic-settings | 2.15.0 | 2.16.2 |
| HTTPX2 | 2.13.0 | 2.16.0 |
| ReportLab | 5.0.1 | 5.1.0 |
| PyTorch | 2.14.0 | 2.15.0 |
| TorchVision | 0.29.0 | 0.29.2 |
| Ultralytics | 8.4.158 | 8.4.192 |
| NumPy (AI test) | 2.4.6 | 2.5.4 |
| pytest (dev/test) | 9.1.1 | 9.2.0 |
| Python container | 3.14.7 | 3.14.10 |
| Node.js container / CI | 26.10.0 | 26.13.0 |
| npm | 12.2.0 | 12.2.1 |
| pip | 26.2.1 | 26.2.2 |
| Nginx | 1.31.6 | 1.31.8 |

## Retained stable, already-current pins

- Vite 8.3.5, Rolldown 1.2.15 (exact override, avoids previously observed E404 for 1.2.16), source-map-js 1.2.2.
- OpenCV Python Headless 5.0.0.93, PyYAML 6.0.3, Psycopg 3.3.6, Argon2-cffi 25.1.0.
- PostgreSQL Docker image 18.6 — keep the existing external volume unchanged.
- Docker images use exact version tags, not `latest`. Backward-incompatible PostgreSQL major upgrade is not attempted.

TorchVision 0.29.2 explicitly supports PyTorch >=2.14 per its upstream release notes. PyTorch 2.15 may change GPU wheels/CUDA dependencies; actual CUDA driver compatibility needs a live test.

## Scope and invariants

- New Alembic migration 0136_dependencies_v05122 updates only `system_settings.schema_version` and downgrades it to 0.5.121 if rolled back. Prior migration files are unmodified.
- No alterations to counting/tracking/classification/benchmark matching or ground-truth records.
- `scripts/test.ps1` retains its npm audit gate and includes a new stdlib-only dependency verification step.
- `.env`, mounted video/model/training files and external PostgreSQL volume are not embedded in this source ZIP and must be preserved on upgrade.

## Installation and verification limits

The packaging environment cannot reach npm/PyPI registries, cannot run Docker or Windows PowerShell and does not have a CUDA GPU. Hence `npm install`, `npm audit`, Vite production build, Python 3.14 Docker dependency resolution, SQLAlchemy 2.1 integration, live PostgreSQL migration and GPU inference **have not been validated here**. Static version assertions and offline tests do not prove end-to-end compatibility.

After backing up your .env and database, unpack to `D:\LienThongDH\DoAn\traffic-ai` and run:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
```

If Docker caches an old image, run `docker compose build --pull` (with the existing environment) then `scripts/start.ps1`. Do not run `docker compose down -v` or delete external PostgreSQL volume. If npm registry returns E404 again, collect the failing package URL and npm debug log rather than bypassing audit.

## Public version references (checked 2026-10-29)

- https://reactjs.dev/ ; https://www.npmjs.com/package/@vitejs/plugin-react
- https://pypi.org/project/fastapi/ ; https://pypi.org/project/SQLAlchemy/
- https://pypi.org/project/torch/ ; https://github.com/pytorch/vision/releases
- https://pypi.org/project/ultralytics/ ; https://pypi.org/project/pydantic/
- https://nodejs.org/en/blog ; https://hub.docker.com/_/python ; https://hub.docker.com/_/nginx
- https://www.npmjs.com/package/rolldown


### Nhật ký xác minh đã hợp nhất (nội dung gốc)

## V0.5.125 - Dark form controls smoke checks

- Change: frontend/src/styles.css only for UI skin; dark backgrounds cover
  Dataset/Clean Retrain, Fine-tune, camera, benchmark, sign-in/password/user forms.
  Buttons, checkboxes, file upload and range controls intentionally exempt.
- Node stdlib frontend regression tests: 79/79 passed on Node 22 (installed
  here; production Docker version remains Node 26.13.0).
- Offline preflight: 6 dark controls + 6 npm consistency + 4 CI/publish +
  5 CRLF + 5 frontend Vite security + 6 dependency upgrade + 5 Rolldown +
  5 version checks = 42/42 Python tests passed. Combined Node/Python: 121/121
  targeted tests passed. CSS parsed cleanly with tinycss2. Version schema head 0139_dark_inputs_v05125 (metadata-only).
- Parsed 298 Python files for syntax, and validated CRLF for 39 PowerShell files.
- This workspace could not render a browser screenshot in headless Chromium
  (process timed out). Docker build, HTTPS login and GPU were not rerun here.
  Validate via scripts/test.ps1 then scripts/start.ps1 on Windows.

# Verification V0.5.124 — stale npm preflight pin

- Reproduced stale `-notmatch 'npm@12\.2\.0'` in V0.5.123's
  `Assert-ObservedPathCleanFrameV0552Contract` despite correct npm 12.2.1
  pins in frontend/Dockerfile and all three GitHub Actions workflows.
- Fixed legacy contract to derive package-manager pin from frontend/package.json.
  Require exactly one distinct npm@x.y.z per installer file.
- Also fixed stale NumPy 2.4.6 check in the same V0.5.52 contract;
  current ai-service/requirements-test.txt pins NumPy 2.5.4.
- Added six stdlib regression cases and metadata-only Alembic 0138.
- No changes to Python dependencies, Node/Vite/React versions, AI engine,
  tracking, Ground Truth, saved events or Docker volumes.
- Offline verified: 6 new npm/NumPy regressions, 6 V0.5.122 dependency
  checks, 5 version-contract checks, 4 V0.5.123 CI/publish safeguards,
  5 release-EOL checks, 5 frontend security, 5 Rolldown checks,
  12 AI raw-motion and 14 backend raw-motion tests, plus 74 Node tests:
  136 targeted tests passed. Node tests ran on available Node v22.16.0,
  NOT the configured production Node 26.13.0.
- Parsed 296 Python files (AST), verified CRLF/no BOM in 38 PowerShell scripts;
  all 26 technology literal source checks match. Verified ZIP checksum/integrity.
- PowerShell `scripts/test.ps1`, full Docker/GPU run and GitHub Release must be
  rechecked on Windows; offline tests do not prove these runtime workflows.

---

# Verification V0.5.123 — CI/publish race safeguards

- Source based on V0.5.122; project version V0.5.123 and metadata-only Alembic 0137.
- Fixed `scripts/test.ps1` using outdated `26.10.0` check against current `26.13.0` workflows; CI version is now derived from `.nvmrc` and checked against Dockerfile.
- Added fail-closed checks in `scripts/publish.ps1` after tests, before staging and pushing, and for Git index, HEAD and tag contents to block VERSION/tag drift (including GH CLI fallback).
- Previously pushed `v0.5.121` tag with `VERSION=0.5.122` is **not overwritten** by this source. New source should be released only as `v0.5.123`.
- Verified offline: 74/74 Node tests; 46 Python assertions passed across CI/publish/dependency/release/security/version/portability/raw-ID groups, with one native-PowerShell-only case skipped; 12/12 AI raw-motion and 14/14 backend raw-motion tests passed. **146 passed, one skipped** across selected groups. Version/migration contract passed. One Python-cache regression group exceeded the local timeout, and broad Python discovery exceeded the environment timeout; neither is counted as passing. This environment cannot execute PowerShell or Windows Docker/GPU; GitHub creation is not claimed.

---

# Verification — Traffic AI V0.5.122

Scoped package/framework modernization, 29 October 2026. The release is NOT certified as a successful Docker/GPU deployment; see detailed phần dependency ngay trong README.md.

- Exact direct pins were aligned across production/test requirements, Dockerfile, CI and Windows test script.
- New migration `0136_dependencies_v05122` is version metadata only. V0.5.121 historical migration preserved.
- Native frontend Node.js tests: 74 passed (using available Node v22 for JS tests only, not the pinned production Node 26.13.0).
- Offline stdlib tests for new dependency pin, frontend Rolldown, Vite security, release metadata passed (6+5+5+5 = 21 cases).
- Raw-motion audit regressions: 12 AI-service and 14 backend offline tests passed.
- Combined targeted test coverage: 21 dependency/security/version + 26 raw-motion + 74 Node frontend = **121 tests passed**.
- Python scripts broad discovery is not a meaningful green integration result: `test_benchmark_gate.py` imports pytest, which is not available under Python -S. A separate large unittest invocation exceeded the execution window.
- Real npm/pip dependency installation, npm audit and Docker/frontend production build, PostgreSQL migration, CUDA / inference benchmark remain unverified due network/Docker/GPU limitations.
- Historical vehicle-count benchmark not rerun; no recall/precision uplift claimed.

---

# Verification — Traffic AI V0.5.121 (frontend dependency release)

## Customer-provided failure evidence, 29 October 2026

Source: `traffic-ai-v0.5.120-full-source(2).zip` and terminal log.
`./scripts/test.ps1`: backend 222 passed / 28 subtests; AI 898 passed /
55 subtests; backup worker 4 passed; source contracts passed, then frontend
`npm install` failed fetching `rolldown-1.2.16.tgz` (HTTP 404). There is no
new GPU replay, ground-truth score or database mutation evidence in the log.

## Scoped change

Vite 8.3.5 depends on `rolldown: ~1.2.14`. The npm registry version page
shows 1.2.15 as published, whereas npm's original resolution selected 1.2.16,
whose tarball returned 404. Pin `frontend/package.json` `overrides.rolldown`
exactly to `1.2.15`, while preserving the existing `source-map-js` override,
Vite security pin, npm audit gate and installation routes in PowerShell, CI
and frontend Dockerfile. No counting or benchmark logic changed.

Added 5 offline release guards (`test_frontend_rolldown_v05121.py`) and wired
into `scripts/test.ps1` ahead of install. App/backend/AI/worker metadata all
bumped to 0.5.121; Alembic head `0135_frontend_pin_v05121` only updates
`system_settings.schema_version`.

## Locally completed checks on the 0.5.121 source ZIP

- 5 V0.5.121 dependency guard tests passed.
- 5 previous Vite security tests, 5 version-contract tests, 5 PowerShell
  line-ending/release safety tests and 5 fingerprint contract tests passed.
- 12 AI plus 14 backend previous raw-motion tests passed (`python -S`).
- 74 frontend native Node tests passed (`node --test`).
- Python `compileall` for app/tests/scripts and `scripts/version-contract.py` passed.
- These are **125 targeted tests**, not a successful complete Docker suite.
- A broad scripts unittest attempt did not finish under the packaging runtime
  limit; it is not counted among the 125 passing tests.

## Verification limits

New offline guards and version-contract tests can be run locally. **No Docker,
PowerShell or network access to npm registry in the packaging environment:**
`npm view rolldown@1.2.15` encountered DNS `EAI_AGAIN`, so `npm install`,
Vite build, browser smoke test and GPU/video inference remain unverified for
.121. The customer must confirm `scripts/test.ps1` finishes on Windows.

---

# Verification — Traffic AI V0.5.120

## Baseline and current evidence

Baseline delivered .119 source ZIP:480files,SHA256
`63d84e4631a33fd7d81b0652adf153030e0f3cfc5104453b258b2fcfcb3b0909`.
All prior paths and test functions/assertions are retained.

Customer #87/session214 ZIP SHA256
`3592d9d242588ab4da236d773ac6c02adf657ea0215a469638617b72a2be3a4b`.
Six manifest certificates,23,650 sequential frame clocks and closed gzip
source were verified. RAR160JPEGs plus raw trace match418,974,845bytes,
SHA256 `7f480e23a6539dcb250a21e882b3dd4fc757419b5af510ed957b2b33f65c6faf`.
Header runtime .119/fingerprint
`3d417ba11176a0774e9503fc93ce7200bfd57b89112ebf53198edb00d9b7fa28`
matches delivered source. Its195 effective-policy fields are complete with
digest `821ab9d456acefae1590e03c6830805907b61bb44f5633d65b76eba514d2cbfd`.

#86→#87 normalized149GT including notes,config and all147 persisted event
signatures (canonical ID,clock,point,confidence,class,direction,method) are
identical:0added/0removed. Measured .119 remains144matched,5missed,3extra,
2class/2direction mismatches,140strict,F1 .972973. No .120 inference score
or count improvement is inferred from this diagnostic upgrade.

## Per-raw motion functionality

The new bounded audit is scoped to one requested canonical owner but measures
box-center displacement only within the same raw token on consecutive source
frames with increasing clocks. Raw changes,missing/invalid target observations
and source-frame gaps split segments. At least2 samples are needed. Synthetic
audit rows and metadata are excluded. Identical duplicate frames are ignored;
conflicting duplicates or out-of-order frames fail closed. Bounds are256frames,
64tracks per frame and8 output segments with explicit truncation.

The backend returns only whitelisted numeric evidence for the requested owner,
validating segment chronology,contiguity,count,gap,finite vectors and rounded
per-frame consistency. The UI adds a separate card to class/direction/extra
cases,seek controls and an optional comparison between an exact matching
handoff jump and the new raw's contiguous motion. Cosine is descriptive only;
physical identity,crossing validity and IN/OUT are not automatically inferred.
Existing observed-track evidence remains separate and retains its schema.

Actual754s fixture: raw312739 forms18834–18842,9samples,dy+.0025px;
raw331821 forms18860–18870,11samples,dx−41.2415/dy−74.505px. The18-frame
handoff displacement dy+229.647px is not folded into either raw segment.
The historical rescued IN754.0452 was created and later OUT754.6878 was
deduplicated as same-track-direction-flip. Future opposing motion alone can
also follow a genuine U-turn, so it is insufficient to authorize suppressing
that earlier event. The established-heading stop-go contract remains intact.

Worker/counting/tracking/classification/fragment ownership/endpoint policies
remain .119. Only read-only trace aggregation and diagnostic projection/rendering
change; no GT/matcher/tolerance or saved events are edited. Source identity
additionally attests the raw-motion audit module; migration0134 changes only
release metadata. Legacy traces without usable raw rectangles have no motion
segments rather than fabricated movement.

## Validation

**1,355 offline cases passed,0 failures:** AI895,backend161,scripts216,
benchmark-gate5,backup4,Node74. The26 isolated .120 stdlib cases (12AI,
14backend) also pass under `python -S`; these overlap the total above.
The64 exact pre-existing HTTP/ORM exclusions and1 native PowerShell skip
are unchanged. All480 old paths,1,319 old Python test ASTs and10 byte-identical
old Node test files are retained. No old test function body or assertion changes.
The488-file source passes456 static checks;288 Python files compile, local
imports/call signatures/state-schema references resolve,39 PS1 files retain
CRLF/noBOM and79 declared PowerShell assertions remain invoked. All19
production JS/JSX files pass Babel parsing; actual .120/migration0134 version
contract CLI passes.

New tests exercise same-raw grouping and ID/frame-gap splitting, missing raw
values, malformed geometry/types/nonfinite data, duplicate/conflicting/out-of-
order frames, record/sample bounds,truncation and detached results. Production
`diagnose_trace` runs on both a synthetic handoff and actual session214's stored
trace. Actual diagnosis → backend raw/observed scopes → frontend helper yields
2 segments and separate jump/motion vectors,cosine−.733142. No score/direction
inference is made. Actual backend attach statements are tested via AST seams;
this does not claim a running HTTP/ORM stack or browser-rendered interaction.

Offline checks do not claim native HTTP/ORM,PowerShell,Docker,browser/Vite
build or new GPU/video inference. No newly measured .120 F1 is claimed.

---

## Previous release verification

# Verification — Traffic AI V0.5.119

## Authoritative baseline and observed run

Built from delivered .118 full source,471 files, SHA256
`91084df203d00488cb9f7f3d934309380638316ada17e924a286551e85112793`.
All previous source paths and test functions/assertions are retained.

New input benchmark86/session213 ZIP SHA256:
`88826aed22fae3183be7ca55b8e2d5f340deeea41fc7d75056b6bd67743b6ba8`.
All six manifest member certificates are verified; the closed gzip and RAR
contain the same418,955,190-byte raw trace, SHA256
`a4caa7eaf36ddbca2d3e54fe4b3542c0d589c712dddad280dd23e3cd0f060eb6`.
There are23,650 sequential frames with valid clocks. The session header says
AI .118 and fingerprint `f2ca2262f9217028e449ae41f1f05bab6540c66a614032246eef6327dd935b35`,
matching the delivered source. Policy snapshot195 fields is complete and its
canonical configuration digest validates. RAR contains160JPEGs plus raw trace.

Observed #85→#86:149GT unchanged,AI148→147,matched144 unchanged,missed5
unchanged,extra4→3,class2/direction2 unchanged,strict140 unchanged,
F1 .969697→.972973. All149 normalized GT rows including notes are equal.
The only config JSON difference is the inference_settings explanatory string;
geometry,tolerance,current camera and model fields match. All147 remaining
normalized events are exactly equal, including canonical IDs, coordinates,
confidence,class,direction,source times/frames and method. Only OUT366576 at
812.5773s is removed; no event is added. These are measured .118 outcomes,
not a .119 detector replay or score.

## New read-only functionality

The AI endpoint reads a bounded trace prefix for the requested session and
validates the recorded policy using the explicit scalar wire schema, type
checks, session identity and canonical digest. It does not treat an absent
legacy policy as disabled. The backend requests this optional diagnostic
through a bounded, timed stream and returns sanitized status on failure.
The new benchmark panel loads the selected session's recorded policy on
expansion, with loading/retry states and stale-request cleanup. It displays
capture scope, historical AI runtime, flags, missing values and searchable
recorded parameters. No current-environment fallback or editable runtime
configuration is introduced. This metadata-only/prefix check does not certify
whole-trace closure, model weights, media identity or full reproducibility.

Worker, counting, tracking, classification, finite endpoint and fragment
ownership source bytes remain .118. Existing benchmark report/matching/GT/
tolerance logic is unchanged. Source identity additionally attests the new
recorded policy reader. Migration0133 updates release metadata only.

## Remaining evidence and limits

Around754s, actual images18860/18870 show a rider traveling OUT while the raw
identity borrows a long-lived parked canonical and proposes IN754.0452s.
The later OUT754.6878s is observed but backend deduplicates it as
same-track-direction-flip. Removing the established-heading exemption would
break the tested stopped-then-moving continuity contract. No general safe
replacement has been proven, so this is a diagnosed case rather than a .119
counting fix. The591s window contains no road/gate track evidence sufficient
to recover an event. Cargo van class and genuine returns remain preserved.

## Validation

**1,316 offline cases passed,0 failures:** AI883,backend147,scripts215,
benchmark-gate5,backup4,Node62. The31 isolated .119 stdlib cases (17AI,
13backend,1schema drift) also pass with `python -S`; they are already included
in the total. There are64 exact pre-existing HTTP/ORM exclusions and1 native
PowerShell skip, unchanged from baseline. All471 old paths,1,287 old Python
test ASTs and9 byte-identical old Node test files are retained. No existing
Python test body or assertion changes in .119. The480-file source passes450
static checks:283 Python files compile, local imports/signatures/globals/state
and schema fields resolve,39 PS1 files retain CRLF/noBOM and79 PowerShell
assertions remain declared/invoked. All17 production JS/JSX files pass Babel
parsing. The actual version contract CLI validates .119/migration0133.

New API tests cover historical scalar/digest validation, partial/legacy/missing
states, wrong sessions, duplicate metadata/keys, unknown fields, nonfinite and
wrong scalar types, prefix/line/response limits, malformed bytes, network-error
redaction and route no-store/404/session forwarding. Route function statements
are exercised via AST without a native HTTP stack. Frontend unit tests cover
available/unknown/partial states, absent versus false, wrong-session and unsafe
payload rejection, plus filtering. The actual #86 raw prefix passes through
the production AI reader, backend validator and frontend helper, showing195
parameters, AI .118,complete,0 missing fields and both endpoint flags enabled.
No browser rendering or end-to-end network success is inferred from this.

Offline checks do not substitute for HTTP/ORM integration, Docker, native
Windows PowerShell, Vite build or new GPU/video inference. No newly measured
.119 F1 is claimed.

---

## Previous release verification

# Verification — Traffic AI V0.5.118

## Baseline and recorded run

Built from delivered .117 full-source ZIP,466 files, SHA256
`bd45055ee4b2a8191f508deb7c3054465c6badc05b0f7f8ebb544a2f5789c0ba`.
All old paths, test functions and assertions are retained. The only existing
AI test expectation extended is the session header's new effective guard flag.

The customer benchmark85/session212 ZIP has SHA256
`62be8d88732572c3a90445aa0de3675804edc1e29caed5a8d544ab7b499e549d`.
It records AI .117:149GT,148DB events,144matched,5missed,4extra,2class
mismatches,2direction mismatches,140strict matches,F1 .969697. These are
historical .117 results, not a .118 detector run or score.

## Recorded-proposal sweep

All six export manifest certificates and the closed gzip source trace were
verified (418,132,768 decompressed bytes, SHA256
`419b951b203d4fdecab0933b67a6431d872349b67102392f8f99ebb23419408b`).
The trace contains23,650 sequential source frames and its .117 fingerprint
matches delivered source. Of162 recorded primary proposals,42 are rescued.
With fixed recorded geometry and proposals, the extension newly rejects one:
frame20327, canonical366576/raw367219, projection .070934, center -.021512.
The other41 rescued proposals and120 other-method proposals have unchanged
helper decisions. IDs/frame numbers occur only in this audit; runtime admission
uses geometry, class, direction and method. This is a helper counterfactual,
not a stateful full-video replay, physical identity proof or new benchmark F1.

## Runtime scope

The finite endpoint helper preserves its old default API: rescued crossings
are considered only with explicit `allow_rescued=True`. The worker uses this
extension only for video with both the existing finite endpoint flag and
`AI_ENDPOINT_RESCUE_GUARD` enabled. The existing edge_fraction .08 and
stable_center_side .04 remain unchanged. The new rejection kind is
`finite_endpoint_rescue_center_uncertain`. Direct crossings, four-wheel
vehicles, interior crossings and stable destination-side centers are unchanged.
Suppression leaves the primary gate closed and does not enqueue Human Guard
or commit an event. The per-rescue counter is a subset of the existing
aggregate precision counter. It is not an estimate of removed DB false positives.

The extra audit-only `policy_metadata` trace row follows the first geometry
row and records allowlisted scalar attributes from actual initialized worker,
resolver, primary and optional rescue/guard/detector components. Missing,
invalid and unreadable field names are recorded without exception contents.
Only finite numeric values, exact bool/int types and permitted enum values
are admitted. No arbitrary environment/object enumeration or secrets are
serialized. Capture failure is diagnostic and does not stop counting.
The canonical SHA256 scope is `allowlisted_effective_algorithm_parameters`;
it is not a complete inference-run identity. Geometry/FPS/model/source
identity and unrecorded settings remain separate or unknown. Historical
exports never substitute the current environment for missing settings.

Source fingerprints now attest `policy_snapshot.py` as well as the previous
nine source files. Benchmark matching, GT and tolerance code is unchanged;
`backend/app/api/routes.py` changes only its inference-settings explanatory
string. Release migration0132 updates schema_version metadata only.

## Validation

Final offline result: **1,276 cases passed,0 failures** (AI866,backend134,
scripts213,benchmark-gate5,backup4,Node54). The20 isolated .118 stdlib tests
also pass under `python -S`; these are already included in the total. There
are64 exact pre-existing HTTP/ORM exclusions and1 native PowerShell skip.
All466 baseline source paths,1,260 old Python test functions and9 byte-identical
Node test files are retained. The sole changed old test body extends the header
expected dictionary with the effective guard flag; after removing exactly that
new false key its AST is identical to baseline. All other old test ASTs match.
The471-file source passes445 static checks:277 Python files compile; local
imports, call signatures, state/schema fields, migration chain,39 PowerShell
CRLF/no-BOM files and79 declared/invoked PowerShell assertions are checked.
All15 production frontend JS/JSX files pass Babel parsing. The actual version
contract CLI confirms .118 and migration0132.

The12 new worker/helper endpoint tests cover flags, old interpolation behavior,
fixed recorded geometry, optout, no Human Guard/context/event/count side effects,
closed gate on jitter, no repeat OUT and a later clear IN return. The12 snapshot
stdlib tests and2 actual-worker first-frame tests cover sanitized capture and
failure behavior. A constructor check captures all195 allowlisted fields from
actual initialized worker/counter/resolver/rescuer objects without missing or
invalid fields (dispatcher/encoder constructors inert to avoid I/O).

Checks use real source/test bodies offline. The current environment has no Docker,
native PowerShell, FastAPI/SQLAlchemy/HTTPX2, Torch or OpenCV. HTTP/ORM tests
are explicitly excluded, with a fail-closed external HTTPX2 import placeholder
for worker unit tests. No HTTP success, Windows execution, GPU inference,
container build, Vite production build, full-video replay or newly measured F1 is claimed.

Run `.\scripts\test.ps1`, `.\scripts\start.ps1`, then
`.\scripts\publish.ps1` in Windows for the full deployment workflow.

---

## Previous release verification

# Verification — Traffic AI V0.5.117

## Authoritative source and customer evidence

Baseline: delivered .116 full-source ZIP,461files, SHA256
`d72448448cd02b4c603ffcc780063ffa00c35990e5fd32a684d06a23ebf8c8bb`.
This is the next version of .116, not an older restored workspace project.
Inputs are read locally without changing their bytes:

| Input | SHA256 |
|---|---|
| `traffic-ai-benchmark-84-session-211(1).zip` | `b7a1bfb68c2c7a37ce2e600c59877ea93c2ce69b3542291de7f611acaf7a33d2` |
| `camera_1(20261023-145231).rar` | `4cc1e9f6775b4492edc74271f3af1549cd7a6bacfa1c9b61a1a00719c9dce66d` |
| `image(20261023-145253).png` | `20ac78801df1418c189b3f88aa794b19e28d2f17162e5270c8fa867119a49950` |
| Raw/gzip-decompressed trace,414,726,212bytes | `63da4f2bbbb9303bac9a3fb3015f54945a354012d6b5bed492b922269a4d918a` |

All six manifest members are verified. The RAR contains164JPEGs plus the same
raw trace, and all23,650 source frames are sequential. The session header
explicitly identifies **AI V0.5.116** with source fingerprint
`d94eecd06da9d2efa0ecfc7069dad7ac8e09747f9e0a3d32167eeaffe88533b6`;
both .116 feature flags are enabled. The .115 screenshot badge is a compiled
frontend version and does not identify the worker runtime.

Observed #83→#84 with unchanged normalized GT/config: matched143→144,
missed6→5, extra5→5, class mismatches3→2, strict matches138→140,
F1 .962963→.966443. OUT145089 at391.9539s is present and196223 at533.9486s
is bicycle. No prior passage is removed; three canonical IDs and one
confidence also change. Final .116 counters: repeated-target rescue1 and
stationary candidate rejections141. These are .116 results, not a .117 score.

## Runtime changes

The new fragment policy requires repeated, same-target nested-box geometry
and consistent relative motion for a newborn two-wheel child beside a mature
moving owner with a recent accepted passage. An exclusive child can be
retired only before any accepted/pending Human Guard passage. Retirement
discards uncommitted primary/secondary/span state together, keeps the owner
heading independent, and reserves the old canonical key so semantic caches
cannot be accidentally reused. Raw fragment observations are held until safe
separation or lifecycle expiry allows a fresh identity. This is geometry
evidence, not appearance-based proof of physical identity.

The video-only default flag is `AI_TWO_WHEEL_FRAGMENT_GUARD=1`. State reports
`two_wheel_fragment_retirements`, `two_wheel_fragment_releases`, and
`two_wheel_fragment_suppressed_current_frame`; these count identities or
filtered boxes, not measured removed DB events. Trace records the effective
flag and bounded evidence. Source fingerprints include `fragment_ownership.py`.

The certificate uses existing observed frame clocks: child age at most5
frames and at most6 class hits; owner at least8 hits with an accepted passage
within75 frames. Three distinct samples, gaps at most2 frames, need child
coverage at least0.90, area at most0.60 of owner, width/height at most0.80,
and normalized relative-offset drift at most0.06. Owner motion needs three
raw observations and an observation at least8 frames old with displacement
at least0.10 of its box diagonal; the child must lie behind that motion.
No target ID, benchmark timecode or GT mark is an admission condition.

At808s the old newborn368014 belongs to the rear of365295. Its first OUT is
followed by a false lost-IN and another OUT after borrowing raw IDs; dropping
only the first event would be unsafe. The recorded-box replay checks this
whole sequence and preserves the distinct following368646. It uses real
resolver/counter/rescuers with fixed recorded detections, not new model
inference or a replacement for backend/Human Guard delivery evaluation.

Final fixed-output sweep: 23,650 frames /271,208 stored observations, exactly
one certificate:368014→365295 at frame20201 using20199/20200/20201, offset
drift0.01484583855. It filters53 historical observations and rearms at20277.
The261-frame actual-policy window20100..20360 reproduces the old seven
proposals and produces four after the fix: the fake child OUT20201,
lost-IN20216 and span-OUT20219 disappear. Owner OUT20170 remains; distinct
following368646 still has OUT (20221→20220), and the812.577 proposal remains.
Rearm gets fresh synthetic canonical−1, stitched=false. Seven replay checks
pass. Only one of the three old child proposals became a persisted extra
event in #84; this is not evidence that three DB false positives are removed.

The full-trace sweep uses fixed historical raw/canonical/class snapshots for
eligibility, not a re-executed complete runtime. The window executes actual
worker filter/resolver/primary/span/center/lost-finalization classes with
constructors extracted from source and default parameters. Historical
environment overrides are unavailable. It omits duplicate coalescence,
Human Guard, semantic refiners, event-time selection, HTTP/backend dedup and
F1; gate_tracks can omit earlier suppressed detections. These limits remain
even though the selected causal sequence is reproduced.

The UI now compares the compiled UI identity with a ready live AI health
version from the existing `/api/system/status` poll. Unknown, malformed or
unready results do not mean mismatch; poll failures clear stale status.
Manual reload is offered on mismatch. Nginx revalidates `/index.html`,
including SPA fallback, while hashed asset caching remains unchanged.
Attachments do not prove whether the old badge came from cache/open tab
or an older frontend container.

## Remaining evidence boundaries

The old report's five extras are unchanged. The separate812s case is not
silently removed as part of the808 fix. Snapshot/trace checks at59s,237s and
406s show real opposing riders; OUT candidates17463/86400/150402 first appear
already on the post-side at frames1486/5945/10178, with no pre-side anchor or
center witness in those windows. Existing IN14/84351/149041 are other real
riders. Flipping them or synthesizing crossings would not be an evidenced
gate fix. Detector/track recall before the gate needs fresh video inference.

Cargo vans remain truck; genuine return passages can count again. No GT,
matcher, matching tolerance or near-time vehicle suppression is changed to
fit the report. No new .117 F1 or promise that all misses/extras are fixed.

## Validation scope

Final validation and packaging counts are recorded below. Actual offline
test functions, unittest and Node tests run against real policy modules;
an external fail-closed HTTP client fixture permits actual worker import,
and backend pure helpers run in isolation. No successful network/ORM/GPU
behavior is substituted. Existing tests and default dependency-backed checks
remain enabled, with .117 pure regressions added to `scripts/test.ps1`.

| Check | Result | Scope |
|---|---:|---|
| AI tests | 840 passed | 765 test functions +75 unittest cases; actual worker import |
| Backend pure tests | 134 passed | Real isolated helpers/shadow guard; no HTTP/ORM integration |
| Script unittest | 212 passed | Includes fragment policy fingerprint coverage |
| Benchmark gate / backup worker | 5 /4 passed | Isolated real test functions |
| Frontend Node tests | 54 passed | Includes7 new version-state behavior cases |
| New pure fragment cases | 26 passed | Also independently run using `python -S`; already included in840 |
| New actual-worker integration cases | 7 passed | Retirement transaction, pending/accepted vetoes, fresh rearm and heavy-plan masking; included in840 |
| Recorded-box replay checks | 7 passed | Separate policy evidence; not added to unit-test total |
| Static source contracts | 442 passed | 272 Python files,204 self/643 direct/60 worker signatures,202 imports,3286 global references |
| Frontend production source syntax | 15 files parsed | Babel; not a Vite/browser build |
| Retention | 461 paths retained | 1,226 prior Python test names,2,412 Python functions,8 old Node test files unchanged |
| Release metadata/migration chain | passed | V0.5.117, single metadata-only head |

**Total: 1,249 test cases passed, zero failures.** Exactly64 pre-existing
HTTP/ORM-dependent cases were not executed (3 AI +61 backend);1 native
PowerShell harness was skipped. This is offline validation, not a complete
pytest/Docker result. Runtime here: Python3.12.14 and Node24.22.1, not the
target container toolchain. All1,226 prior Python test ASTs remain identical
except the session-header expectation that adds the new default-false flag;
no old assertion is weakened. Four trace-isolation tests initially found an
optional-field compatibility issue, fixed in production code with `getattr`
and rerun successfully. All39 PowerShell files keep CRLF/no BOM, and all79
declared `Assert-*` functions in `test.ps1` remain invoked.

Independent review additionally verified class-wobble quarantine, exact
box-to-finite-segment release distance, fresh synthetic identity even beside
a tempting counted owner, stale-alias detachment and heavy-plan masking so
a quarantined car label cannot suppress a real truck. The final tested code
manifest freezes464 code files; only README/VERIFICATION may change after it.
Packaging validates all466 source members, safe unique paths, CRC, exact
source bytes and different archive timestamps for modified Python members.

Full pytest collection, native PowerShell, Docker/Compose, live PostgreSQL,
Nginx/browser execution, online npm audit/Vite production build and new
original-video inference were not run here. Migration
`0131_runtime_status_v05117` is metadata-only, parent
`0130_target_evidence_v05116`. Keep runtime data/volumes on update and create
a fresh session/benchmark to measure .117.

---

# Verification — Traffic AI V0.5.116

## Authoritative baseline and protected evidence

This release starts from the supplied V0.5.115 full source, not an older
workspace snapshot. All 457 delivered baseline paths and all existing Python
and PowerShell function names must remain present.

| Input | SHA256 |
|---|---|
| `traffic-ai-v0.5.115-full-source(1).zip` | `749ec30df8c5381b8d3e92ad2927fdf6e1eb6fee65168ac8969bde5a3960b6ec` |
| `traffic-ai-benchmark-83-session-210(1).zip` | `0dcc722620fbdd1ae2bf2274edc6bddcf4fb006ac15232059187d7f8290d679f` |
| `camera_1(20261022-123043).rar` | `05a6ad5c4a1e1c48f51cb3ffe697fcbacfe08b9aa7e16563fced8ef8b5b13a37` |
| Certified source trace, 413,160,406 bytes | `32e842e704a29c5b2c54fed787852fdc309a4930eacfbec5629a66173dd84558` |

The RAR has 163 JPEGs plus the continuous JSONL trace; the JPEGs do not
constitute the original continuous video. The .115 trace source identity is
`a18765beb5c4464ecbe799a64382c368258bb3db90bee1265aba9f2450d8ee0c`.
Stored #83 metrics remain GT149 / AI148 / matched143 / missed6 / extra5 /
class mismatches3 / direction mismatches2 / F1 0.962963.
No benchmark evidence, matcher or tolerance is modified or rescored.

## Runtime fixes and evidence boundaries

**Stationary ownership:** a new two-wheel raw ID could borrow the history of
a parked rider after a gap of 21 frames. The existing short-gap guard only
covers 1..12 frames; the large newcomer box also expands the old proximity
allowance. The new bounded certificate retains the same raw owner's origin,
minimum footprint, full-episode maximum drift and three distinct observations
over at least 12 frames. In the 13..normal-gap window, both a large direct jump
relative to the old owner and a contradictory velocity prediction are needed
to reject the alias candidate. Established moving headings, same-raw returns
and four-wheel rules retain their existing behavior. The counter
`stationary_alias_rejections` counts rejected candidate offers, not recovered
crossings or proven count improvements.

**Repeated target views:** track196223 at frame13355 was stored as motorcycle.
Its fresh tight general crop says bicycle0.303955078125; general wide views
at13345 and13355 say bicycle0.462890625 and0.70068359375, above primary
motorcycle0.638671875. Previous rules require stronger or independent-source
agreement, so this is an explicit bounded policy expansion. A new crossing-only
fallback requires all three same-source views, existing confidence floors,
a primary-score margin, recent ordinary winning support and no contradictory
motorcycle evidence. It returns0.70068359375 unchanged. It neither claims
independent model agreement nor proves physical identity from geometry alone.

Fresh tight opinions are captured from actual model results, cleared each
frame/alias/passage, and never loaded from audit rows. Counter and override
commit follow existing Human Guard transaction rules. Default-on flags apply
only to videos; trace metadata records their effective values. Source
fingerprints now also cover `classification.py` and `tracking.py`.

The fixed .115 trace sweep covers all 23,650 frames, 167 context decisions and
1,337 ordinary refiner observations. Reconstructed prior ordinary-support
tuples match all 167 stored tuples. Exactly one previously rejected decision
meets the new fallback requirements; the other 166 remain ineligible. This is
a fixed-output policy counterfactual, not new GPU inference or an accuracy
measurement. The ID replay similarly checks resolver/primary-gate behavior
on recorded boxes, not the entire runtime/backend admission chain.

In the causal window 9690..9850, the new guard keeps raw145089 separate from
parked owner143964. The primary gate then accepts OUT at frame9806, with
geometric crossing frame9799.848500482003 / source391.953940019s. Guard-off
does not emit this event; the other primary OUT at9848 remains unchanged.
This is recorded-box replay, not confirmation that final backend delivery or
the fresh video's result will match.

The complete resolver-only sweep is broader than that one example: 23,650
frames / 271,208 observations, stitches1172 to1149,141 rejected candidate
offers. Eighteen new-token decisions change from stitched to fresh and one
from fresh to stitched; other ownership changes propagate through subsequent
observations (80 changed new-token decisions and44,834 observations across
91 raw IDs). Rounded trace boxes, default resolver parameters and omitted
runtime duplicate coalescence limit this experiment. These are changes of ID
ownership, not a measurement of improved counts; other identity changes need
review on a fresh full run.
Of the18 stitched-to-fresh cases,12 have a later observation of the old raw
owner returning near its parked location; six lack enough identity evidence
to confirm physically. Three certificates span only12..13 frames. No GT
labels are used to declare these cases correct. These residual risks are
another reason to inspect the next full-video run rather than project F1.

The rear-fragment case around808s is deferred: dropping its first event alone
can expose another false return event. Unmatched real riders, cargo vans and
genuine return passages are not removed to fit GT.

## Validation for this release

The final validation record is below. Offline adapters execute actual test
functions and the actual worker module with a fail-closed external HTTP-client
placeholder. They do not simulate successful network I/O or replace policy
implementations. Backend pure helpers are extracted for isolated execution;
HTTP/ORM tests require the target dependencies and are reported separately.

| Check executed here | Result | Scope |
|---|---:|---|
| AI tests | 807 passed | 758 test functions +49 unittest cases; actual worker import, no inference |
| Backend pure tests | 134 passed | Isolated real helpers/shadow guard, no HTTP/ORM integration |
| Script unittest | 211 passed | Includes new policy-fingerprint regression |
| Benchmark gate / backup worker | 5 /4 passed | Real test functions, isolated fixtures |
| Frontend Node unit tests | 47 passed | Built-in Node runner |
| New .116 pure AI cases | 40 passed | Independently rerun with `python -S`; already included in807 |
| Source contracts | 438 checks passed | 269 Python files, call signatures, imports, state/schema payloads, PowerShell text contracts |
| Frontend production source syntax | 14 files parsed | Babel syntax/import checks; no Vite bundle |
| Source retention | 457 paths retained | 1,176 prior test names and2,344 Python function names retained |
| Versions and migration chain | passed | V0.5.116, one metadata-only Alembic head |

**Total: 1,208 test cases passed, zero failures.** Separately,64 dependency-
requiring cases were not executed (3 AI and61 backend HTTP/ORM), and1 native
PowerShell harness was skipped. This is an offline validation report, not a
claim that the complete dependency-backed pytest/Docker suite ran here.
All old test function ASTs remain identical except the session-header test,
whose expected dictionary adds the two default-false effective feature flags.
All39 PowerShell files retain CRLF/no BOM, and all79 declared `Assert-*`
functions in `test.ps1` remain invoked. Source CRC, exact member bytes,
safe unique paths and modified Python archive timestamps are checked at
packaging; no caches or personal runtime data are included.

Windows PowerShell, Docker Compose, live PostgreSQL, original-video GPU
inference, online npm audit and Vite production build have not run here.
The normal Windows `scripts/test.ps1` still runs its full dependency-backed
checks, with new stdlib-only .116 regressions added. No dependency audit is
bypassed. Migration `0130_target_evidence_v05116` updates version metadata
only; its parent is `0129_review_tracks_v05115`.

Run the commands in the current README, process the same original video into
a fresh session and create a new benchmark to measure .116. Old session210
results and exports do not change after replacing source. Keep user data,
`.env`, `.git`, model/video/snapshot files and persistent volumes on update.

---

# Verification — Traffic AI V0.5.114

## Root cause / fix

The AI image only bundles `ai-service/app`; the review-frame PowerShell command
mounted `export-benchmark-review-frames.py` and `benchmark-forensics.py` but
not the latter's sibling dependency `benchmark-gate.py`. The exact reported
`/opt/benchmark-gate.py` missing-file failure follows from this omission.

- Added the missing read-only bind mount and explicit verifier file preflight.
- Added 4 new regression tests, invoked by the default PowerShell test workflow.
- Updated all release versions to 0.5.114 and added metadata-only Alembic head
  `0128_review_mount_v05114`.
- No change to AI recognition, crossings, Ground Truth, PostgreSQL data, or model.

## Verification in this environment

| Verification | Result | Evidence / limit |
|---|---|---|
| New verifier mount regressions | **4 passed** | `python -S -m unittest discover -s scripts/tests -p test_review_frame_verifier_mount_v05114.py` |
| Existing frame export regressions | **7 passed** | `python -S -m unittest discover -s scripts/tests -p test_review_frame_export_v05112.py` |
| All script Python tests via pytest | **207 passed, 1 skipped** | `python -m pytest -q scripts/tests`; 97 passing subtests; skip is Windows PowerShell native harness |
| Frontend unit tests | **47 passed** | `node --test frontend/tests/*.test.js` |
| Real Benchmark #81 / Session #208 verifier | **verified 11 cases** | `verified_cases` using the actual user-supplied ZIP with all three sibling files present |
| Python release metadata/migrations | **passed** | `python scripts/version-contract.py` |
| Windows PowerShell `test.ps1` / Docker container execution | **not run** | Docker and PowerShell unavailable here; verify on target Windows host |
| Original video frame extraction | **not run** | Video `clip1.mp4` not supplied to this environment |
| npm online security audit and production build | **not run** | Not required for isolated exporter fix; must pass on Windows |

The isolated `unittest` discovery across *every* script test with `python -S`
can fail because `test_benchmark_gate.py` intentionally needs `pytest`.
The complete script test suite was therefore validated with installed `pytest`
and passes. Docker's production `test.ps1` calls the unit-only portions in its
own isolated environment and runs benchmark-gate tests separately.

---

# Verification — Traffic AI V0.5.113

## Input and issue

- Based on the user's Windows V0.5.112 `scripts/test.ps1` log, not a newly run
  benchmark: backend 195 passed, AI 761 passed, frontend 47 passed.
- Frontend audit failed with 1 high-severity vulnerability: installed Vite
  version `8.3.0` and its `launch-editor` dependency chain; npm proposed
  Vite `8.3.5`. The `Frontend build` step did not finish.
- The user did not attach a fresh benchmark/video in this turn. No claim is
  made about better inference or reduced count error.

## Applied change

- Exact pin `vite=8.3.5` in `frontend/package.json`, updated Windows
  technology-version contract, added release metadata migration 0127.
- Added dependency-free five-case regression in test.ps1. Kept npm audit at
  high severity in Docker, local Windows scripts and CI.
- Existing package-lock.json is deliberately not distributed (project gitignore);
  no fabricated transitive dependency hashes.

## Validation

| Test | Verified locally | Conditions |
|---|---:|---|
| Python version/migration chain | passed | `scripts/version-contract.py` |
| New security regressions (stdlib-only) | 5 passed | `python -S -m unittest` |
| Script unittest discovery | 198 passed, 1 skipped | one native PowerShell test not runnable on Linux |
| AI service pytest | 761 passed | temporary `httpx2`->`httpx` shim outside source |
| Backend pytest | 195 passed | SQLite test DB + same local shim |
| Frontend Node tests | 47 passed | `node --test`, no third-party modules required |
| Benchmark gate pytest | 5 passed | isolated test fixtures |
| Backup worker pytest | 4 passed | isolated test fixtures |
| Python compileall | passed | backend, AI service and scripts |
| Source completeness and ZIP CRC | passed | checked after archive assembly |
| npm audit / Vite production build | **not run here** | npm registry resolution returned `EAI_AGAIN` |
| Windows Docker compose, live PostgreSQL, GPU inference | **not run here** | must verify on user's Windows host |

**Total independent test cases:** 1,210 passed and 1 skipped
(761 AI + 195 backend + 47 frontend + 198 script unittest + 5 benchmark gate
+ 4 backup worker); one test-only HTTPX compatibility shim used in AI/backend
runs and **not included** in the ZIP. Negative regression fixture output may
contain `[ERROR]`/`[FAIL]` text even when its test is marked `ok`.

Before production deployment, rerun `./scripts/test.ps1` in Windows PowerShell;
this will fetch `vite@8.3.5`, perform the official online npm high-severity audit,
and build the final frontend image. No performance or counting improvement is
claimed in this release.

---

# Verification — Traffic AI V0.5.109

## Source and customer evidence

- Source baseline: provided `traffic-ai-v0.5.108-full-source(1).zip`, 400 archive
  members. Original source files preserved; new code is additive.
- User screenshot for Benchmark #79 / Session #206 shows: 149 GT / 148 AI /
  143 timecode matches / 6 unmatched GT / 5 unmatched AI / F1 ~96.3%.
  **No #79 benchmark ZIP or continuous video was attached in this turn.**
- Provided `test.ps1` and publication log: backend 195 passed, AI 750 passed,
  frontend 47 passed, Docker builds completed and GitHub Release v0.5.108
  succeeded. The isolated logged `[ERROR]` text comes from negative unit-test
  fixtures and is followed by `ok`, not failing release steps.
- The camera RAR contains 163 frames as JPG, but not all 23,650 video frames.
- Historical #77 benchmark (not the #79 run) was re-audited: 12 cases, 23,650
  verified frames, 149 GT / 149 AI / 143 matched / 6 missed / 6 extra;
  margin/near-gate fields in this older trace were **null (unknown)**.

## Checks executed here

| Suite | Verified result | Caveat |
|---|---:|---|
| AI pytest (including 6 new pure regressions) | 756 passed | Test-only `httpx2` alias to installed `httpx`, not distributed |
| Backend pytest | 195 passed | SQLite in-memory override + test-only `httpx2` alias; not live PostgreSQL |
| JavaScript frontend Node tests | 47 passed | Did not rebuild production Vite bundle here |
| Script unittest discovery (including 4 new contracts) | 170 passed, 1 skipped | Native PowerShell case unavailable on Linux |
| Python compileall | passed | Syntax only |
| Source version / single Alembic head | passed | `0.5.109`, `0123_road_probe_v05109` |
| Real verified #77 gate audit | passed | read-only, historical V0.5.105 trace |

**Aggregate: 1,168 tests passed and 1 skipped** (independent test suites;
production inference not included). An initial local run outside the AI service
cwd failed import discovery (`app` not found), and a run without the project's
pinned `httpx2` failed collection; both are environment setup errors, not
release test failures. Five early AST-fixture regressions were corrected by
making the new per-track probe conditional; the final AI run is green.

Not verified here: original Windows `test.ps1` as a whole, live Docker/HTTPS,
PostgreSQL migration on the user volume, Vite production build, CUDA inference,
full video replay, #79 event-level comparison or any V0.5.109 F1 improvement.

The new diagnostic does not confer counting permission. A strict Road Zone count
of zero may coexist with margin-observed anchors. A margin-observed anchor is
not proof of two-sided crossing, semantic class, or independent physical identity.

---

# Verification — Traffic AI V0.5.108

## Evidence and scope

- Authoritative baseline: attached `traffic-ai-v0.5.107-full-source(1).zip`,
  385 members; SHA256 `53c8c93a7ca941e28bf736c2d061bfbee100ad54019e3922d6da0dcf95fd4c4b`.
- Benchmark #78 / Session #205: all manifest member hashes, sizes, ZIP CRC,
  certified closed trace and 23,650 frames checked. Trace runtime .107 composite
  source fingerprint `5c65884ca1cef9462f85ddac38e7cac3068d85b99360d16cd3a546562c25b46c`
  exactly matches the source bytes from the attached baseline.
- RAR has 163 camera JPEGs and Session #205 trace. Its trace hash equals the
  benchmark's certified uncompressed trace. No camera pictures are distributed.
- Actual supplied score remains 149 GT / 148 AI / 143 temporal matches /
  6 missed / 5 extra / F1 0.962963, strict matches 138. This is the user's .107
  run, not an inference result generated with .108.
- Baseline endpoint CLI reports 0 candidates on #78. Certified producer trace
  records 2 endpoint suppressions: geometric clocks 519.4182969201s and
  811.9252006786s; confirmation frames 12989 and 20301. The final cumulative
  endpoint counter is 2. Successfully suppressed proposals have no DB event,
  so a scan restricted to events cannot report these decisions.
- .108 fixes that audit omission, adds precise per-passage clock evidence and
  explicit unknown/inconsistent statuses. The historical `flagged_*` keys
  still concern persisted-event counterfactual candidates; actual runtime
  suppressions are a separate result. Runtime counting code is unchanged.
- Final #78 audit: 2 recorded suppressions, 0 remaining candidates; 89 exact
  persisted-event clock links and 1 explicitly unknown pending-producer link
  (event 14901 / track 5799 / 20.2295s). The stored event exists; unknown refers
  only to audit confirmation evidence. Its original HumanGuard-pending center
  is not replaced with a later center.
- Cargo van remains truck, and return crossings remain separate passages.
  Geometry/GT proximity alone does not authorize suppressing the moving rider
  at 812.577s or changing GT. Remaining class/count errors are not resolved by
  this reporting change. Migration 0122 updates version metadata only.

## Actual executed results

| Runnable suite | Passed |
|---|---:|
| AI pure/worker functions plus endpoint unittest | 747 |
| Backend pure functions and isolated helpers | 134 |
| Script stdlib unittest, including 24 new endpoint cases | 166 |
| Benchmark release gate functions | 5 |
| Backup worker mocked-command functions | 4 |
| Frontend Node | 47 |
| **Total (no duplicate counting of new cases)** | **1,103** |

Zero failures; 64 HTTP/ORM cases excluded by the offline harness and 1 native
PowerShell case skipped. The new 24 tests also passed under `python -S`.
Combined script discovery caught an `app` namespace collision; loading the
policy directly from its source file fixes this and the combined suite passes.
All 245 Python sources compile; 1,310 static contract checks, 817 local import
symbols, version/single-migration-head and Babel parsing of 14 frontend files
pass. All 385 original source paths, 1,097 historical Python test names and
PowerShell test functions are preserved. Static checks are not runtime tests.

## Verification approach

Actual new regression results, full source contract checks, historical test
retention and the #78 CLI output are included in `docs/verification-v05108/`.
The available environment uses Python 3.12.14 and Node.js 24.19.0; it has no
pytest, FastAPI, SQLAlchemy, HTTPX2, PowerShell, Docker or GPU inference runtime.
The broad offline harness executes real pure test functions and worker methods
(with a test-only HTTP Client placeholder, mocked by relevant dispatcher tests),
plus AST-extracted backend helpers. It is not a substitute for the complete
pytest/application suite. No compatibility shim is shipped with the source.

Not run: full Windows `scripts/test.ps1`, Docker image builds, live HTTP/ORM,
PostgreSQL migration against persistent data, npm install/production bundle,
CUDA/full-video inference, or GitHub push/release. Run the Windows commands in
README.md; the existing publish script runs tests, commits, pushes and creates
release tag v0.5.108 when invoked by the user.

---

# Verification — Traffic AI V0.5.107

- Fix: `scripts/test.ps1` no longer invokes `pytest` in the dependency-free
  `python:3.14.7-slim` endpoint regression container.
- The same three regression cases now use `unittest.TestCase`, compatible with
  both stdlib `unittest` and the existing AI `pytest` suite.
- Added `scripts/tests/test_endpoint_test_runner_v05107.py`, which verifies
  the PowerShell runner and executes endpoint tests with Python `-S`.
- No change to the detector, counting engine, endpoint policy, GT, database
  event handling or worker telemetry. Migration is release metadata only.
- Tests and checks for this build: see `docs/verification-v05107/`.
- Host PowerShell, Windows Docker Compose, persistent PostgreSQL migration,
  CUDA inference and full-video GT/F1 performance remain to be checked on
  the user's machine.

---

# Verification — Traffic AI V0.5.106

## Source and benchmark evidence
- Input source: V0.5.105 full-source ZIP (all existing files preserved).
- Input verified export: Benchmark #77 / Session #204, closed 23,650-frame trace,
  session header `ai_runtime_version=0.5.105` and source digest present.
- Read-only edge-policy audit: 2 previously unmatched candidates at 519.418s
  and 811.925s, **0 previously matched candidates**. This is not an accuracy
  result from model inference with the new version.
- Experimental worker precision condition is **enabled by default on local video**;
  can be disabled using `AI_FINITE_ENDPOINT_PRECISION_GUARD=0` in `.env`.
- Runtime session metadata contains the effective switch. Production data/GT
  and benchmark events are not changed by the audit. No full video inference
  performed in this environment.

## Actual tests executed in isolated Linux workspace
- AI pytest: **750 passed** with a test-only `httpx2` alias to installed `httpx`
  (no alias distributed; production must use pinned dependency).
- Backend pytest: **195 passed** under a test-only SQLite DB URL and HTTPX alias.
- Frontend Node: **47 passed**.
- Python script unittest discovery: **140 passed, 1 skipped** (141 total).
- New endpoint unit tests (3) included in AI suite; endpoint release checks (4)
  included in script suite.
- `scripts/version-contract.py` passed; new migration head
  `0120_endpoint_precision_v05106` is consistent. Python compileall passed.
- Benchmark #77 audit produces a JSON and Markdown candidate report without
  rewriting the input ZIP.

**Not verified:** Windows Docker builds, original PowerShell `test.ps1`, CUDA,
real model run, persistent PostgreSQL migration, live GitHub publish and
actual post-change F1. Test on the original clip and compare benchmarks before
claiming a precision improvement; rollback if Recall decreases.

---

# V0.5.105 — Verified runtime trace identity and wrong-session safety

## Supplied data / limitation
- Screenshot: Benchmark #76, Session #203, UI version V0.5.104, GT 149, AI 149, matched 143, missed 6, extra 6.
- Supplied ZIP: Benchmark #75, Session #202 (SHA256 122e055bd7ddf3380bf90df66dec3f5a2ca47352f006d5a8f2caf462f939d02e), NOT #76 / #203.
- Verified #75: 23,650 continuous trace frames, 12 mismatch cases; legacy-unattested per-track decisions. No claim is made about the trace schema of #76 because #76 was not supplied.

## Release changes
- Trace session header explicitly declares runtime version, worker/counting source SHA256 fingerprint and gate-decision schema.
- Every gate-track trace record has primary/final decision keys even when HumanGuard keeps the event pending; no accept/suppress policy changed.
- Audit supports `-ExpectedSession` and `-RequireProvenance`, and refuses a mismatch or broken declared per-track schema.
- AI Service fails startup if API runtime version and trace runtime version disagree.
- Version metadata and Alembic head `0119_trace_attest_v05105` synchronized; metadata only.

## Offline QA
- 747 AI Python tests passed (test-only `httpx2` alias to local `httpx`; no alias is shipped).
- 195 backend Python tests passed (test-only SQLite database override and `httpx2` alias).
- 136 Python script unittest tests passed, 1 skipped (PowerShell native harness unavailable).
- 47 frontend Node tests passed (host Node v22, production pin >=v26).
- 4 backup worker tests passed, 5 benchmark gate tests passed.
- Total: **1134 passed, 1 skipped** in the tested suites. New provenance suite 8/8 passed; included in script total.
- Existing benchmarking audit validates #75 and legacy status. Incorrect `ExpectedSession 203` against #75 aborts with an explicit error, no output modification.
- Version contract and Python source compilation pass. ZIP CRC and prior-source path parity verified.

## Not verified
- Full `scripts/test.ps1` on Windows PowerShell, Docker image build/run, CUDA/GPU inference, PostgreSQL migration on live database, browser production bundle and Windows publish.
- Full-video inference precision/recall/F1 gain. F1 of supplied screenshot remains 96.0%; no counter-accuracy improvement claimed.
- Photo files in newly supplied RAR appear to be tied to another session; they were not bound to wrong benchmark by matching timecode.

## Windows verification
```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
.\scripts\start.ps1
.\scripts\audit-gate-coverage.ps1 -Export ".\traffic-ai-benchmark-76-session-203.zip" -ExpectedSession 203 -OutputDirectory ".\gate-coverage-audit"
# Only for traces newly generated by V0.5.105: also add -RequireProvenance
# Once verified: .\scripts\publish.ps1
```

---

# V0.5.104 — Verification and limitations

- Base archive: V0.5.103 full source (349 files), all previous paths retained.
- Tests: **747 AI** pass (using `httpx2` -> local `httpx` test-only alias), **195 backend** pass (local SQLite override and HTTPX alias), **128 Python script** pass with **1 native PowerShell test skipped**, **47 frontend Node** pass. Total **1117 passed, 1 skipped**.
- Complete gate-coverage audit of Benchmark #75: 23650 verified frames, 12 cases (6 missed, 6 extra).
- Counter/worker per-track reasons are read-only observations; no new counting acceptance or suppression branch.
- SQLite and compatibility alias were used for isolated test execution only; neither is included in production source.
- Full Windows PowerShell + Docker test.ps1, GPU inference, PostgreSQL integration, npm dependency install and frontend production bundle were **not** run here.
- Logs in `docs/verification-v05104/`; a successful validation on the user Windows host is still required before publish.
- Migration head `0118_gate_decision_v05104` updates schema-version metadata only.

---

# V0.5.103 — Source verification and limitations

- Baseline: V0.5.102 full source ZIP, original 345 source files. All old file paths retained; 4 new source files; 349 total. Metadata bumped to V0.5.103 / Alembic `0117_gate_audit_v05103` (schema version only).
- User-provided Benchmark #74 / Session #201 and 165 camera JPGs inspected. Benchmark GT149 / AI149 / match143 / miss6 / extra6 / F1 96.0%. Exactly the same 149 event signatures as Benchmark #73 / Session #200; no measured detector improvement between these prior runs.
- New read-only verified finite-gate spatial witness audit. Source/GT/events/report unchanged. Full 23,650-frame archive verified by existing benchmark-forensics, report for 12 mismatched cases exported to JSON/CSV/Markdown. Geometry measures normalized perpendicular distance and segment projection for real observed track anchors, may report geometric sign-flip review candidates but NEVER asserts same physical identity or authorizes adding/removing counts.
- Test execution (Linux Python 3.13 / Node.js 22): AI pytest 741 passed; backend pytest 195 passed; frontend node 47 passed; script unittest 122 passed, 1 native PowerShell test skipped; backup worker 4 passed; benchmark gate 5 passed (1 intentional duplicate ZIP-name warning). Total unique suites: **1,114 passed, 1 skipped**. Version contract and `compileall` pass; 35 PowerShell scripts normalized to CRLF without BOM. Windows native script, Docker Compose, PostgreSQL migration/live transaction, npm production build and GPU/full-video inference not executed in this environment.
- The local test harness requires an HTTPX2 shim mapped to installed httpx, outside release code; backend uses SQLite in-memory override. Neither shim nor temporary environment configuration is shipped. Native compatibility must be checked with Docker on Windows.
- This release intentionally does not change counting thresholds, GT, model weights, matching tolerance or stored events. **No claim of F1 increase or reduction of the 6 missed / 6 extra events.**

On Windows: `cd D:\LienThongDH\DoAn\traffic-ai`, unblock scripts, `scripts\test.ps1`, `scripts\start.ps1`, then `scripts\audit-gate-coverage.ps1 -Export ".\traffic-ai-benchmark-74-session-201.zip"`. Once verified, `scripts\publish.ps1`. Preserve user `.env`, video, models, database and Docker volumes.

---

# V0.5.102 — Verification / limits

**Baseline** `traffic-ai-v0.5.101-full-source.zip` (341 source members). **Measured previous run** Benchmark #73 / Session #200: 149 GT, 149 AI events, 143 assigned matches, 6 unmatched GT, 6 unmatched AI, 96.0% F1. Source camera RAR extracted: 165 JPG verified readable via libarchive; report/manifest/hash/closed trace verified using the project's forensics tool, not altered.

**Offline QA actually executed (Linux sandbox, 18/10/2026):**

| Suite | Result |
|---|---:|
| AI pytest | 741 passed |
| Backend pytest with SQLite in-memory | 195 passed |
| Frontend Node built-in tests | 47 passed |
| Script unittest | 110 passed, 1 skipped (PowerShell-native) |
| Backup worker + benchmark-gate pytest | 9 passed |
| **Total (unique suites)** | **1102 passed, 1 skipped** |

- Compiled Python application, tests and scripts via `compileall`: PASS.
- `scripts/version-contract.py`: PASS; Alembic head `0116_queue_admit_v05102`.
- Source ZIP: original 341 paths preserved plus 4 new files; 345 total, ZIP CRC validated. All 34 `.ps1` files normalized to CRLF.
- Benchmark #73 read via verified `benchmark-forensics.analyze`: complete manifest+trace SHA-256 and terminal receipt summary; temporal worklist 12 cases, camera evidence matched 10/12 JPG snapshots within one second.
- `httpx2` unavailable here: AI + backend tests used a *temporary test-only* import shim to installed `httpx` 0.28.x **outside the release source**. Native dependency parity requires Windows Docker tests. Backend used SQLite in-memory; PostgreSQL schema migration/live transactions not tested.
- No Windows PowerShell, Docker Compose, Node 26 image builds, browser, YOLO model/MP4 inference or GPU replay executed. Do not claim benchmark improvements from test outcomes. Logs for local verification are provided separately with evidence ZIP.

**Changes:** transactional ordering of deferred HumanGuard event-admission state, three new regression tests, verified read-only ±2s temporal-neighbor worklist with six stdlib tests, Windows wrapper and script contract, version 0.5.102 with Alembic migration 0116. **No change** to detector, YOLO weights, GT/event history, geometry, matching, dedup policy, or saved event counts. No claim that F1 improves without a new inference run.

# V0.5.101 — Kiểm chứng sửa lỗi HumanGuard / Raw-ID Handoff

Nguồn lỗi: log người dùng chạy `scripts/test.ps1`: 6 failures cùng `AttributeError: _raw_handoff_guard_enabled` ở `app/worker.py:_commit_guard_crossing`; 729 AI tests passed và 195 backend passed ở V0.5.100.

**Sửa:** `getattr(self, "_raw_handoff_guard_enabled", False)` ở nhánh deferred commit và dời `note_passage()` sau dispatcher acceptance. Chỉ đường commit deferred thay đổi; đường direct crossing vẫn giữ nguyên. Ba tests mới (legacy `__new__`, guard-on successful submission, failed dispatcher) được thêm để chống hồi quy.

**Đã chạy trong môi trường Linux Python 3.13 / Node.js 22, ngày 18-10-2026:**

- `ai-service`: **738 passed**, bao gồm 6 ca báo lỗi và 3 regressions mới, qua `python -m pytest -q tests`.
- `backend`: **195 passed**, với biến môi trường test như `scripts/test.ps1`.
- `scripts/tests` (không tính subtests lặp): **109 passed, 1 skipped** (native PowerShell không có), 59 subtests passed.
- `frontend`: **47 passed** dùng Node 22 cho unit tests (project cần Node 26 để build/release).
- `scripts/version-contract.py`: PASS phiên bản V0.5.101, Alembic head `0115_guard_commit_v05101`.
- Tổng độc lập: **1089 passed, 1 skipped**; 68 bài chạy nhắm riêng human guard trước đó không cộng thêm lần nữa.

**Giới hạn kiểm chứng:** `httpx2==2.13.0` không cài trong container kiểm thử nên AI + backend dùng một module shim tạm thời ngoài source (`from httpx import *`, httpx 0.28.1). Shim không nằm trong ZIP. Không xác nhận full parity với HTTPX2 thực; Docker/PowerShell/Node26, PostgreSQL live, GPU/video replay vẫn phải chạy trên Windows bằng `scripts/test.ps1` và `scripts/start.ps1`. Mốc GT149 / AI150 / khớp143 / lọt6 / dư7 là kết quả phiên #199 trên phiên bản cũ; không tuyên bố đổi F1.

---

# V0.5.100 — Kiểm chứng Raw-ID Handoff Duplicate Guard

Baseline source: `traffic-ai-v0.5.99-full-source.zip` (328 member). Inputs: `traffic-ai-benchmark-72-session-199.zip`, `camera_1(20261018-111357).rar`; compare baseline `traffic-ai-benchmark-71-session-198(1).zip`. RAR chứa 166 ảnh JPG và một trace nguyên bản; ảnh trích ra bằng libarchive để rà soát, không đóng cùng source. Các file benchmark được công cụ verifier xác nhận SHA-256, source trace gzip đầy đủ 326177104 bytes, metadata/footer closed, và 23650 frame liên tiếp.

**Kết quả cũ:** hai benchmark có chữ ký 150 sự kiện DB không đổi; 143 khớp / 6 lọt / 7 dư. 4 GT chưa ghép do temporal assignment cạnh tranh, 2 GT không có event tương ứng. Có 1 raw-alias double direct crossing ở frame 12306, source time 492.2s: canonical 181574 -> 182056, raw 182056, overlap 0.7003, Δframe 7, cùng hướng OUT, điểm cắt gần. Hai phương tiện khác raw ID và gần timecode không có quyền suppression.

**Runtime thay đổi:** thêm `app/raw_handoff_guard.py`, tích hợp worker tại `resolve`/`committed`, lưu trace cùng telemetry, chỉ bật mặc định cho video source và hai bánh. Session mới không dùng GT để quyết định. Không xóa event đã lưu.

**Replay shadow đã chạy:** `scripts/audit-raw-handoff.py` kiểm tra CRC, manifest hash và gzip source hash của cả 2 benchmark; mỗi bản có 23650 frame / 167 proposals và 1 ứng viên. Công cụ này chạy trên *dữ liệu đã lưu*, không phải toàn bộ inference sau thay đổi, và không dự báo đáng tin cậy F1 của phiên mới.

**Hạn chế môi trường:** Không có `pwsh`, Docker, GPU, `httpx2`, `psycopg` để xác minh chạy Windows/Docker/GPU/HTTP đầy đủ. Đã chạy QA offline chọn lọc: AI 513 đạt / 1 loại trừ do thiếu httpx2; backend 80 đạt / 1 loại trừ do thiếu psycopg; scripts 104 đạt / 1 skip native PowerShell; frontend Node 47 đạt. Tổng cộng **744 đạt, 1 skip, 2 loại trừ**. Kiểm thử 12 ca riêng của guard nằm trong 513 bài AI, không cộng lần nữa. Đã chạy `python3 -m compileall -q ai-service/app ai-service/tests backend/app scripts` và `python3 scripts/version-contract.py` đều đạt. Windows `scripts/test.ps1` cần chạy trước khi phát hành. Cần một phiên AI mới với GT cùng clip/vạch để đo thay đổi thực sự.

---

# V0.5.99 - Verified passage evidence worklist (read-only)

Baseline ZIP: `traffic-ai-v0.5.98-full-source(1).zip`; inputs: `traffic-ai-benchmark-71-session-198(1).zip`, `camera_1(20261018-095241).rar`. Verified original export through benchmark-forensics verifier, including full compressed/uncompressed trace digests and closed delivery summary. RAR decoded locally with libarchive: 166 JPG plus a raw trace member. Original GT and event records are unchanged.

Benchmark #71 persisted outcomes: GT149 / AI150 / match143 / miss6 / extra7; four misses linked to events *already matched to a different GT* (`persisted_event_claimed_by_other_gt`), two do not contain such event links. Among extras: gap rescue 1, spatial-neighbor 1, direct/interpolated unmatched 5. 11/13 cases have JPG within 1 second; images for 392.179 s and 591.091 s were not sufficiently close in RAR. Classifier is only a review queue, not a true-identity or auto-correction rule. The new tool does not alter inference, models, dedup, scoring or database event counts. Accordingly these are baseline numbers, not improved benchmark scores after upgrading.

Added `scripts/audit-error-evidence.py` and PowerShell entrypoint. Exact source SHA and manifest validated before processing; cases fail closed on incomplete trace or mismatched totals; images sampled by 1-based frame/FPS from the verified session. Output includes per-case matched-claim relations and trace witnesses with cautious identity scope. Added `scripts/tests/test_audit_error_evidence_v0599.py` (9 offline tests), wired into `scripts/test.ps1`. Metadata version advanced .98 -> .99 and Alembic 0113. No existing counted-event, GT, backend matching or tracking logic changed.

Additional tested source: `scripts/version-contract.py` passes; 96 stdlib script tests passed, 1 native PowerShell test skipped (test_benchmark_gate uses pytest separately: 5 passed). 397 AI counting/classification/tracking/human-guard regression tests plus 32 additional AI offline tests passed; 47 Node built-in frontend tests passed (includes 4 new passage-summary tests). Total 577 passed in the selected local suites, 1 skipped; there was one expected diagnostic collection failure in a separate optional AI group because `httpx2` is unavailable; that group was rerun without the worker-dependent file and passed 32/32. Existing `test_python_cache_v0596.py` end-to-end local test was interrupted after exceeding 200 seconds; no complete native `scripts/test.ps1` pass is claimed. `compileall` of application/source scripts succeeds. Source/UI added `verifiedPassageSummary` with fail-closed scope/count checks to display the 4-versus-2 assignment distinction.

Environment limitations: local execution does not have Windows PowerShell, Docker, GPU or the training model/video input. Native `scripts/test.ps1`, production Docker build, migration against live PostgreSQL, and a full-video inference/replay are not verified in this environment. Do not claim a reduction of 6 missed / 7 extra until the user's subsequent run and report. The companion evidence results originate from the old run, not from a new inference.

---

# V0.5.98 — Kiểm chứng quyền sở hữu clock hint qua alias merge

Baseline: full source .97 SHA256 `932a350a97f92d11d0d9f6f51ab0a2db5a413b7d67ef7487819b1ac23752d4f4`, 320 file. Scope sửa đúng ba thân hàm `VerifiedAnchorSpanRescuer._store_clock_hint_if_safe`, `reconciliation_crossing_frame_for`, `merge_track`. Không đổi các thân hàm khác, signature/global/class statement của counting.py; bảy file thuật toán trọng yếu còn lại giữ nguyên bytes. Metadata active tăng .98, thêm migration/test và contract kiểm tra source.

## Input #70 và đối chiếu #69

`traffic-ai-benchmark-70-session-197.zip`: đủ bảy member an toàn, CRC tốt, sáu member dữ liệu khớp toàn bộ SHA/size manifest. Gzip được đọc tới EOF: 326.296.835 byte, SHA256 `311b137a92ea11da58383f5d6dfc95ea0a9df8ed66bc22d9ca5e9c3e8a55f7d5`, 23.650 frame liên tục. RAR ảnh và trace được đọc local, không thay file đầu vào.

149 GT tương đương trên thời gian/frame/hướng/loại/note; config giống từng byte. Cả 150 event #69 và #70 giống nhau trên time/frame/track/class/direction/method/xy/confidence: không thêm/bớt/đổi crossing. Matcher thật tính lại đúng report #70: 149 GT / 150 AI / 143 khớp / 6 lọt / 7 dư, F1 0.956522, strict match 138. Đây số liệu export người dùng, không phải inference .98.

167 proposal tương ứng 167 receipt = 150 created + 17 deduplicated. Delivery drain complete, pending/dropped 0; không có bằng chứng mất lượt do gửi backend. Raw/canonical IDs, rectangles, anchors/centers, primary/stable class và velocity của các gate frame giống #69; class_override, playback lag, lịch/refiner audit và counter phụ có khác. Không tuyên bố trace byte-exact giữa hai phiên.

Ảnh giao diện hiển thị V0.5.97; trace không ghi build/version hash để độc lập chứng minh bytes runtime. Các ca lọt/dư còn lại vẫn cần bằng chứng vật lý, không tự sửa GT hoặc loại event bằng timecode. Track 296297 có proposal IN sau handoff gap18, rồi proposal OUT tại 754.6878 s bị backend gộp `same-track-direction-flip`; trusted span clock lúc IN là None, nên không quy lỗi đó cho hint vừa sửa. Proposal và receipt chưa tự chứng minh identity vật lý của phương tiện. Các track gần miss 237/406 đi IN; miss 392 có lịch sử canonical bị gián đoạn nhưng chưa đủ chứng minh auto merge an toàn.

## Tái lập lỗi và thay đổi

Dùng chính `CountingLine` và `VerifiedAnchorSpanRescuer` thật, không inject hint giả: update track 1 tại (500,470)/frame10, (500,530)/13, (500,540)/20 với commit=False tạo hint IN 11.5 từ span kết thúc 13. Track 2 nhận OUT/frame18 qua mark_counted; merge 1→2; reconciliation cho IN/frame22 ở .97 vẫn trả 11.5 dù span cũ đã kết thúc trước lượt được nhận.

.98 yêu cầu endpoint của hint/pending span phải **lớn hơn** latest accepted passage frame. Khi merge, tính cutoff từ cả source và target, loại hint cũ ở cả hai phía rồi chọn hint hợp lệ có endpoint mới nhất; giữ ưu tiên target khi bằng endpoint. Kiểm tra tồn tại cả lúc lưu, đọc và gộp hint. Không so crossing_frame nội suy với confirmation frame vì chúng là hai clock khác nhau.

Bộ 16 regression mới có stale source/target và hai hướng merge, endpoint bằng cutoff, hint mới và cũ cùng có, pending span, hint hết hạn, alias thiếu state, self-merge lặp, mismatch hướng không tiêu thụ hint, truy vấn không nhận count/tăng rescue telemetry và lượt IN thật sau khi loại hint cũ vẫn đếm được. Case dương bắt buộc endpoint 13 sau xác nhận 12 vẫn trả geometric clock 11.5. Bản cũ chạy thật **12 đạt / 4 lỗi**; bản .98 **16 đạt / 0 lỗi**. Các 16 ca này đã nằm trong tổng test bên dưới, không cộng lại. Proof độc lập bốn ca ban đầu có 1 lỗi baseline → 0 lỗi .98 và không được cộng vào test sản phẩm.

## QA thực thi

| Nhóm | Đạt |
|---|---:|
| AI offline / worker helpers | 720 |
| Backend offline | 135 |
| Scripts stdlib unittest | 95 |
| Benchmark-gate standalone | 5 |
| Backup-worker standalone | 4 |
| Node built-in | 43 |
| Tổng | 1002 |

0 lỗi. Giữ nguyên 1007 identities/thân AST Python lịch sử; thêm 16 thành 1023 definitions. Bảy file Node cũ/43 tests byte-exact; 79 thân hàm Assert lịch sử không đổi. 63 test HTTP/ORM chưa thực thi là đúng danh sách cũ (3 AI, 60 backend); 1 native PowerShell runner skip riêng vì không có pwsh, không tính là đạt. Baseline .97 có 986 test được chạy lại riêng, không cộng vào 1002.

322 file source, 216 Python parse/compile, 31 PowerShell UTF-8 CRLF không BOM; text khác LF. 797 internal imports, 1101 literal PowerShell predicates, 121 cặp UI/runtime; Babel 20 JS/JSX và 47 relative import/export symbols. 320 code/config hashes đóng băng; hai tài liệu được duyệt độc lập trước archive audit. Toàn bộ 320 đường dẫn baseline được giữ.

38 release checks đạt: 17 thực thi Git/artifact cục bộ, 14 static, 4 simulation, 3 Bash syntax. Không push GitHub hoặc tạo Release thật. Replay matcher .97/.98 trên cùng input #70 cho full output giống nhau, input không đổi; đây replay matcher dữ liệu đã lưu, không phải chạy lại counter/model toàn pipeline.

Runtime sẵn có Python 3.12.14 / Node 24.19.0, khác pin Python 3.14.7 / Node >=26.10.0 / npm12.2.0. Không cài thêm dependency. Chưa thực thi native PowerShell/Docker .98, full pytest HTTP/ORM, PostgreSQL/migration live, npm install/audit/Vite production build, browser hoặc GPU/full-video inference. Không chứng minh mức giảm lọt/dư hay F1 .98 từ các phép kiểm này. Cache test .96 tiếp tục tách khỏi source với 20 lệnh Docker Python; ZIP dùng UTC build timestamp mới và kiểm các Python member đổi bytes không trùng timestamp baseline.

## Chạy trên máy người dùng

Giữ .env/.git/models/video/snapshots/volumes/data khi chép source. Migration metadata `0112_clock_owner_v0598` parent `0111_count_review_v0597`, chỉ nâng schema_version .98 / downgrade .97. Không tạo lại Admin.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.98 và Release
.\scripts\publish.ps1
```

Để đo .98: chạy AI một lần, tạo benchmark cho phiên mới rồi sao chép GT #70 nếu cùng clip/vạch. Các phần dưới là lịch sử, không phải các phép chạy .98 mới.

---

# V0.5.97 — Kiểm chứng rà soát hình học và đổi raw ID

Baseline là ZIP .96 SHA256 `bb4609315117077df430f2382a126abf57fd6365e138369b2b106b6e4256ed27`, 313 file. V0.5.97 thêm bằng chứng đọc từ trace và giao diện xem video trước/sau; không đổi thuật toán detector, tracking, counting, class policy, Human Guard, rescuer, dedup, matcher hoặc GT.

## Input và đối chiếu benchmark thực tế

Input mới: `traffic-ai-benchmark-69-session-196.zip`, SHA256 `871887eb3326d48c7949f3aa643dded85f26dddf498b0fd9a4a8d1b9a43c5c55`. Bảy member an toàn/CRC tốt; sáu member dữ liệu khớp toàn bộ SHA/size trong manifest, gzip đọc đến EOF. Trace có 23.650 frame liên tục, source time 0..945.96 s ở 25 fps. Bytes trace từ RAR giống gzip export sau giải nén.

167 proposal = 166 committed_before_submit + 1 submitted_after_guard. Có 167 delivery receipt, 150 created + 17 deduplicated; 150 created tương ứng đủ tập event DB, mọi source field khớp. Drain complete, pending/dropped 0, mỗi acknowledgement một lần thử. Không có bằng chứng mất lượt do gửi backend.

Đối chiếu đủ cả export #68/195 và #69/196: 149 GT tương đương theo thời gian/frame/hướng/loại/note; config byte-exact. 149 AI event cũ giữ nguyên source time/frame/direction/class/track/method/xy/confidence. Thêm duy nhất motorcycle IN 143399 tại 397.0209 s khớp GT 397.288 s. Matcher source thật tái tạo cả hai report: matched 142→143, lọt 7→6, dư 7→7; F1 0.953020→0.956522; strict match 137→138. Không có GT lọt mới hoặc FP mới trong phép đối chiếu này.

6 GT chưa ghép: 59.446 IN, 237.042 OUT, 289.824 IN, 392.179 OUT, 406.488 OUT, 591.091 IN bicycle. 7 event chưa ghép: 15369 OUT 54.296, 110284 OUT 292.864, 181574 OUT 491.920, 191795 OUT 519.418, 368014 OUT 808.000, 345897 OUT 811.925, 286434 truck IN 882.290. Gần thời gian không chứng minh cùng phương tiện.

## Bằng chứng ảnh và lựa chọn triển khai

Ảnh frame 12299/12306 cho thấy một xe máy với hai box 181574/182056; hai track cùng hiện ở 5 frame được giữ trong fixture. Trước crossing thứ hai chỉ có hai quan sát cặp; vận tốc lọc cosine khoảng 0.989 nhưng dịch chuyển tâm box thực giữa hai frame cosine khoảng 0.717. Predicate thử nghiệm có thể chọn đúng cặp này trên clip nhưng cũng nhận một convoy bị che trong phản ví dụ hình học. Vì vậy .97 chỉ đưa ra bằng chứng rà soát, không bật rule suppression theo cặp này. Audit dùng quan sát cả trước/sau trong cửa sổ; không phải cơ chế chống trùng chạy nhân quả tại thời điểm event.

Track 296297 đổi raw 312739→331821 từ frame 18842→18860, gap 18 frame và tâm box dịch khoảng 236 px. Token mới sau đó đi lên nhưng crossing rescue đã ghi IN. Frame đầu token mới thiếu motion riêng; không mở rộng/nới ngưỡng alias guard chỉ từ một mẫu.

Ảnh frame 7243: người dắt xe đạp và xe máy track 25767 là hai đối tượng riêng; không đổi track xe máy để khớp nhãn GT bicycle. Frame 13355 có hỗ trợ bicycle từ general refiner nhưng không đủ hai nguồn theo policy hiện tại. Ảnh frame 16050 là van chở hàng phù hợp truck; ảnh frame 22059 cho thấy van cắt vạch IN thật. Không tự đổi GT hoặc loại event van. Tại 591.091 s thiếu track/proposal ở vạch và không có ảnh đúng thời điểm/raw detections, nên chưa chứng minh tầng nào gây lọt; road-zone reason là heuristic toàn frame.

## Tích hợp và giới hạn bằng chứng

`ObservedTrackAudit` đọc cùng các cửa sổ trace đang được chẩn đoán; không chạy thêm model hoặc quét trace riêng. Giới hạn mỗi cửa sổ: 256 frame, 64 track/frame, 16 peer lưu, 4 peer trả ra, 8 lần đổi raw ID; có cờ truncated. Độ phủ là intersection/diện tích box nhỏ; bottom alignment là chênh mép dưới/chiều cao box lớn. Đây là phép đo, không phải xác nhận identity. `max_consecutive_frames` là số frame đồng xuất hiện liên tiếp, không phải số lần nested liên tiếp.

Backend bổ sung target dư và sai hướng bằng time/track của event DB, chiếu lại đúng canonical owner và giới hạn trường số. Frontend từ chối scope/owner/schema sai, số không hữu hạn và identity claim; phân biệt actual box displacement và filtered velocity. Seek controls nằm ngoài nút timecode. Trace cũ thiếu rect/raw/velocity được xử lý như thiếu bằng chứng.

## Kiểm thử .97

| Nhóm thực thi | Đạt |
|---|---:|
| AI offline / worker helpers | 704 |
| Backend offline | 135 |
| Scripts stdlib unittest | 95 |
| Benchmark-gate standalone | 5 |
| Backup-worker standalone | 4 |
| Node built-in tests | 43 |
| Tổng | 986 |

Không có lỗi. Thêm 21 Python và 10 Node tests; giữ nguyên 986 test identities/thân AST Python lịch sử, cả 6 file Node cũ/33 tests và 79 thân hàm Assert lịch sử. Tổng định nghĩa Python hiện tại 1007; đây là số definitions, không phải số test thực thi.

63 HTTP/ORM tests chưa thực thi vẫn đúng danh sách cũ (3 AI, 60 backend). 1 native PowerShell runner skip riêng vì thiếu pwsh, không tính là đạt. Các regression mới gồm fixture thật 181574/182056 và 296297, box/time/owner sai, clock lặp/đảo/xung đột, số không hữu hạn, giới hạn bộ nhớ, peer truncation và projection backend; UI tests giữ actual displacement khác filtered velocity và kiểm tra không sửa input/score.

320 source file; 214 Python parse/compile; 31 PowerShell UTF-8/CRLF không BOM; text khác LF. Đã kiểm 795 internal imports, 1096 literal PowerShell source predicates và 121 cặp UI/runtime. Babel parse 20 JS/JSX và 47 relative import/export symbols. 38 release checks: 17 thực thi Git/artifact cục bộ, 14 static, 4 simulation, 3 Bash syntax; không push GitHub hoặc tạo Release thật.

Replay matcher thật của .96 và .97 trên cùng GT/events cho output giống nhau hoàn toàn và khớp report #69, input không đổi. Replay diagnose_trace thật trên trace 326.237.314 byte, 18 target (6 lọt, 3 sai loại, 7 dư, 2 sai hướng), cửa sổ ±0.75 s: .97 khoảng 4.489 s, peak RSS 21.632 KiB tại đây. Chỉ bỏ field observed_track_audit mới thì toàn bộ diagnosis cũ giống .96. Đây là một lần đo cục bộ, không tuyên bố tăng tốc hoặc bảo đảm timeout trên mọi máy.

Trong cửa sổ mặc định của FP 491.92 s, thực tế trả 4 frame cặp với peer 182056 (12305..12316), không phải toàn bộ 5 frame có trong fixture; cửa sổ kết thúc trước frame 12318. Có 2 frame đồng xuất hiện liên tiếp, sau đó có gap 9 frame. Độ phủ 0.937083..0.999671; target còn có raw handoff 181574→182056 rồi quay lại. Ca sai hướng 296297 trả đúng handoff gap18, tâm box dịch [-56.7605,229.6465] px. Các bằng chứng đã được chiếu lại qua backend và kiểm tra bởi frontend view model.

Môi trường hiện tại Python 3.12.14 / Node 24.19.0, khác runtime pin Python 3.14.7 / Node >=26.10.0 / npm12.2.0. Chưa chạy .97 native PowerShell/Docker, full pytest HTTP/ORM, PostgreSQL/migration live, npm install/audit/Vite production build, trình duyệt hoặc GPU/full-video inference. Không cài thêm dependency. 955 test của .96 được chạy lại làm baseline và ghi riêng, không cộng vào 986. F1 95.6522% thuộc export phiên 196 do bạn gửi; ảnh giao diện hiển thị .96 nhưng trace không có version/build hash để độc lập xác minh bytes runtime. Không suy ra F1 .97 hoặc số lượt lọt/dư sau inference mới.

## Sử dụng

Giữ .env/.git/models/video/snapshots/volumes khi chép source. Cache test vẫn tách khỏi source như .96; ZIP dùng timestamp UTC build mới và kiểm tránh trùng timestamp cũ của Python member đổi bytes. Migration metadata `0111_count_review_v0597`, parent `0110_pycache_v0596`, chỉ nâng schema_version .97 / downgrade .96.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.97 và Release
.\scripts\publish.ps1
```

Chọn benchmark #69 rồi Đối chiếu lại để đọc bằng chứng từ trace hiện có. Không tạo lại Admin. Các mục dưới đây là lịch sử, không phải các phép chạy .97 mới.

---

# V0.5.96 — Kiểm chứng sửa Python bytecode cache

Baseline là full source .95, SHA256 `0966e3d02e908b7ee11cb5936afda3a75ad46cf20e436e5edbc49b998ec9dd4d`, 311 file. Bản .96 sửa môi trường chạy test và cách đóng gói. Không sửa predicate HumanGuard, tracking, counter, worker, rescuer, dedup, matcher hoặc GT.

## Log mới do người dùng cung cấp

File `Văn bản đã dán (1)(20261017-124555).txt` có hai lần chạy .95. Mỗi lần đều qua static version contract `0.5.95`, migration `0109_docker_guard_v0595`, host Docker readiness **26 assertions** và các bước Docker trước backend tests.

Backend pytest mỗi lần: **186 passed / 3 failed**, lần lượt 8.18 s và 8.63 s. Ba lỗi là `test_root_metadata`, `test_backend_version_metadata`, `test_v0533_version`: app trả .94 trong khi VERSION đọc từ source là .95. Hai lần lặp cùng scenario không được cộng thành 52 native tests hoặc 372 backend tests mới. Đây là bằng chứng người dùng chạy Windows/Docker .95, không phải .96 tại môi trường này. Lỗi `[ERROR]`/`[FAIL]` trong các test âm về replay trước đó là output dự kiến và các test đó vẫn `ok`.

## Tái lập nguyên nhân bằng source đã gửi

Lấy chính `backend/app/main.py` từ ZIP .94 và .95: mỗi file 1181 byte, khác version; cả hai có ZIP timestamp `2026-10-17 00:00:00`. Tạo `.pyc` timestamp-based bằng CPython rồi chép bytes .95 lên cùng mtime/kích thước. Tiến trình Python riêng dùng SourceFileLoader thật nhận code constants .94, mặc dù source đọc trực tiếp có .95.

| Cách đọc source sau overlay | Kết quả tái lập |
|---|---|
| Cache mặc định | Còn code .94 |
| `-B` | Còn code .94 |
| Chỉ `PYTHONDONTWRITEBYTECODE=1` | Còn code .94 |
| `PYTHONPYCACHEPREFIX` mới | Code .95 |

Reproducer không thực thi FastAPI hoặc gọi HTTP endpoint: nó kiểm đúng bytecode mà loader import sẽ nhận. Vì vậy không gọi đây là chạy lại ba backend HTTP test trong môi trường hiện tại. Bằng chứng dùng artifact thật và cơ chế CPython thật phù hợp trực tiếp với lỗi version trong log; không sửa expected version để làm test đạt.

8 regression mới gồm subprocess import thật, no-write flags, prefix mới, prefix cũ bị tái dùng, compileall với prefix riêng và coverage các Docker Python calls. Bộ kiểm tra chạy trên Python 3.12.14 tại đây; log Windows dùng Docker Python pin 3.14.7. Chưa chạy lại container 3.14.7 .96 ở môi trường này.

## Thay đổi và rà soát cache

19 lệnh Docker Python cũ giữ nguyên command text khi bỏ hai env flags mới; thêm một bước regression, tổng 20 lệnh đều có prefix `/tmp/traffic-ai-test-pycache` và no-write env. Prefix nằm ngoài `/src` bind mount, không có volume gắn vào nó, và thuộc container `--rm` mới. Việc tái sử dụng một prefix đã chứa cache cũ vẫn có thể gây stale import; regression bao phủ điều đó, nên thiết kế dựa vào cache filesystem mới của từng container chứ không coi prefix string tự nó luôn mới.

`compileall` chủ động tạo bytecode kể cả khi bật no-write, nhưng khi có prefix thì output ở `/tmp` của container. `.dockerignore` không áp dụng cho bind mount khi chạy test; nó bảo vệ build context riêng. Backend/AI được bổ sung `**/__pycache__`, `**/*.pyc`, `**/*.pyo`, giữ các rule cũ. Docker hỗ trợ `**` cho mọi độ sâu; tham khảo [tài liệu build context chính thức](https://docs.docker.com/build/concepts/context/). Chưa gọi Docker build/matcher thực tế tại đây, không dùng Python glob giả làm Docker để tuyên bố đã build.

Node Docker command byte-exact .95. Docker readiness helper, native harness, start.ps1 và toàn bộ thuật toán AI giữ nguyên .95; chỉ metadata version trong app main/backup đổi .96. Không xóa cache/source/data trên máy người dùng, không đổi cache Docker toàn hệ thống hoặc đặt env host lâu dài.

Cách đóng ZIP chuyển từ mốc 00:00 cố định sang UTC build timestamp (độ phân giải DOS 2 giây), có kiểm tra tránh trùng timestamp của các Python member đã thay đổi so với .95. Audit ZIP yêu cầu mtime mới cho từng Python member cũ có bytes đổi. Cache isolation vẫn cần thiết và không phụ thuộc timestamp archive.

## Kiểm thử .96 thực thi tại đây

| Nhóm | Đạt |
|---|---:|
| AI offline / worker helpers | 689 |
| Backend offline | 129 |
| Scripts stdlib unittest | 95 |
| Benchmark-gate standalone | 5 |
| Backup-worker standalone | 4 |
| Node built-in tests | 33 |
| Tổng | 955 |

63 HTTP/ORM test chưa thực thi vẫn đúng danh sách lịch sử (3 AI, 60 backend). 1 conditional native PowerShell runner mới từ .95 tiếp tục bỏ qua vì thiếu pwsh tại đây; bằng chứng 26 assertions Windows đã đạt nằm trong log người dùng .95 và được ghi riêng. Không cộng native assertions hoặc các phép tái lập bổ sung vào 955.

978 Python test identities/thân AST cũ và cả 6 Node test file cũ (33 tests) giữ nguyên byte/AST tương ứng. Thêm 8 Python regression, tổng 986 definitions. Toàn bộ 79 thân hàm Assert lịch sử giữ nguyên. Không nới test hoặc sửa expected version; test metadata tiếp tục so với VERSION hiện hành.

313 source file; 210 Python parse/compile; 31 PowerShell UTF-8/CRLF không BOM, text khác LF. 790 internal imports, 1090 literal PowerShell source predicates, 121 cặp UI/runtime; Babel 18 JS/JSX / 45 import-export symbols. 311 code/config hashes đóng băng, README/VERIFICATION được duyệt riêng trước archive audit. Source retains đủ 311 baseline paths, chỉ thêm test và migration.

38 release checks đạt: 17 Git/artifact cục bộ thực thi, 14 static, 4 simulation, 3 Bash syntax. Không push GitHub hoặc tạo Release thật.

## Giới hạn và sử dụng

Chưa thực thi .96 native PowerShell/Docker, full pytest HTTP/ORM, PostgreSQL/migration live, pinned npm install/audit/Vite build, browser hoặc GPU/full-video inference. Python 3.12.14 và Node 24.19.0 có sẵn; môi trường thiếu pytest/FastAPI/SQLAlchemy/Alembic/httpx/httpx2/cv2/Torch/pwsh/Docker. Các kết quả runtime khác ở phần lịch sử không được coi là phép chạy .96 mới.

Benchmark #68/session 195 (bản .94) vẫn là kết quả gần nhất: 149 GT / 149 AI / 142 khớp / 7 lọt / 7 dư, F1 95.302%. .96 không thay thuật toán nên không tạo hoặc suy ra F1 mới. Bản .95 khôi phục rider cần đánh giá bằng lần inference mới sau khi quy trình test chạy thông suốt.

Migration metadata `0110_pycache_v0596`, parent `0109_docker_guard_v0595`, chỉ đổi schema_version .96 / downgrade .95; không sửa GT/events. Giữ .env/.git/models/video/volumes khi chép source.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.96 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl+F5. Không tạo lại Admin. Các mục sau là lịch sử giữ nguyên byte.

---

# V0.5.95 — HumanGuard recovery và Docker Linux preflight

Full source tiếp tục đúng ZIP V0.5.94, SHA256 `f3cb76c0dd1562273dec2fa1601d9299eaf26f9b8fd55300aaeac6236640dfe7`, 305 file. Đã thực thi **947 kiểm thử offline/Node, 0 lỗi**; PowerShell native và Docker không có trong môi trường này.

## Kết quả kiểm tra source

| Nhóm thực thi | Đạt |
|---|---:|
| AI offline / worker helpers thực tế | 689 |
| Backend offline | 129 |
| Scripts stdlib unittest | 87 |
| Benchmark-gate standalone | 5 |
| Backup-worker standalone | 4 |
| Node built-in tests | 33 |
| Tổng | 947 |

63 test HTTP/ORM chưa thực thi là đúng danh sách lịch sử (3 AI, 60 backend). Có **1 test mới bỏ qua riêng** vì thiếu `pwsh`: runner của harness PowerShell native. Không gộp trường hợp này vào danh sách loại trừ HTTP/ORM. 8 kiểm tra Python của Docker chỉ xác minh source contract; các kiểm tra subprocess/timeout/chính sách daemon thực tế bằng PowerShell chưa được chạy tại đây. Chúng được tích hợp chạy trên host Windows trước preflight và test đầu tiên cần Docker.

Giữ nguyên toàn bộ 964 Python test identities/thân AST cũ, cả 6 file Node test cũ (33 tests), 79 thân hàm Assert lịch sử. Thêm 5 AI test và 9 Python scripts test definitions, tổng 978 definitions; trong 9 mới có 8 static contract đạt và 1 native runner chưa chạy. Các test cũ không bị sửa hoặc bỏ để làm bản mới đạt.

311 source file, 208 Python parse/compile hợp lệ, 31 PowerShell UTF-8/CRLF không BOM, text khác LF. Đã đối chiếu 790 internal imports, 1087 literal PowerShell source predicates và 121 cặp trường UI/runtime. Babel parse 18 JS/JSX / 45 import-export symbols; frontend ngoài version không đổi. 309 code/config/fixture hashes đóng băng; README/VERIFICATION review riêng, sau đó kiểm CRC/đường dẫn/byte equality của ZIP.

38 kiểm tra release giữ kết quả đạt: 17 Git/artifact cục bộ thực thi, 14 static, 4 mô phỏng, 3 Bash syntax. Không push GitHub/tạo Release thật. Kiểm tra độc lập HumanGuard trên 35.280 tổ hợp box/ý kiến hợp lệ xác nhận thay đổi chỉ thuộc nhánh direct-positive geometry-neutral; các precondition và 10.080 trường hợp PERSON chiếm ưu thế hình học giữ kết quả cũ. Đây là kiểm tra bổ sung, không cộng vào 947.

## Input #68 / session 195 chạy V0.5.94

ZIP bảy member an toàn, CRC và toàn bộ manifest bytes/SHA hợp lệ; gzip được đọc đến EOF. Trace JSONL từ RAR giống tuyệt đối trace giải nén: 325.953.712 byte, SHA256 `1bbc7b8789aece8a57ca94ac02fb7c0a8c83b66380ae4449b12a28d72981fa87`. Có 23.650 frame liên tục; RAR gồm 165 ảnh và một trace session 195.

166 proposal = 28 direct + 95 interpolated + 43 rescued. 166 terminal receipt có source fields khớp toàn bộ, 149 created khớp tập DB events + 17 deduplicated; delivery drain complete, pending/dropped 0. Không có bằng chứng mất event khi gửi backend. 149 GT nội dung/thứ tự clone và config byte-exact so với session 194, giữ đủ các mark cùng semantic.

Matcher thực tế tái tạo mọi base/matched/missed/false-positive field của cả hai báo cáo:

| Chỉ số | #67 / 194 | #68 / 195 |
|---|---:|---:|
| GT / AI | 149 / 151 | 149 / 149 |
| Khớp / Lọt / Dư | 140 / 9 / 11 | 142 / 7 / 7 |
| Recall | 93,9597% | 95,3020% |
| Precision | 92,7152% | 95,3020% |
| F1 | 93,3333% | 95,3020% |
| Đúng class / đúng hướng | 137 / 138 | 139 / 140 |
| Đúng cả time/class/direction | 135 | 137 |

Hết lọt tại GT OUT 525.21028 s → AI 525.3925 s (194513) và GT IN 816.964611 s → AI 816.9225 s (345897). Không có GT lọt mới. Ba mark sai loại giữ nguyên. Hướng startup 0.16 s được sửa, có sai hướng mới tại GT OUT 754.558486 s → AI IN 754.045 s (296297); không tuyên bố không có regression.

FP 491.92 s của 181574 vốn đã tồn tại và khớp ở 194; 195 có proposal/event 182056 OUT 492.2 s gần GT hơn nên matcher đổi ownership, event cũ trở thành unmatched. Chưa chứng minh cùng phương tiện nên không thêm dedup tùy tiện. 345897 vẫn có OUT unmatched 811.925 s dù IN thật 816.9225 s đã được khôi phục. Tổng AI bằng GT không có nghĩa là hết lọt/dư.

Refiner checks 2195 → 1419 và HumanGuard rejections 37 → 38; config/model path không chứng minh cùng weights/model availability/toàn bộ runtime. Điểm 95,302% thuộc lần chạy .94 được gửi, **không phải điểm .95 và không suy ra mọi thay đổi do một fix**.

## Sửa HumanGuard có bằng chứng

Track 143399 bị rejected từ frame 9806. Frame 9822 có direct vehicle 0.700684 / PERSON 0.672363, IoU 0.357267 / coverage 0.463132; PERSON không đủ ưu thế hình học. Hàm .94 trả neutral sớm nên bỏ mất direct evidence, policy giữ rejected. Các candidate frame 9929 (source 397.020933 s) và 9938 (397.374 s) tiếp tục bị chặn; GT quanh 397.288 s vẫn lọt.

.95 đưa comparator **direct_competitive hiện có** lên trước nhánh geometry-neutral, chỉ nhánh này được trả rider_evidence khi direct >= max(0.20, person - confidence_margin - 0.03), cả person/direct trong [0,1]. Không đổi ngưỡng. NaN, ±Inf, âm hoặc >1 không khôi phục ở nhánh mới. Nhánh PERSON chiếm ưu thế hình học, thiếu PERSON, box không giống người, class ngoài hai bánh giữ cách xử lý cũ. Nearby vehicle hoặc motion đơn lẻ vẫn neutral trong nhánh mới; không dùng confidence primary/periodic khác nguồn thay cho crop verifier.

`HumanGuardTrackPolicy`, tracking, counting, toàn bộ rescuer, worker và backend dedup byte-exact .94. Chỉ app/main.py đổi version; human_guard.py là thay đổi AI thuật toán duy nhất. Guard audit schema/caching/stride và số lần inference giữ nguyên.

Fixture 32.425 byte SHA256 `4ed6eddc58b048361108a7331c4b7382773df8dc8486f130532b64dfef8ed5ec` chứa 26 quan sát fresh đã ghi. Kiểm tra predicate/policy/cache thực tế tái tạo đầy đủ mọi decision/action/status .94 trong fixture rồi so với .95: rejected 9806 → released 9822; vẫn có pending 9880 khi có ý kiến bất lợi, rider 9896 và tại candidate 9929/9938. Force cùng frame không gọi verifier lần hai và không tạo thêm strike. Các test bao gồm nearby/motion không đủ, người đi bộ mạnh vẫn cần các frame riêng biệt, precondition cũ và score lỗi.

Trace không có PERSON rectangle/width-ratio; fixture chủ động đưa IoU/coverage đã ghi vào phép kiểm tra, không giả vờ đã tái tạo crop hoặc inference model. Reproducer không chạy lại detector/tracker/guard models, dispatcher/deferred crossing/counter/backend transaction toàn pipeline. Phân tích guard diện rộng còn dữ liệu hình học không tái dựng được nên chỉ là thăm dò; không dùng số lượng track giả định giải phóng làm hiệu quả. **Chưa có F1 .95 hoặc bằng chứng 7 lượt lọt giảm còn bao nhiêu.**

## Docker engine và log Windows

Log .94 cho thấy static contracts đã chạy nhưng lệnh Docker đầu tiên báo pipe `dockerDesktopLinuxEngine` không tồn tại; start sau đó query volume thất bại rồi hiểu nhầm là cần tạo volume. Chưa có bằng chứng volume PostgreSQL hỏng hoặc cần xóa.

Shared `scripts/docker-engine.ps1` chỉ định nghĩa functions khi import. Probe gọi Docker executable qua ProcessStartInfo.ArgumentList, không qua shell, không phụ thuộc $LASTEXITCODE. Đọc stdout/stderr đồng thời; WaitForExit và chờ drain chia chung deadline, timeout dừng process probe và Dispose. Không in stderr/endpoint chứa dữ liệu nhạy cảm.

Engine Linux khỏe được chấp nhận ngay, bao gồm remote/custom context, không ngủ cố định và không lookup context thêm. Khi chưa khỏe, auto mở Desktop chỉ trên Windows + context desktop-linux + endpoint npipe dockerDesktopLinuxEngine đã xác minh. Mở một lần nếu chưa có tiến trình Desktop; nếu đã mở chỉ chờ. Tổng chờ engine cấu hình mặc định 120 giây, mỗi probe tối đa 5 giây theo phần thời gian còn lại. Docker CLI chưa có, Windows engine, remote/custom chưa sẵn sàng hoặc timeout sẽ dừng có hướng dẫn; không tự sửa context/service/WSL hoặc xóa volume.

start.ps1 gọi preflight trước .env/secret/certificate/volume; kiểm LASTEXITCODE của volume ls trước khi quyết định tạo volume. test.ps1 chạy harness host độc lập daemon trước preflight và trước Docker-dependent step đầu tiên. Python source contracts kiểm thứ tự/timeout/dữ liệu; native harness có subprocess thật, stdout+stderr lớn, nonzero exit, hung process và chính sách mocked endpoint/launch/deadline. Các mock nằm trong child script scope, env được khôi phục; **native harness chưa thực thi tại đây vì không có pwsh**.

Toàn bộ dòng lịch sử start/test được giữ nguyên theo thứ tự, chỉ chèn preflight, volume-error check, test invocation và contract .95. User chưa cung cấp log chạy .95, vì vậy không nói Docker Desktop đã được mở hoặc hệ thống Windows của bạn đã sửa xong từ xa.

## Môi trường và lệnh sử dụng

Python 3.12.14 / Node 24.19.0 hiện có; chưa có pytest/FastAPI/SQLAlchemy/Alembic/httpx/httpx2/cv2/Torch/PowerShell/Docker. Không chạy HTTP/ORM/PostgreSQL migration live, pinned npm install/audit/Vite build, browser/React DOM hay GPU/full-video .95. Dependencies pin và các feature/UI cũ giữ nguyên.

Migration `0109_docker_guard_v0595`, parent `0108_guard_audit_v0594`, chỉ đồng bộ schema_version .95/downgrade .94, không sửa GT/events. Không tạo lại Admin, không publish GitHub thật.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.95 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl+F5. Giữ .env/.git/models/video/volumes khi cập nhật source; chạy lại cùng clip/vạch/model, chép GT đã review rồi xuất benchmark ZIP mới sau khi có GT. Các phần dưới là lịch sử kiểm chứng .94 và các bản trước được giữ nguyên byte.

---

# V0.5.94 — Kiểm chứng ổn định điểm neo và Human Guard audit

Bản này tiếp tục đúng ZIP full source .93 có SHA256 `a682bac12333683a5c8dec2f563c27c3989e73b0abee19c52a7ae4945d6b0f36`, 300 file. Đã thực thi **934 kiểm thử sản phẩm, 0 lỗi**, bằng harness offline/hàm thực tế và Node; không gọi đây là một lần chạy pytest/Docker/PowerShell đầy đủ.

## Kiểm tra source và hồi quy

| Nhóm thực thi | Đạt |
|---|---:|
| AI offline: module và worker helpers thực tế | 684 |
| Backend offline: pure functions/helpers thực tế | 129 |
| Scripts stdlib unittest | 79 |
| Benchmark-gate standalone | 5 |
| Backup-worker standalone | 4 |
| Node built-in tests | 33 |
| Tổng | 934 |

Giữ nguyên danh tính và thân AST của **943 Python test cũ**, cùng cả 5 file Node test cũ (30 tests) byte-exact. Thêm 7 tracking test, 14 HumanGuard test và 3 Node test. Tổng Python test definitions là 964; 63 test HTTP/ORM chưa thực thi vẫn đúng danh sách cũ (3 AI, 60 backend), không thêm trường hợp bỏ qua. Không dùng kết quả pytest lịch sử ở phần dưới làm kết quả môi trường này.

305 source file, 205 Python parse/compile hợp lệ; 29 PowerShell UTF-8 không BOM/CRLF, text còn lại LF. 786 internal-import symbols, 1081 literal PowerShell source predicates, 79 thân hàm Assert lịch sử giữ nguyên, 121 cặp trường UI/runtime được đối chiếu. Babel parse 18 JS/JSX và xác minh 45 import/export symbols. 303 code/config/data-fixture hashes đã đóng băng; README và tài liệu này được review riêng trước khi audit ZIP.

38 kiểm tra release: 17 thực thi Git/artifact cục bộ, 14 static, 4 mô phỏng lựa chọn và 3 Bash syntax; không push GitHub hay tạo Release thật. Thêm 4 kiểm tra render component HumanGuard bằng Babel/VM: trace cũ, identity đã ghép, tuổi cache/hình học chưa biết, scope lân cận/truncation và thiếu ý kiến model. Các kiểm tra bổ sung này không cộng vào 934.

## Bằng chứng input #67 / session 194

ZIP mới: CRC, đường dẫn và toàn bộ payload SHA/byte lengths hợp lệ; gzip đọc hết EOF, dữ liệu giải nén giống tuyệt đối trace trong RAR. Trace 197.761.000 byte, SHA256 `c20b45db45090dd34a42988747971154334e38f8246a9ce07a77c96e4faa6e8a`; 23.650 frame liên tục, 271.208 Gate-track observations. RAR 191 member an toàn: 190 ảnh và đúng một trace session 194.

191 proposal = 191 terminal receipt, đối chiếu đủ các source fields. 151 created khớp 151 DB events; 40 deduplicated, drain hoàn tất, pending/dropped bằng 0. Không có bằng chứng event bị mất ở bước gửi backend.

Matcher thực tế tái tạo đúng mọi base/matched/missed/false-positive field của cả hai báo cáo:

| Chỉ số | #66 / 193 | #67 / 194 |
|---|---:|---:|
| GT / AI | 149 / 150 | 149 / 151 |
| Khớp / Lọt / Dư | 138 / 11 / 12 | 140 / 9 / 11 |
| Recall | 92,6174% | 93,9597% |
| Precision | 92,0000% | 92,7152% |
| F1 | 92,3077% | 93,3333% |
| Đúng class / đúng hướng | 136 / 136 | 137 / 138 |
| Đúng cả time/class/direction | 134 | 135 |

149 GT semantic và thứ tự giống nhau, có hai cặp trùng semantic vẫn giữ đủ multiplicity; không tự xóa vì có thể hai xe cùng frame. Config byte-exact. Khớp thêm GT 534.086505 s (AI motorcycle 533.9503 s, GT bicycle) và 640.140782 s (AI 639.7107 s); hết FP 638.12 s, không có miss/FP signature mới. Class mismatch từ 2 lên 3 vì xe đạp vừa được khớp còn sai loại; không phải một xe trước đúng bị đổi sai. Chưa chứng minh weights/model availability và toàn bộ môi trường inference giống nhau nên không suy ra quan hệ nhân quả đầy đủ từ config/path.

Đính chính ghi chú .93: ảnh mới frame 15954/15968 cho thấy track 255061 là bbox thân trên người đi xe máy. Sau khi tách identity, OUT 638.6037 s khớp GT OUT 639.119033 s; canonical 251681 IN 639.7107 s khớp GT IN 640.140782 s. Không lặp lại suy diễn đây là người đi bộ. Nội dung .93 bên dưới được giữ nguyên như lịch sử, không phải nhận định cập nhật.

## Thay đổi heading và phạm vi tái lập

Chỉ thêm inertia cho hướng điểm neo hai bánh: bán kính là nửa đường chéo lớn hơn của hai box, sàn 1.5 px. Bước tâm nhỏ hơn bán kính giới hạn góc quay ngắn nhất ở `travel/radius` radian; góc nhỏ được cập nhật ngay khi có đủ chuyển động hỗ trợ. Bước lớn từ một bán kính trở lên dùng hướng vận tốc mới ngay. Dùng góc atan2 tránh vector 0 ở trường hợp đối hướng. Không thay measured/prediction velocity, resolver association, ngưỡng cắt vạch, vùng đường hay dedup.

Flag `AI_TWO_WHEEL_HEADING_INERTIA=0` nối từ worker/Compose env_file và khôi phục đường heading .93. Xe bốn bánh, thiếu rect, heading chưa thiết lập hoặc gap quá cửa sổ dùng cách xử lý cũ. Policy/quy ước class, bao gồm van chở hàng là truck, không đổi. Counting.py và mọi rescuer giữ nguyên byte.

100 tracking test = 93 cũ + 7 mới: quay đầu thật, box nhỏ/xe nhanh, góc đối hướng, rollback/vận tốc đo, source clock/gap và fixture số liệu 677 hàng từ trace thật. Fixture 42.229 byte được đóng gói cùng source; không chứa ảnh, video, GT hoặc đường dẫn riêng. Reproducer dùng đầy đủ lịch sử target từ frame 19343, không khởi tạo lạnh ngay sát lỗi.

Track 345897: primary counter .93/flag-off tạo 5 crossing dao động; .94 còn OUT khoảng 811.925 s và IN 816.922 s. Tái lập mở rộng dùng primary + thứ tự gọi anchor-span/heavy-center/two-wheel-center rescuer thật cũng loại chu kỳ quanh 815 s. OUT sớm chưa có GT tương ứng nên không coi là nhãn sai và không khẳng định hết FP. Không thực thi lại model, HumanGuard/deferred rollback, lost-finalization, dispatcher/backend transaction hoặc association toàn clip.

Kiểm tra hình học mở rộng trên 271.208 recorded observations: 195 → 168 proposals, 142 → 143 GT khớp thời gian, giữ toàn bộ 142 GT từng khớp, proposal chưa khớp 53 → 25. Flag-off khôi phục chính xác 195 event cũ. Đây là **bộ kiểm tra có kiểm soát**, không phải 151 event DB hay F1 mới của ứng dụng. Track 354713 IN 793.828 s vẫn có rescuer tại observed frame 19841, source 793.4923 s, trong ±0.75 s; không nới counter để cứu test.

Ba assignment hướng trong phép kiểm tra tốt hơn, một assignment kém hơn quanh GT 606.18197 s. Event OUT đúng của 235019 tại 606.0992026189118 vẫn giữ nguyên time/route/geometry/frame. Proposal IN cạnh tranh của 234512 đã có từ trước, đổi 606.0901768847625 → 606.0994639160751 (khoảng 9.287 ms), trở nên gần GT hơn event OUT khoảng 0.261 ms nên matcher theo thời gian chọn khác. Các OUT 234512 tại 606.0/606.267 vẫn giữ nguyên. Ghi nhận rõ hạn chế này; không đổi matcher, GT hay tuyên bố không có trade-off. **Chưa có benchmark full pipeline .94.**

## Human Guard decision audit

Hàm `human_dominates_two_wheel_candidate` và toàn bộ `HumanGuardTrackPolicy` AST giống .93. Thêm field metadata tùy chọn và helper audit; không tăng lần inference, đổi threshold hoặc tính strike. Cache cùng frame giữ nguồn cũ, interval/out-of-order không được gọi là quan sát mới. Không có decision ghi null; hình học chưa tính ghi `geometry_computed=false` và IoU/coverage null. Lỗi metadata không làm mất decision đã suy luận thành công hoặc ngắt đếm.

14 test mới gọi worker methods/NumPy verifier thực với model double có kiểm soát; kiểm fresh/same-frame/interval/out-of-order/unavailable, rider release, strike không đếm đôi, lỗi audit, finite whitelist, bỏ path/private fields, giới hạn và parser trace cũ. 3 Node test kiểm scope đúng identity, scores/frame sai kiểu và giới hạn 8. UI hiện rõ khi chỉ có track gần timecode, chưa biết identity GT.

Bookkeeping tối đa 256 track/frame, không ghi model response/ảnh crop/path; mỗi cửa sổ chẩn đoán giữ 8 bản ghi. Bỏ audit cho bốn bánh không có guardcache/context, giữ lịch sử guard nếu class đổi. Ước lượng synthetic trên 264.972 quan sát hai bánh của input: thêm khoảng 88,8–169,3 MB JSON chưa nén tùy độ đầy đủ của decision; đây không phải đo gzip/inference mới. Giới hạn export nén 128 MiB và cơ chế trace warning giữ nguyên. HumanGuard 143399 ở 397 s chưa có crop opinions trong trace cũ: không giảm threshold/TTL/bypass chỉ từ confidence primary/periodic khác nguồn.

## Môi trường và chạy trên Windows

Runtime Python 3.12.14, Node 24.19.0, NumPy/Pydantic/ReportLab/openpyxl/pypdf có sẵn. Không có pytest, FastAPI/SQLAlchemy/Alembic/httpx/httpx2, cv2/Torch, PowerShell hoặc Docker. Chưa thực thi HTTP/ORM/PostgreSQL/migration live, npm install/audit/Vite build với phiên bản pin, browser/React DOM hay GPU/full-video replay. Các module report/PDF/font/license và kiểm tra cũ được giữ byte-exact; không chạy lại PDF render không liên quan. Hướng dẫn Windows dưới đây chạy bộ kiểm tra Docker chính thức và vẫn cần môi trường/model của bạn.

Migration `0108_guard_audit_v0594` → parent `0107_reports_guard_v0593`, chỉ đổi schema_version .94, downgrade .93; không cập nhật GT/events. Không push GitHub hay tạo Release thật trong lượt này.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.94 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl+F5. Chạy lại cùng clip/vạch/model, sao chép GT đã review và xuất benchmark ZIP sau khi có GT để đo bản .94. Không tạo lại Admin. Các phần sau là lịch sử kiểm chứng được giữ nguyên.

---

# V0.5.93 — Kiểm chứng source, báo cáo và sửa nối ID

## Kết quả hiện tại

| Phạm vi | Đã thực thi |
|---|---:|
| AI algorithms/worker helpers offline | 663 đạt |
| Backend pure algorithms/helpers offline | 129 đạt |
| Scripts unittest | 79 đạt |
| Benchmark gate standalone functions | 5 đạt |
| Backup worker standalone functions | 4 đạt |
| Frontend Node tests | 30 đạt |
| **Tổng kiểm tra thực thi** | **910 đạt, 0 lỗi** |
| HTTP/ORM integration chưa chạy | **63**, gồm 62 cũ và 1 SQLite report test mới |
| Supplementary report UI checks | 7/7 Babel/Node VM có kiểm soát; không cộng vào 910 |
| Local release checks | 38: 17 executed, 14 static, 4 simulation, 3 Bash syntax; không cộng vào 910 |

Đây **không phải full pytest**. Runtime hiện tại Python 3.12.14 / Node 24.19.0 / npm 11.9.0, có NumPy/Pydantic/ReportLab/openpyxl/pypdf nhưng thiếu pytest/FastAPI/SQLAlchemy/Alembic/httpx/httpx2/cv2/Torch/pwsh/Docker. Một lần thử cài dependency có timeout ngắn không lấy được gói, không tiếp tục lặp cài hay gọi các kiểm tra bị loại là đã chạy.

Các Python test function thực tế chạy bằng harness với fixture tối thiểu approx/raises/tmp_path/monkeypatch; worker/backend helpers trích AST để tránh import HTTP/ORM chưa có. Dispatcher dùng queue/thread với HTTP được kiểm soát. Scripts unittest và frontend node --test chạy bằng runtime thực.

Giữ đủ **926 Python test identity cũ**, thêm 17 (6 tracking + 11 report), tổng 943 definition. Giữ đủ 19 Node test cũ, thêm 11 thành 30. Không sửa assertion/body của test cũ. 63 integration exclusion gồm 3 AI + 59 backend cũ và 1 report SQLite mới; tổng 880 Python function thực thi + 63 chưa chạy = 943 definition, cộng 30 Node = 910 kiểm tra đạt.

## Rà soát full source

Baseline đúng ZIP .92 người dùng gửi: **641.978 byte / 290 path**, SHA256 `a85220e42e266261f45642d43d43dfeb6c3890ffb86602d6f3950cd34b1c8ed9`. Source .93 giữ đủ 290 path, thêm 10, tổng 300 file. Không đóng gói .env thật, runtime volumes, camera RAR, video, model weights, trace/raw input hoặc caches.

- 203 Python file parse/compile hợp lệ; 107 migration, head `0107_reports_guard_v0593`, parent `0106_cycle_witness_v0592`, revision dưới 32 ký tự. Migration chỉ cập nhật schema_version 0.5.93, downgrade 0.5.92.
- 29 PowerShell script UTF-8 không BOM / CRLF; các text source/config khác giữ LF. Historical contract và các lệnh cũ được giữ lại.
- 1.071 source predicate PowerShell, 774 internal Python import symbol, 121 frontend runtime-field pair được rà soát, không còn finding. Đây là kiểm tra tĩnh, không phải PowerShell runtime.
- Babel parse 16 JS/JSX file và 43 local import/export symbol đạt, không phải Vite build hoặc React DOM/browser.
- 298 code/config SHA256 đã đóng băng sau các kiểm tra cuối; README/VERIFICATION review và pin riêng trước đóng gói.
- Legacy counting/Gate/worker/classification/Human Guard / backend dedup / matching giữ nguyên byte của .92. Tracking chỉ thay lower bound của đúng một guard 4→1; khôi phục lower bound thì toàn bộ AST algorithm trở về baseline. CSS cũ giữ nguyên byte; report CSS dùng selectors riêng.
- API report router được đăng ký trong backend main; global authentication/RBAC middleware không đổi. Viewer chỉ xem, Admin/Operator export; đường dẫn /export tiếp tục bị viewer từ chối theo policy hiện có.

## Dữ liệu benchmark và trace đã đối chiếu

Benchmark #66/session 193 ZIP có 5 data JSON cùng manifest: kiểm SHA256 và byte lengths đủ 5 file. Dùng hàm match_crossings thực tế của source hiện tại tái tính, tất cả base fields/matching rows khớp report:

| Chỉ số input .92 | Giá trị |
|---|---:|
| GT / AI | 149 / 150 |
| Khớp / Lọt / Dư | 138 / 11 / 12 |
| Recall / Precision / F1 | 92,6174% / 92,0000% / 92,3077% |
| Đúng class / đúng hướng | 136/138 / 136/138 |
| Khớp đủ time/class/direction | 134 |
| AI IN / OUT | 69 / 81 |

RAR 158.592.235 byte, SHA256 `4f433ae6bb9e38d8a2556a1030c962f51830c2995a959e51e8b6918d42591a0f`, có 380 member có đường dẫn an toàn, không trùng, gồm **cả session 192 và 193**. Không nhầm trace 192 thành 193. Trace 193: 196.117.028 byte, SHA256 `4417cbfc80e8401615c7a8a04174bed92b9f2fb09c1fe7e101b8c16aa07726e8`; trace 192: 197.559.471 byte, SHA256 `7ff2972c2f808b3bf556bdb0f97ea588bda8ae60e5d6ba6b4489ca266674daae`.

Mỗi run có 23.650 frame liên tục, 271.208 Gate-track observation, 191 proposal = 191 terminal receipt, 150 created + 41 dedup. Mọi receipt khớp 11 source field của proposal; 150 created khớp đủ 150 DB event. Drain complete/pending 0 / dropped 0; không có bằng chứng rơi event khi gửi backend.

Hai run 192/193 giữ frame/time/hướng/loại/điểm cắt/tracking/outcome/dedup reason; một confidence khác nhẹ tại 86667 IN 250.5291 s. Cùng 150 AI và cùng 11 lọt / 12 dư; .92 thêm audit không giải quyết các lỗi này. Crossing-cycles người dùng gửi là benchmark 65 / session 192; năm cặp được crosswalk duy nhất sang 193 bằng chữ ký chính xác, không gán raw witness 192 cho 193.

GT đang có 0 truck / 1 car / 4 bicycle, AI 2 truck / 0 car / 1 bicycle. Sai loại OUT 641.981 GT car → AI truck và IN 289.449941 GT bicycle → AI motorcycle được xác nhận bằng report. Van IN 882.2898 không có GT trong ±0,75 s; không dùng điều đó để tự xóa AI hoặc đổi van về CAR. Người dùng cần review GT theo clip và quy ước van chở hàng là Xe tải.

## Sửa nối ID và phạm vi hiệu quả

Canonical 251681 bị raw 255061 chiếm đúng một quan sát ở frame 15954, tạo event IN 638.12. Ảnh mục tiêu cho thấy box người đi bộ kế thừa identity/rider của track xe. Proposal 251681 IN 639.7107 gần GT 9635 IN 640.1409 sau đó bị backend same-track-repeat-jitter gộp vào event sớm.

Giữ guard .85 hiện có nhưng mở window gap 4–12 thành 1–12 frame, chỉ cho candidate hai bánh khác raw ID, đủ hai rect và đồng thời direct_jump >1.75 × footprint / predicted_jump >1.50 × footprint. Switch AI_SHORT_GAP_ALIAS_GUARD vẫn là rollback; không thay global distance, prediction threshold, Gate/tolerance/cooldown/dedup/HumanGuard/heading/class.

93 tracking test thực thi, gồm 87 cũ và 6 mới; là subset của 663 AI. Có controls gap 1/2/3, xe nhanh khớp prediction, flag off, bốn bánh/gap > 12/missing rect / known raw.

Reproducer có kiểm soát dùng 158 dòng đo thật của target, resolver thực từ ZIP baseline/current và primary counter/defaults trích từ worker. .92 ghép raw 255061 vào 251681 và phát crossing 15954. .93 để raw 255061 giữ identity riêng, giữ 251681 ở 15957/15997 và primary counter phát IN 639.7106917 s tại observed frame 15996. Trace từ pipeline worker đầy đủ trước đó chọn cùng source clock nhưng gửi ở frame 15997; khác biệt observed frame được ghi rõ. Tắt flag khôi phục kết quả baseline của reproducer.

Đây là replay chọn lọc observations, không chạy detector/tracker/model/HumanGuard/dispatcher/backend dedup toàn pipeline và **không phải F1 mới**. Case 345897 còn anchor dao động theo cạnh box trong lúc center ổn định; không sửa heading thiếu kiểm chứng. Human Guard 143399 dùng cùng raw ID trước crossing, trace thiếu person/rider opinions nên không có căn cứ giảm ngưỡng/TTL/bypass. Không tự thay GT hoặc hứa đã hết 11 lọt / 12 dư.

## Báo cáo nâng cao và exports

Pure aggregation kiểm tra ngày UTC+7 `[start,end)`, giới hạn 366 ngày / 31 ngày theo giờ, zero-fill hour/day/month, tổng IN/OUT/unknown, camera/class/session filters, 5 peak-hour bucket, tie-order, dữ liệu rỗng và giới hạn 100.000 nhóm không âm thầm cắt tổng. SQL query chỉ đọc detected_at/events; video source_time_seconds không bị cộng vào ngày hiện tại hay suy diễn thành ngày quay.

10 pure test báo cáo thực thi; một SQLAlchemy/SQLite integration test chưa chạy và được giữ trong source. XLSX mở lại bằng openpyxl, 5 sheet, numeric cell thật, Unicode và không có formula; CSV UTF-8 BOM xử lý ô có khả năng bị hiểu là formula. PDF có font DejaVuSans nhúng cùng giấy phép, ToUnicode, phân trang + header lặp; pypdf đọc 4 trang và tiếng Việt, Poppler render/xem đủ 4 trang. Tiêu đề section dùng keepWithNext tránh mồ côi bảng. ReportLab thực tế 4.4.9; production/test dependency pin 5.0.1 chưa cài được trong runtime này.

11 Node test mới kiểm tra whole-day/UTC+7/query/export whitelist/totals/NaN chart. 7 kiểm tra Babel/VM có kiểm soát thực thi handler/render với schema backend thực, pending/stale selection, viewer permission, blob download/revoke, HTTP 403 / wrong MIME / unmount; không gọi đây là browser test.

Đối chiếu 150 event thực session 193 qua report helper: 150 / IN 69 / OUT 81 / MC 147 / bike 1 / truck 2, đúng dữ liệu gốc. Đồng hồ detected_at của chúng nằm **15/10/2026, 21h UTC+7** dù file đính kèm 16/10; UI điền ngày theo phiên. Chart/peak thể hiện thời điểm hệ thống ghi nhận, không khẳng định giờ giao thông thực ngoài đời của video replay. Chọn một phiên tránh cộng nhiều lần chạy lại cùng clip.

## Giới hạn và chạy trên Windows

Chưa chạy native PowerShell / Docker / PostgreSQL / HTTP ORM / migration live, pytest với dependency đã pin, npm audit/Vite production build, React DOM/browser, GPU/full video/model replay. Không publish GitHub hoặc tạo Release thật; 38 release check chỉ Git/artifact cục bộ và static/simulation/syntax.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.93 và Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl+F5. Trong Báo cáo, chọn camera/phiên và Xem báo cáo trước khi xuất. Để đánh giá bản sửa đếm, chạy lại cùng clip/vạch/model, benchmark mới dùng GT đã review, đối chiếu và xuất ZIP sau khi có GT. Bản này giữ đủ lịch sử source .92; những kết quả các bản cũ ở phần dưới là lịch sử, không phải phép chạy của môi trường hiện tại.

---

# V0.5.92 verification

- Source based on V0.5.91 full source ZIP, benchmark #65 Session #192 and 190 uploaded camera snapshots.
- Verification pipeline: signed ZIP/manifest hash, closed trace, raw source SHA-256 + byte count; 150 AI events, 149 GT, 138 matched, 11 missed, 12 extra, 92.3% F1 unchanged.
- New cycle audit: 5 pairs within 12 seconds; 2 pairs involve unmatched AI; raw-ID evidence changed for 3 pairs. No automatic event suppression, GT edits or claims of improved F1.
- Node frontend test coverage now 19 tests; scripts Python regression suite 79 tests; AI pytest 660, backend pytest 178, backup worker pytest 4. Backend and AI tests use `httpx2` alias to installed `httpx` **only in test interpreter, not in production source**; backend SQLite in-memory; production Docker must be tested on Windows.
- Packaging verified: version-contract, Alembic head <=32 chars, PowerShell CRLF, Python compileall; new script powershell contract and JS UI navigation module.
- Node 22 locally, project requires Node >=26.10; Vite production bundle and Docker/GPU replay not verified in this environment.

# V0.5.91 verification

- Verified ZIP benchmark #64 report, 149 GT / 150 persisted AI / 138 matched / 11 missed / 12 extra.
- Comparator vs #62: identical GT and 150 persisted crossing signatures, no measured performance change.
- New read-only frontend case navigator: 7 Node.js tests and a PowerShell contract.
- Executed: 660 AI tests, 178 backend tests, 71 script tests, 15 frontend Node tests, 4 backup worker tests.
- AI/backend used a temporary `httpx2 -> httpx` import shim outside the source, and backend tests used an in-memory SQLite URL. This does NOT validate the production httpx2 and PostgreSQL stack.
- JSX parsed/transpiled without error using TypeScript 5.x. Vite production build unavailable (Node 22 versus required >=26, package registry DNS blocked).
- No real GPU/video replay performed; no new F1 result can be claimed.

# V0.5.90 — Verified AI-only comparison for unscored benchmark exports

- Input: integrity-verified `traffic-ai-benchmark-62-session-188.zip` (GT 149) and `traffic-ai-benchmark-63-session-190.zip` (GT 0, exported before copy).
- Confirmed identical 150 persisted event signatures, 0 added/removed; reports **no GT metric comparison** because the second ZIP has no GT.
- Later screenshot shows GT 149 / AI 150 / matched 138 / missed 11 / extra 12 / F1 92.3%; those results are NOT in the attached older ZIP.
- Comparison tool validates all six manifest-tracked JSON documents, trace digest, session ID, conservation of AI event count, persistence integrity, video/gate/FPS geometry. For scored pairs it retains existing GT fingerprint/tolerance check and benchmark-gate conservation tests.
- Eleven new tests (including five verified error-queue tests) cover unscored-to-scored, scored-to-unscored, changed AI signatures, forged score, tampered hash, incompatible FPS.
- No inference algorithm change, no measured F1 improvement. Windows/Docker/GPU testing still required by the user.

---

# V0.5.89 — Release packaging, immutable tag safety

- Source from V0.5.88 ZIP; new metadata-only migration `0103_release_eol_v0589`.
- Packaged PowerShell file line endings are CRLF (before any Windows publish run).
- `.gitignore` now excludes downloaded root-level benchmark ZIPs, camera RARs
  and benchmark comparison output (previously eligible for git add -A).
  A publish guard rejects those artifacts if they were already staged.
- `publish.ps1` still refuses to move an existing local/remote Git tag; logs only
  names and statuses of changed files, not file contents.
- Windows V0.5.88 user's supplied log independently verifies existing official
  `test.ps1`, Docker image build/start, GPU service readiness and local HTTPS.
- Local checks after V0.5.89 changes: 660 AI pytest, 178 backend pytest,
  4 backup worker pytest, 60 scripts unittest, 8 frontend node tests:
  **910/910 tests passed**. Backend test environment used a temporary test-only
  `httpx2` shim outside the packaged ZIP; not a substitute for Docker testing.
- Existing-tag error occurred before source push; v0.5.89 publish on Windows
  and GitHub Actions has NOT been executed here.
- No changes to inference or benchmark comparison outcomes; the baseline of
  GT 149 / AI 150 / missed 11 / extra 12 is not claimed to improve.
- Git status in user's repository cannot be inspected from this ZIP; existing
  tag + pending changes may have causes besides CRLF normalization.

---

# V0.5.88 — Verification and limitations

- Root cause: V0.5.67 PowerShell contract pinned obsolete literal `Tổng GT = AI`,
  but V0.5.87 frontend correctly supports competition review when totals differ.
- Refactored presentation predicate into JS module covered by four focused tests.
- Contract now checks the predicate integration, both audit fields, backend regression,
  and explicit equal/unequal count frontend regression cases.
- No AI inference, crossing thresholds, GT marks or benchmark event data modified;
  no measured F1 improvement claimed.
- **Local automated verification:** AI 660/660 (pytest), backend 178/178 (SQLite-memory
  pytest), scripts 55/55 (Python unittest), backup worker 4/4 (pytest), frontend 8/8
  (Node built-in test runner): **905/905**. All Python `compileall` and
  `scripts/version-contract.py` passed.
- The Alembic revision name initially exceeded the historical 32-character limit;
  it was shortened to `0102_temporal_review_v0588` (26 chars). Version checker now
  fails on future oversized migration IDs and has a regression test.
- Backend/AI test runs used a temporary **test-only** `httpx2` import shim outside
  the ZIP because `httpx2` is not installed here; this is not validation of the
  production dependency. Linux Node 22 executed the JS test runner; Vite production
  build requires the project's configured Node 26 environment.
- **Not run:** Windows PowerShell `scripts/test.ps1` as a whole, Docker image builds,
  Windows startup, PostgreSQL integration, Vite production build and GPU inference.
  Rerun the full official test script on the user's Windows host before publishing.

---

# V0.5.87 — Verification and limitations

- Validated completed Benchmark #61 and #62 source archive hashes, compared GT/event crossing signatures, reviewed trace and selected camera JPEGs. The before/after GT 149 / AI 150 / matched 138 / missed 11 / extra 12 is **unchanged**.
- New script `compare-benchmark-exports.py` is read-only; never relabels GT or emits new AI events. New frontend temporal audit block fixes hidden review when GT 149 differs from AI 150.
- Full inference replay with GPU/model/MP4, Windows Docker stack and real PowerShell tests must be performed on the user's machine. No new precision/recall claims.

---

# V0.5.86 — Verification and limitations

- Benchmark #61 / Session #187 ZIP fully validated by the bundled read-only forensic tool (trace compressed/uncompressed SHA256, metadata, delivery drain). Baseline: GT149 AI150 matching138 missed11 extra12, direction2 and class2 mismatches; **these are V0.5.85 values**.
- JPEG RAR inspected with libarchive: 190 images, specific frames 7243, 16050, 22059 visually reviewed. No model weights / original MP4 were supplied in the source ZIP; no GPU inference or 23,650-frame replay done here.
- `tests/test_tracking.py` adds 5 regression scenarios for the new two-wheel 4–12-frame visible-incumbent reservation; existing main counts/gate algorithms unchanged. Before claiming quality improvement, rerun clip and export new benchmark/trace.
- Sandbox automated verification: **660/660 AI pytest**, **178/178 backend pytest** (in-memory SQLite), **4/4 backup-worker pytest**, **47/47 scripts unittest**, **4/4 frontend Node tests** = **893/893 tests passed**. Benchmark forensics validated the supplied ZIP with both compressed and decompressed trace SHA-256, and produced 23 audited cases. Full Python `compileall` passed, `scripts/version-contract.py` passed, TypeScript JSX parser reported **0 syntax diagnostics** for the frontend.
- Missing native `httpx2` package was replaced with a **test-only** `httpx→httpx2` compatibility alias placed outside the ZIP; this is not production validation of `httpx2`. Backend tests used `DATABASE_URL_OVERRIDE=sqlite+pysqlite:///:memory:`; PostgreSQL/live services were not started.
- **Not executed**: `scripts/test.ps1` under Windows PowerShell, Docker stack, GPU/video replay, frontend Vite production build, full HTTP system integration and publish/GitHub Actions. Run `scripts/test.ps1` on the target Windows machine before publishing.

---

## Verification of previous versions

# V0.5.85 — Verification and limitations

## Những phần đã kiểm chứng trong môi trường hiện tại

- AI Service: **655/655 pytest PASS**, bao gồm 4 test mới về alias bất thường, tiếp tục xe nhanh, xe 4 bánh và chế độ rollback.
- Backend: **178/178 pytest PASS** trong SQLite memory, với test token riêng cho CI.
- Backup Worker: **4/4 pytest PASS**.
- Frontend: **4/4 node --test PASS**.
- Công cụ: **47/47 unittest PASS**. Dòng `[FAIL]` của negative test replay là output kỳ vọng; unittest tổng kết OK.
- Tổng cộng **888/888 test đạt**. `scripts/version-contract.py` kiểm tra version và migration chain PASS.
- Lớp tương thích `httpx2` trong lúc test ở đường dẫn ngoài source; **không có trong ZIP**.

## Giới hạn quan trọng

- **Chưa chạy lại GPU/video nguồn** cho V0.5.85. Không có bằng chứng đã giảm 11 lượt lọt / 13 lượt dư ở Benchmark #60.
- **Chưa chạy Docker, PowerShell và Vite production build** trong môi trường này. `test.ps1` trên Windows sẽ kiểm tra chúng trước khi phát hành.
- Guard mới có thể tắt tạm bằng `AI_SHORT_GAP_ALIAS_GUARD=0` để so sánh, sau khi khởi động lại AI Service. Không thay đổi GT hoặc dữ liệu lịch sử.
- Không đóng gói video, trace camera, RAR, `.env` hoặc database người dùng.

## Phân tích nguồn

Xem `docs/session-186-alias-handoff-v0585.md`. Nhóm sự kiện tại 606 giây mới là giả thuyết có bằng chứng quỹ đạo; kết quả cuối phải được xác nhận bằng phiên replay mới.

---

## Xác minh V0.5.84 trước đó

# Traffic AI V0.5.84 - Verification

## Baseline: GT benchmark #59 / Session #185 (V0.5.83)

- Source video: 23,650 frames, 25 FPS.
- GT 149; AI 151; timecode matched 138; strict matched 134.
- Missed 11; extra 13; wrong-direction 2; wrong-class 2.
- The V0.5.84 source has **not** been GPU-replayed against the video; no
  claim of numerical improvement to GT recall or precision is made.

## Implemented

- Dual-provenance Raw ID Reuse Guard: inspect separately measured Raw ID
  trajectory AND canonical-alias handoff to avoid hiding a genuine ID jump
  behind another alias' recent coordinates. Large canonical alias jumps
  remain fail-closed to avoid manufactured vehicle passages.
- Raw observations are pruned with canonical TTL cleanup. The gate,
  cooldown, rescue, class refiners, existing direct-shadow protection,
  backend authorization, backup/restore and PostgreSQL schema are unchanged.
- Read-only ZIP raw-id audit now distinguishes **worker cumulative resets**
  from jumps present in **gate_tracks** sample. Timecodes and GT-nearness are
  review hints only, not proof of a causal relationship.
- V0.5.84 migration is metadata-only; no table schema change.

## Tests run in this environment

| Suite | Result |
|---|---:|
| Backend pytest (SQLite in-memory) | 178/178 PASS |
| AI Service pytest | 651/651 PASS |
| Backup Worker pytest | 4/4 PASS |
| Frontend node --test | 4/4 PASS |
| Scripts stdlib unittest | 47/47 PASS |
| **Total** | **884/884 PASS** |

- Source version/migration chain check: PASS.
- Benchmark #59 trace: gzip SHA-256 verified, 23,650 frames scanned;
  10 worker Raw-ID resets and 0 gate-sampled discontinuities.
- Worker reset nearby missed GT (within 2 seconds): at 58.280s and
  290.160s. This is **not** proof of a false reset or a recovered count.
- Backend/AI tests use a temporary `httpx2` compatibility shim located
  **outside** the ZIP because that dependency is not installed in the
  execution environment. Do not treat the shim as a substitute for a real
  Docker/runtime dependency test.
- Not executed here: PowerShell on Windows, Docker Compose startup,
  PostgreSQL restore, full Vite production build, GPU video replay and
  GitHub Actions on the remote runner.
- Before publishing, run `scripts/test.ps1`, then `scripts/start.ps1` on
  Windows, and compare a fresh GT benchmark. Retain Docker volumes and `.env`.

## V0.5.110 — Trace recovery verification (2026-10-20)

- Full source based on V0.5.109. `VERSION`, AI/runtime fingerprint, API, UI, backup worker and Alembic head `0124_trace_recovery_v05110` aligned. No GT or event database schema changes.
- **761/761 AI tests** passed using a temporary outside-source `httpx2`→`httpx` compatibility import (the official `httpx2` Python package is not installed in this environment). See `docs/verification-v05110/ai-compat-tests.log`. The temporary shim is **not included** in the release.
- **195/195 backend tests** passed under the same isolated compatibility setup and SQLite. See `docs/verification-v05110/backend-compat-tests.log`.
- **179 script tests** run, **178 passed + 1 skipped** (PowerShell native harness unavailable on Linux), including 8 new recovery tests. See `docs/verification-v05110/scripts-full.log`.
- **47/47 frontend Node tests** passed. **4/4 backup-worker tests** passed.
- API trace gzip repair: 5 targeted tests passed (closed/incomplete/mismatched/oversized/concurrent). Complete `test_benchmark_trace.py` and road telemetry regression: **27/27 passed**.
- Production frontend build **not verified here**: `vite` is not installed in the container (`npm run build` failed before compilation). No Docker runtime is available here; Docker Compose build, PowerShell full `test.ps1`, PostgreSQL and GPU inference remain to be verified on the user's Windows PC.
- Original Benchmark #80 / Session #207 ZIP was missing its trace with `reason=too_large`. Recovered all 23,650 frames (raw 413,128,306 bytes → gzip 24,087,359 bytes). New derived ZIP passes ZIP CRC, `benchmark-gate.py`, `audit-gate-coverage.py -ExpectedSession 207 -RequireProvenance`; original report, GT, events, session and config each match byte-for-byte. Detailed case review: `docs/verification-v05110/benchmark80-analysis.md`.
- Runtime auto-repair is covered by unit tests; **not** end-to-end validated against a live AI Service and API on Windows. F1 remains 96.3%; no algorithm accuracy claim.


## V0.5.111 — Local ZIP preflight / explicit errors

- Root source: V0.5.110. New migration `0125_zip_preflight_v05111` (settings-only version bump).
- The exact supplied recovered Benchmark #80 is a valid 7-member archive; local Linux replay of
  `audit-gate-coverage.py --expected-session 207 --require-provenance` succeeded
  (23,650 frames; 11 gate cases; runtime 0.5.109).
- `scripts/benchmark-gate.py` and `audit-gate-coverage.ps1` distinguish
  absent local file, directories, invalid/truncated ZIP and permission errors.
- This release does not modify vehicle counts, trace data, Ground Truth or worker policy.
- Execute `scripts/test.ps1` on Windows with Docker to verify deployment-specific behavior.

## V0.5.112 — Verified benchmark review-frame exporter

- Source baseline: full V0.5.111 ZIP (426 files).
- Benchmark: #81 / Session #208, complete verified trace 23,650 frames,
  271,208 tracked gate decisions, runtime provenance `0.5.111`.
- Scored results: 149 GT, 148 AI, 143 matched, 6 missed, 5 extra; F1 96.3%.
- Added review tool + Docker PowerShell wrapper + seven stdlib-only regression
  tests. The new tool selects samples from the local original MP4 after a
  session/FPS/frame-count/aspect-ratio preflight. It does **not** train or
  relabel anything and cannot establish byte-identity of the video.
- Existing AI: 761 tests passed offline under installed compatibility module
  for `httpx2`; module is external and NOT shipped in the source archive.
- Existing backend: 195 passed with SQLite in-memory override and external
  HTTPX compatibility; no PostgreSQL integration was run here.
- Existing frontend: 47 node tests passed with installed Node.js v22.16.0.
- New exporter tests: 7 passed with `python -S` (stdlib-only / simulated OpenCV
  container). The exporter has **not** been tested against the actual original
  clip1.mp4 because it was not uploaded as a continuous MP4.
- Full Docker startup, GPU inference and Windows native PowerShell still need
  verification on the user's workstation. No new Recall/Precision/F1 is claimed.


## Verification — V0.5.115 (review track overlays)

- Added `scripts/annotate-benchmark-review-frames.py` and corresponding
  PowerShell/Docker wrapper, plus 8 stdlib-only regression cases in
  `scripts/tests/test_review_track_overlay_v05115.py`.
- Verification checks correct benchmark/session/trace SHA and original frame
  clock, bounded per-frame tracks, path/symlink safety, nonempty-output refusal,
  exact trace frames and ZIP integrity. No training labels are generated.
- Version 0.5.115 / migration `0129_review_tracks_v05115`. No change in AI
  crossing logic or benchmark scoring.
- Production video replay and Docker-on-Windows validation require the user's
  machine; no improvement in the counting F1 score is asserted.

### Local execution results (2026-10-21)

| Suite | Result | Verification |
|---|---|---|
| scripts Python unittest | 211 executed: 210 passed, 1 skipped | `verification-logs/v05115-scripts-tests.log` |
| AI Service pytest | 761 passed | `verification-logs/v05115-ai-tests.log` |
| Backend pytest | 195 passed | `verification-logs/v05115-backend-tests.log` |
| Frontend node --test | 47 passed | `verification-logs/v05115-frontend-tests.log` |
| Benchmark Gate | 5 passed | independent pytest |
| Backup Worker | 4 passed | independent pytest |
| Syntax / version / migration | pass | local compileall + version contract |
| Benchmark #82 (Session #209) | 11 cases / 23,650 frames verified, V0.5.114 trace | `verification-logs/v05115-benchmark82-audit.log` |
| Original source completeness | pass | archive-file comparison |

**Test environment:** the AI/backend suites used a temporary `httpx2`→`httpx` import alias OUTSIDE the release source. The official Python dependency and Docker GPU runtime were not exercised here. Windows `test.ps1`, full container production build, and continuous-video inference have not been run in this environment. Frontend tests were run via `node --test`, not production Vite build.

**Metric attribution:** 149 GT / 148 AI / 143 matched / 6 missed / 5 extra (F1 96.3%) were observed on V0.5.114, Session #209. V0.5.115 is a review-overlay tool, not a detector or counting accuracy upgrade. No improvement in F1 is claimed.

### Local execution results (2026-10-21)

| Suite | Result | Verification |
|---|---|---|
| scripts Python unittest | 211 passed, 1 skipped | `verification-logs/v05115-scripts-tests.log` |
| AI Service pytest | 761 passed | `verification-logs/v05115-ai-tests.log` |
| Backend pytest | 195 passed | `verification-logs/v05115-backend-tests.log` |
| Frontend node --test | 47 passed | `verification-logs/v05115-frontend-tests.log` |
| Benchmark Gate | 5 passed | independent pytest |
| Backup Worker | 4 passed | independent pytest |
| Syntax / version / migration | pass | local compileall + version contract |
| Benchmark #82 (Session #209) | 11 cases / 23,650 frames verified, V0.5.114 trace | `verification-logs/v05115-benchmark82-audit.log` |
| Original source completeness | pass | archive-file comparison |

**Test environment:** the AI/backend suites used a temporary `httpx2`→`httpx` import alias OUTSIDE the release source. The official Python dependency and Docker GPU runtime were not exercised here. Windows `test.ps1`, full container production build, and continuous-video inference have not been run in this environment. Frontend tests were run via `node --test`, not production Vite build.

**Metric attribution:** 149 GT / 148 AI / 143 matched / 6 missed / 5 extra (F1 96.3%) were observed on V0.5.114, Session #209. V0.5.115 is a review-overlay tool, not a detector or counting accuracy upgrade. No improvement in F1 is claimed.
