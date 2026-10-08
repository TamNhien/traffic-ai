# Traffic AI V0.5.65 — Giữ semantic Xe tải cho van

Nâng cấp từ full source **V0.5.64 đã giao**, giữ đủ193 đường dẫn cũ và thêm migration0079. Theo quy ước người dùng xác nhận, **van chở hàng thuộc Xe tải**. Đơn vị đếm là lượt cắt vạch; một xe quay lại cắt vạch lần nữa được tính thêm một lượt.

## Kết quả đầu vào V0.5.64

Ảnh session170 / benchmark47, sao chép149 GT từ benchmark46:

| Chỉ số | V0.5.64 đã chạy trên máy người dùng |
|---|---:|
| Ground truth / AI đếm | 149 /149 |
| Khớp | 135 |
| Lọt / dư | 14 /14 |
| Recall / Precision / F1 | 90.6% /90.6% /90.6% |
| Class đúng / sai loại theo GT hiện tại | 99.3% /1 |
| IN / OUT | 68 /81 |
| AI xe máy /xe đạp /ô tô /xe tải | 146 /1 /2 /0 |

Worker195 proposal, backend gộp46, DB149 timed events, Human Guard loại30; Integrity OK. Class refine1888; truck semantic locks2 và truck lock→car2, truck crossings0. Lỗi benchmark còn hiển thị là bicycle04:49.450 IN→motorcycle.

**99.3% không chứng minh hai van đã đúng loại.** Bảng Sai loại chỉ đang hiển thị lỗi xe đạp; chưa có GT/event assignment export để xác minh nhãn và cặp ghép của hai van. Người dùng đã xác nhận van cần tính Xe tải. Chưa replay .65 và chưa có F1/class accuracy mới.

RAR có194 ảnh và JSONL session170. Trace195 proposal khớp195 receipts,149 created +46 deduplicated; all attempt1, footer drain_complete=true/pending0/dropped0. Hai event bị lưu CAR:

| Lượt van | Canonical | Source frame /frame quan sát | Backend event |
|---|---:|---:|---:|
| OUT641.9311s (10:41.931) | 254023 | 16049 /16050 | 10063 |
| IN882.2898s (14:42.290) | −22, raw286434 | 22058 /22059 | 10105 |

Ảnh tại hai crossing đều cho thấy thân van kín màu trắng/xanh; overlay primary TRUCK. Không dùng màu xe để chứng minh hai tracking ID là cùng danh tính vật lý. Cả hai receipt là created, nên đây là lỗi class trước delivery, không phải backend gộp hoặc mất event.

## Sửa lỗi V0.5.65

### CAR chung không tự vượt khóa Xe tải còn hiệu lực

Ở OUT, primary/stable TRUCK có certainty.926907/hits25, semantic lock.995817; general CAR ởf16049/f16050 có confidence.838867/.858887. Ở IN, primary/stable TRUCK có certainty.972858/hits28, lock.986346; general CAR ởf22058/f22059 có confidence.903809/.948242. **Domain không có opinion, consensus=false trong cả hai ca.**

Sampling .64 đã hoạt động đúng. Lỗi là đường crossing-only CAR demotion cho phép hai generic CAR wins thắng một TRUCK lock còn hiệu lực, mặc dù generic CAR chưa xác nhận van là ô tô theo taxonomy dự án.

`.65` giữ một TRUCK semantic lock hợp lệ khi chỉ có CAR từ refiner chung. Để demote khóa đang sống, phải đồng thời có:

- Đủ CAR wins theo policy hiện có: confidence ≥.80, ít nhất hai frame nguồn liên tiếp, frame mới nhất đúng frame quan sát đang xử lý crossing.
- Đủ **domain CAR wins** trên chính cửa sổ frame đó, cùng ngưỡng và số frame; domain phải có opinion thật ở từng source frame.
- Domain CAR phải thắng các nhãn four-wheel cạnh tranh trên từng frame; confidence/clock từ general không được mượn làm domain proof.

Không có domain, domain yếu/một frame/cũ/future hoặc bị TRUCK/BUS mạnh hơn veto thì giữ khóa Xe tải. Không kéo dài TTL hay xóa semantic lock toàn cục. Đường CAR thông thường khi không có khóa TRUCK hợp lệ giữ nguyên; domain CAR đủ bằng chứng vẫn được sửa nhãn TRUCK sai tại crossing.

Đây là bảo vệ **van đã có bằng chứng TRUCK**, không phải detector mới nhận diện mọi van. Nếu model chưa từng cung cấp TRUCK proof hoặc khóa đã hết hạn, class vẫn dựa vào bằng chứng hiện có. Việc yêu cầu domain corroboration có thể giữ nhãn TRUCK sai lâu hơn khi domain model không cho ý kiến; cần xem trace/model training khi gặp ca đó.

Trace thêm `crossing_truck_class_resolution_audit`: lý do giữ/đổi, nguồn lock, số CAR/domain CAR frames và source clock event gốc. Không tạo opinion giả, crossing mới hoặc backend response giả. Cảnh báo dashboard bỏ lời khẳng định cũ V0.5.30, hướng người dùng kiểm tra clip và GT.

### Giữ các cải tiến V0.5.64

Giữ deterministic all-frame crossing admission, ngân sách/refiner/caches/source clocks; periodic/prescan vẫn theo điều kiện tải cũ. Giữ matching audit tối đa4 event đã ghép với GT khác, disclosure stack tránh chồng chữ và dashboard/GT–Report50/50. Gate/Road Zone/cooldown, tracking, Human Guard, backend dedup, terminal receipts, global temporal matching và tolerance0.75s không đổi.

## Kiểm tra nhãn GT của van

Replay cùng clip/vạch/Road Zone, tạo benchmark mới và sao chép149 GT từ **benchmark47** tương thích. Xem lại các mốc quanh **10:41.93 OUT** và **14:42.29 IN**; nếu đúng van chở hàng, dùng ô sửa class GT để chọn **Xe tải**, giữ timecode và hướng đã kiểm tra. Bấm Đối chiếu lại rồi Tải hồ sơ benchmark.

Source không tự đổi ground truth đang lưu. Nếu GT của van là Ô tô, sửa van về Xe tải có thể làm số Sai loại tăng; đó là bất đồng taxonomy cần review, không được dùng để tuyên bố model .65 kém hơn hoặc tốt hơn.

## Hồ sơ benchmark cho lần phân tích tiếp theo

Sau khi phiên hoàn tất, bấm **Tải hồ sơ benchmark**. ZIP gồm ground-truth.json, events.json, report.json, config.json, manifest.json và benchmark-trace.jsonl.gz khi trace đóng thành công. Đây là cách lấy cả GT/event assignments thay vì chỉ ảnh và thư mục camera.

Backend ưu tiên gzip từ AI service, fallback raw cho service cũ; cap128MiB cho representation truyền qua HTTP và deadline20s. Kiểm tra hash gzip, identity content encoding, certificate/stat signature của trace đóng; không inflate trace vào RAM hoặc tạo observation giả. Trace không lấy được thì manifest ghi lý do, report vẫn tải được. Geometry dùng header lịch sử của worker, không lấy camera hiện tại thay thế.

Giữ proposal/receipt audit cap8 và phân biệt matched canonical với track lân cận. URL metadata bỏ credentials/query/fragment; không export môi trường, model paths hoặc weights. Giữ JSONL trong thư mục camera khi nén ảnh; chỉ JPG không đủ provenance.

## Version và môi trường

| Thành phần | Giá trị |
|---|---|
| VERSION /Frontend /Backend /AI Service | 0.5.65 |
| Alembic head | `0079_van_semantics_v0565` |
| Parent | `0078_replay_audit_v0564` |
| schema_version | 0.5.65 |
| npm Docker /CI /packageManager | 12.2.0 |
| Node.js Docker /CI | 26.10.0 |

npm12.2.0 đối chiếu [npm CLI latest](https://github.com/npm/cli/releases/latest) ngày08/10/2026. Giữ pin Docker/CI/packageManager và Node26.10.0. Migration0079 chỉ cập nhật schema_version, giữ dữ liệu và GT. Kết quả kiểm tra chính xác và giới hạn môi trường nằm trong `VERIFICATION.md`; chưa có replay/F1 .65.

## Đầy đủ lệnh test, start và tự động publish

Giải nén full source vào thư mục dự án; giữ .env, video, model weights và dữ liệu đang dùng. Docker Desktop cần chạy; publish cần Git/GitHub CLI và checkout main.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.65 và Release
.\scripts\publish.ps1
```

Mở **https://traffic-ai.test:8443**, Ctrl+F5. Làm benchmark theo phần Kiểm tra nhãn GT ở trên, tải ZIP hồ sơ và gửi screenshot để kiểm tra kết quả mới.

Nếu chưa đăng nhập GitHub CLI, chạy một lần:

```powershell
gh auth login
gh auth setup-git
```

Publish đọc VERSION tạo tag **v0.5.65**, mặc định TamNhien/traffic-ai: test→commit→push→tag→chờ Actions đúng tag/SHA/push→Release. Asset gồm ZIP, TAR.GZ, README, SHA256SUMS; CLI fallback hoàn tất release tạo dở. Khi gián đoạn, xử lý lỗi mạng/quyền và chạy lại khi source không đổi. Source đổi sau tag đã có cần tăng version; script không di chuyển/ghi đè tag. -NoWait trả về khi Release còn chờ.

```powershell
.\scripts\publish.ps1 -Owner TEN_GITHUB -Repository TEN_REPO

gh workflow run release.yml --repo TamNhien/traffic-ai -f tag=v0.5.65

# npm ngoài Docker, sau khi dùng Node tương thích
npm install -g npm@latest
npm --version
```
