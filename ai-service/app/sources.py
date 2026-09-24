from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.m4v', '.webm'}
VIDEO_ROOT = Path(os.getenv('VIDEO_DIR', '/data/videos')).resolve()


def list_video_sources() -> list[dict[str, Any]]:
    VIDEO_ROOT.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    for path in sorted(VIDEO_ROOT.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        stat = path.stat()
        items.append({
            'name': path.name,
            'source_url': f'/data/videos/{path.name}',
            'size_bytes': stat.st_size,
            'modified_at': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })
    return items


def resolve_video_path(source_url: str) -> Path:
    value = (source_url or '').strip()
    if not value:
        raise ValueError('Chưa cấu hình đường dẫn video.')
    candidate = Path(value)
    canonical_root = Path('/data/videos')
    if candidate.is_absolute():
        try:
            relative = candidate.relative_to(canonical_root)
            candidate = VIDEO_ROOT / relative
        except ValueError:
            # A custom VIDEO_DIR may itself be exposed as an absolute path in tests
            # or non-Docker deployments. Accept it only when it is already inside
            # VIDEO_ROOT; the relative_to guard below remains the final boundary.
            pass
    else:
        candidate = VIDEO_ROOT / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(VIDEO_ROOT)
    except ValueError as exc:
        raise ValueError('Video local phải nằm trong thư mục /data/videos.') from exc
    if candidate.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError(f'Định dạng video không được hỗ trợ: {candidate.suffix or "(không có phần mở rộng)"}.')
    return candidate


def inspect_source(source_type: str, source_url: str, *, probe: bool = False) -> dict[str, Any]:
    source_type = (source_type or '').strip().lower()
    source_url = (source_url or '').strip()

    if source_type == 'video':
        try:
            path = resolve_video_path(source_url)
        except ValueError as exc:
            videos = list_video_sources()
            return {'valid': False, 'source_type': 'video', 'source_url': source_url, 'message': str(exc), 'videos': videos, 'available_videos': videos}
        if not path.exists() or not path.is_file():
            videos = list_video_sources()
            suggestion = videos[0]['source_url'] if len(videos) == 1 else None
            return {
                'valid': False,
                'source_type': 'video',
                'source_url': str(path),
                'message': f'Không tìm thấy video: {source_url}. Hãy chọn một video đang có trong thư mục videos.',
                'suggested_source_url': suggestion,
                'videos': videos,
                'available_videos': videos,
            }
        result: dict[str, Any] = {
            'valid': True,
            'source_type': 'video',
            'source_url': f'/data/videos/{path.name}',
            'message': 'Video sẵn sàng.',
            'size_bytes': path.stat().st_size,
        }
        if probe:
            try:
                import cv2
                cap = cv2.VideoCapture(str(path))
                try:
                    if not cap.isOpened():
                        raise ValueError('OpenCV không mở được video.')
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        raise ValueError('Không đọc được frame đầu tiên của video.')
                    height, width = frame.shape[:2]
                    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
                    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                    result['width'] = int(width)
                    result['height'] = int(height)
                    result['fps'] = round(fps, 4) if fps > 0 else None
                    result['frame_count'] = frame_count
                    result['duration_seconds'] = round(frame_count / fps, 4) if fps > 0 and frame_count > 0 else None
                finally:
                    cap.release()
            except Exception as exc:
                return {
                    'valid': False,
                    'source_type': 'video',
                    'source_url': f'/data/videos/{path.name}',
                    'message': f'Video tồn tại nhưng không đọc được: {exc}',
                    'videos': list_video_sources(),
                    'available_videos': list_video_sources(),
                }
        return result

    if source_type == 'rtsp':
        if source_url.lower().startswith(('rtsp://', 'rtsps://')):
            return {'valid': True, 'source_type': 'rtsp', 'source_url': source_url, 'message': 'RTSP URL hợp lệ về định dạng.'}
        return {'valid': False, 'source_type': 'rtsp', 'source_url': source_url, 'message': 'RTSP URL phải bắt đầu bằng rtsp:// hoặc rtsps://.'}

    if source_type == 'webcam':
        try:
            index = int(source_url)
            if index < 0:
                raise ValueError
        except (TypeError, ValueError):
            return {'valid': False, 'source_type': 'webcam', 'source_url': source_url, 'message': 'Webcam phải là chỉ số thiết bị không âm, ví dụ 0.'}
        return {'valid': True, 'source_type': 'webcam', 'source_url': str(index), 'message': 'Chỉ số webcam hợp lệ.'}

    return {'valid': False, 'source_type': source_type, 'source_url': source_url, 'message': f'Loại nguồn không hỗ trợ: {source_type}.'}


def read_source_preview(source_type: str, source_url: str, *, max_width: int = 1280, jpeg_quality: int = 82) -> bytes:
    """Read one representative frame without starting the AI pipeline."""
    import cv2

    source_type = (source_type or '').strip().lower()
    source_url = (source_url or '').strip()
    if source_type == 'video':
        path = resolve_video_path(source_url)
        if not path.exists() or not path.is_file():
            raise ValueError(f'Không tìm thấy video: {source_url}')
        source: str | int = str(path)
    elif source_type == 'webcam':
        source = int(source_url)
    else:
        source = source_url

    cap = cv2.VideoCapture(source)
    try:
        if not cap.isOpened():
            raise ValueError(f'Không mở được nguồn: {source_url}')
        if source_type == 'video':
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            if frame_count > 10:
                cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(frame_count * 0.12)))
        ok, frame = cap.read()
        if not ok or frame is None:
            raise ValueError('Không đọc được frame xem trước.')
        h, w = frame.shape[:2]
        if max_width > 0 and w > max_width:
            scale = max_width / float(w)
            frame = cv2.resize(frame, (max_width, max(2, int(round(h * scale)))), interpolation=cv2.INTER_AREA)
        ok, encoded = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
        if not ok:
            raise ValueError('Không mã hóa được ảnh xem trước.')
        return encoded.tobytes()
    finally:
        cap.release()
