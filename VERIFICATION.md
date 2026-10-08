# Kiểm tra Traffic AI V0.5.65

## Kết quả thực hiện

| Phạm vi | Kết quả |
|---|---|
| Test functions offline thực thi | **723 đạt, 0 lỗi**: 628 AI +95 backend |
| HTTP/ORM/app integration chưa chạy | **35**: đúng3 AI +32 backend identities của .64 |
| Test definitions trong source | **758**: giữ đủ742 cũ, thêm16 |
| Kiểm tra tĩnh source/contracts | **631 đạt** |
| Python parse/compile | **134 files** |
| Alembic | **79 migrations**, head/parent hợp lệ, không cycle |
| Release cục bộ | **38 đạt**: 17 executed +14 static +4 simulation +3 Bash syntax |
| Frontend | **41 đạt**: Babel/Node VM/controlled JSX, không phải browser/Vite build |
| Full source | **194 files**: 191 UTF-8 text +3 binary assets |
| Code/config đóng băng sau test | **192 SHA256**, hai tài liệu review riêng |

723 là test functions thực sự chạy qua offline harness, không phải full pytest. 758 definitions gồm35 integration chưa chạy. Giữ đủ742 baseline test identities; thêm5 classifier +11 worker-context tests. Bảy test bodies cũ được cập nhật: **3 class-policy tests** theo quyết định mới và **4 health/version tests** theo0.5.65; không xóa test hoặc gọi assertion của policy cũ là bất biến.

Actual NumPy2.3.5/Pydantic2.13.5 và algorithm modules dùng thư viện thực. Worker/pure backend helpers trích AST để tránh HTTP/ORM imports thiếu; pytest shim chỉ cung cấp approx/raises/tmp_path/monkeypatch. Dispatcher dùng queue/thread/retry thực với HTTP client được kiểm soát. Model opinions là fixture/recorded evidence, không phải inference thật.

Frontend dùng Babel parser/transform đã cài và controlled JSX element factory. CSS, AnnotationEditor và toàn bộ GroundTruthBenchmark state/handlers/render giữ đúng byte .64. Chỉ APP_VERSION và lời cảnh báo van đổi. Ca mới kiểm tra actual JSX warning condition: chỉ completed+TRUCK proof+không lượt Xe tải mới hiện; running/no-lock/đã có TRUCK không bị cảnh báo. Không thêm controls hoặc tự xác nhận danh tính xe.

## Baseline và input

Baseline đúng ZIP .64 đã giao: **443,482byte /193files**, SHA256 `c3785a299976851039d2d199b252bf4ce5d3e0c4902c4afad1e9624d85f92619`. Đã kiểm CRC/safe unique paths và giải nén byte-exact. Source .65 giữ đủ193 paths, thêm duy nhất migration0079.

Ảnh .64 session170/benchmark47, clone149 GT từ benchmark46:149GT/149AI/135matched/14miss/14extra/Recall=Precision=F1=90.6%/class99.3%/1bikeerror/IN68OUT81. Worker195/backend gộp46/DB149 timed events/Human Guard30/IntegrityOK;1888classchecks. Truck locks2, truck lock→car2, truck crossings0. AI146MC/1bicycle/2CAR/0TRUCK. Đây là **input .64**, không phải kết quả .65.

RAR81,046,409byte, SHA256 `d48a335f73abeb5e180f4656d184cf1eaff73dca19e91da04870002e6409c9c7`;195 safe unique regular members =194 JPG +1JSONL. Tất cả ảnh decode thành công,1440×811/session170; đã xem đủ5 contact sheets và hai ảnh crossing.

Trace195,708,229byte, SHA256 `056fcc999c857c26ed7f5524294999ac91a0217d8afd65d36c795c6f2105a799`. Có23,650 continuous observation frames,195proposals=195terminalreceipts khớp11source fields:149created+46deduplicated, allattempt1, mọi dedup ID resolve tới created event. Footer drain_complete=true/pending0/dropped0; không trùng canonical trong cùng frame.

| Ca van | Source/observed frame | Bằng chứng chính/stable TRUCK | Refiner chung CAR ở hai frame | Backend |
|---|---|---|---|---|
| 254023 OUT641.9311s | 16049/16050 | certainty.926907,hits25,lock.995817 | .838867/.858887 | created10063 |
| −22 IN882.2898s, raw286434 | 22058/22059 | certainty.972858,hits28,lock.986346 | .903809/.948242 | created10105 |

Ở cả hai ca domain=null/consensus=false; all-frame admission .64 đã lấy mẫu đúng, budget còn đủ. Primary overlay vẫnTRUCK, event/receipt lạiCAR. Ảnh cho thấy thân van kín trắng/xanh; không dùng hình dáng/màu để khẳng định hai canonical là cùng phương tiện vật lý.

Người dùng xác nhận van thuộc Xe tải. Bảng Sai loại chỉ đang hiển thị lỗi xe đạp; chưa có GT/event assignment export để xác minh nhãn GT hoặc cặp ghép của hai van. Class99.3% không chứng minh van đúng loại. Không tự sửa GT để làm đẹp score. Cần review loại GT quanh10:41.93OUT và14:42.29IN; timecode/hướng giữ theo clip đã kiểm tra.

## Chính sách mới và hồi quy

TRUCK semantic lock còn hiệu lực yêu cầu domain CAR corroboration trước khi crossing-only demotion: giữ ngưỡng mặc định.80, số frame mặc định2 liên tiếp và frame mới nhất đúng frame quan sát đang xử lý crossing (16050/22059 trong hai ca input). Domain phải có CAR opinion thật, đạt ngưỡng ở mỗi source frame và thắng mọi nhãn four-wheel cạnh tranh. Generic CAR không được cho domain mượn confidence hoặc clock.

Thiếu domain/một frame/yếu/cũ/future/kháccanonical hoặc TRUCK/BUS mạnh hơn thì giữ lock. CAR bình thường khi không có khóa hoặc khóa đã hết hạn giữ đường cũ. Domain đủ bằng chứng vẫn có thể sửa một khóa TRUCK sai. Không reset TTL/xóa lock hoặc tạo model opinion giả. Quy tắc này bảo vệ van đã có TRUCK proof, không hứa nhận đúng mọi van không từng có proof.

16 test mới gồm source qualification, hai passage đúngcanonical âm/dương, missing/weak/stale/future/domainoneframe/cross-track/veto, clearCAR/no-lock/expiredlock/domaincorroborated positivecontrols, actual run branch/budget/allframe lag và observed-versus-selected source clocks.

**14 controlled differential cases mỗi phiên bản** dùng actual delivered .64 ZIP source: cả hai ca input .64 chọnCAR/demotion1, .65 chọnTRUCK/demotion0; các positivecontrols CAR đủ bằng chứng vẫn qua. Ba lag0/.36/2.0 của actual crossing branch vẫn cùng ngân sách/mẫu/admission .64, nay giữTRUCK khi domain thiếu. Không dùng TypeError/missing new helper làm regression evidence.

256 randomized aggregate comparisons do class agent và independent **400 evidence histories /2400 query contexts**, cùng explicit required_source=None, giữ default recent_four_wheel_wins đúng .64. Thêm8 độc lập domain qualification cases đạt. Đây là kiểm tra bổ sung, không cộng vào723 test functions.

Raw `crossing_truck_class_resolution_audit` có14 top-level fields và tối đa4 nested lock fields,6 fixed reasons. Ghi observed frame, original selected source frame/time, confidence/số frame yêu cầu, qualified lock thật, aggregate/domain CAR winning frames và quyết định. Không credentials/URL/model paths hoặc backend outcome giả. Record chỉ gắn trong trace actual crossing; parser/Gate evidence không đổi.

## Rà soát full source và contracts

Đối chiếu .64 ZIP:8 policy modules giữ nguyên từng byte, gồm Gate/counting, tracking, Human Guard, dispatcher, runtime, backend matching/routes và trace. Worker61/64 methods và classifier48/49 methods giữ nguyên; chỉ recent_four_wheel_wins/_fresh_car_crossing_override/_resolve_crossing_class_refinement/run đổi trong phạm vi đã review. Sau bỏ đúng additive audit threading/attachments, resolver và run phần điều khiển còn lại khớp .64.

Prescan/deferred refinements, replay admission, class caches/source clocks, models/taxonomy mapping, backend dedup, global matching/tolerance, geometry/cooldown/Human Guard không đổi. Default aggregate API vẫn tương thích; required_source là optional keyword mới. Cảnh báo dashboard chỉ đổi text, điều kiện cũ giữ nguyên.

**960 source regex predicates**, **661 internal imported symbols** và **117 frontend runtime-field pairs** được rà soát; không còn findings. New `Assert-VanSemanticsV0565Contract` khai báo/gọi. Legacy .30 warning guard được cập nhật theo cảnh báo đúng mới, thay vì yêu cầu câu khẳng định cũ. Các historical functions/invocations vẫn còn;192 hash final code được so với source đã scan.

VERSION/frontend/API health/start message0.5.65 đồng bộ. Head `0079_van_semantics_v0565`, parent `0078_replay_audit_v0564`; upgrade schema_version0.5.65/downgrade0.5.64, không đổi DB schema/GT/events. Revision dưới32 ký tự.

17 PowerShell scripts UTF-8 no-BOM/CRLF; text source/config khác LF. npm Docker/CI/packageManager12.2.0 đối chiếu official npm CLI latest ngày08/10/2026; Node pin26.10.0 giữ nguyên. Đây là source contracts, không phải native PowerShell chạy thành công.

## Giới hạn và chạy lại trên Windows

Môi trường kiểm tra thực Python3.12.14/Node24.19.0/npm11.9.0; availability kế thừa .64, không probe/install dependency lặp lại. Thiếu pytest/FastAPI/SQLAlchemy/Alembic/httpx2/cv2/Torch/pwsh/Docker. Không chạy full dependency-pinned pytest, HTTP/ORM/database/migration thực, PowerShell native, Docker/npm audit/Vite build, browser/React DOM, GPU/model/video replay. Integration tests vẫn nguyên trong source cho scripts/test.ps1 trên máy đủ Docker.

38 release checks dùng isolated local Git/artifact workflow execution và static/simulation/Bash syntax đã phân loại; không push GitHub/tạo Release thật. Chưa có F1 hoặc class accuracy .65. Cần replay cùng clip, cùng geometry và review GT loại van để đánh giá.

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

Mở https://traffic-ai.test:8443, Ctrl+F5. Clone149 GT từ benchmark47 tương thích; review van quanh10:41.93OUT/14:42.29IN thành Xe tải theo quy ước người dùng, giữ timecode/hướng đã kiểm tra. Đối chiếu lại và Tải hồ sơ benchmark ZIP+screenshots.
