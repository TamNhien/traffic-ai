from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app import sources


def test_missing_video_suggests_only_available_video(tmp_path: Path, monkeypatch) -> None:
    demo = tmp_path / "demo.mp4"
    demo.write_bytes(b"not-a-real-video")
    monkeypatch.setattr(sources, "VIDEO_ROOT", tmp_path.resolve())

    state = sources.inspect_source("video", "/data/videos/traffic_video.mp4", probe=False)
    assert state["valid"] is False
    assert state["suggested_source_url"] == "/data/videos/demo.mp4"
    assert state["available_videos"][0]["source_url"] == "/data/videos/demo.mp4"


def test_video_source_listing(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "demo.mp4").write_bytes(b"x")
    (tmp_path / "ignore.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(sources, "VIDEO_ROOT", tmp_path.resolve())

    response = TestClient(app).get("/sources/videos")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["name"] == "demo.mp4"
    assert payload[0]["source_url"] == "/data/videos/demo.mp4"
    assert payload[0]["size_bytes"] == 1
    assert "modified_at" in payload[0]


def test_resolve_video_path_stays_inside_video_root(monkeypatch, tmp_path):
    import app.sources as sources
    monkeypatch.setattr(sources, "VIDEO_ROOT", tmp_path.resolve())
    good = tmp_path / "demo.mp4"
    good.write_bytes(b"demo")
    assert sources.resolve_video_path("/data/videos/demo.mp4") == good.resolve()
    try:
        sources.resolve_video_path("/etc/passwd.mp4")
    except ValueError:
        pass
    else:
        raise AssertionError("path traversal/outside VIDEO_ROOT must be rejected")
