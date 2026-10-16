"""Traffic reports: clock boundaries, replay scope, totals and real export files."""
from datetime import date, datetime, timezone
from io import BytesIO
import csv
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import pytest

from app.traffic_reports import (build_traffic_report, export_csv, export_pdf, export_xlsx,
                                 report_filters, utc_report_bounds)


def sample_report(group_by="day"):
    filters = report_filters(date(2026, 10, 15), date(2026, 10, 17), group_by)
    return build_traffic_report([
        {"bucket": "2026-10-15T23:00:00", "camera_id": 1, "camera_name": "Cổng trường Ánh Dương", "vehicle_type": "motorcycle", "direction": "in", "session_id": 193, "count": 68},
        {"bucket": "2026-10-16T00:00:00", "camera_id": 1, "camera_name": "Cổng trường Ánh Dương", "vehicle_type": "motorcycle", "direction": "out", "session_id": 193, "count": 78},
        {"bucket": "2026-10-16T00:00:00", "camera_id": 1, "camera_name": "Cổng trường Ánh Dương", "vehicle_type": "truck", "direction": "out", "session_id": 193, "count": 2},
        {"bucket": "2026-10-16T01:00:00", "camera_id": 2, "camera_name": "=HYPERLINK(\"https://invalid\")", "vehicle_type": "bicycle", "direction": "unknown", "session_id": 194, "count": 2},
    ], filters)


def test_v0593_report_totals_directions_peaks_and_dimensions():
    report = sample_report()
    assert report["summary"] == {"total": 150, "in": 68, "out": 80, "unknown": 2,
                                  "session_count": 2, "camera_count": 2, "peak_hour": report["peak_hours"][0]}
    assert report["peak_hours"][0] == {"bucket": "2026-10-16T00:00:00+07:00", "total": 80, "in": 0, "out": 80, "unknown": 0}
    assert [row["total"] for row in report["series"]] == [68, 82]
    assert sum(row["total"] for row in report["per_class"]) == sum(row["total"] for row in report["per_camera"]) == 150
    assert report["filters"]["clock"] == "recorded" and report["filters"]["timezone"] == "Asia/Ho_Chi_Minh"
    assert "chạy lại" in report["warnings"][0]


def test_v0593_report_date_window_utc7_is_half_open():
    filters = report_filters(date(2026, 10, 16), date(2026, 10, 17), "day")
    assert utc_report_bounds(filters) == (datetime(2026, 10, 15, 17, tzinfo=timezone.utc), datetime(2026, 10, 16, 17, tzinfo=timezone.utc))
    rows = [{"bucket": bucket, "camera_id": 1, "camera_name": "A", "vehicle_type": "truck", "direction": "in", "session_id": 1, "count": 1}
            for bucket in ["2026-10-15T23:00:00", "2026-10-16T00:00:00", "2026-10-16T23:00:00", "2026-10-17T00:00:00"]]
    assert build_traffic_report(rows, filters)["summary"]["total"] == 2


def test_v0593_report_empty_buckets_hour_day_month_and_no_fake_peak():
    for group_by, expected in [("hour", 48), ("day", 2), ("month", 1)]:
        report = build_traffic_report([], report_filters(date(2026, 10, 15), date(2026, 10, 17), group_by))
        assert len(report["series"]) == expected
        assert all(row["total"] == 0 for row in report["series"])
        assert report["summary"]["peak_hour"] is None and report["peak_hours"] == []


def test_v0593_report_month_boundary_zero_fill_and_tie_order():
    filters = report_filters(date(2026, 9, 30), date(2026, 11, 2), "month")
    rows = [{"bucket": bucket, "camera_id": 1, "camera_name": "A", "vehicle_type": "car", "direction": "out", "session_id": 1, "count": 3}
            for bucket in ["2026-10-31T12:00:00", "2026-09-30T12:00:00"]]
    report = build_traffic_report(rows, filters)
    assert [(row["bucket"], row["total"]) for row in report["series"]] == [("2026-09", 3), ("2026-10", 3), ("2026-11", 0)]
    assert report["peak_hours"][0]["bucket"] == "2026-09-30T12:00:00+07:00"


def test_v0593_report_single_session_camera_class_filters():
    raw = [{"bucket": "2026-10-16T00:00:00", "camera_id": cam, "camera_name": "A", "vehicle_type": vehicle,
            "direction": "in", "session_id": session, "count": 1} for cam, vehicle, session in
           [(1, "truck", 193), (1, "truck", 194), (2, "truck", 193), (1, "car", 193)]]
    filters = report_filters(date(2026, 10, 16), date(2026, 10, 17), camera_id=1, vehicle_type="truck", session_id=193)
    assert build_traffic_report(raw, filters)["summary"]["total"] == 1


def test_v0593_report_filter_range_and_type_validation():
    for start, end, group, options in [
        (date.min, date(1, 1, 2), "day", {}),
        (date(2026, 1, 1), date(2026, 1, 1), "day", {}),
        (date(2026, 1, 2), date(2026, 1, 1), "day", {}),
        (date(2026, 1, 1), date(2028, 1, 1), "day", {}),
        (date(2026, 1, 1), date(2026, 3, 1), "hour", {}),
        (date(2026, 1, 1), date(2026, 1, 2), "year", {}),
        (date(2026, 1, 1), date(2026, 1, 2), "day", {"vehicle_type": "van"}),
        (date(2026, 1, 1), date(2026, 1, 2), "day", {"camera_id": 0}),
        (date(2026, 1, 1), date(2026, 1, 2), "day", {"session_id": True}),
    ]:
        with pytest.raises(ValueError):
            report_filters(start, end, group, **options)


def test_v0593_report_group_cap_rejects_without_truncating(monkeypatch):
    import app.traffic_reports as reports
    monkeypatch.setattr(reports, "MAX_AGGREGATE_ROWS", 1)
    row = {"bucket": "2026-10-16T00:00:00", "camera_id": 1, "vehicle_type": "truck", "direction": "in", "session_id": 1, "count": 1}
    with pytest.raises(ValueError):
        build_traffic_report([row, row], report_filters(date(2026, 10, 16), date(2026, 10, 17)))


def test_v0593_report_csv_utf8_and_formula_neutralization():
    content = export_csv(sample_report())
    assert content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(content.decode("utf-8-sig").splitlines()))
    assert ["Tổng lượt", "150"] in rows
    assert any("Ánh Dương" in cell for row in rows for cell in row)
    assert any("#2 =HYPERLINK" in cell for row in rows for cell in row)
    # Camera names have a #id prefix; raw metadata also cannot be interpreted as a formula.
    from app.traffic_reports import _safe_text
    for value in ["=2+2", "+2", "-cmd", "@SUM(A1)", "  =1", "\tname"]:
        assert _safe_text(value).startswith("'")


def test_v0593_report_xlsx_real_ooxml_typed_numeric_unicode_and_no_formulas():
    content = export_xlsx(sample_report())
    assert content.startswith(b"PK")
    with ZipFile(BytesIO(content)) as archive:
        assert archive.testzip() is None
        assert "xl/workbook.xml" in archive.namelist()
        for name in archive.namelist():
            if name.endswith((".xml", ".rels")):
                ET.fromstring(archive.read(name))
        overview = archive.read("xl/worksheets/sheet1.xml").decode()
        assert "<v>150</v>" in overview and "Tổng lượt" in overview
        assert "Ánh Dương" in archive.read("xl/worksheets/sheet3.xml").decode()
        assert not any(b"<f>" in archive.read(name) for name in archive.namelist())


def test_v0593_report_pdf_real_paginated_document_and_embedded_font():
    content = export_pdf(sample_report("hour"))
    assert content.startswith(b"%PDF-") and content.rstrip().endswith(b"%%EOF")
    assert b"/FontFile2" in content and b"/ToUnicode" in content
    assert content.count(b"/Type /Page\n") >= 2


def test_v0593_report_sqlite_query_and_replay_session_scope():
    # Requires the regular backend test environment; the pure-helper checks above
    # also run in the offline review harness without FastAPI/SQLAlchemy installed.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.db.base import Base
    from app.models.all_models import Camera, CountingSession, VehicleEvent
    from app.traffic_report_routes import _load_report
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Camera(id=1, name="Cổng A", code="A", source_type="video", source_url="private.mp4"))
        db.add_all([CountingSession(id=193, camera_id=1, status="completed"), CountingSession(id=194, camera_id=1, status="completed")])
        db.flush()
        for index, timestamp in enumerate([datetime(2026, 10, 15, 16, 59), datetime(2026, 10, 15, 17), datetime(2026, 10, 16, 16, 59), datetime(2026, 10, 16, 17)]):
            db.add(VehicleEvent(camera_id=1, session_id=193, vehicle_type="truck", direction="out", confidence=.9, detected_at=timestamp))
        db.add(VehicleEvent(camera_id=1, session_id=194, vehicle_type="truck", direction="out", confidence=.9, detected_at=datetime(2026, 10, 15, 17)))
        db.commit()
        filters = report_filters(date(2026, 10, 16), date(2026, 10, 17), "hour", camera_id=1, session_id=193)
        report = _load_report(db, filters)
        assert report["summary"]["total"] == 2 and report["summary"]["session_count"] == 1
        assert report["series"][0]["total"] == 1 and report["series"][-1]["total"] == 1
        assert "source_url" not in str(report)
    engine.dispose()
