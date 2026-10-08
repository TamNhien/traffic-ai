# Traffic AI V0.5.64 — Mẫu class tại crossing và bằng chứng ghép GT

Nâng cấp từ full source **V0.5.63 đã giao**, giữ đủ 192 đường dẫn cũ và thêm migration0078. Đơn vị đếm là **lượt cắt vạch**; cùng phương tiện quay lại cắt vạch lần nữa được tính thêm một lượt.

## Benchmark đầu vào V0.5.63

Ảnh session169 / benchmark46, sao chép149 GT từ benchmark45:

| Chỉ số | V0.5.63 đã chạy trên máy người dùng |
|---|---:|
| Ground truth / AI đếm | 149 / 149 |
| Khớp | 135 |
| Lọt / dư | 14 / 14 |
| Recall / Precision / F1 | 90.6% / 90.6% / 90.6% |
| Class đúng / sai loại | 98.5% / 2 |
| IN / OUT | 68 / 81 |

Hai lỗi loại xe còn lại: xe đạp04:49.450 IN→xe máy và ô tô10:41.981 OUT→xe tải. Worker195 proposal, backend gộp46, DB149 timed events, Human Guard loại30; Integrity OK. AI146 xe máy/1 xe đạp/2 xe tải. Các điểm số trên là **input V0.5.63**, chưa phải kết quả replay V0.5.64.

RAR cung cấp194 JPG và JSONL session169. Trace có195 terminal receipts: **149 created +46 deduplicated**; tất cả ở attempt1, footer drain_complete=true/pending0/dropped0. Mỗi receipt dedup tham chiếu một event created trong trace. Source OUT69.4566 của canonical20863 được tạo thành event9828; OUT70.52 của canonical17578 tạo event9829. Vì vậy không thể quy hàng GT69.457 bị lọt cho backend gộp chỉ dựa vào thời gian gần nhau. Chưa có events.json/ground-truth.json của benchmark46 để xác định event đã được ghép với GT nào.

## Thay đổi V0.5.64

### Lấy mẫu phân loại tại crossing của replay toàn bộ frame

Source .63 dùng điều kiện playback lag theo thời gian thực để quyết định lấy mẫu refiner tại crossing, cả khi video chọn deterministic/all-frames. Máy chậm có thể bỏ mẫu crossing mặc dù vẫn đọc đủ source frames.

`.64` chỉ bỏ **lag gate tại crossing** khi source là video, deterministic_video_replay=true và frame_policy=all-frames. Vẫn giữ class-refine flag, nhãn được hỗ trợ, model khả dụng, cache/source clock và ngân sách mỗi frame. Video ngoài chế độ này giữ lag gate; nguồn live giữ hành vi admission cũ. Lượt periodic/prescan vẫn giữ điều kiện tải cũ; đây không phải cam kết toàn bộ inference độc lập với tốc độ máy.

Giữ ngưỡng CAR .80, hai frame liên tiếp, TTL, consensus, semantic lock và bicycle veto. Không tạo opinion hoặc nhãn giả khi thiếu model/ngân sách. Trace ghi admission reason, frame quan sát, lag/limit, slot đã dùng, model khả dụng, lượt lấy mẫu đã thử, opinion có hay không và source clock crossing gốc. Đây là metadata audit, không tạo event hoặc sửa điểm số.

Trace .63 có general CAR .838867 ởf16049 nhưng không có class audit ởf16050. Vì trace cũ chưa ghi admission/lag, **không khẳng định lag là nguyên nhân cụ thể của lần chạy169**, và không hứa lỗi ô tô đã hết trước khi replay model thật.

### Giải thích event lân cận đã ghép với GT khác

Review candidate của hàng lọt trước đây chỉ lấy từ AI event chưa được ghép. `.64` bổ sung `matching_audit` cho missed GT nếu có event lân cận **đã ghép**: event ID/source time/track/hướng/loại và GT ID/time/hướng/loại mà phép ghép hiện tại đã chọn.

Chỉ dùng pair indices và source clocks chưa làm tròn trong cùng report; tối đa4 record, sắp theo khoảng cách thời gian và event ID, ghi số record bị lược. Cửa sổ đúng bằng scoring tolerance. Scope là temporal_neighbor_assignment, danh tính phương tiện vật lý vẫn chưa được chứng minh. Evidence này giúp phân biệt một event đã lưu nhưng được ghép với GT khác với một candidate còn dư; không tự gán event cho GT lọt.

**Global matching vẫn tối đa số cặp và tối thiểu tổng sai lệch thời gian.** Không dùng class/hướng để chọn cặp; class/hướng chấm riêng. Giữ tolerance0.75s mặc định, review candidates, toàn bộ metrics, GT, Gate/cooldown, tracking và backend dedup.

### Sửa bố cục bằng chứng và dashboard

Hai disclosure trong hàng sai loại trước đây cùng chiếm grid-area audit, làm chồng chữ. Một wrapper sở hữu ô grid; từng disclosure nằm ở một hàng riêng. Hàng lọt nhóm nút tua và bằng chứng cùng card, controls không lồng nhau. Sửa dashboard ở màn hình ≥1500px về hai cột bằng nhau; GT/Report vẫn50/50. Giữ state, handlers, scoring controls và AnnotationEditor.

## Hồ sơ benchmark cho lần phân tích tiếp theo

Sau khi phiên hoàn tất, bấm **Tải hồ sơ benchmark**. ZIP gồm ground-truth.json, events.json, report.json, config.json, manifest.json và benchmark-trace.jsonl.gz khi trace đóng thành công. Đây là cách lấy cả GT/event assignments thay vì chỉ ảnh và thư mục camera.

Backend ưu tiên gzip từ AI service, fallback raw cho service cũ; cap128MiB cho representation truyền qua HTTP và deadline20s. Kiểm tra hash gzip, identity content encoding, certificate/stat signature của trace đóng; không inflate trace vào RAM hoặc tạo observation giả. Trace không lấy được thì manifest ghi lý do, report vẫn tải được. Geometry dùng header lịch sử của worker, không lấy camera hiện tại thay thế.

Giữ proposal/receipt audit cap8 và phân biệt matched canonical với track lân cận. URL metadata bỏ credentials/query/fragment; không export môi trường, model paths hoặc weights. Giữ JSONL trong thư mục camera khi nén ảnh; chỉ JPG không đủ provenance.

## Version và môi trường

| Thành phần | Giá trị |
|---|---|
| VERSION / Frontend / Backend / AI Service | 0.5.64 |
| Alembic head | `0078_replay_audit_v0564` |
| Parent | `0077_delivery_prescan_v0563` |
| schema_version | 0.5.64 |
| npm trong Docker / CI / packageManager | 12.2.0 |
| Node.js trong Docker / CI | 26.10.0 |

npm12.2.0 được đối chiếu [npm CLI latest](https://github.com/npm/cli/releases/latest) ngày08/10/2026. Giữ pin đồng bộ Docker/CI/packageManager và Node26.10.0. Migration0078 chỉ cập nhật schema_version, giữ dữ liệu và GT. Phạm vi kiểm tra thực hiện, số test và giới hạn môi trường nằm trong `VERIFICATION.md`. Chưa chạy Docker/PowerShell/HTTP-ORM integration/browser/model replay trong môi trường đóng gói; chưa có F1 V0.5.64.

## Đầy đủ lệnh test, start và tự động publish

Giải nén full source vào thư mục dự án; giữ .env, video, model weights và dữ liệu hiện có. Docker Desktop cần chạy; publish cần Git/GitHub CLI và checkout nhánh main.

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Test
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push GitHub, tạo tag v0.5.64 và Release
.\scripts\publish.ps1
```

Mở **https://traffic-ai.test:8443**, nhấn Ctrl+F5. Replay đúng clip, cùng vạch/Road Zone; tạo benchmark cho session mới, sao chép149 GT từ **benchmark46** tương thích và bấm **Đối chiếu lại**. Sau đó tải ZIP hồ sơ benchmark kèm screenshot để kiểm tra kết quả .64.

Nếu chưa đăng nhập GitHub CLI, chạy một lần:

```powershell
gh auth login
gh auth setup-git
```

Publish đọc VERSION để tạo tag **v0.5.64**, mặc định repository TamNhien/traffic-ai: test→commit→push→tag→chờ Actions đúng tag/SHA/push→Release. Asset gồm ZIP, TAR.GZ, README, SHA256SUMS; CLI fallback hoàn tất release tạo dở. Khi gián đoạn, xử lý lỗi mạng/quyền rồi chạy lại khi source không đổi. Source đổi sau tag đã có cần tăng version; script không di chuyển hoặc ghi đè tag. -NoWait trả về khi release còn chờ.

```powershell
# Repository khác
.\scripts\publish.ps1 -Owner TEN_GITHUB -Repository TEN_REPO

# Chạy lại workflow cho tag hiện tại
gh workflow run release.yml --repo TamNhien/traffic-ai -f tag=v0.5.64

# Cập nhật npm ngoài Docker, sau khi dùng Node tương thích
npm install -g npm@latest
npm --version
```
