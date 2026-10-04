# Traffic AI V0.5.56 — Anchor liên tục và hồ sơ benchmark

Nâng cấp từ full source V0.5.55. Đơn vị đếm là **lượt cắt vạch**: cùng phương tiện quay lại và cắt vạch lần nữa được tính thêm một lượt.

## Benchmark đầu vào V0.5.55

Hai screenshot hiện tại ghi session 159 / benchmark 38, GT sao chép từ benchmark 37:

| Chỉ số | V0.5.55 |
|---|---:|
| Ground truth | 149 |
| AI đếm | 152 |
| Khớp | 136 |
| Lọt không đếm | 13 |
| Đếm dư | 16 |
| Recall | 91.3% |
| Precision | 89.5% |
| F1 | 90.4% |
| Class đúng | 98.5% |
| Sai loại | 2 |

Kết quả cuối chưa đổi so với V0.5.54. Worker đề xuất 223, backend gộp 71, Human Guard loại 37; DB có 152 event với timecode. Lọt: anchor span 5, gần vạch chưa span 3, center-only 1, cooldown 4. Dư: rescue 8, direct 5, interpolation 2, gần GT đã khớp/cùng điểm cắt 1.

Đã xem toàn bộ **222 JPG** trong RAR camera hiện tại. Chúng không chứa JSONL, model scores hay video đầy đủ. Ở các frame 1647/1650/1653/1655/1657, cùng scooter #19086 đi đều lên trái nhưng điểm cyan chuyển qua lại giữa cạnh trên và cạnh trái bbox. Source chọn cạnh bằng `abs(vx) > abs(vy)`, khiến thay đổi heading rất nhỏ có thể đẩy anchor sang phía đối diện của vạch. Overlay là candidate trước backend dedup; không quy mọi proposal thành event dư đã lưu.

Hai lỗi loại xe vẫn là 04:49.450 IN GT bicycle → AI motorcycle và 10:41.981 OUT GT car → AI truck. Snapshot gần 04:49 có người dắt xe đạp chưa được box và xe máy riêng bên cạnh; chưa xác định ID của event đã ghép. Van gần 10:41 được model gọi truck. Bản này giữ taxonomy GT và chính sách class hiện có, không ép nhãn theo timestamp.

**Chưa replay V0.5.56**. Các số trên là benchmark đầu vào, không phải kết quả sau nâng cấp.

## Thay đổi V0.5.56

### Điểm bám liên tục theo hướng di chuyển

Anchor theo heading trên ellipse nằm trong bbox thay cho lựa chọn cứng cạnh ngang/dọc. Hướng thẳng vẫn giữ điểm dẫn trước cũ; inset xe lớn vẫn áp dụng. Khi tốc độ vừa vượt ngưỡng đứng yên, điểm bám chuyển dần từ bottom-center sang điểm dẫn trước, tránh bước nhảy bằng cả chiều cao bbox.

Regression kiểm tra thay đổi heading nhỏ, chuỗi đi chéo không đảo phía vạch, ngưỡng bắt đầu chuyển động và lượt cắt vạch thật. Thay đổi vị trí anchor ở hướng chéo cần được đánh giá bằng replay cùng geometry; các ngưỡng gate/Road Zone/dedup toàn cục giữ nguyên.

### Pending span dùng quỹ đạo sau merge

Khi alias bổ sung observation nằm bên trong span đã chứng minh hoặc thay endpoint cùng frame, gate dựng lại proof trên quỹ đạo canonical. Kiểm tra lại finite segment, Road Zone, path length, normal motion và approach progression trước confirm hoặc finalize-lost. Đường hợp lệ cập nhật điểm cắt và source frame theo crossing thực; đường bị phản chứng không giữ chord cũ. Passage quay lại hợp lệ vẫn có thể tạo proof mới.

### Consensus xe đạp và thời hạn Human Guard

Bicycle minority consensus chỉ dùng frame/source thắng motorcycle. Frame thua hoặc hòa không bổ sung hit, confidence hay source diversity. Giữ aggregate motorcycle margin, ngưỡng fused/strongest/hits và ngoại lệ single-source rõ ràng; context motor veto hiện có không đổi.

Pending Human Guard hết hạn theo frame quan sát được xử lý trước active-track loop. Xe xuất hiện lại đúng/sau deadline không hồi sinh crossing cũ. Trace giữ geometry của xe đang pending và trạng thái guard cuối; event được chấp nhận vẫn giữ source time/frame riêng.

### Tải hồ sơ benchmark

Nút **Tải hồ sơ benchmark** trong Report tải ZIP gồm:

| File | Nội dung |
|---|---|
| manifest.json | ID, thời điểm export, hash/size từng file và trạng thái trace |
| report.json | Báo cáo từ cùng danh sách GT/event được export |
| ground-truth.json | Các mốc GT, loại xe, hướng và timecode |
| events.json | Event DB gồm ID, track, time/frame nguồn, class và phương pháp crossing |
| session.json | Thông tin phiên được chọn lọc |
| config.json | Geometry/tolerance benchmark và cấu hình camera hiện tại được ghi riêng |
| benchmark-trace.jsonl | Trace gốc nếu còn trên AI service và nằm trong giới hạn 128 MiB |

API: `GET /api/benchmarks/{id}/export`; AI nội bộ cung cấp `GET /benchmark-traces/{session_id}/download`. Export không cập nhật GT/event/tổng đếm. Nếu trace thiếu, quá lớn, timeout hoặc AI service không truy cập được, ZIP vẫn có report và manifest ghi rõ lý do. Không cắt trace để giả thành bản đầy đủ.

URL metadata bỏ user/password/query/fragment; file video chỉ giữ tên. ZIP không lấy environment/settings, đường dẫn model hoặc video/model weights. Geometry camera hiện tại không được coi là cấu hình inference lịch sử của session. Với phiên đang chạy, trace/event có thể tiếp tục tăng sau export; nên tải khi session đã hoàn tất.

### Publish và toàn bộ source contract

Probe tag local dùng `Invoke-QuietProbe`, nhận exit code 1 của tag chưa tồn tại để tiếp tục tạo tag; lỗi repository vẫn bị chặn. Cách này tương thích PowerShell có native-command error preference bật. Giữ tag bất biến, kiểm thử trước commit/push và fallback hoàn tất Release.

## Version, môi trường và database

| Thành phần | Giá trị |
|---|---|
| VERSION / Frontend / Backend / AI Service | 0.5.56 |
| Alembic head | `0070_benchmark_evidence_v0556` |
| Parent | `0069_refine_admission_v0555` |
| schema_version | 0.5.56 |
| npm trong Docker / CI / packageManager | 12.2.0 |
| Node.js trong Docker / CI | 26.10.0 |

Đối chiếu ngày 04/10/2026: [npm CLI releases](https://github.com/npm/cli/releases) và [npm Docs](https://docs.npmjs.com/cli/v12/using-npm/) ghi npm 12.2.0 là latest; giữ pin thống nhất. Migration 0070 chỉ cập nhật schema version, giữ dữ liệu/GT. Camera Preview / Vehicle Count và GT / Report giữ bố cục 50/50.

## Đầy đủ lệnh test, start và tự động publish

Giải nén full source vào thư mục dự án; giữ `.env`, video, model weights và dữ liệu đang dùng. Cần Docker Desktop chạy; cần Git/GitHub CLI cho publish và checkout nhánh `main`.

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

Mở **https://traffic-ai.test:8443**, nhấn `Ctrl + F5`. Chạy lại đúng clip, cùng vạch/Road Zone; tạo benchmark cho session mới, sao chép GT 149 từ benchmark tương thích và bấm **Đối chiếu lại**. Sau đó bấm **Tải hồ sơ benchmark** để lấy ZIP dùng cho lần phân tích tiếp theo.

Nếu chưa đăng nhập GitHub CLI, chạy một lần:

```powershell
gh auth login
gh auth setup-git
```

Nếu chưa cấu hình Git author, đặt `git config --global user.name` và `git config --global user.email` bằng thông tin của bạn.

Publish tự đọc VERSION để tạo tag **v0.5.56**, mặc định repository `TamNhien/traffic-ai`. Script kiểm thử source đã chuẩn hóa, commit/push/tag, chờ đúng Actions run theo tag/SHA/push và tạo Release có ZIP, TAR.GZ, README, SHA256SUMS. Fallback CLI bổ sung đủ asset từ tag và hoàn tất Release tạo dở.

Nếu bị gián đoạn, xử lý lỗi mạng/quyền truy cập rồi chạy lại `publish.ps1` khi source không đổi. Thay đổi source sau tag đã có cần tăng version; script không di chuyển hoặc ghi đè tag. `-NoWait` chỉ đẩy source/tag rồi trả về khi Release còn đang chờ.

Đổi repository đích hoặc chạy lại workflow của tag đã có:

```powershell
.\scripts\publish.ps1 -Owner TEN_GITHUB -Repository TEN_REPO

gh workflow run release.yml --repo TamNhien/traffic-ai -f tag=v0.5.56
```

Khi dùng npm ngoài Docker trên Windows, Node.js cần 26.10.0 trở lên:

```powershell
npm install -g npm@latest
npm --version
```

Chi tiết kiểm tra thực hiện và giới hạn môi trường đóng gói có trong `VERIFICATION.md`.
