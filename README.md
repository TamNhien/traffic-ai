# Traffic AI V0.5.44 — Benchmark Review 9.0 + Passage Delivery Semantics + Re-arm Stability

V0.5.44 tiếp tục từ benchmark V0.5.43 mới nhất của `clip1(6).mp4` / `camera_1(20260928-111258).rar`: **GT 149 / AI 155 / khớp 136 / lọt 13 / dư 19 / Recall 91.3% / Precision 87.7% / F1 89.5% / class đúng 98.5%**. Bản này không tự thay đổi ground truth và không nới threshold class toàn cục; trọng tâm là làm phần Lọt/Đếm dư đọc được, tách lệch timecode khỏi mất event thật, và đóng một lỗi persistence có thể làm mất lượt cắt lại của cùng track.

- **Benchmark Review 9.0 UI:** các mục `Lọt không đếm` và `AI đếm dư` chuyển thành card nhiều dòng: timecode, hướng/loại xe, nguyên nhân, chi tiết audit và `Δt/Δxy` nằm ở các hàng riêng; scrollbar có gutter ổn định, không còn đè lên chữ. Report panel có minimum width lớn hơn trên desktop và tự xếp 1 cột khi màn hình hẹp.
- **Near-unmatched review link:** sau global temporal matching chính thức, backend ghép phụ một-một giữa GT lọt và AI dư gần nhau trong cửa sổ review rộng hơn để hiển thị `AI gần nhất` / `GT gần nhất`. Đây chỉ là **audit**, không làm thay đổi `matched`, Recall, Precision hay F1. Chip `Review gần` cho biết có bao nhiêu cặp cần xem lại vì có khả năng lệch timecode.
- **Same-track delivery semantics:** backend không còn coi `session + tracking_id + direction` là khóa duy nhất cho cả phiên. Retry mạng gần như cùng frame/time vẫn dedup, nhưng cùng canonical track quay lại cắt cùng hướng ở thời điểm sau được phép lưu thành lượt mới — đúng nguyên tắc **mỗi lần cắt vạch là một lượt**.
- **Passage Re-arm Stability:** adaptive re-arm production thêm guard tối thiểu `AI_GATE_PASSAGE_REARM_MIN_FRAMES=10` và yêu cầu anchor hiện tại thực sự ra khỏi release distance trước khi mở chu kỳ mới. Điều này tránh V0.5.43 re-arm quá sớm vài frame sau crossing rồi sinh bounce/duplicate, trong khi full cooldown vẫn cho phép xe quay lại hợp lệ.
- **Giữ class guard an toàn:** các frame quanh ca `04:49.450` vẫn cho thấy bicycle bị detector/refiner giữ ở motorcycle; ca `10:41.981` là van lớn bị gắn truck. V0.5.44 không ép đổi class bằng một rule ảnh đơn để tránh làm giảm class accuracy 98.5%; hai ca tiếp tục được giữ trong audit để refinement có mục tiêu.
- **Version/database:** `VERSION = 0.5.44`, Alembic `0058_benchmark_review_v0544`, `schema_version = 0.5.44`; migration chỉ cập nhật version marker, không xóa camera, event, session, benchmark, ground truth, dataset, training run hay model.

## Kiểm thử V0.5.44

- Python compile: PASS.
- AI Service: **160/160** unit tests PASS.
- Backend: **33/33** unit tests PASS bằng SQLite test override.
- Tổng Python unit tests: **193/193** PASS.
- Có regression test cho review-link không làm đổi score, same-track delivery retry, legacy payload dedup bảo thủ và minimum-frame passage re-arm.
- Vite production build vẫn cần máy Windows đích vì sandbox hiện có Node 22 trong khi project yêu cầu Node >= 26.10.0 và không có dependency cache.
- PowerShell/Docker full-suite vẫn cần xác nhận bằng `scripts\test.ps1` trên máy đích.

---

# Traffic AI V0.5.43 — Crossing Closure 8.6 + Passage Re-arm + X-Frame Priority

V0.5.43 tiếp tục trực tiếp từ benchmark V0.5.42 (GT 149 / AI 153 / khớp 135 / lọt 14 / dư 18 / F1 89.4%). Bản này giữ threshold detector/class toàn cục, tập trung vào các failure mode đã nhìn thấy trong benchmark và ảnh `camera_1(20260928-081907).rar`.

- **Post-Confirm Closure 8.6:** pending Verified Anchor Span không bị hủy bởi đúng một sample bật ngược phía do box jitter; phải có 2 observation ngược liên tiếp mới đóng pending.
- **Anchor Road-edge Closure:** chỉ nhánh Verified Anchor Span được phép dùng corridor margin rất nhỏ 0.006 quanh Road Zone; primary gate vẫn strict.
- **Passage Cycle Re-arm:** `counted_directions` không còn khóa cả vòng đời track. Sau khi xe đã đi xa và cooldown/adaptive release hợp lệ, cùng canonical ID có thể quay vòng và cắt cùng hướng lần nữa — đúng semantics “lượt cắt vạch”.
- **Cross-Frame Bicycle Priority:** giữ nguyên budget scan nhưng ưu tiên weak-motorcycle gần vạch nhất thay vì phụ thuộc thứ tự ByteTrack, giúp case bicycle 04:49 có cơ hội tích lũy trail đúng track.
- **Dashboard auto-height:** panel Camera không còn bị kéo cao bằng cột telemetry; bỏ hard-code `V0.5.41` trong hướng dẫn sửa GT.
- **Version/database:** `VERSION = 0.5.43`, Alembic `0057_cross_closure_v0543`, `schema_version = 0.5.43`; migration chỉ cập nhật version marker, không xóa dữ liệu.

> Hai sai class benchmark (04:49 Xe đạp→Xe máy và 10:41 Ô tô→Xe tải) vẫn được giữ trong audit. V0.5.43 không hạ threshold class toàn cục và không ép van thành ô tô bằng rule ảnh đơn, để tránh làm giảm class accuracy 98.5%.

## Kiểm thử V0.5.43

- Python compile: PASS.
- AI Service: **159/159** unit tests PASS, gồm Post-Confirm jitter hold/cancel, tiny Road-edge closure, passage-cycle re-arm và X-frame priority ordering/budget.
- Backend: **30/30** unit tests PASS bằng SQLite test override.
- Tổng Python unit tests: **189/189** PASS.
- Static PowerShell contract audit: **663/663** marker map trực tiếp PASS + các marker loop/dynamic được kiểm tra riêng.
- Alembic: single head `0057_cross_closure_v0543`, không có missing parent, revision ID đều <= 32 ký tự.
- JSON/YAML source config parse: PASS.
- Sandbox không có PowerShell Windows, Docker Desktop và Node 26 dependency cache; vì vậy `scripts/test.ps1`, Docker full-suite và Vite production build vẫn cần máy Windows đích xác nhận.

---

# Traffic AI V0.5.42 — Full-Source Contract Closure + Compact Telemetry Compatibility

V0.5.42 là bản hotfix tăng version từ V0.5.41 theo policy phát hành mới: **mỗi lần fix phải tăng version**. Bản này không nới threshold AI; mục tiêu là đóng các false-fail contract lịch sử sau khi Dashboard được rút gọn và rà toàn bộ full source trước khi đóng gói.

- Sửa contract **Full-frame Detect + Strict Road Count V0.5.14**: bỏ phụ thuộc literal DETECT/ROI đã được loại khỏi Dashboard; kiểm tra capability thật ở `worker.py`/`runtime.py`.
- Giữ diagnostics frontend `detections_current_frame`, `active_tracks`, `road_tracks_current_frame`.
- Quét toàn bộ các biểu thức frontend `-notmatch` trong `scripts/test.ps1`; không còn marker bắt buộc nào thiếu trong source ở thời điểm đóng gói.
- Thêm contract V0.5.42 bảo vệ Dashboard compact/full-width và telemetry V0.5.14.
- Thêm migration marker dữ liệu-an-toàn `0056_contract_closure_v0542`, `schema_version = 0.5.42`; không xóa dữ liệu.
- Giữ nguyên V0.5.41 Anchor-Span Recovery, Post-Confirm Closure, Bicycle Decision Audit 8.5 và semantics **trên → dưới = IN / dưới → trên = OUT**.

# Traffic AI V0.5.41 — Dashboard Full-Width + Stable IN/OUT Direction Hotfix

- Dashboard desktop dùng toàn bộ chiều rộng khả dụng (`main max-width: none`), giảm vùng trống bên phải; Live AI chia lại Camera/Vehicle Count cho màn hình rộng.
- Bỏ hai đoạn mô tả dài dưới Vehicle Count và bỏ chuỗi `INFERENCE ...` dài cạnh ô chọn Camera; telemetry vẫn nằm trong các ô trạng thái/counter chuyên dụng.
- Chuẩn hóa vạch theo thứ tự trái → phải ở Counting Engine để semantics không bị đảo khi người dùng kéo hai đầu vạch qua nhau: **trên → dưới = IN**, **dưới → trên = OUT**.
- Benchmark overlay và Line Editor dùng cùng semantics với engine; legend hiển thị rõ `↓ IN · ↑ OUT`.
- Thêm regression test cho trường hợp endpoint lưu theo thứ tự phải → trái.
- Cập nhật contract V0.5.33/V0.5.41 để kiểm tra chức năng thật thay vì bắt Dashboard phải giữ văn bản giải thích/changelog.

# Traffic AI V0.5.41 — Verified Anchor-Span Recovery + Post-Confirm Closure + Cross-Frame Bicycle Decision Audit 8.5 🚦🚲

V0.5.41 tiếp tục từ V0.5.40 và tập trung đúng các lỗi benchmark còn lại trong `clip1(4).mp4` / `camera_1(20260927-154039).rar`: crossing đã có quỹ đạo anchor span nhưng primary Gate không phát event, crossing dừng ở bước xác nhận phía sau vạch, và bicycle context X-frame có scan nhưng chưa giải thích được quyết định cuối. Dashboard cũng được rút gọn để chỉ hiển thị telemetry hiện tại; changelog chi tiết được giữ trong README/Release notes.

## Điểm chính V0.5.41

### 1. Verified Anchor-Span Recovery

- **Không hạ ngưỡng primary Gate**. `LineCrossingCounter` giữ nguyên policy đã ổn định.
- Thêm `VerifiedAnchorSpanRescuer` chạy **chỉ sau khi primary Gate trả về không có event**.
- Candidate phải đồng thời thỏa finite counting segment, Road Zone corridor, bounded jump, đủ side depth và chuyển động đủ vuông góc với vạch.
- Span cực rõ có thể đóng ngay; span chưa đủ mạnh chỉ được giữ làm pending candidate.
- Telemetry: `verified_anchor_span_rescues`.

### 2. Post-Confirm Closure

- Pending anchor span không tạo event ngay.
- Khi có observation kế tiếp ở đúng phía đích trong cửa sổ ngắn, crossing mới được đóng.
- Nếu track quay lại phía cũ hoặc hết cửa sổ xác nhận, candidate bị bỏ.
- Telemetry: `post_confirm_closures`.

Defaults:

```env
AI_GATE_ANCHOR_SPAN_RECOVERY=1
AI_GATE_ANCHOR_SPAN_HISTORY_GAP=12
AI_GATE_ANCHOR_SPAN_MIN_NORMAL_RATIO=0.40
AI_GATE_ANCHOR_SPAN_IMMEDIATE_NORMAL_RATIO=0.68
AI_GATE_ANCHOR_SPAN_MAX_JUMP_RATIO=0.12
AI_GATE_ANCHOR_SPAN_MIN_SIDE_RATIO=0.006
AI_GATE_ANCHOR_SPAN_IMMEDIATE_SIDE_RATIO=0.012
AI_GATE_ANCHOR_SPAN_ROAD_MARGIN_RATIO=0.010
AI_GATE_POST_CONFIRM_SAMPLES=2
AI_GATE_POST_CONFIRM_MAX_GAP=6
```

### 3. Cross-Frame Bicycle Decision Audit 8.5

V0.5.40 đã cho phép thu context của weak-motorcycle trước crossing. V0.5.41 giữ nguyên nguyên tắc precision-first nhưng tách **decision** thành hàm thuần và ghi audit reason cho từng geometry-proven crossing. Evidence DOMAIN và GENERAL được phép nằm ở **hai frame khác nhau**, nhưng vẫn phải đủ hai nguồn + hai frame.

Audit fail-closed gồm các reason như `primary_motorcycle_too_strong`, `insufficient_frames`, `insufficient_sources`, `motorcycle_source_veto`, `source_win_missing`, `bicycle_evidence_too_weak`, `fused_bicycle_too_weak`, `fused_margin_reject`, hoặc `accepted`.

Defaults V0.5.40/V0.5.41:

```env
AI_BICYCLE_CONTEXT_XFRAME=1
AI_BICYCLE_CONTEXT_XFRAME_HISTORY=18
AI_BICYCLE_CONTEXT_XFRAME_GATE_DISTANCE_RATIO=0.070
AI_BICYCLE_CONTEXT_XFRAME_INTERVAL=4
AI_BICYCLE_CONTEXT_XFRAME_MAX_PER_FRAME=1
AI_BICYCLE_CONTEXT_XFRAME_MAX_MOTOR_CONF=0.52
AI_BICYCLE_CONTEXT_XFRAME_MIN_SOURCE_CONF=0.08
AI_BICYCLE_CONTEXT_XFRAME_MIN_FRAMES=2
AI_BICYCLE_CONTEXT_XFRAME_MIN_SOURCES=2
AI_BICYCLE_CONTEXT_XFRAME_SOURCE_WIN=0.015
AI_BICYCLE_CONTEXT_XFRAME_MOTOR_VETO=0.10
AI_BICYCLE_CONTEXT_XFRAME_MIN_STRONG=0.14
AI_BICYCLE_CONTEXT_XFRAME_DUAL_CONF=0.30
AI_BICYCLE_CONTEXT_XFRAME_FUSED_MARGIN=0.015
```

### 4. Gate-Span Benchmark Audit 8.5

Frame trace lưu `track_id`, class hiển thị, signed distance chuẩn hóa của motion-leading anchor và box center. Khi detector/tracker/Road Zone/cooldown/confirmation không giải thích được miss, diagnostic chia tiếp:

- `crossing_anchor_span_reject`: anchor đã span hai phía nhưng Gate không có event.
- `crossing_center_only_span`: center span nhưng anchor chưa span đủ.
- `crossing_near_no_span`: track tới gần vạch nhưng chưa có span hai phía.

Trace cũng ghi `bicycle_xframe_decision_audit` để xem chính xác X-frame bị reject/accept vì lý do nào.

### 5. Dashboard cleanup

Dashboard không còn nhồi changelog hoặc đoạn giải thích dài. Panel Vehicle Count chỉ giữ số đếm và telemetry hiện tại; phần chọn Camera cũng không lặp chuỗi INFERENCE dài. Lịch sử thay đổi vẫn nằm trong README/Release notes.

- Sửa false-fail contract V0.5.25 trong `scripts/test.ps1`: kiểm tra trực tiếp các telemetry key `human_guard_pending_crossings`, `human_guard_deferred_commits`, `bracket_confirm_rescues` thay vì bắt Dashboard phải giữ literal lịch sử `Crossing Engine 7.2`.

### 6. Giữ nguyên V0.5.39 infrastructure guard

- EOL policy: PowerShell CRLF; source/config LF; bổ sung explicit LF cho `.gitattributes`, `.gitignore`, `**/.dockerignore`, `*.txt`.
- `scripts/postgres-info.ps1` kiểm tra container health, `pg_isready`, TCP host port và password authentication; thông tin pgAdmin lấy từ `.env`.
- pgAdmin Desktop dùng host `127.0.0.1` + `POSTGRES_HOST_PORT` (mặc định `5445`), không dùng `postgres:5432` từ Windows.

## Database / migration

Chuỗi marker migration bảo toàn dữ liệu:

```text
0052_bike_ultra_v0538
  -> 0053_release_db_v0539
  -> 0054_bike_gate_v0540
  -> 0055_span_recovery_v0541
```

`schema_version = 0.5.41`. Các migration V0.5.39–V0.5.41 chỉ cập nhật marker version, không xóa bảng/dữ liệu.

## Benchmark đầu vào đã đối chiếu

Replay V0.5.41 mới nhất do máy đích ghi nhận ở Session #143 / Benchmark #23 (28/09/2026):

```text
GT                  149
AI                  153
Khớp                135
Lọt                  14
Dư                   18
Sai số tổng           +4
Recall              90.6%
Precision           88.2%
F1                  89.4%
Class đúng          98.5%
```

So với benchmark trước, số khớp tăng 1, lọt giảm 1 và dư giảm 1. Hai lỗi class còn thấy rõ trong report là `04:49.450 GT Xe đạp -> AI Xe máy` và `10:41.981 GT Ô tô -> AI Xe tải`. Bộ snapshot `camera_1(20260928-071404).rar` có frame gần đúng cả hai timecode (frame 7242/7250 và frame 16049), dùng làm evidence cho vòng tinh chỉnh class tiếp theo. Đây là số đo replay trên máy đích, không phải số suy đoán từ sandbox đóng gói.

## Kiểm thử

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\test.ps1
```

Bộ unit test bao gồm regression cho Cross-Frame Bicycle Decision, strict anchor-span recovery, Post-Confirm Closure và Gate-Span Audit. Ở môi trường đóng gói V0.5.42: Python compile PASS, AI Service `153/153` PASS, Backend `30/30` PASS (tổng `183/183`), Alembic single head = `0056_contract_closure_v0542`, JSON/YAML config PASS. Vite/Docker/PowerShell end-to-end vẫn phải được `scripts\test.ps1` xác nhận trên máy Windows đích vì sandbox đóng gói không có Docker/PowerShell và không có npm dependency cache. Contract Smooth Playback hiện kiểm tra capability thật (`nativeVideoUrl`, `overlayStreamUrl`, `previewMode`, runtime lag/progress) thay vì bắt Dashboard phải hiện chuỗi telemetry/changelog đã được yêu cầu loại bỏ.

## Chạy hệ thống

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\start.ps1
```

Dashboard: `https://traffic-ai.test:8443`  
API Docs: `https://traffic-ai.test:8444/docs`

Kiểm tra PostgreSQL/pgAdmin:

```powershell
.\scripts\postgres-info.ps1
```

## Phát hành một lệnh

Sau khi source chạy ổn:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
.\scripts\publish.ps1
```

Script tiếp tục test → commit/push → tag theo `VERSION` → kích hoạt GitHub Actions → tạo GitHub Release/fallback bằng GitHub CLI.

---

## Lịch sử trước V0.5.41

### Traffic AI V0.5.38 — Near-Margin Bicycle Context + Ultra-Spatial Rescue Signature 8.3 🚲🎯

V0.5.38 được xây từ source V0.5.37-R1 và benchmark mới của `clip1.mp4` (GT 149) cùng 184 snapshot trong `camera_1(20260927-123141).rar`. V0.5.37 đã cải thiện precision counting nhưng chưa thay đổi số GT khớp và nhánh bicycle context vẫn chưa promote được ca 04:49.

Benchmark V0.5.37 nhận được:

```text
GT                  149
AI                  154
Khớp                134
Lọt                  15
Dư                   20
Recall              89.9%
Precision           87.0%
F1                  88.4%
Class đúng          99.3%
```

So với V0.5.36, số dư đã giảm `22 -> 20`; telemetry `2W spatial = 2` xác nhận Spatial Rescue Signature 8.2 đã loại được hai duplicate mà không đổi recall. Tuy nhiên Benchmark vẫn còn `6` event dư sát GT đã khớp + cùng điểm cắt, và bicycle telemetry là `Bike ctx match = 9` nhưng `Bike weak-MC = 0`, `Bike margin = 0`, `Bike context = 0`. Snapshot `frame_7242` vẫn cho primary `motorcycle ~0.49` ở ca GT Xe đạp 04:49.450.

## 1. Near-Margin Bicycle Context

V0.5.37 yêu cầu mỗi refiner bicycle phải thắng motorcycle theo margin tương đối rõ. V0.5.38 thêm một fallback hẹp hơn, chỉ mở khi primary motorcycle cực yếu (`<= 0.50`) và có đủ **hai nguồn context độc lập**.

Fallback mới yêu cầu đồng thời:

- mỗi nguồn có bicycle target-match tối thiểu `0.10`;
- ít nhất một nguồn cho bicycle thắng motorcycle `>= 0.02`;
- không nguồn nào được cho motorcycle thắng bicycle quá `0.08` (motorcycle veto);
- fused bicycle `>= 0.28`;
- fused bicycle vẫn phải thắng fused motorcycle ít nhất `0.02`;
- motorcycle primary mạnh hơn `0.50` không được dùng nhánh này.

Telemetry mới: `Bike near-M`.

Mục tiêu là ca 04:49.450: cho phép hai refiner gần hòa nhưng cùng nghiêng về bicycle cứu một primary motorcycle 0.49, trong khi scooter có motorcycle-context mạnh vẫn bị veto.

## 2. Ultra-Spatial Rescue Signature 8.3

V0.5.37 đã dedup được 2 event (`2W spatial = 2`) nhưng Benchmark còn 6 spatial duplicate candidates. V0.5.38 không nới `direct/direct`. Chỉ cặp có `rescued` hoặc `interpolated` mới được dùng tail mới:

```text
rescued involved     : Δt <= 1.02 s và Δcross <= 0.008
interpolated involved: Δt <= 0.90 s và Δcross <= 0.007
direct/direct        : không dùng ultra tail
```

Backend query window tăng lên 1.05 s chỉ để nhìn thấy candidate; generic signature vẫn giữ `0.22 s`, còn four-wheel semantic guard vẫn giữ giới hạn riêng cũ. Telemetry mới: `2W ultra`.

## 3. Benchmark spatial audit chi tiết hơn

Mỗi `spatial_duplicate_near_gt` giờ trả thêm:

- `near_matched_time_delta`;
- `near_matched_spatial_distance`;
- `near_matched_crossing_method`;
- detail có cặp method, ví dụ `direct -> rescued`.

Nhờ đó bản sau có thể phân biệt rõ duplicate do rescue/interpolation với hai xe thật chạy gần nhau, thay vì tiếp tục nới threshold theo cảm tính.

## 4. Phần giữ nguyên

- Center-Gate Rescue 8.0 vẫn giữ vì `2W center = 9` và là nguồn tăng recall lớn từ V0.5.34.
- Không siết generic long-gap rescue ở V0.5.38 vì Benchmark vẫn còn 8 miss kiểu Crossing Gate không phát event; siết rescue toàn cục có nguy cơ đổi false-positive thành false-negative.
- Truck Semantic Lock / Canonical 4W Fusion giữ nguyên; benchmark hiện vẫn cho `Xe tải = 2` lượt cắt vạch.
- Deterministic Replay, Confidence-aware Time Sync, Human Guard 2.1 và Road Zone giữ nguyên.

Database: `0052_bike_ultra_v0538`, `schema_version = 0.5.38`. Không xóa dữ liệu.

---

# Traffic AI V0.5.37-R1 — Historical 2W Signature Contract Hotfix 🔧

R1 không đổi runtime/AI/database của V0.5.37. Hotfix chỉ sửa `scripts/test.ps1` để contract lịch sử V0.5.35 nhận cả implementation cũ `two-wheel-rescue-signature` và successor V0.5.37 `two-wheel-spatial-signature`. V0.5.37 đã nâng `_two_wheel_rescue_signature_duplicate` thành `_two_wheel_spatial_signature_duplicate`, nên việc bắt literal reason cũ làm local test fail oan dù backend vẫn giữ semantics dedup hẹp và regression tests.

- `VERSION` vẫn là `0.5.37`.
- Alembic vẫn là `0051_bike_comp_v0537`.
- Không đổi `.env`, model, benchmark, database hoặc thuật toán đếm.

---

# Traffic AI V0.5.37 — Competitive Bicycle Context + Spatial Rescue Signature 8.2 🚲🎯

V0.5.36 giữ nguyên baseline GT 149 (`156 AI / 134 khớp / 15 lọt / 22 dư / F1 87.9% / class 99.3%`). Telemetry cho thấy `Bike ctx match = 4` nhưng `Bike weak-MC = 0`, nên context đã tìm đúng vùng bicycle nhưng rule tuyệt đối vẫn chưa đủ để cứu `04:49.450`. Spatial audit cũng cho thấy 7 event dư vừa gần thời gian vừa gần điểm cắt của một GT đã khớp.

V0.5.37 xử lý hai điểm này theo hướng precision-first:

- **Competitive Bicycle Context**: mỗi refiner context trả cả bicycle và motorcycle trên cùng target. Một primary `motorcycle` yếu (`<= 0.55`) chỉ được đổi thành bicycle khi bicycle thắng motorcycle theo margin trên cùng vùng hình học. Dual-source có thể dùng confidence tuyệt đối thấp hơn vì đã có đối chứng class; single-source vẫn cần temporal evidence. Telemetry mới: `Bike margin`.
- **Spatial Rescue Signature 8.2**: backend chỉ mở rộng dedup time window cho cặp two-wheel có `rescued/interpolated`, đồng thời siết crossing-point distance. `direct/direct` không được nới. Telemetry mới: `2W spatial`.

Database: `0051_bike_comp_v0537`, `schema_version = 0.5.37`. Không xóa dữ liệu.

---

# Traffic AI V0.5.36 — Weak-Motor Dual Context + Spatial Benchmark Audit 🚲🔎

V0.5.35 trên GT 149 giữ nguyên counting so với V0.5.34 (`156 AI / 134 khớp / 15 lọt / 22 dư`) nhưng telemetry đã xác định đúng nút thắt mới: `Bike ctx match = 4` trong khi `Bike context = 0`, `Bike trail = 0`; tức crop/matcher đã nhìn thấy bicycle candidate nhưng cổng quyết định vẫn quá chặt. Đồng thời `2W dedup = 0` cho thấy 10 mục benchmark gắn nhãn “event dư gần GT” chưa đủ bằng chứng để xóa runtime chỉ dựa vào thời gian.

V0.5.36 xử lý hai điểm an toàn:

- **Weak-Motor Dual Context**: chỉ khi detector đang gọi `motorcycle` với confidence yếu (`<= 0.62`) và **cả refiner miền + refiner chung** cùng target-match bicycle, runtime được dùng ngưỡng fused thấp hơn (`0.58`). Motorcycle confidence cao hoặc single-source guess vẫn không được phép đổi class. Đây là nhánh nhắm đúng trường hợp `04:49.450`, nơi snapshot cho thấy detector motorcycle khoảng `0.49` nhưng bicycle context đã match.
- **Spatial Benchmark Audit**: chẩn đoán `duplicate_near_gt` giờ kiểm tra thêm `crossing_x/y`. Chỉ event vừa gần thời gian vừa gần điểm cắt (`<= 0.045`) mới được gọi `spatial_duplicate_near_gt`; hai xe đi gần thời gian nhưng ở vị trí khác trên vạch sẽ quay về chẩn đoán theo crossing method thay vì bị gắn nhãn duplicate quá sớm.

Telemetry mới: `Bike weak-MC`.

Database: `0050_bike_spatial_v0536`, `schema_version = 0.5.36`. Không xóa dữ liệu.

---

# Traffic AI V0.5.35 — Bicycle Context Trail + 2W Rescue Signature 8.1 🚲🛵🎯

V0.5.34 trên GT 149 đã tăng **khớp 126 → 134**, giảm **lọt 23 → 15**, Recall **84.6% → 89.9%** và F1 **85.1% → 87.9%**. `2W center = 9` trong khi số khớp tăng 8 và đếm dư chỉ tăng 1, vì vậy V0.5.35 giữ nguyên Center-Gate Rescue 8.0 thay vì rollback. Hai điểm còn lại được xử lý riêng:

- `Bike context = 0` và lỗi class duy nhất vẫn là `04:49.450 GT Xe đạp → AI Xe máy`: matcher context mới chấp nhận refiner nhìn toàn bộ bicycle trong khi ByteTrack chỉ giữ box bánh trước/giỏ, sau đó có thể kết hợp với evidence target-matched từ các frame trước vạch.
- Benchmark còn nhiều event `duplicate_near_gt` / rescue gap dư: backend có **2W Rescue Signature 8.1**, chỉ mở rộng dedup khi cặp cùng hướng/cùng family ở rất sát điểm crossing và ít nhất một event là rescue/interpolation. Direct/direct không bị nới để bảo vệ hai xe thật chạy sát nhau.

Telemetry mới: `Bike ctx match`, `Bike trail`, `2W dedup`.

Database: `0049_two_wheel_sig_v0535`, `schema_version = 0.5.35`. Không xóa dữ liệu.

---

# Traffic AI V0.5.34 — Two-Wheel Context + Center-Gate Rescue 8.0 🚲🛵🎯

V0.5.34 được xây từ replay deterministic V0.5.33 trên `clip1.mp4` / GT 149 và 176 snapshot trong `camera_1(10).rar`. Baseline mới đã giữ được precision class rất cao nhưng counting geometry vẫn là nút thắt:

```text
GT                  149
AI                  147
Khớp                126
Lọt                  23
Dư                   21
Recall              84.6%
Precision           85.7%
F1                  85.1%
Class đúng          99.2%
```

Benchmark chỉ còn **1 lỗi class đã khớp rõ ràng**: `04:49.450 · GT Xe đạp → AI Xe máy`. Snapshot cho thấy người áo xanh đi xe đạp nhưng box detector chủ yếu ôm phần bánh trước/giỏ, vì vậy crop target thông thường không thấy đủ rider + khung xe. Một xe đạp thật khác ở gần cuối clip cũng có box hai bánh hẹp và có nguy cơ nằm trong nhóm crossing miss.

## 1. Crossing-only Bicycle Context Rescue

V0.5.33 vẫn giữ nguyên chính sách bicycle precision chặt để scooter không bị đổi thành xe đạp. V0.5.34 **không hạ các threshold đó**. Thay vào đó, chỉ khi geometry đã chứng minh một crossing hai bánh nhưng event vẫn là `motorcycle`, runtime chạy tối đa một lượt context rescue trên frame:

```text
box tracker hẹp (bánh trước / giỏ)
        ↓
geometry crossing thật
        ↓
crop rộng hơn quanh đúng target
        ↓
best.pt DOMAIN + YOLO26m GENERAL
        ↓
2 nguồn cùng ủng hộ bicycle
HOẶC 1 nguồn cực mạnh
        ↓
BIKE-CTX+ → bicycle
```

Một medium one-shot bicycle guess vẫn không được phép lật scooter. Context rescue chỉ chạy tại crossing nên không làm hàng nghìn track roadside đổi class.

Telemetry mới:

```text
Bike context
```

## 2. Strict Two-Wheel Center-Gate Rescue 8.0

Baseline V0.5.33 còn `11 Crossing Gate không phát event + 7 chưa đủ xác nhận phía sau vạch`. Với xe hai bánh, motion-leading anchor có thể nhảy khi detector chuyển từ rider+xe sang chỉ bánh trước/đuôi xe. V0.5.34 bổ sung cổng center trajectory **sau khi primary gate không phát crossing**.

Cổng phụ chỉ chấp nhận khi đồng thời thỏa:

- canonical track hai bánh đã đủ history;
- center thật sự giao finite counting segment;
- crossing không nằm sát endpoint;
- gap ngắn (`12` frame mặc định);
- normal motion mạnh (`>= 0.42`);
- jump bị giới hạn (`<= 0.10` diagonal);
- hai phía đủ sâu khỏi dead-band;
- hai center + corridor đều hợp lệ trong Road Zone.

Khi primary gate đã đếm, center rescue không tạo event thứ hai. Khi center rescue chứng minh crossing trước, `register_external_crossing()` ghi state ngược vào primary gate để chặn duplicate về sau.

Telemetry mới:

```text
2W center
```

## 3. Không thay đổi phần đã ổn

- Deterministic Replay V0.5.32 giữ nguyên.
- Bicycle Precision 4.0 / GT Class Audit V0.5.33 giữ nguyên.
- Truck Semantic Lock + Canonical 4W Fusion giữ nguyên; `Xe tải = 2` vẫn là 2 **lượt cắt vạch** của cùng chiếc van quay lại, không phải 2 van vật lý.
- Confidence-aware Time Sync, Human Guard 2.1, Heavy center rescue và backend dedup giữ nguyên.

Database:

```text
0047_two_wheel_v0533
        ↓
0048_two_wheel_gate_v0534
schema_version = 0.5.34
```

---

# Traffic AI V0.5.33-R2 — Benchmark Class Audit UI Hotfix 🧩

Hotfix R2 không đổi AI runtime, model, database hay migration. Bản này chỉ sửa giao diện danh sách **Sai loại phương tiện** của GT Class Audit: panel báo cáo hẹp trước đây ép 4 cột (timecode / GT / AI / dropdown) trên cùng một hàng nên chữ bị xuống dòng từng từ, chồng lấn và select bị co. R2 chuyển mỗi dòng sang layout 3 tầng ổn định: `timecode + GT` → `AI` → `dropdown sửa GT` full-width, đồng thời chừa gutter cho scrollbar để nội dung không bị che.

`scripts/test.ps1` bổ sung regression contract cho layout này. `VERSION` vẫn là `0.5.33`; Alembic head vẫn `0047_two_wheel_v0533`; `schema_version` vẫn `0.5.33`.

---

# Traffic AI V0.5.33-R1 — Historical Contract Hotfix 🔧

Hotfix R1 không thay đổi AI runtime, model, database hay migration. Bản này sửa hai historical contract trong `scripts/test.ps1` bị khóa vào default cũ sau khi V0.5.33 siết Bicycle Precision:

- V0.5.26 không còn bắt buộc `.env.example` phải giữ `AI_BICYCLE_REFINE_OVERRIDE_CONF=0.58`; contract kiểm tra setting hiện tồn tại và `start.ps1` vẫn có migration `0.58 -> 0.90`.
- V0.5.29 không còn bắt buộc `.env.example` phải giữ `AI_BICYCLE_CONSENSUS_MIN_HITS=3`; contract kiểm tra setting hiện tồn tại và `start.ps1` vẫn có migration `3 -> 4`.
- `VERSION` vẫn là `0.5.33`; Alembic head vẫn là `0047_two_wheel_v0533`; `schema_version` vẫn là `0.5.33`.

---

# Traffic AI V0.5.33 — Bicycle Precision 4.0 + GT Class Audit + Passage Semantics 🚲🛵🚚

V0.5.33 được tạo sau khi đối chiếu hai replay deterministic V0.5.32 trên cùng `clip1.mp4` và 352 snapshot trong `camera_1(9).rar` (176 frame ứng viên, mỗi frame xuất hiện đúng hai lần giữa hai replay). Hai lượt đều cho cùng `147` crossing, xác nhận replay đã ổn định.

## Kết luận kiểm tra clip trước khi sửa

- **Van/xe tải:** trong clip chỉ có **một chiếc van màu trắng-xanh**, nhưng chiếc xe này **cắt vạch hai lần** ở hai thời điểm khác nhau (xấp xỉ `10:42.9` và `14:43.1`, hai hướng khác nhau). Dashboard đang đo **lượt cắt vạch**, vì vậy `Xe tải = 2` là đúng theo semantics đếm lượt, không có nghĩa có hai chiếc van khác nhau. V0.5.33 bổ sung giải thích ngay trên Dashboard để tránh nhầm giữa *số xe vật lý duy nhất* và *số lượt qua vạch*.
- **Xe đạp/xe máy:** `Xe đạp = 4` ở V0.5.32 chưa đúng. Review khung hình cho thấy hai lượt xe đạp thực sự nổi bật quanh `04:49` và `15:22`; một số scooter đã bị bicycle consensus promote nhầm.
- **Ground Truth cũng có nhãn class sai:** các mốc `10:39.119`, `14:24.671`, `15:04.244` đang ghi GT `Xe đạp` nhưng khung hình cho thấy phương tiện là scooter/xe máy. Vì vậy không được dùng toàn bộ 7 dòng `Sai loại phương tiện` để tune model một cách mù quáng.

Theo 149 lượt GT hiện có, sau khi audit class thủ công, phân bố hợp lý nhất của clip là khoảng **145 lượt xe máy + 2 lượt xe đạp + 2 lượt van/xe tải = 149 lượt**. Đây là phân bố theo *lượt cắt vạch*, không phải số phương tiện vật lý duy nhất.

## Bicycle Precision 4.0

Bicycle rescue được siết theo ba tầng:

- consensus bicycle tối thiểu `4` frame thay vì `3`; fused confidence `0.78`, margin so với motorcycle `0.16`, strongest hit `0.45`;
- ưu tiên ít nhất `2` nguồn refiner độc lập (`best.pt` domain + YOLO26m general); một nguồn duy nhất chỉ được cứu khi lặp nhiều frame và có hit rất mạnh `>=0.88`;
- one-shot bicycle override tăng `0.58 → 0.90`, nên một dự đoán bicycle vừa phải không còn dễ biến scooter thành xe đạp. Strong repeated primary-bicycle path vẫn được giữ để xe đạp rõ không bị ép thành motorcycle.

## GT Class Audit

Benchmark cho phép sửa trực tiếp `vehicle_type` của một Ground Truth mark bằng dropdown. PATCH giữ nguyên timecode/frame/direction, do đó không cần xóa rồi đánh dấu lại 149 mốc chỉ để sửa `Xe đạp ↔ Xe máy`.

## Passage semantics

Dashboard ghi rõ các số theo loại là **lượt cắt vạch**: cùng một xe quay lại và cắt vạch lần nữa được tính thêm một lượt. Không thêm long-window dedup cho chiếc van, vì làm vậy sẽ xóa một crossing thật.

Database:

```text
0046_replay_time_v0532
        ↓
0047_two_wheel_v0533
schema_version = 0.5.33
```

---

# Traffic AI V0.5.32-R1 — Historical Contract Hotfix

Hotfix này không đổi AI/runtime/database. Nó chỉ sửa historical contract V0.5.30 trong `scripts/test.ps1`: UI V0.5.32 đã đổi nhãn `Gộp ID 4W` thành `Gộp canonical 4W`, nhưng test cũ vẫn bắt literal cũ nên chặn oan. R1 kiểm tra semantic keys thật (`truck_semantic_locks`, `truck_crossing_tracks`, `four_wheel_duplicate_suppressed`) và warning truck thay vì khóa wording UI. `VERSION` vẫn là `0.5.32`, Alembic vẫn `0046_replay_time_v0532`.

---

# Traffic AI V0.5.32 — Deterministic Replay + Confidence-aware Time Sync 🎯

V0.5.32 được tạo từ benchmark thật V0.5.31 / GT 149. V0.5.31 đã sửa được startup duplicate và một số timestamp rescue, nhưng lần chạy mới chỉ còn `AI 143 / khớp 125 / lọt 24 / dư 18`, trong khi V0.5.30 từng đạt `AI 149 / khớp 130 / lọt 19 / dư 19`. Telemetry `Time-sync 141` cho thấy geometric timestamp đã áp dụng quá rộng; đồng thời hai lần replay cùng clip ở các build trước cho thấy worker candidate có thể dao động vài crossing.

V0.5.32 xử lý hai tầng:

- **Deterministic local-video replay**: cố định Python/NumPy/OpenCV/PyTorch seed, tắt CuDNN benchmark, bật deterministic algorithms ở chế độ warn-only, tắt TF32, và chờ refiner + Human Guard warmup xong trước frame đầu. RTSP/live không bị ép vào chế độ này.
- **Confidence-aware Time Sync**: direct crossing giữ frame quan sát; interpolated chỉ được lùi tối đa `0.24 s`; rescued tối đa `0.72 s`. Geometric time vẫn được dùng nhưng long-gap back-shift bị clamp thay vì nội suy tuyến tính vô hạn qua perspective.
- **Canonical 4W telemetry cleanup**: `Gộp canonical 4W` chỉ tăng khi thật sự hợp nhất hai canonical state; raw CAR/TRUCK box overlap theo frame vẫn có telemetry tức thời riêng nhưng không còn làm số cumulative phình lớn.

Telemetry mới/bổ sung:

```text
Replay ổn định
Aux sẵn từ đầu
Time-sync
Time-clamp
Gộp canonical 4W
```

Database:

```text
0045_cross_time_v0531
        ↓
0046_replay_time_v0532
schema_version = 0.5.32
```

---

# V0.5.31-R1 — GitHub Actions Release/CI workflow hotfix

Hotfix này không đổi AI/runtime/database. Nó sửa workflow GitHub Actions bị GitHub từ chối trước khi tạo job vì dùng `${{ runner.temp }}` ở job-level `env`. Runtime path nay được tạo trong step bằng `$RUNNER_TEMP` và truyền qua `$GITHUB_ENV`. Đồng thời npm cache của `setup-node` được tắt vì source hiện không commit `frontend/package-lock.json`; tránh blocker cache kế tiếp. `scripts/test.ps1` có regression contract để lỗi này không quay lại.

> `VERSION` vẫn là `0.5.31`; tag `v0.5.31` đã phát hành rồi thì không chạy `publish.ps1` lại với tag này. Commit/push hotfix vào `main`; bản version kế tiếp sẽ dùng workflow đã sửa.

---

# Traffic AI V0.5.31 — Geometric Crossing Time + Startup Ghost Guard ⏱️🎯

V0.5.31 được tạo từ benchmark thật V0.5.30 / GT 149. V0.5.30 đã sửa đúng semantic van/xe tải: Dashboard hiện `Xe tải = 2`, `Xe tải xác nhận = 2`, `Khóa class tải = 2`, `Xe tải cắt vạch = 2`. Tuy nhiên tổng `AI = 149` vẫn chỉ khớp `130`, còn `19 lọt + 19 dư`.

Dữ liệu benchmark cho thấy một nút thắt mới nằm ở **thời điểm event** chứ không chỉ ở việc có/không có crossing. Ví dụ GT `02:39.148` bị báo lọt trong khi AI có event `02:39.920`: lệch `0.772 s`, chỉ hơn cửa sổ ghép `0.75 s` đúng `0.022 s`. Với rescued/interpolated track, runtime cũ đóng dấu thời gian ở frame *xác nhận* sau vạch thay vì frame mà trajectory thực sự cắt vạch. Điều này có thể biến một xe thật thành đồng thời `1 lọt + 1 dư`.

## 1. Geometric Crossing Time

Mỗi crossing giờ lưu thêm vị trí frame thực tại giao điểm giữa trajectory và finite counting line:

```text
observation trước vạch @ frame A
            ↓
       giao điểm thật
            ↓
observation sau vạch @ frame B

source_time = nội suy A ↔ B tại giao điểm
```

`VehicleEvent.source_time_seconds` không còn mặc định dùng frame xác nhận `B`. Direct crossing chỉ dịch rất ít; interpolated/rescued crossing có thể dịch ngược đúng vài frame hoặc hàng chục frame. Geometry/count không đổi, chỉ timestamp persistence được đưa về thời điểm vật lý cắt vạch.

Telemetry mới:

```text
Time-sync
```

chỉ tăng khi timestamp được hiệu chỉnh ít nhất `0.5 frame`.

## 2. Heavy-center cũng dùng crossing time thật

`HeavyVehicleCrossingRescuer` V0.5.29/V0.5.30 giờ cũng nội suy crossing frame từ center trajectory. Khi van/truck bị cứu qua gap, event giữ class/canonical track của V0.5.30 nhưng timestamp phản ánh giao điểm thật, không phải frame cuối của gap.

## 3. Startup Ghost Guard

Benchmark V0.5.30 vẫn còn event dư `00:00.360` trong khi đầu clip đã có crossing thật gần đó. V0.5.31 thêm một backend signature guard cực hẹp chỉ trong 1 giây đầu video:

```text
same direction + same vehicle family
+ time <= 0.45 s
+ crossing point distance <= 0.040 normalized
→ startup-crossing-signature dedup
```

Guard này không nới cho toàn clip và không gộp hai xe cách xa nhau trên vạch.

## 4. Human Guard transaction vẫn giữ đúng event-time

Nếu crossing hai bánh phải chờ frame sau để xác nhận rider/pedestrian, pending transaction giữ riêng `observed_frame_index` để timeout không bị ảnh hưởng bởi timestamp nội suy; event commit cuối vẫn dùng source frame/time tại giao điểm thật.

Database:

```text
0044_truck_lock_v0530
        ↓
0045_cross_time_v0531
schema_version = 0.5.31
```

---

# Traffic AI V0.5.30 — Truck Semantic Lock + Canonical 4W Fusion 🚚🔒

V0.5.30 được tạo từ benchmark thật V0.5.29 / GT 149. Ảnh snapshot cho thấy **cùng canonical track van `#286423`** đã từng là `truck` với semantic certainty cao khi còn ở xa, nhưng ngay sát vạch lại rơi về `car`. Dashboard đồng thời hiển thị `Gộp car/truck 2172`, vì telemetry cũ cộng lại cùng một cặp box ở mọi frame nên dễ bị hiểu nhầm là số xe.

Bản này sửa ba lớp:

- **Truck Semantic Lock**: chỉ khóa `truck` sau bằng chứng bền vững (stable detector hoặc refiner consensus nhiều frame), giữ tối đa 450 frame để close-up ở vạch không làm `truck → car`; lock vẫn tự hết hạn và chỉ áp dụng family bốn bánh.
- **Canonical 4W state fusion**: khi CAR/TRUCK/BUS box trùng nhau đổi raw ID, không chỉ alias ByteTrack ID mà còn nhập history của Strict Gate, Heavy-center, label smoother, refiner evidence và telemetry về cùng canonical track.
- **Unique 4W telemetry + backend semantic dedup**: `Gộp ID 4W` chỉ đếm cặp raw-ID duy nhất thay vì cộng lặp mỗi frame; backend có thêm guard ngắn cho cross-class `car ↔ truck/bus` cùng crossing signature để một van đổi class/ID không tạo hai event.

Telemetry mới:

```text
Xe tải xác nhận
Khóa class tải
Xe tải cắt vạch
Gộp ID 4W
```

Warning chỉ xuất hiện **sau khi phiên hoàn tất**, khi đã có Truck Semantic Lock nhưng database vẫn chưa có event `truck`; nội dung cũng nói rõ `Gộp ID 4W` không phải số xe tải.

Database:

```text
0043_heavy_track_v0529
        ↓
0044_truck_lock_v0530
schema_version = 0.5.30
```

---

# Traffic AI V0.5.29-R2 — Forward-Compatible Historical UI Contracts

V0.5.29-R2 không thay đổi AI runtime, model, database hay migration. Hotfix này tiếp tục xử lý bộ kiểm thử lịch sử: V0.5.27 từng bắt buộc frontend phải còn nguyên slogan `Dual Refiner Consensus 4.0`, trong khi V0.5.29 đã thay phần mô tả UI nhưng vẫn giữ đầy đủ telemetry `general_refine_checks`, `truck_tracks_seen`, `truck_crossing_tracks`, `Refiner chung`, `Xe tải thấy`, `Xe tải cắt vạch`.

- Contract V0.5.27 giờ kiểm tra **semantic telemetry** thay vì một chuỗi slogan giao diện.
- Contract V0.5.28 cũng được chuyển sang kiểm tra `video_start_rescues` + `heavy_anchor_tracks`, tránh lỗi tương tự ở bản sau.
- Giữ nguyên hotfix R1 cho `HEAVY_CONFLICTS` / `FOUR_WHEEL_CONFLICTS`.
- `VERSION` vẫn là `0.5.29`; migration vẫn là `0043_heavy_track_v0529`.

---

# Traffic AI V0.5.29-R1 — Legacy Contract Hotfix

V0.5.29-R1 không thay đổi AI runtime, model, database hay migration. Hotfix này chỉ sửa tính tương thích kiểm thử sau khi V0.5.29 đổi tên tập class duplicate guard từ `HEAVY_CONFLICTS` sang `FOUR_WHEEL_CONFLICTS`.

- Giữ alias `HEAVY_CONFLICTS = FOUR_WHEEL_CONFLICTS` để contract lịch sử V0.5.17 vẫn nhận diện được implementation.
- `scripts/test.ps1` chấp nhận cả tên cũ lẫn tên mới, tránh historical test chặn release mới.
- `VERSION` vẫn là `0.5.29`; migration vẫn là `0043_heavy_track_v0529`.

---

# Traffic AI V0.5.29 — Heavy Track Fusion + Center-Gate Rescue + Bicycle Precision 🚚🚲🎯

V0.5.29 được xây trực tiếp từ benchmark thật V0.5.28 trên cùng `clip1.mp4` / GT 149. Bản này không đổi model nền và chưa yêu cầu train lại `best.pt`; nó tập trung vào hai vấn đề còn thấy rõ sau V0.5.28:

- **Van/xe tải trắng đã được AI nhận ra nhưng vẫn không phát crossing**: Dashboard V0.5.28 ghi `Xe tải thấy 25`, `Xe lớn anchor 73` nhưng `Xe tải cắt vạch 0` và `Xe tải 0`, trong khi video gốc xác nhận chiếc van thực sự cắt vạch khoảng 14:40–14:44.
- **Bicycle consensus bắt đầu cứu được xe đạp nhưng hơi quá nhạy**: số xe đạp tăng, tuy nhiên benchmark V0.5.28 xuất hiện thêm một số `GT Xe máy → AI Xe đạp`. Vì vậy V0.5.29 siết lại bằng chứng bicycle thay vì hạ threshold tiếp.

## Kết quả đầu vào V0.5.28

```text
Ground truth       149
AI đếm             146
Khớp               130
Lọt                  19
Đếm dư               16
Recall              87.2%
Precision           89.0%
F1                  88.1%
Class đúng          94.6%
```

So với V0.5.27, V0.5.28 tăng `Khớp 129 → 130`, giảm `Lọt 20 → 19`, giữ `Đếm dư = 16`, nhưng class accuracy giảm `95.3% → 94.6%`. Vì vậy bản này ưu tiên **giữ recall crossing**, đồng thời giảm false bicycle promotion.

## 1. Heavy Track Fusion — gộp CAR/TRUCK/BUS của cùng một van

COCO detector có thể đổi nhãn một chiếc van qua nhiều frame:

```text
car → truck → car → bus → truck
```

NMS mặc định theo class có thể để hai box bốn bánh khác class cùng tồn tại trên một frame, làm ByteTrack cấp nhiều raw ID cho cùng một xe. V0.5.29 mở rộng Single-Object Guard thành nhóm bốn bánh:

```text
CAR / TRUCK / BUS
      + IoU cao
      + cùng frame
          ↓
    giữ box mạnh nhất
          ↓
 alias raw ID còn lại
          ↓
  một canonical track
```

Chỉ các box **khác class trong cùng family bốn bánh** mới được gộp. Hai xe thật cùng class hoặc xe hai bánh không bị gom theo rule này.

Telemetry:

```text
Gộp car/truck
```

## 2. Heavy-specific Track Stitching — nối lại ID van qua gap dài hơn

Xe van/truck tiến gần camera làm bounding box phình nhanh, đôi khi bị che hoặc đổi ID lâu hơn xe máy. V0.5.29 giữ cửa sổ stitch cũ cho xe hai bánh nhưng cấp cửa sổ riêng cho bốn bánh:

```ini
AI_STITCH_HEAVY_MAX_GAP=90
AI_STITCH_HEAVY_DISTANCE_RATIO=0.18
```

Với gap dài, resolver không tin tuyệt đối velocity cũ ở xa camera vì perspective có thể làm dự đoán vượt quá vị trí thật. Nó so cả **predicted distance** và **direct distance**, chỉ dùng chính sách này cho family bốn bánh.

Telemetry:

```text
Nối track xe lớn
```

## 3. Center-Gate Rescue — cổng cứu thứ hai cho van/truck

Heavy-Vehicle Anchor Inset V0.5.28 vẫn là cổng chính. V0.5.29 không thay nó bằng center; center chỉ được dùng khi **strict anchor gate đã không phát event**.

```text
four-wheel track
      ↓
Strict anchor gate
      ↓
  có crossing? ── YES → dùng event cũ
      │
      NO
      ↓
center trajectory
      +
finite counting segment
      +
bounded gap
      +
normal motion
      +
Road Zone corridor
      ↓
HEAVY-C+
      ↓
register vào primary counter
      ↓
VehicleEvent
```

Cấu hình:

```ini
AI_HEAVY_CENTER_RESCUE=1
AI_HEAVY_CENTER_HISTORY_GAP=90
AI_HEAVY_CENTER_MIN_NORMAL_RATIO=0.20
AI_HEAVY_CENTER_ROAD_MARGIN_RATIO=0.020
```

Khi center rescue thành công, crossing được **register ngược vào LineCrossingCounter** để strict gate không đếm lại cùng hướng khi anchor phục hồi vài frame sau.

Telemetry:

```text
Xe lớn cứu center
```

## 4. Bicycle Precision Consensus — giảm GT Xe máy → AI Xe đạp

V0.5.28 đã chứng minh Dual Refiner có thể nhận ra bicycle, nhưng 2-frame consensus vẫn có thể promote nhầm scooter/xe máy mảnh thành bicycle. V0.5.29 siết riêng chiều `motorcycle → bicycle`:

```ini
AI_BICYCLE_CONSENSUS_MIN_HITS=3
AI_BICYCLE_CONSENSUS_MARGIN=0.08
AI_BICYCLE_CONSENSUS_MIN_STRONG=0.34
AI_BICYCLE_OVERRIDE_TTL_FRAMES=60
```

Một bicycle promotion giờ cần:

```text
>= 3 source frame độc lập
+
fused bicycle evidence đủ ngưỡng
+
có ít nhất 1 observation đủ mạnh
+
bicycle evidence thắng motorcycle evidence theo margin
```

Bằng chứng `best.pt` và YOLO26m trên **cùng một frame** vẫn chỉ tính một hit. TTL bicycle cũng ngắn hơn bốn bánh để một promote sai không bám quá lâu.

## 5. Telemetry V0.5.29

Dashboard giữ toàn bộ V0.5.28 và thêm:

```text
Xe lớn cứu center
Nối track xe lớn
Gộp car/truck
```

Để chẩn đoán chiếc van trắng, đọc theo chuỗi:

```text
Xe tải thấy
   ↓
Nối track xe lớn / Gộp car-truck
   ↓
Xe lớn cứu center (nếu anchor gate miss)
   ↓
Xe tải cắt vạch
   ↓
Xe tải
```

Mong muốn trên clip hiện tại là `Xe tải cắt vạch >= 1` và `Xe tải >= 1` nếu class tại event vẫn là truck.

## 6. Database

```text
0042_origin_heavy_v0528
        ↓
0043_heavy_track_v0529
schema_version = 0.5.29
```

Migration chỉ cập nhật schema version, không xóa dữ liệu.

## 7. Regression tests V0.5.29

- Large van center trajectory cắt finite gate trong Road Zone → heavy center rescue.
- External heavy crossing được đăng ký vào primary counter → không duplicate khi anchor phục hồi.
- Four-wheel raw ID có thể stitch qua gap dài hơn; two-wheel không được hưởng cửa sổ heavy.
- CAR/TRUCK box chồng mạnh của cùng một van → alias một canonical track.
- Bicycle cần số frame riêng lớn hơn khi cấu hình precision consensus.
- Bicycle evidence không được promote nếu motorcycle refiner support gần tương đương.

## 8. Cập nhật trên máy

Chép source đè vào:

```text
D:\LienThongDH\DoAn\traffic-ai
```

Giữ nguyên:

```text
.env
gateway\certs\
videos\
models\
snapshots\
datasets\
training-runs\
```

Không dùng:

```powershell
docker compose down -v
```

Chạy:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
```

Cần thấy:

```text
[Traffic AI] Heavy Track Fusion + Center-Gate Rescue V0.5.29
[OK] Heavy Track Fusion + Center-Gate Rescue V0.5.29
[SUCCESS] All Traffic AI tests passed.
```

Sau đó:

```powershell
.\scripts\start.ps1
.\scripts\verify-database.ps1
```

Mong muốn database:

```text
0043_heavy_track_v0529
schema_version = 0.5.29
```

Rồi `Ctrl + F5`, chạy lại đúng clip GT 149 và chụp Dashboard + Benchmark.

## 9. Phát hành vẫn một lệnh

Khi test và benchmark đạt yêu cầu:

```powershell
.\scripts\publish.ps1
```

Pipeline vẫn tự động:

```text
test → build → commit/push → tag v0.5.29 → GitHub Actions → GitHub Release
```

---

# Lịch sử phiên bản

# Traffic AI V0.5.28 — Video-Origin + Heavy-Vehicle Gate Rescue 🚚🎬

V0.5.28 được xây trực tiếp từ V0.5.27 sau khi đối chiếu `clip1(3).mp4` và snapshot thực tế. Hai lỗi được xác nhận bằng video: **xe đầu clip đang cắt vạch nhưng ByteTrack chưa có đủ lịch sử phía trước vạch**, và **xe van/truck trắng thực sự đi qua vạch khoảng 14:40–14:44 nhưng box bốn bánh lớn có thể tạo anchor quá sát/ngoài biên Road Zone**.

## Điểm mới V0.5.28

- **Video-Origin Rescue**: với video local, trong 20 frame đầu, counter được phép dùng tâm box (`origin_probe`) để suy ra một điểm trước vạch chỉ khi track bắt đầu sát vạch, chuyển động rời vạch đủ mạnh, quỹ đạo suy ra cắt đúng đoạn vạch hữu hạn và vẫn vượt toàn bộ Road Zone/motion guards. Không nới rule này cho RTSP/live.
- **Heavy-Vehicle Anchor Inset**: car/bus/truck dùng motion-leading anchor lùi 16% vào trong box theo hướng chuyển động. Điều này tránh van/truck lớn bị Road Zone loại chỉ vì box detector bị kéo dài/clipped ở mép ảnh, trong khi vẫn giữ hướng IN/OUT.
- `Video-start` giờ phản ánh **origin rescue thật sự**, không chỉ đếm mọi crossing xảy ra sớm.
- Dashboard thêm **Xe lớn anchor** để biết có bao nhiêu track bốn bánh đang dùng anchor an toàn.
- Giữ nguyên Dual Refiner Consensus 4.0, Transactional Human Guard 2.1, Crossing Engine 7.2 và global benchmark matching của V0.5.27.

## Cấu hình mới

```ini
AI_VIDEO_ORIGIN_RESCUE_FRAMES=20
AI_VIDEO_ORIGIN_DISTANCE_RATIO=0.065
AI_VIDEO_ORIGIN_MIN_NORMAL_RATIO=0.30
AI_HEAVY_ANCHOR_INSET_RATIO=0.16
```

## Database

```text
0041_dual_refiner_v0527
        ↓
0042_origin_heavy_v0528
schema_version = 0.5.28
```

## Regression tests mới

- Video bắt đầu khi xe đang straddle vạch → rescue và đếm đúng.
- Track bắt đầu xa vạch → không origin-rescue.
- Jitter song song vạch ở đầu clip → không rescue.
- Anchor bốn bánh lớn được inset theo hướng chuyển động.

---

## Lịch sử V0.5.27


V0.5.27 tập trung vào hai điểm quan sát được từ phiên V0.5.26 GT=149: class refiner chạy rất nhiều nhưng không cứu được bicycle/truck, và báo cáo benchmark có thể ghép tham lam sai cặp khi nhiều crossing nằm gần nhau.

## Điểm mới

- **Dual Refiner**: khi `best.pt` được kích hoạt, nó vẫn là refiner theo miền; `yolo26m.pt` chạy như second-opinion độc lập thay vì bị bỏ qua.
- **Multi-frame consensus**: cùng-frame từ hai model chỉ tính một observation; bicycle/truck chỉ được promote khi có bằng chứng target-matched ở ít nhất 2 frame riêng biệt.
- **Truck seen vs counted**: telemetry tách `truck_tracks_seen`, `truck_crossing_tracks` và số event `truck`. Thấy xe tải không đồng nghĩa đã đếm; chỉ track cắt vạch vàng hợp lệ mới tăng số xe tải.
- **Benchmark Global Match**: ghép GT↔AI toàn cục theo timecode, tối đa số cặp hợp lệ rồi tối thiểu tổng sai số thời gian; class/direction được chấm độc lập, không dùng để quyết định ghép.
- Giữ nguyên Crossing Engine 7.2, Transactional Human Guard 2.1, Video-start Rescue và các contract V0.5.26.

### Ghi chú từ snapshot phiên #124

Ở V0.5.27, chuỗi snapshot rời rạc quanh `frame_17930` từng khiến việc quan sát kết thúc ở lúc van còn phía trên vạch. Khi đối chiếu lại **toàn bộ `clip1(3).mp4`**, van trắng thực tế tiếp tục đi xuống và cắt qua vạch khoảng 14:40–14:44. Vì vậy `Xe tải = 0` ở phiên cũ là **một miss của gate/anchor**, không phải vì xe chưa đi qua. V0.5.28 sửa đúng nhận định và runtime này. Một số dòng GT Xe đạp → AI Xe máy vẫn nằm trong các cụm crossing sát nhau; global temporal matching tiếp tục tránh ghép cặp tham lam.

---

# Traffic AI V0.5.26 — Target-aware Class Refiner 3.0 + Video Start Rescue 🚚🚲🎯

V0.5.26 tiếp tục từ benchmark thật của V0.5.25 trên cùng `clip1.mp4` / GT 149:

```text
Ground truth       149
AI đếm             146
Khớp               128
Lọt                  21
Đếm dư               18
Recall              85.9%
Precision           87.7%
F1                  86.8%
Class đúng          96.9%
```

Bản này tập trung vào hai lỗi được nhìn thấy trực tiếp trong snapshot người dùng gửi:

- **Xe đạp thật bị gắn nhãn `motorcycle`** gần vạch đếm.
- **Xe tải/van giao hàng nhỏ bị detector pretrained gắn nhãn `car`**. Việc đổi class không được phép tự tạo lượt đếm: xe vẫn chỉ được cộng khi track thực sự cắt vạch hợp lệ.

Ngoài ra benchmark có GT thật ở khoảng `00:00.160`; startup grace 12 frame cũ có thể chặn crossing hợp lệ của video local. V0.5.26 tách startup policy giữa file video và RTSP.

## 1. Target-aware Class Refiner 3.0

V0.5.25 lấy detection có confidence cao nhất trong crop mở rộng. Trong giao thông đông, crop có thể chứa một xe máy đậu bên cạnh và refiner vô tình sửa class theo **xe khác**.

V0.5.26 dùng geometry match theo chính track mục tiêu:

```text
tracked box
   + IoU
   + target coverage
   + evidence coverage
   + center distance
          ↓
TARGET MATCH
          ↓
best.pt mới được quyền sửa class
```

Detection không thuộc box mục tiêu bị loại dù confidence cao hơn.

## 2. Cứu xe đạp bị gọi là xe máy

Policy cũ ưu tiên an toàn theo hướng `motorcycle`, nên nếu detector chính liên tục gọi một xe đạp là xe máy thì custom `best.pt` gần như không thể sửa lại.

V0.5.26 cho phép **target-matched custom refiner** override trong cùng family hai bánh:

```text
YOLO26s: motorcycle
      ↓
track ổn định
      ↓
best.pt target-match: bicycle đủ mạnh
      ↓
BIKE+
      ↓
bicycle
```

Mặc định:

```ini
AI_BICYCLE_REFINE_OVERRIDE_CONF=0.58
AI_CLASS_REFINE_INTERVAL=10
AI_CLASS_REFINE_GATE_DISTANCE_RATIO=0.11
```

## 3. Cứu xe tải nhỏ bị gọi là car

Xe tải/van nhỏ nhìn từ camera cao có thể giống COCO `car`. V0.5.26 cho phép target-aware refiner promote:

```text
car → truck
```

với threshold riêng:

```ini
AI_TRUCK_REFINE_OVERRIDE_CONF=0.48
AI_HEAVY_REFINE_OVERRIDE_CONF=0.54
AI_CLASS_REFINE_HEAVY_INTERVAL=45
```

Chiều ngược `truck/bus → car` vẫn cần evidence mạnh hơn để tránh làm mất xe tải thật.

**Quan trọng:** sửa `car → truck` chỉ sửa loại phương tiện. Bộ đếm vẫn bắt buộc geometry cắt vạch + Road Zone + cooldown/guard hợp lệ. Xe tải đang đứng/chạy phía trên vạch sẽ **không** bị cộng cưỡng bức.

## 4. Refine trước crossing + cache class

Xe bốn bánh được kiểm tra định kỳ khi nằm trong Road Zone để overlay có thể hiện `truck` trước khi chạm vạch. Xe hai bánh chỉ refine gần counting line để giữ FPS.

Kết quả refine được cache theo track và tái dùng ở crossing, tránh gọi `best.pt` hai lần trên cùng frame.

```ini
AI_REFINE_MAX_PER_FRAME=2
AI_CLASS_OVERRIDE_TTL_FRAMES=180
AI_REFINE_TARGET_MIN_IOU=0.08
AI_REFINE_TARGET_MIN_COVERAGE=0.16
```

`start.ps1` chỉ nâng default cũ:

```text
AI_REFINE_MAX_PER_FRAME 1 → 2
```

Nếu người dùng đã tự chỉnh giá trị khác thì script không ghi đè.

## 5. Video Start Rescue

Video local và RTSP không còn dùng chung startup grace.

```ini
AI_VIDEO_STARTUP_GRACE_FRAMES=0
AI_GATE_STARTUP_GRACE_FRAMES=12
```

- **Video local / benchmark:** đếm được crossing thật ngay từ đầu clip.
- **RTSP/live:** vẫn giữ 12 frame startup guard để tránh state/tracker khởi tạo gây event giả.

Telemetry mới `Video-start` cho biết crossing nào được cứu nhờ chính sách này.

## 6. Benchmark hiện rõ sai loại xe theo timecode

Report ngoài `Class đúng %` còn có danh sách:

```text
Sai loại phương tiện
00:xx.xxx · IN/OUT · GT Xe đạp → AI Xe máy
00:yy.yyy · IN/OUT · GT Xe tải → AI Ô tô
```

Nhờ vậy lần test tiếp theo có thể xác nhận trực tiếp `BIKE+` / `TRUCK+`, không phải suy luận từ tổng số.

## 7. Telemetry V0.5.26

Dashboard thêm:

```text
Class refine
Xe đạp cứu
Xe tải cứu
Video-start
```

và overlay runtime:

```text
CLASS-R
BIKE+
TRUCK+
START+
```

Các telemetry V0.5.25 vẫn giữ nguyên: `Bracket-confirm`, `Human Guard`, `Rider giữ`, `Guard chờ`, `Guard xác nhận`, `Guard timeout`.

## 8. Kiểm thử V0.5.26

Đã chạy trong môi trường build hiện tại:

```text
Python compile                                  ✅
AI Service unit tests                    92/92 ✅
Backend unit tests                       17/17 ✅
Benchmark regression                      7/7 ✅
Target refiner bỏ neighbor sai                  ✅
Bicycle motorcycle→bicycle rescue               ✅
Small truck car→truck rescue                     ✅
Local video startup grace = 0                    ✅
RTSP startup grace vẫn = 12                      ✅
Alembic single head 0040_class_refiner_v0526    ✅
Frontend main.jsx JSX syntax                     ✅
```

Host kiểm thử hiện tại chỉ có Node 22 và không có Docker/PowerShell, trong khi project khóa Node 26.10 + Docker Desktop. Vì vậy `test.ps1`, Docker full build và Vite production build phải được xác nhận trên máy Windows của dự án.

## 9. Database

Migration:

```text
0039_guard_tx_v0525
        ↓
0040_class_refiner_v0526
```

Mong muốn:

```text
0040_class_refiner_v0526
schema_version = 0.5.26
```

Migration chỉ cập nhật schema version, không xóa dữ liệu.

## 10. Cập nhật trên máy

Chép source V0.5.26 đè vào:

```text
D:\LienThongDH\DoAn\traffic-ai
```

Giữ nguyên:

```text
.env
gateway\certs\
videos\
models\
snapshots\
datasets\
training-runs\
```

Không dùng:

```powershell
docker compose down -v
```

Chạy:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 |
    Unblock-File

.\scripts\test.ps1
```

Cần thấy:

```text
[Traffic AI] Target-aware Class Refiner 3.0 + Video Start Rescue V0.5.26
[OK] Target-aware Class Refiner 3.0 + Video Start Rescue V0.5.26
[SUCCESS] All Traffic AI tests passed.
```

Sau đó:

```powershell
.\scripts\start.ps1
.\scripts\verify-database.ps1
```

Rồi `Ctrl + F5` và chạy lại đúng benchmark GT 149.

## 11. Phát hành một lệnh

Khi test/benchmark đạt yêu cầu:

```powershell
.\scripts\publish.ps1
```

Pipeline phát hành vẫn là:

```text
test → build → commit/push → tag v0.5.26 → GitHub Actions → GitHub Release
```

---

# Lịch sử V0.5.25

# Traffic AI V0.5.25 — Transactional Human Guard 2.1 + Crossing Engine 7.2 🛵🧍🎯

V0.5.25 tiếp tục trực tiếp từ lần benchmark V0.5.24 trên clip thật:

```text
Ground Truth        149
AI đếm              138
Khớp                120
Lọt                  29
Đếm dư               18
Recall              80.5%
Precision           87.0%
F1                  83.6%
Class đúng          96.7%
Human Guard            34
Rider giữ             151
```

Kết quả này cho thấy model phân loại không phải nút thắt chính. V0.5.25 tập trung vào hai lỗi runtime đã xác định trong source V0.5.24: **Human Guard có thể kiểm tra cùng một frame hai lần** và **crossing hai bánh còn ở trạng thái PENDING vẫn có thể được phát event ngay**; đồng thời Crossing Engine 7.2 bổ sung một rescue hình học hẹp cho các track cắt vạch hữu hạn rõ nhưng biến mất ngay sau vạch.

## 1. Human Guard strike giờ bắt buộc là frame khác nhau

V0.5.24 có thể chạy verifier ở nhánh periodic và chạy lại ở nhánh crossing trên cùng một source frame. Nếu cả hai lần đều PERSON-dominant, một frame có thể vô tình tạo đủ 2 strike.

V0.5.25 thêm `last_strike_frame` + same-frame observation cache:

```text
Frame 100 · periodic check
→ PERSON dominate
→ strike 1

Frame 100 · crossing check lại
→ dùng lại kết quả frame 100
→ vẫn strike 1 ✅

Frame 101 · PERSON vẫn dominate
→ strike 2
→ HUMAN-X
```

Ngay cả evidence PERSON rất mạnh (`hard_reject`) cũng không được bỏ qua nguyên tắc **distinct source frames** khi `AI_HUMAN_GUARD_REQUIRED_STRIKES=2`.

## 2. Transactional crossing — PENDING không còn lọt DB

V0.5.24 có cửa sổ logic:

```text
crossing thật
→ Human Guard = PENDING
→ chưa REJECTED
→ VehicleEvent vẫn có thể được submit ❌
```

V0.5.25 đổi thành transaction buffer:

```text
MOTORCYCLE / BICYCLE crossing
            ↓
       Human Guard
            ↓
  ┌─────────┼─────────┐
  ↓         ↓         ↓
RIDER      KEEP     PENDING
  ↓         ↓         ↓
COMMIT     COMMIT    giữ RAM
                      ↓
             frame khác kế tiếp
                ┌─────┴─────┐
                ↓           ↓
              RIDER       HUMAN
                ↓           ↓
              COMMIT       DROP
                ↓           ↓
              DB +1      revoke gate
```

Khi PENDING, hệ thống giữ nguyên:

- source frame crossing;
- source timecode;
- crossing method;
- crossing point;
- snapshot frame gốc.

Nhưng **không tăng tổng xe và không gửi backend** cho đến khi semantic guard giải quyết xong.

Telemetry mới:

```text
Guard chờ      = crossing đang nằm trong transaction buffer
Guard xác nhận = crossing PENDING sau đó được xác nhận/giữ và commit
Guard timeout  = track biến mất trước khi có frame xác nhận thứ hai → fail-closed
```

Mặc định:

```env
AI_HUMAN_GUARD_PENDING_MAX_FRAMES=12
```

## 3. Crossing Engine 7.2 — Bracket Confirm

Benchmark V0.5.24 báo nhiều xe thật bị lọt vì `Crossing chưa đủ xác nhận phía sau vạch`. V0.5.25 không bỏ side-confirm toàn cục. Thay vào đó chỉ rescue khi hai observation gần nhau đã tự tạo một crossing hình học rất rõ:

```text
sample A          sample B
   ●----------------●
          ↓
   cắt finite gate thật
          +
   motion chủ yếu vuông góc vạch
          +
   gap rất ngắn
          ↓
     BRACKET-CONFIRM ✅
```

Sau rescue này, các guard cũ vẫn phải pass:

```text
finite visible segment
Road Zone
minimum crossing motion
normal-motion ratio
cooldown
rescue validation
```

Cấu hình:

```env
AI_GATE_BRACKET_CONFIRM=1
AI_GATE_BRACKET_CONFIRM_MIN_NORMAL_RATIO=0.55
AI_GATE_BRACKET_CONFIRM_MAX_GAP=2
```

Telemetry:

```text
Bracket-confirm / BRACKET+
```

## 4. Không đổi `best.pt`

Giữ nguyên model/dataset hiện tại. V0.5.25 không train lại vì benchmark V0.5.24 vẫn cho `Class đúng 96.7%`; thay đổi nằm ở event transaction và crossing runtime.

## 5. Database

Migration mới:

```text
0038_rider_guard_v0524
        ↓
0039_guard_tx_v0525
schema_version = 0.5.25
```

Migration chỉ nâng schema version, không xóa session, benchmark, Ground Truth, dataset, model hay video.

## 6. Cập nhật trên máy

Chép full source V0.5.25 đè vào:

```text
D:\LienThongDH\DoAn\traffic-ai
```

Giữ nguyên:

```text
.env
gateway\certs\
videos\
models\
snapshots\
datasets\
training-runs\
```

Không dùng `docker compose down -v`.

Sau đó:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai

Get-ChildItem .\scripts -Recurse -Filter *.ps1 |
    Unblock-File

.\scripts\test.ps1
```

Mong muốn có:

```text
[Traffic AI] Transactional Human Guard 2.1 + Crossing Engine 7.2 V0.5.25
[OK] Transactional Human Guard 2.1 + Crossing Engine 7.2 V0.5.25
[SUCCESS] All Traffic AI tests passed.
```

Nếu PASS:

```powershell
.\scripts\start.ps1
.\scripts\verify-database.ps1
```

Database mong muốn:

```text
0039_guard_tx_v0525
schema_version = 0.5.25
```

Sau đó `Ctrl + F5`, chạy lại **chính clip + chính vạch + chính Road Zone** của benchmark V0.5.24 và bấm **Đối chiếu lại** với 149 GT cũ.

### Cần gửi lại các số này

```text
Ground truth
AI đếm
Khớp
Lọt không đếm
Đếm dư
Recall
Precision
F1
Human Guard
Rider giữ
Guard xác nhận
Guard timeout
Bracket-confirm
```

Mục tiêu của lượt test này là xác nhận 3 việc riêng biệt:

```text
1. người đi bộ không còn lọt event khi crossing mới chỉ PENDING
2. rider thật frame_519 / frame_1739 vẫn không bị same-frame double strike
3. số lỗi "chưa đủ xác nhận phía sau vạch" giảm nhờ Bracket Confirm
```

## 7. Phát hành vẫn một lệnh

Sau khi benchmark thực tế ổn:

```powershell
.\scripts\publish.ps1
```

```text
→ test
→ build
→ commit/push GitHub
→ tag v0.5.25
→ GitHub Actions
→ GitHub Release
→ upload ZIP/README/checksums
```

## Kiểm thử bổ sung V0.5.25

```text
Same source frame cannot create two strikes          PASS
Hard PERSON evidence still needs distinct frames    PASS
Rider recovery policy remains compatible            PASS
Bracket-confirm strong finite crossing               PASS
Bracket-confirm rejects lateral/parallel jitter      PASS
Pending crossing transaction static contract         PASS
Python compile                                       PASS
```

---

# Traffic AI V0.5.24 — Rider-aware Human Guard 2.0 🛵🧍🎯

V0.5.24 sửa lỗi được xác nhận trực tiếp từ clip và file nén `camera_1(1).rar` người dùng cung cấp.

## Kết quả kiểm tra dữ liệu thực tế

- clip màn hình dài khoảng **45.43 giây** cho thấy `Human Guard` tăng từ khoảng **100 → 107** trong khi tổng đếm gần như chỉ **61 → 62**;
- file RAR có **86 snapshot AI Overlay**;
- `frame_519` và đặc biệt `frame_1739` cho thấy **người đang ngồi/lái xe máy thật bị gắn `PERSON-GUARD`**, nên track xe bị loại khỏi event crossing;
- nguyên nhân source V0.5.23: một track bị PERSON-dominant ở một/ít frame có thể bị đưa vào tập reject lâu dài; đồng thời crop verifier chỉ coi trọng two-wheel evidence chồng trực tiếp lên box mục tiêu nên dễ bỏ qua **thân xe nằm thấp hơn người lái**.

### Sai trước đây

```text
Rider + scooter thật
      ↓
Detector box MOTORCYCLE cao/hẹp quanh người lái
      ↓
Verifier thấy PERSON mạnh
      ↓
không thấy motorcycle vì thân xe nằm thấp hơn box
      ↓
PERSON-GUARD
      ↓
track bị khóa
      ↓
xe thật cắt vạch nhưng KHÔNG ĐẾM ❌
```

## Human Guard 2.0 mới

```text
Candidate motorcycle/bicycle
      ↓
PERSON evidence
      +
DIRECT two-wheel evidence
      +
NEARBY-LOWER two-wheel evidence
      +
motion của track
      ↓
┌───────────────────────────────┐
│ Rider evidence rõ            │ → RIDER → GIỮ XE ✅
│ Person dominate nhiều lần    │ → PEDESTRIAN → CHẶN ✅
└───────────────────────────────┘
```

### 1. Crop rider-aware

Crop kiểm tra mở rộng mạnh hơn xuống phía dưới để bao cả scooter/motorcycle dưới thân người lái. Hai-wheel evidence không còn bắt buộc phải chồng trực tiếp >=18% với box MOTORCYCLE ban đầu; evidence ở **vùng rider envelope phía dưới** cũng được tính nếu nằm đúng quan hệ hình học người-ngồi-trên-xe.

### 2. Không permanent-reject chỉ vì một frame

V0.5.24 dùng `HumanGuardTrackPolicy`:

```text
1 frame PERSON mạnh
→ PENDING

2 lần PERSON-dominant liên tiếp
→ REJECT pedestrian
```

Mặc định:

```env
AI_HUMAN_GUARD_REQUIRED_STRIKES=2
AI_HUMAN_GUARD_CHECK_INTERVAL=8
```

### 3. Rider có thể cứu lại track đã từng bị reject

Nếu vài frame đầu chưa thấy rõ xe nhưng frame sau bắt được scooter/motorcycle nằm dưới người:

```text
PERSON-GUARD
    ↓
Rider evidence xuất hiện
    ↓
RELEASE TRACK
    ↓
xe tiếp tục được đếm
```

### 4. Track bị Guard vẫn giữ trajectory

Đây là thay đổi quan trọng. V0.5.23 `continue` sớm nên track bị Guard không đi qua `counter.update()` và mất lịch sử trước/sau vạch. V0.5.24 vẫn cho track đi qua geometry engine, nhưng **chỉ chặn/revoke VehicleEvent khi crossing xảy ra mà track vẫn được xác nhận là pedestrian**.

Nhờ vậy rider được cứu ngay ở sát vạch vẫn còn đầy đủ quỹ đạo để đếm.

### 5. Telemetry mới

```text
HUMAN-X  = pedestrian thật bị chặn
RIDER+   = track rider được giữ/cứu khỏi Human Guard
```

Frontend hiển thị thêm:

```text
Human Guard ... · Rider giữ ...
```

`Human Guard` cao bất thường trong khi `Rider giữ=0` là tín hiệu cần kiểm tra lại verifier.


## Cập nhật trên máy

Chép full source V0.5.24 đè vào:

```text
D:\LienThongDH\DoAn\traffic-ai
```

Giữ nguyên:

```text
.env
gateway\certs\
videos\
models\
snapshots\
datasets\
training-runs\
```

Không dùng `docker compose down -v`. Sau đó:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
.\scripts\test.ps1
```

Mong muốn có:

```text
[Traffic AI] Rider-aware Human Guard 2.0 V0.5.24
[OK] Rider-aware Human Guard 2.0 V0.5.24
[SUCCESS] All Traffic AI tests passed.
```

Nếu PASS:

```powershell
.\scripts\start.ps1
.\scripts\verify-database.ps1
```

Database mong muốn:

```text
0038_rider_guard_v0524
schema_version = 0.5.24
```

Phát hành vẫn một lệnh:

```powershell
.\scripts\publish.ps1
```

```text
→ test → build → push GitHub → tag v0.5.24 → GitHub Actions → Release
```

---

## Database

```text
0037_integrity_v0523
        ↓
0038_rider_guard_v0524
schema_version = 0.5.24
```

Migration chỉ nâng schema version; không xóa dataset/model/session/benchmark/149 Ground Truth.

## Cấu hình mới

```env
AI_HUMAN_GUARD=1
AI_HUMAN_GUARD_MODEL=yolo26s.pt
AI_HUMAN_GUARD_IMGSZ=512
AI_HUMAN_GUARD_CHECK_INTERVAL=8
AI_HUMAN_GUARD_CONF=0.08
AI_HUMAN_GUARD_REQUIRED_STRIKES=2
```

`start.ps1` tự nâng default cũ `AI_HUMAN_GUARD_CHECK_INTERVAL=12 → 8`; custom value khác 12 được giữ nguyên.

## Cách test đúng

Giữ nguyên clip/vạch/Road Zone và chạy lại clip. Quan sát:

```text
Rider thật đi qua vạch:
RIDER+ tăng hoặc giữ ổn định
Xe máy phải tăng ✅

Người đi bộ qua vạch:
HUMAN-X tăng
Xe máy KHÔNG tăng ✅
```

Sau khi session hoàn tất, tạo benchmark mới và sao chép 149 GT cũ để so với baseline V0.5.22:

```text
GT          149
AI          158
Khớp        133
Lọt          16
Dư           25
Recall      89.3%
Precision   84.2%
F1          86.6%
```

Mục tiêu V0.5.24 là giảm **false negative do Rider bị Human Guard khóa** mà không mở lại lỗi người đi bộ bị tính thành xe máy.

## Kiểm thử bổ sung V0.5.24

```text
Python compile                                  PASS
AI Service tests                               79/79 PASS
Backend tests (SQLite test mode)               17/17 PASS
Standalone pedestrian reject                   PASS
Nearby motorcycle below PERSON → rider keep    PASS
Weak nearby noise does not rescue pedestrian   PASS
Temporal two-strike pedestrian confirmation    PASS
Rejected track can be released by rider proof  PASS
```

---

# V0.5.23-R1 — Legacy test contract hotfix

Bản R1 không đổi AI runtime, database, model, dataset hay migration. Hotfix chỉ sửa `scripts/test.ps1` để các contract legacy kiểm tra **ý nghĩa tương thích** thay vì bắt cứng chuỗi giao diện của engine cũ.

- V0.5.18 không còn bắt buộc literal `Crossing Engine 6.0`; V0.5.23 đang dùng Crossing Engine 7.1 nhưng vẫn phải giữ `Tổng lượt cắt vạch`, `Trực tiếp`, `Nội suy` và `rescued_crossings`.
- V0.5.21 chấp nhận workflow tái sử dụng GT mới `Sao chép ... GT từ Benchmark ...`, thay cho wording cũ `... sang Session`.
- thêm contract `Legacy semantic contract compatibility V0.5.23-R1` để ngăn regression tương tự ở các bản sau.

Lỗi được sửa:

```text
[Traffic AI] Crossing Engine 6.0 V0.5.18
Frontend thiếu tổng xe hoặc breakdown crossing V0.5.18.
```

Đây là **false-fail của test legacy**; frontend V0.5.23 vẫn có đầy đủ breakdown crossing và đã nâng nhãn engine lên 7.1.

---

# Traffic AI V0.5.23 — Benchmark Integrity + Crossing Engine 7.1 + Human-vs-Motorcycle Guard 🚗🎯🧍

V0.5.23 tiếp tục trực tiếp từ benchmark thật của `clip1.mp4` và frame camera người dùng cung cấp.

Baseline V0.5.22 đã đo được:

```text
Ground Truth      149
AI event DB       158
Khớp              133
Lọt                16
Đếm dư             25
Recall            89.3%
Precision         84.2%
F1                86.6%
Class đúng        97.0%
```

Ngoài ra Session #120 từng hiển thị `162` ở worker nhưng Benchmark chỉ có `158` event DB. Frame camera thực tế còn cho thấy **một người đi bộ bị YOLO gán `motorcycle`**, nên nếu người đó cắt vạch thì có thể tạo false positive xe máy.

Bản này xử lý đồng thời ba lớp thay vì tiếp tục hạ confidence:

1. **Human-vs-Motorcycle Guard** — dùng PERSON evidence của YOLO26 pretrained để chặn người bị nhầm thành motorcycle/bicycle trước khi tăng IN/OUT.
2. **Benchmark Integrity** — tổng Session sau khi COMPLETED lấy từ `vehicle_events` thật trong DB; worker total, event bị backend dedup và event thiếu timecode được hiển thị tách biệt.
3. **Crossing Engine 7.1** — fast-confirm cho xe nhanh, adaptive cooldown cho lượt quay đầu thật, rescue validation chống ID-jump và crossing-signature dedup cực hẹp cho ID switch.

---

## 1. Human-vs-Motorcycle Guard

Ảnh camera cho thấy trường hợp điển hình:

```text
người đi bộ
   ↓
YOLO vehicle detector
   ↓
motorcycle #... 0.52   ❌
   ↓
ByteTrack
   ↓
đi qua vạch
   ↓
Xe máy +1              ❌
```

V0.5.23 thêm verifier person-aware độc lập:

```text
candidate motorcycle/bicycle
        ↓
box cao/hẹp giống người?
        ↓
YOLO26 pretrained kiểm tra crop:
PERSON + MOTORCYCLE + BICYCLE
        ↓
PERSON chiếm gần toàn candidate
và two-wheel evidence yếu
        ↓
PERSON-GUARD
        ↓
KHÔNG đưa vào Crossing Counter
KHÔNG tăng IN / OUT
KHÔNG tạo VehicleEvent
```

Guard cố ý **không** xóa motorcycle khi có người lái thật. Nếu crop vẫn có two-wheel evidence cạnh tranh, candidate được giữ.

Telemetry mới:

```text
Human Guard 3
HUMAN-X 3
```

Box bị loại trên AI Overlay hiển thị `PERSON-GUARD` để dễ kiểm tra bằng mắt.

Runtime:

```env
AI_HUMAN_GUARD=1
AI_HUMAN_GUARD_MODEL=yolo26s.pt
AI_HUMAN_GUARD_IMGSZ=512
AI_HUMAN_GUARD_CHECK_INTERVAL=12
AI_HUMAN_GUARD_CONF=0.08
```

`best.pt` Run #3 vẫn giữ vai trò refine class của phương tiện. Human Guard dùng model pretrained vì custom dataset hiện không có class `person`.

---

## 2. Benchmark Integrity: worker 162 nhưng DB 158 được giải thích rõ

Trước đây:

```text
AI worker total       162
backend dedup          -4
VehicleEvent DB       158

Session.total_vehicles = max(..., 162)
Benchmark AI count     = 158
```

nên Dashboard và Benchmark có hai tổng khác nhau.

V0.5.23 đổi semantics:

```text
worker_total_vehicles   = tổng candidate crossing ở worker

total_vehicles          = số VehicleEvent thật đã persist DB

dedup_suppressed_events = worker_total - persisted DB
```

Khi session kết thúc backend **COUNT trực tiếp `vehicle_events`** rồi chốt Session.

Benchmark Report có khối:

```text
✓ Benchmark Integrity OK
Worker đề xuất 162
DB lưu        158
Có timecode   158
Backend gộp     4
Human Guard     ...
```

Migration cũng sửa các session cũ có event DB để Session #120 không tiếp tục hiển thị `162` trong lịch sử khi DB chỉ có `158` event. Giá trị worker cũ được giữ ở `worker_total_vehicles`.

---

## 3. Crossing Engine 7.1

### Fast destination confirmation

V0.5.21 yêu cầu hai observation ở phía sau vạch. Benchmark cho thấy một số xe nhanh đã đi đủ xa sang phía mới nhưng vẫn bị ghi:

```text
Crossing chưa đủ xác nhận phía sau vạch
```

V0.5.23 cho phép xác nhận ngay khi điểm mới đã cách vạch đủ xa:

```env
AI_GATE_FAST_CONFIRM_DISTANCE_RATIO=0.018
```

Nó không nới crossing cho điểm chỉ rung sát dead-band.

### Adaptive cooldown

Cooldown cứng 60 frame giảm overcount nhưng cũng chặn một số lượt quay đầu thật.

V7.1 chỉ giữ cooldown nếu track **chưa thật sự rời xa vạch**. Track đã đi xa rồi quay lại có thể được release sớm:

```env
AI_GATE_ADAPTIVE_COOLDOWN=1
AI_GATE_COOLDOWN_RELEASE_RATIO=0.055
```

Telemetry:

```text
COOL-REL ...
```

### Rescue validation

Long-gap rescue là nguồn false positive rủi ro nhất. V7.1 từ chối rescue nếu:

- chuyển động quá song song với vạch;
- jump quá xa giống ID switch;
- hai điểm chỉ nằm rất sát hai phía dead-band.

```env
AI_GATE_RESCUE_MIN_NORMAL_RATIO=0.28
AI_GATE_RESCUE_MAX_JUMP_RATIO=0.26
AI_GATE_RESCUE_MIN_SIDE_RATIO=0.010
```

Telemetry:

```text
RESCUE-X ...
```

### Crossing signature dedup

Mỗi event mới lưu thêm vị trí giao vạch chuẩn hóa:

```text
crossing_x
crossing_y
```

Backend chỉ gộp hai event khác track khi chúng:

```text
cùng session
cùng hướng
cùng họ phương tiện
cách nhau <= ~0.22s
điểm cắt gần như cùng vị trí
```

Threshold được cố ý đặt hẹp để không gộp hai xe máy thật chạy gần nhau.

---

## 4. Database V0.5.23

Migration:

```text
0036_gt_reuse_v0522
        ↓
0037_integrity_v0523
```

Schema:

```text
schema_version = 0.5.23
```

`counting_sessions` thêm:

```text
worker_total_vehicles
dedup_suppressed_events
human_guard_rejections
```

`vehicle_events` thêm:

```text
crossing_x
crossing_y
```

Không xóa:

```text
Dataset #4
600 ảnh
Run #3
best.pt
Benchmark #1 / #2
149 Ground Truth
vehicle_events cũ
training-runs/
models/
```

---

## 5. Cách test đúng V0.5.23

Giữ nguyên vạch và Road Zone hiện tại để tái sử dụng đúng 149 GT.

```text
V0.5.22 baseline
GT 149 · AI 158 · Match 133 · Miss 16 · FP 25
        ↓
V0.5.23
Chạy lại đúng clip1.mp4 đến COMPLETED
        ↓
Tạo Benchmark Session mới
        ↓
Sao chép 149 GT
        ↓
Đối chiếu lại
```

So sánh:

```text
AI
Khớp
Lọt
Dư
Recall
Precision
F1
Benchmark Integrity
Human Guard
```

Không cần đánh I/O lại 149 lần.

---

## 6. Cập nhật trên máy

Chép full source đè vào:

```text
D:\LienThongDH\DoAn\traffic-ai
```

Giữ nguyên:

```text
.env
gateway\certs\
videos\
models\
snapshots\
datasets\
training-runs\
```

Không dùng:

```powershell
docker compose down -v
```

Nếu Windows chặn `.ps1`:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
```

Kiểm thử:

```powershell
.\scripts\test.ps1
```

Mong muốn:

```text
[Traffic AI] Benchmark Integrity + Crossing Engine 7.1 + Human Guard V0.5.23
[OK] Benchmark Integrity + Crossing Engine 7.1 + Human Guard V0.5.23

[SUCCESS] All Traffic AI tests passed.
```

Khởi động:

```powershell
.\scripts\start.ps1
```

Database:

```powershell
.\scripts\verify-database.ps1
```

Mong muốn:

```text
0037_integrity_v0523
schema_version = 0.5.23
```

Trình duyệt:

```text
Ctrl + F5
```

---

## 7. Phát hành vẫn một lệnh

```powershell
.\scripts\publish.ps1
```

```text
→ test
→ build
→ push GitHub
→ tag v0.5.23
→ GitHub Actions
→ Release
```

---

## Kiểm thử trong môi trường đóng gói

```text
Python compile                         PASS
AI Service unit tests                 74/74 PASS
Backend unit tests                    17/17 PASS
Human Guard geometry policy           PASS
Pedestrian dominates motorcycle       PASS
Real rider two-wheel evidence          PASS
Fast-confirm crossing                 PASS
Adaptive cooldown release             PASS
Long-gap rescue validation             PASS
Crossing rollback for Human Guard      PASS
Benchmark Integrity source contract    PASS
Alembic head/revision safety           PASS
```

Frontend `npm install` trong môi trường đóng gói bị timeout mạng; vì vậy Vite + Docker full-suite không được ghi PASS giả và vẫn do `./scripts/test.ps1` trên máy Windows/Docker của bạn xác nhận.

---

# Traffic AI V0.5.22 — Ground Truth Reuse Fix ♻️🎯

V0.5.22 sửa lỗi UX của V0.5.21: sau khi tạo Benchmark mới cho Session mới, selector tự chuyển sang Benchmark đích `GT 0`, làm nút sao chép biến mất vì frontend chỉ nhìn Ground Truth của benchmark đang chọn.

Bản này thêm API sao chép GT **vào benchmark đã tạo** và tự tìm benchmark nguồn tương thích (cùng video + cùng vạch). Với tình huống hiện tại:

```text
Benchmark #1 · Session #119 · GT 149
Benchmark #2 · Session #120 · GT 0
          ↓
Sao chép 149 GT từ Benchmark #1 sang Benchmark #2
          ↓
Benchmark #2 · GT 149
          ↓
Đối chiếu lại với AI Session #120
```

Không cần xem lại 15:46 phút clip và không cần bấm I/O lại. Backend từ chối sao chép nếu video/vạch khác hoặc benchmark đích đã có GT, để tránh benchmark sai hoặc nhân đôi dữ liệu.


## Với dữ liệu hiện tại của bạn

Sau khi nâng V0.5.22, chọn:

```text
Benchmark #2 · Session #120 · GT 0
```

ngay dưới selector sẽ hiện:

```text
Sao chép 149 GT từ Benchmark #1 sang Benchmark #2
```

Bấm một lần, Benchmark #2 thành `GT 149`, sau đó bấm `Đối chiếu lại`. Không cần tạo Benchmark #3 và không cần đánh lại I/O.

V0.5.22 cũng sửa một lỗi React kín: nút `Tạo benchmark cho phiên này` trước đây truyền click-event vào tham số clone vì dùng `onClick={createBenchmark}`. Bản mới gọi tường minh `onClick={()=>createBenchmark()}` nên tạo benchmark thường không còn bị hiểu nhầm là yêu cầu clone.

## Database

```text
0035_crossing_v0521
        ↓
0036_gt_reuse_v0522
schema_version = 0.5.22
```

Không xóa dataset, model, session, benchmark hay 149 Ground Truth cũ.

---

# Traffic AI V0.5.21 — Ground-truth Error Analyzer + Crossing Engine 7.0 🎯🚗

V0.5.21 dùng trực tiếp Ground-truth Benchmark để xử lý hai vấn đề còn lại: **nút “Đối chiếu lại” không có phản hồi nhìn thấy được** và **Crossing Engine còn overcount / lọt xe**.

## Điểm mới chính

### 1. `Đối chiếu lại` giờ là một hành động thật

Frontend gọi endpoint riêng:

```text
POST /api/benchmarks/{id}/reconcile
```

Nút chuyển trạng thái:

```text
Đối chiếu lại
      ↓
Đang đối chiếu…
      ↓
Đã đối chiếu lại lúc HH:mm:ss
```

Nếu số liệu không đổi, giao diện nói rõ:

```text
Kết quả không đổi: khớp ..., lọt ..., dư ...
```

Không còn trường hợp bấm nút nhưng không biết hệ thống có chạy hay không.

### 2. Ground-truth Auto Error Analyzer cho `AI đếm dư`

Mỗi false-positive event được phân tích theo timecode, tracking ID và crossing method. Report có thể gắn các nhãn chẩn đoán:

```text
Event giả lúc khởi tạo clip
Cùng track đảo IN/OUT quá nhanh
Cùng track phát event lặp
Event dư nằm sát một GT đã khớp
Rescue qua gap nhưng GT không có
Nội suy qua vạch nhưng GT không có
Direct crossing nhưng GT không có
```

Đây là **chẩn đoán**, không thay Ground Truth. GT do người dùng đánh dấu vẫn là chuẩn để xác định xe có thật sự cắt vạch hay không.

### 3. Crossing Engine 7.0 giảm overcount

Runtime mặc định mới:

```env
AI_GATE_STARTUP_GRACE_FRAMES=12
AI_GATE_SIDE_CONFIRM_SAMPLES=2
AI_GATE_COOLDOWN_FRAMES=60
AI_ROAD_ANCHOR_MARGIN_RATIO=0.012
```

Luồng đếm mới:

```text
Track đi tới vạch
   ↓
không tính crossing trong 12 frame đầu clip
   ↓
trajectory thật sự đổi phía vạch
   ↓
phải có thêm observation xác nhận ở phía mới
   ↓
không được lặp crossing cùng canonical track trong cooldown
   ↓
Road Zone corridor vẫn strict
   ↓
COUNT
```

Mục tiêu là giảm các event kiểu:

```text
IN → OUT → IN
```

trong vài frame do jitter / ID instability.

### 4. Road Zone edge tolerance chỉ cứu sai số anchor nhỏ

Road Guard trước đây yêu cầu cả hai observed anchor phải nằm tuyệt đối trong polygon. V0.5.21 cho phép **chỉ observed anchor** lệch ra mép Road Zone một khoảng rất nhỏ (`0.012` cạnh ngắn frame), trong khi:

```text
crossing point
probe trước crossing
probe sau crossing
```

vẫn bắt buộc nằm **strict** trong Road Zone.

Do đó mục tiêu là cứu các GT bị `Road Zone reject` vì leading-edge anchor lệch vài pixel, nhưng không mở cửa cho xe chạy ngoài lề.

### 5. Backend chống rapid direction-flip lần hai

Ngay cả khi runtime gửi lại event do bất ổn, backend còn có lớp idempotency bổ sung cho cùng canonical `tracking_id` trong cửa sổ ngắn theo frame/timecode.

### 6. Không phải đánh lại 149 Ground Truth

Sau khi chạy V0.5.21 thành một Session mới với **cùng clip + cùng vạch**, Benchmark Studio hiện nút:

```text
Sao chép 149 GT sang Session #...
```

Backend chỉ cho sao chép khi nguồn video và vạch đếm khớp benchmark nguồn. Nhờ vậy bạn có thể dùng đúng 149 mốc GT đã đánh để so V0.5.20 ↔ V0.5.21, không phải xem lại 15 phút clip và bấm I/O lần nữa.

---

# Database V0.5.21

Migration:

```text
0034_benchmark_overlay_v0520
        ↓
0035_crossing_v0521
```

Schema:

```text
schema_version = 0.5.21
```

Migration này không xóa bảng/dữ liệu và không đụng:

```text
Dataset #4
Ground Truth Benchmark hiện có
Run #3
best.pt
vehicle_events cũ
counting_sessions cũ
```

---

# Cập nhật trên máy

Chép full source đè vào:

```text
D:\LienThongDH\DoAn\traffic-ai
```

Giữ nguyên:

```text
.env
gateway\certs\
videos\
models\
snapshots\
datasets\
training-runs\
```

Không dùng:

```powershell
docker compose down -v
```

Nếu Windows đánh dấu file PowerShell từ ZIP:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
```

Sau đó:

```powershell
.\scripts\test.ps1
```

Mong muốn có:

```text
[Traffic AI] Crossing Engine 7.0 + Benchmark Reconcile V0.5.21
[OK] Crossing Engine 7.0 + Benchmark Reconcile V0.5.21
```

Nếu PASS:

```powershell
.\scripts\start.ps1
```

Database:

```powershell
.\scripts\verify-database.ps1
```

mong muốn:

```text
0035_crossing_v0521
schema_version = 0.5.21
```

Sau đó `Ctrl + F5` trên trình duyệt.

---

# Kiểm thử V0.5.21

```text
Python compile                         PASS
Backend unit tests                    15/15 PASS
AI Service unit tests                 66/66 PASS
Crossing Engine 7.0 regression        PASS
Ground-truth false-positive analyzer  PASS
Benchmark reconcile endpoint          PASS
Ground Truth clone contract           PASS
Alembic single head                   PASS
head = 0035_crossing_v0521            PASS
Revision ID <= 32 chars               PASS
Sensitive/runtime artifact scan       PASS
```

Môi trường đóng gói hiện tại không có đúng Node 26.10/Docker Desktop của máy đích, nên vòng `Vite build + Docker full-suite` vẫn do `./scripts/test.ps1` trên máy Windows của bạn xác nhận. Backend tests ở môi trường đóng gói dùng SQLite và temporary `httpx2 -> httpx` compatibility shim; source thật không đổi dependency của dự án.


# Benchmark sau khi nâng

Benchmark cũ vẫn được giữ để xem kết quả V0.5.20. Để đo hiệu quả Crossing Engine 7.0, hãy chạy lại **đúng clip + đúng vạch + đúng Road Zone** thành một Session mới rồi tạo Benchmark mới. Ground Truth cũ có thể dùng làm mốc tham chiếu, nhưng event AI của session mới phải được đối chiếu với session mới.

Mục tiêu không phải làm tổng AI “gần 149” bằng cách ép số, mà là đồng thời:

```text
missed ↓
false positive ↓
Recall ↑
Precision ↑
F1 ↑
```

---

# Phát hành vẫn một lệnh

```powershell
.\scripts\publish.ps1
```

```text
→ test
→ build
→ push GitHub
→ tag v0.5.21
→ GitHub Actions
→ Release
```

---

# Lịch sử trước V0.5.21

# Traffic AI V0.5.20 — Benchmark Gate Overlay + IN/OUT 🎯🛣️

V0.5.20 sửa blocker của Ground-truth Benchmark: **video benchmark phải hiển thị đúng vạch đếm, Road Zone và hướng IN/OUT**, nếu không người dùng không thể biết lúc nào xe thực sự cắt vạch để đánh dấu GT.

Điểm mới:

- benchmark lưu snapshot `line_x1/y1/x2/y2` và 4 điểm Road Zone khi tạo;
- benchmark cũ V0.5.19 được backfill geometry từ camera hiện tại khi migrate;
- video benchmark vẽ trực tiếp **Road Zone xanh + vạch vàng + mũi tên IN/OUT**;
- hướng IN/OUT dùng đúng cùng quy ước `signed_side()` của Counting Engine, không phải mũi tên minh họa đoán tay;
- geometry đã snapshot không đổi nếu sau này bạn chỉnh camera;
- video không còn ép khung 16:9 để overlay lệch trên nguồn khác tỉ lệ.

```text
          IN
          ↓
   ┌───────────────┐
   │   ROAD ZONE   │
   │               │
   │ ===== VẠCH ===│
   │               │
   └───────────────┘
          ↑
         OUT
```

Khi benchmark, chỉ bấm `I` hoặc `O` lúc **tâm/quỹ đạo xe thật sự cắt đúng vạch vàng đang hiển thị trên video**.

---

## Nền tảng từ V0.5.19

V0.5.19 tiếp tục từ V0.5.18 và tập trung vào vấn đề còn lại: **AI vẫn lọt một số xe không đếm được nhưng nhìn tổng cuối clip không biết xe nào bị lọt và bị lọt ở tầng nào**.

Bản này không tiếp tục chỉnh confidence/tracker một cách đoán mò. Nó thêm một quy trình benchmark có ground truth theo **timecode của chính video** để đo chính xác:

- xe thật sự cắt vạch bao nhiêu;
- AI đếm bao nhiêu;
- xe nào khớp;
- xe nào **lọt không đếm**;
- event nào **đếm dư**;
- Counting Precision / Recall / F1;
- sai class và sai hướng;
- nguyên nhân xe lọt nằm ở detector, ByteTrack, Road Zone hay Crossing Gate.

---

## Kiến trúc benchmark mới

```text
Video gốc
   ↓
Chạy AI V0.5.19
   ↓
Mỗi event lưu:
- source_frame_index
- source_time_seconds
- crossing_method
   ↓
Frame trace của toàn phiên:
DET / track / road / crossing / reject
   ↓
GROUND-TRUTH BENCHMARK
   ↓
Người dùng xem lại chính clip
và đánh dấu từng xe thật cắt vạch
   ↓
GT timecode ↔ AI event timecode
   ↓
Matched / Missed / False positive
   ↓
Precision / Recall / F1
   ↓
Phân loại nguyên nhân xe lọt
```

---

## Vì sao phiên cũ 191 xe chưa dùng để tìm chính xác xe lọt?

Phiên trong V0.5.18 có thể đã lưu 191 `vehicle_events`, nhưng các event cũ chưa có:

```text
source_time_seconds
source_frame_index
crossing_method
```

V0.5.19 **không tự ước lượng timecode từ đồng hồ hệ thống**, vì warm-up CUDA/video pacing có thể làm lệch thời gian và biến benchmark thành số liệu giả.

Vì vậy sau khi nâng V0.5.19, hãy **chạy lại clip một lần**. Phiên mới sẽ có timecode chuẩn để đối chiếu.

---

# Ground-truth Counting Benchmark Studio

Sidebar có thêm:

```text
Benchmark
```

Panel mới:

```text
GROUND-TRUTH COUNTING BENCHMARK
Đánh dấu xe thật cắt vạch trên chính clip
```

Quy trình:

```text
1. Chạy clip bằng AI đến hết
2. Chọn session vừa hoàn tất
3. Tạo benchmark
4. Xem lại video ở 0.5×
5. Mỗi xe thật sự cắt vạch:
   I = IN
   O = OUT
6. Đối chiếu report
```

### Phím nhanh

```text
I   → đánh dấu IN
O   → đánh dấu OUT
[   → lùi 1 frame
]   → tiến 1 frame
```

Class được chọn bằng combobox:

```text
Xe máy
Xe đạp
Ô tô
Xe buýt
Xe tải
Khác
```

Mặc định video benchmark phát ở **0.5×**, phù hợp clip có khoảng 190–200 xe mà không cần click nút cho từng frame.

---

# Báo cáo benchmark

Report hiển thị:

```text
Ground truth
AI đếm
Khớp
Lọt không đếm
Đếm dư
Sai số tổng

Counting Recall
Counting Precision
F1
Class accuracy
```

Ví dụ:

```text
GT            200
AI            191
Matched       188
Missed         12
False positive  3

Recall      94.0%
Precision   98.4%
```

Điểm quan trọng là **sai số tổng -9 không che mất thực tế có 12 xe lọt và 3 xe đếm dư**.

---

# Click đúng xe bị lọt

Danh sách:

```text
Lọt không đếm
00:14.320 · IN · Xe máy
00:27.080 · OUT · Xe máy
...
```

Click timecode sẽ đưa video benchmark thẳng tới đúng thời điểm đó để kiểm tra bằng mắt.

Danh sách `AI đếm dư` hoạt động tương tự.

---

# V0.5.19 tự phân loại nguyên nhân xe lọt

Trong lúc chạy video, AI Service ghi một JSONL trace nhẹ theo từng frame vào:

```text
snapshots/benchmark-traces/session_<id>.jsonl
```

Nó chỉ lưu telemetry số, không lưu thêm video:

```text
frame
source time
DET
track
road track
crossing event
total count
road rejects
segment rejects
```

Khi một Ground Truth không tìm thấy AI event gần timecode, hệ thống xem telemetry xung quanh thời điểm đó và phân loại:

### `Detector không thấy xe`

```text
DET = 0
```

→ vấn đề model/confidence/imgsz/dataset.

### `YOLO thấy nhưng ByteTrack mất ID`

```text
DET > 0
track = 0
```

→ vấn đề tracking.

### `Track bị Road Zone loại`

```text
track > 0
road = 0
```

hoặc road reject tăng.

→ vùng lòng đường quá hẹp/sai vị trí.

### `Track trong đường nhưng Crossing Gate không phát event`

```text
DET > 0
track > 0
road > 0
nhưng không crossing
```

→ tập trung sửa Strict Gate/Crossing Engine thay vì detector.

Report còn tổng hợp **nguyên nhân lọt nổi bật**, để bản nâng cấp kế tiếp sửa đúng tầng gây lỗi nhiều nhất.

---

# Timecode chính xác của AI event

`vehicle_events` có thêm:

```text
source_frame_index
source_time_seconds
crossing_method
```

Ví dụ:

```text
source_frame_index = 7312
source_time_seconds = 292.4400
crossing_method = interpolated
```

Ground truth và AI được ghép one-to-one bằng timecode, mặc định:

```text
±0.75 giây
```

Bạn có thể chỉnh từ UI. Sai class hoặc sai hướng được đánh giá **riêng** với counting match, tránh biến một xe đã đếm nhưng sai class thành “1 missed + 1 false positive”.

---

# Database V0.5.19

Migration:

```text
0032_crossing_engine_v0518
        ↓
0033_ground_truth_v0519
```

Schema:

```text
schema_version = 0.5.19
```

Thêm hai bảng:

```text
counting_benchmarks
ground_truth_crossings
```

`counting_sessions` thêm:

```text
source_url
source_fps
source_duration_seconds
```

`vehicle_events` thêm:

```text
source_frame_index
source_time_seconds
crossing_method
```

Không xóa:

```text
Dataset #4
annotations
Run #3
best.pt
models/
training-runs/
vehicle_events cũ
counting_sessions cũ
```

---

# Lưu ý với session V0.5.18 trở về trước

Nếu chọn session cũ, UI sẽ báo:

```text
⚠ Phiên cũ thiếu timecode
191 event được tạo trước V0.5.19 nên không thể ghép chính xác.
Hãy chạy lại clip một lần trên V0.5.19 rồi benchmark session mới.
```

Đây là fail-closed có chủ ý; hệ thống không tạo benchmark “chính xác giả”.

---

# Cập nhật trên máy

Chép full source V0.5.20 đè vào:

```text
D:\LienThongDH\DoAn\traffic-ai
```

Giữ nguyên:

```text
.env
gateway\certs\
videos\
models\
snapshots\
datasets\
training-runs\
```

Không dùng:

```powershell
docker compose down -v
```

Nếu Windows đánh dấu `.ps1` từ ZIP là file Internet:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | Unblock-File
```

Sau đó:

```powershell
.\scripts\test.ps1
```

Mong muốn có:

```text
[Traffic AI] Ground-truth Counting Benchmark V0.5.19
[OK] Ground-truth Counting Benchmark V0.5.19

[Traffic AI] Benchmark gate overlay + IN/OUT V0.5.20
[OK] Benchmark gate overlay + IN/OUT V0.5.20
```

Nếu PASS:

```powershell
.\scripts\start.ps1
```

Database:

```powershell
.\scripts\verify-database.ps1
```

mong muốn:

```text
0034_benchmark_overlay_v0520
schema_version = 0.5.20
```

Trình duyệt:

```text
Ctrl + F5
```

---

# Quy trình benchmark cho clip hiện tại

Sau khi nâng source:

```text
1. Chạy AI
2. Để clip chạy hết
3. Không đổi vạch/Road Zone giữa phiên
4. Vào Benchmark
5. Chọn session vừa hoàn tất
6. Tạo benchmark
7. Phát lại ở 0.5×
8. Nhấn I/O mỗi lần xe thật cắt vạch
9. Đối chiếu
```

Khi report có `Lọt không đếm`, click từng timecode. Hệ thống sẽ đồng thời cho biết tầng nghi ngờ:

```text
Detector
Tracker
Road Zone
Crossing Gate
```

Đây sẽ là dữ liệu đầu vào để fix tiếp, thay vì tiếp tục hạ confidence hoặc thay tracker khi chưa biết nguyên nhân thật.

---

# Kiểm thử đã thực hiện

```text
Python compile                         PASS
AI Service tests                      62/62 PASS
Backend tests                         11/11 PASS
Benchmark matching                    PASS
Benchmark API create/mark/report       PASS
Missed / false-positive matching      PASS
Class mismatch separated from count   PASS
Tolerance boundary                    PASS
Benchmark trace diagnosis             PASS
Detector miss diagnosis               PASS
Tracker miss diagnosis                PASS
Road Zone reject diagnosis            PASS
Crossing Gate miss diagnosis          PASS
SQLite ORM create_all                 PASS
New benchmark tables                  PASS
Event source-time columns             PASS
JSX parse/transpile                   PASS
Alembic single head                   PASS
head = 0033_ground_truth_v0519        PASS
Alembic revision <= 32 chars          PASS
```

Môi trường đóng gói hiện tại không có Docker Desktop/PowerShell và `npm install` bị timeout mạng, nên frontend Vite + Docker full-suite vẫn do `./scripts/test.ps1` trên máy của bạn xác nhận. Backend/AI tests ở môi trường đóng gói dùng temporary `httpx2 -> httpx` compatibility shim; source thật vẫn giữ dependency của dự án.

---

# Phát hành vẫn một lệnh

Sau khi chạy ổn:

```powershell
.\scripts\publish.ps1
```

```text
→ test
→ build
→ push GitHub
→ tag v0.5.20
→ GitHub Actions
→ Release
```


## V0.5.19-R1 — Benchmark responsive UI hotfix

- Sửa hàng `Phiên AI / Tạo benchmark / Benchmark` bị tràn sang panel `Benchmark Report` khi card bên trái hẹp hoặc trình duyệt đang zoom.
- `Benchmark` selector tự xuống một hàng riêng trên desktop hẹp; ở viewport nhỏ toàn bộ control xếp dọc.
- `select` dùng `min-width: 0`, `max-width: 100%` và `box-sizing: border-box` để không vượt chiều rộng card.
- Hai panel benchmark dùng `overflow: hidden` như lớp bảo vệ cuối, nhưng control vẫn được bố trí lại thay vì chỉ cắt phần tràn.
- Không đổi database, migration, AI, dataset, `best.pt` hay logic benchmark. Runtime vẫn là `0.5.19`.


## V0.5.20 — Benchmark Gate Overlay

- Lưu snapshot vạch đếm + Road Zone vào `counting_benchmarks`.
- Migration `0034_benchmark_overlay_v0520` backfill benchmark đã tạo trước đó bằng geometry camera hiện tại.
- Video Benchmark vẽ vạch vàng, vùng xanh và mũi tên `IN` / `OUT`.
- `IN` là hướng từ phía signed-side âm sang signed-side dương của vạch; `OUT` là chiều ngược lại, đúng cùng logic với `ai-service/app/counting.py`.
- Dùng `I` / `O` để đánh GT sau khi nhìn xe cắt đúng vạch hiển thị.

## V0.5.26-R1 - test contract hotfix

- Sửa regression trong `scripts/test.ps1`: contract lịch sử V0.5.8 trước đây ghim cứng `AI_REFINE_MAX_PER_FRAME=1`, trong khi V0.5.26 hợp lệ đã nâng default `1 -> 2` cho Target-aware Class Refiner 3.0.
- Contract V0.5.8 giờ chấp nhận cả default lịch sử `1` hoặc migration forward-compatible `Set-EnvDefaultUpgrade "AI_REFINE_MAX_PER_FRAME" "1" "2"` + current default `2`.
- Không đổi runtime counting/classification, model, database schema hay VERSION; đây chỉ là hotfix cho bộ kiểm thử để không chặn một cấu hình V0.5.26 hợp lệ.


## V0.5.34-R1 — GitHub Actions Annotation Cleanup

Hotfix R1 không đổi AI/runtime/database. GitHub Actions được làm sạch hai annotation đã xuất hiện khi phát hành v0.5.34:

- Pin toàn bộ GitHub-hosted runner từ `ubuntu-latest` sang `ubuntu-24.04` để workflow không bị annotation về đợt chuyển `ubuntu-latest` sang Ubuntu 26.04 và tránh thay đổi môi trường ngoài ý muốn.
- Nâng `softprops/action-gh-release@v2` lên `softprops/action-gh-release@v3`; nhánh v3 chạy trên Node.js 24, không còn cảnh báo action Node.js 20.
- `scripts/test.ps1` có regression contract để chặn việc quay lại `ubuntu-latest` hoặc `action-gh-release@v2`.

Do tag `v0.5.34` đã phát hành, không tạo lại tag cùng phiên bản. Có thể push hotfix này lên `main` rồi chạy thủ công `gh workflow run release.yml --ref main` để xác nhận workflow sạch annotation mà không tạo Release mới; bước tạo Release chỉ chạy khi ref là tag.
