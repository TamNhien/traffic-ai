import React from 'react'
import { buildRawMotionAuditView } from './raw-motion-audit.js'

const signed = value => `${value >= 0 ? '+' : ''}${value.toFixed(2)}`
const vectorText = value => value ? `Δx ${signed(value[0])}, Δy ${signed(value[1])}` : 'Chưa ghi'

export function RawMotionAudit({ item, onSeek }) {
  const audit = buildRawMotionAuditView(item)
  if (!audit) return null
  return <details className="bicycle-context-audit raw-motion-audit">
    <summary>Chuyển động theo raw ID ({audit.segments.length} đoạn)</summary>
    <p>Các tâm box liên tiếp cùng raw ID của canonical {audit.trackId}. Bước nhảy khi nối ID được tách riêng, không dùng làm chuyển động của một raw ID.</p>
    {audit.segments.map(segment => <div className="bicycle-context-record" key={`${segment.rawId}-${segment.firstFrame}-${segment.lastFrame}`}>
      <strong>Raw ID {segment.rawId} · frame {segment.firstFrame}–{segment.lastFrame}</strong>
      <p>{segment.sampleCount} quan sát liên tiếp · {segment.firstTime.toFixed(3)}s–{segment.lastTime.toFixed(3)}s</p>
      <dl className="raw-motion-measurements">
        <div><dt>Tâm box dịch chuyển</dt><dd>{vectorText(segment.displacement)} px</dd></div>
        <div><dt>Trung bình từ quan sát</dt><dd>{vectorText(segment.observedVelocity)} px/frame</dd></div>
        <div><dt>Vận tốc canonical đã lọc (mẫu cuối)</dt><dd>{segment.filteredVelocity ? `${vectorText(segment.filteredVelocity)} px/frame` : 'Chưa ghi'}</dd></div>
      </dl>
      {segment.handoff && <div className="raw-motion-handoff">
        <p>Nối raw {segment.handoff.fromRawId} → {segment.handoff.toRawId}: tâm box đổi {vectorText(segment.handoff.displacement)} px qua {segment.handoff.gapFrames} frame.</p>
        <p>Độ cùng chiều giữa bước nối ID và đoạn quan sát: <strong>{segment.handoffMotionCosine === null ? 'Chưa đủ chuyển động' : segment.handoffMotionCosine.toFixed(3)}</strong>. Giá trị âm là ngược chiều.</p>
      </div>}
      <div className="observed-track-seek"><button type="button" className="secondary compact" onClick={() => onSeek(segment.firstTime)}>Đầu {segment.firstTime.toFixed(3)}s</button><button type="button" className="secondary compact" onClick={() => onSeek(segment.lastTime)}>Cuối {segment.lastTime.toFixed(3)}s</button></div>
    </div>)}
    {audit.truncated && <p>Danh sách đã giới hạn; tải hồ sơ benchmark để xem trace đầy đủ.</p>}
    <p>Chuyển động tâm box và ID chưa chứng minh cùng phương tiện hay một lượt cắt vạch. Hãy đối chiếu video; dữ liệu này không sửa hướng đếm, Ground Truth hoặc điểm số.</p>
  </details>
}
