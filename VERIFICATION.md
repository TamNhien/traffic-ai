# Kiểm tra Traffic AI V0.5.53

## Kết quả đã thực hiện

- **279 test functions offline đạt, 0 lỗi**: 238 AI và 41 backend.
- AI gồm 102 counting, 56 classification, 22 worker context và 8 guard transaction tests, cùng các test thuần hiện có. 33 test sử dụng method worker thực trích từ AST để tránh import HTTP transport chưa cài; geometry/classification/human_guard dependencies lấy từ source thực.
- Backend gồm 16 benchmarking tests thuần và 25 helper/schema/geometry tests. Route helpers/Enums trích từ source thực, validation sử dụng Pydantic thực. Không thay bằng endpoint hay ORM giả.
- **20 integration tests bị loại tường minh** khỏi harness offline; vẫn giữ trong full source để chạy với pytest trên môi trường dự án. Ba ORM regression mới của V0.5.53 nằm trong nhóm chưa chạy.
- Harness chỉ cung cấp các phần pytest cần dùng (`approx`, `raises`, temporary path, monkeypatch). Model output trong các regression worker được cung cấp bằng fixture; không chạy inference thực. 279 là số test functions đã thực thi qua harness, không phải kết quả toàn bộ pytest.
- Python 3.12.14: compileall và AST parse **120 file Python** thành công.
- **228 static source checks đạt**: PipelineState 126 fields, payload worker/start/finish, backend/AI schema, version/package/Node/npm, gate và contract V0.5.51/V0.5.52/V0.5.53.
- 40 lời gọi constructor/method gate, 106 lời gọi self/cls và 353 lời gọi trực tiếp resolve được trong source khớp signature. Scope không gồm mọi dynamic/framework-generated call; static audit không thay thế execution.
- 67 migration có revision duy nhất, không vượt 32 ký tự, parent đầy đủ và một head `0067_candidate_evidence_v0553`, parent `0066_observed_path_v0552`.
- Contract V0.5.53 được gọi trong test.ps1. Các regex source predicate của V0.5.52/V0.5.53 đối chiếu bằng Python và đạt; chưa chạy PowerShell parser/runtime. Một regex mới không khớp lời gọi motor veto nhiều dòng đã được sửa trước khi đóng gói.
- Cả bốn gate và continuous approach fallback dùng helper directed observed crossing. Anchor proposal/update/lost/ack/rollback signatures khớp worker; finite-gate context queue, cache clock và unconditional evidence consumption có regression.
- 177 text files giải mã UTF-8 thành công, giữ 3 image assets; backend entrypoint đạt bash -n.
- Full source có 180 file, giữ đầy đủ 179 file của V0.5.52 và thêm migration 0067. Không đóng gói cache, video, model weights hoặc snapshot đầu vào.

## Regression V0.5.53

Thêm **46 test functions**:

| Nhóm | Test mới | Phạm vi |
|---|---:|---|
| Counting | 11 | Proposal/commit, handoff bị loại, lost retry, rollback telemetry, history đã tiêu thụ, zero touch, source clock, alias metadata |
| Classification | 9 | Motor-only/veto theo frame, winning-frame diversity, truck family/source clock/expiry |
| Worker context | 14 | Finite gate/Road Zone budget, frame trùng/cũ, cache/override, veto và tiêu thụ passage |
| Human Guard transaction | 2 | Frame cũ không thêm strike, rollback cập nhật span/override telemetry |
| Backend helper/ORM | 7 | Source-clock precedence, source neighbor, retry cũ sau IN→OUT→IN và FPS thấp |
| Benchmark | 3 | Candidate cùng điểm cắt, xe làn khác, direct/direct ngược hướng |

43 regression mới chạy qua harness; 3 ORM regression chưa chạy. Các test cũ được giữ và các thuật toán thuần đã chạy lại sau thay đổi cuối cùng.

Đã tái hiện những lỗi trước/sau bằng code thực từ ZIP V0.5.52, gồm post-confirm chốt quá sớm, cùng span được đề xuất lại, zero-distance touch làm đổi crossing time/point, delivery clock ghi đè source clock và chẩn đoán nhầm lane/opposite direct crossing. Không dùng timestamp GT để ép class hoặc tự tạo kết quả benchmark mới.

## Release verifier

**30 kiểm tra đạt**: 13 thực thi, 3 cú pháp Bash, 12 static YAML/publisher và 2 fixture mô phỏng Python.

Đã thực thi các bước Bash Verify VERSION và Build release artifacts lấy trực tiếp từ release.yml trong Git repository cô lập. Đúng tag/version/HEAD đạt; sai tag/version/HEAD bị chặn. ZIP, TAR.GZ và README lấy đúng byte từ tag dù README working tree khác; ba SHA256 khớp SHA256SUMS.

Bare repository local được dùng để kiểm tra annotated tag/peeled commit, tag chưa tồn tại khác lỗi lookup, fetch giữ đúng tag object khi retry và checkout tag khi main đã tiến. Hai fixture mô phỏng chọn đúng tag/SHA/event và kiểm tra push URL; đây không phải execution PowerShell.

Ba workflow YAML parse được và các bước Bash release đạt bash -n. Source publisher vẫn đọc VERSION, test source đã chuẩn hóa trước commit/push, giữ tag bất biến, chọn đúng run và bổ sung asset/draft từ tagged bytes. Không push source, tạo tag remote hay tạo GitHub Release thật trong phiên đóng gói.

## Bằng chứng hình ảnh và giới hạn

Đã đọc hai screenshot V0.5.52 và giải nén an toàn **236 JPG**, tổng 81.219.008 byte, kích thước 1440 × 811, frame 3–23454. Đã xem các ảnh/crop đại diện, đặc biệt vùng xe đạp, van và hai lượt lọt đầu tiên.

Ảnh 04:49 cho thấy xe đạp có giỏ đang được dắt cạnh xe máy đứng yên, có khả năng context chứa vật thể lân cận nhưng chưa chứng minh bằng model run. Van trắng/xanh ở 10:41 có GT car/model truck; không tự đổi GT hoặc taxonomy từ ảnh. Một số mốc lọt không có snapshot gần đủ để chứng minh trajectory/identity.

Mốc đầu vào **V0.5.52: GT149 / AI154 / khớp136 / lọt13 / dư18 / F1 89.8%**. Chưa có replay V0.5.53.

Chưa thực hiện toàn bộ pytest với pinned dependencies, PowerShell parser/runtime, Docker/frontend npm build/audit, HTTP/ORM integration, migration PostgreSQL, model inference hay replay clip đầy đủ. Môi trường không có pytest/FastAPI/SQLAlchemy/httpx2/OpenCV/Torch/Ultralytics/pwsh/Docker. Python thực là 3.12.14, NumPy 2.3.5, Pydantic 2.13.5; NumPy 2.4.6 của requirements-test chưa được cài/chạy ở đây. npm 12.2.0/Node 26.10.0 giữ nguyên pin Docker/CI; môi trường npm/frontend đó chưa được build trong phiên.

## Đầy đủ lệnh trên máy dự án

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File

# Kiểm tra
.\scripts\test.ps1

# Khởi động
.\scripts\start.ps1

# Tự test, commit, push, tạo tag và GitHub Release
.\scripts\publish.ps1
```

Mở https://traffic-ai.test:8443, Ctrl + F5, replay đúng clip/cùng vạch/Road Zone rồi tạo benchmark session mới từ GT 149 tương thích. Publish tự đọc VERSION để phát hành v0.5.53; README có hướng dẫn auth GitHub CLI và retry.
