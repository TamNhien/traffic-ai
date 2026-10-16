"""Bounded traffic summaries and real document exports, independent of the database.

Recorded time is VehicleEvent.detected_at. A video's source offset has no calendar
origin and is deliberately never promoted to an invented calendar timestamp.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO, StringIO
from pathlib import Path
import re
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

REPORT_TIMEZONE = "Asia/Ho_Chi_Minh"
LOCAL_TZ = timezone(timedelta(hours=7))
MAX_REPORT_DAYS = 366
MAX_HOURLY_DAYS = 31
MAX_AGGREGATE_ROWS = 100_000
VEHICLE_LABELS = {
    "motorcycle": "Xe máy", "bicycle": "Xe đạp", "car": "Ô tô",
    "bus": "Xe buýt", "truck": "Xe tải", "other": "Khác",
}
RECORDED_WARNING = (
    "Thời điểm ghi nhận (UTC+7) là lúc hệ thống xử lý lượt cắt vạch, không phải "
    "ngày giờ quay video. Chọn một phiên để tránh cộng nhiều lần chạy lại cùng video."
)


def report_filters(start: date, end: date, group_by: str = "day", *,
                   camera_id: int | None = None, vehicle_type: str | None = None,
                   session_id: int | None = None) -> dict:
    if not isinstance(start, date) or isinstance(start, datetime) or not isinstance(end, date) or isinstance(end, datetime):
        raise ValueError("Ngày báo cáo phải có dạng YYYY-MM-DD")
    span = (end - start).days
    if start == date.min:
        raise ValueError("Ngày bắt đầu nằm ngoài phạm vi chuyển đổi UTC+7")
    if span <= 0 or span > MAX_REPORT_DAYS:
        raise ValueError("Khoảng báo cáo phải từ 1 đến 366 ngày; ngày kết thúc không bao gồm")
    if group_by not in {"hour", "day", "month"}:
        raise ValueError("group_by phải là hour, day hoặc month")
    if group_by == "hour" and span > MAX_HOURLY_DAYS:
        raise ValueError("Báo cáo theo giờ tối đa 31 ngày")
    if vehicle_type is not None and vehicle_type not in VEHICLE_LABELS:
        raise ValueError("Loại phương tiện không hợp lệ")
    for value in (camera_id, session_id):
        if value is not None and (type(value) is not int or not 1 <= value <= 2_147_483_647):
            raise ValueError("Mã camera/phiên phải là số nguyên dương")
    return {"start": start.isoformat(), "end": end.isoformat(), "group_by": group_by,
            "camera_id": camera_id, "vehicle_type": vehicle_type, "session_id": session_id,
            "timezone": REPORT_TIMEZONE, "clock": "recorded"}


def utc_report_bounds(filters: dict) -> tuple[datetime, datetime]:
    return tuple(datetime.combine(date.fromisoformat(filters[key]), time.min, LOCAL_TZ).astimezone(timezone.utc)
                 for key in ("start", "end"))


def _counter(**values) -> dict:
    return {**values, "total": 0, "in": 0, "out": 0, "unknown": 0}


def _add(row: dict, direction: str, count: int) -> None:
    row["total"] += count
    row[direction if direction in {"in", "out"} else "unknown"] += count


def _local_hour(value) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    # SQL groups yield local wall time without an offset on both dialects.
    return (parsed.replace(tzinfo=LOCAL_TZ) if parsed.tzinfo is None else parsed.astimezone(LOCAL_TZ)).replace(minute=0, second=0, microsecond=0)


def _bucket(hour: datetime, group_by: str) -> str:
    return hour.isoformat() if group_by == "hour" else hour.strftime("%Y-%m-%d" if group_by == "day" else "%Y-%m")


def build_traffic_report(grouped_rows, filters: dict) -> dict:
    """Combine SQL counts; never accept or silently truncate raw event histories.

    Each row: bucket (local hour), camera_id/name, vehicle_type, direction,
    session_id and count. Query filters are applied before SQL aggregation.
    """
    # Revalidate all caller-controlled fields before generating zero buckets.
    filters = report_filters(date.fromisoformat(filters["start"]), date.fromisoformat(filters["end"]),
                             filters["group_by"], camera_id=filters.get("camera_id"),
                             vehicle_type=filters.get("vehicle_type"), session_id=filters.get("session_id"))
    total = _counter()
    series, hours, cameras, classes = {}, {}, {}, {}
    sessions = set()
    start, end = (datetime.combine(date.fromisoformat(filters[key]), time.min, LOCAL_TZ) for key in ("start", "end"))
    cursor = start
    step = timedelta(hours=1) if filters["group_by"] == "hour" else timedelta(days=1)
    while cursor < end:
        key = _bucket(cursor, filters["group_by"])
        series.setdefault(key, _counter(bucket=key))
        cursor += step
    for index, row in enumerate(grouped_rows):
        if index >= MAX_AGGREGATE_ROWS:
            raise ValueError("Quá nhiều nhóm dữ liệu; thu hẹp ngày, camera hoặc phiên")
        hour = _local_hour(row["bucket"])
        if not start <= hour < end:
            continue
        count = int(row["count"])
        if count <= 0:
            continue
        camera_id = int(row["camera_id"])
        vehicle = str(getattr(row["vehicle_type"], "value", row["vehicle_type"]))
        direction = str(getattr(row["direction"], "value", row["direction"]))
        if filters["camera_id"] is not None and camera_id != filters["camera_id"]:
            continue
        if filters["vehicle_type"] is not None and vehicle != filters["vehicle_type"]:
            continue
        if filters["session_id"] is not None and row.get("session_id") != filters["session_id"]:
            continue
        camera = cameras.setdefault(camera_id, _counter(camera_id=camera_id, camera_name=str(row.get("camera_name") or f"Camera #{camera_id}")))
        vehicle = vehicle if vehicle in VEHICLE_LABELS else "other"
        cls = classes.setdefault(vehicle, _counter(vehicle_type=vehicle))
        hourly = hours.setdefault(hour.isoformat(), _counter(bucket=hour.isoformat()))
        for target in (total, series[_bucket(hour, filters["group_by"])], camera, cls, hourly):
            _add(target, direction, count)
        if row.get("session_id") is not None:
            sessions.add(row["session_id"])
    peaks = sorted(hours.values(), key=lambda item: (-item["total"], item["bucket"]))[:5]
    return {"filters": filters,
            "summary": {**total, "session_count": len(sessions), "camera_count": len(cameras), "peak_hour": peaks[0] if peaks else None},
            "series": list(series.values()), "per_camera": sorted(cameras.values(), key=lambda item: item["camera_id"]),
            "per_class": sorted(classes.values(), key=lambda item: list(VEHICLE_LABELS).index(item["vehicle_type"])),
            "peak_hours": peaks, "warnings": [RECORDED_WARNING]}


def report_tables(report: dict) -> list[tuple[str, list[list]]]:
    """All exports use the same aggregate payload as the visible report."""
    filters, summary = report["filters"], report["summary"]
    metadata = [["BÁO CÁO LƯU LƯỢNG GIAO THÔNG"], ["Thời gian", filters["start"], filters["end"], "Kết thúc không bao gồm"],
                ["Đồng hồ", "Thời điểm ghi nhận (UTC+7)"], ["Nhóm", {"hour": "Theo giờ", "day": "Theo ngày", "month": "Theo tháng"}[filters["group_by"]]],
                ["Camera", filters["camera_id"] or "Tất cả"], ["Loại xe", VEHICLE_LABELS.get(filters["vehicle_type"], "Tất cả")],
                ["Phiên", filters["session_id"] or "Tất cả"], ["Lưu ý", RECORDED_WARNING],
                ["Tổng lượt", summary["total"]], ["IN", summary["in"]], ["OUT", summary["out"]], ["Chưa rõ hướng", summary["unknown"]],
                ["Số phiên", summary["session_count"]], ["Số camera", summary["camera_count"]]]
    def rows(values, label, key):
        return [[label, "Tổng lượt", "IN", "OUT", "Chưa rõ hướng"]] + [
            [key(item), item["total"], item["in"], item["out"], item["unknown"]] for item in values]
    return [("Tong quan", metadata),
            ("Luu luong", rows(report["series"], "Khoảng thời gian (UTC+7)", lambda item: item["bucket"])),
            ("Camera", rows(report["per_camera"], "Camera", lambda item: f"#{item['camera_id']} {item['camera_name']}")),
            ("Loai xe", rows(report["per_class"], "Loại xe", lambda item: VEHICLE_LABELS[item["vehicle_type"]])),
            ("Gio cao diem", rows(report["peak_hours"], "Giờ cao điểm (UTC+7)", lambda item: item["bucket"]))]


def _safe_text(value) -> str:
    value = str(value)
    # CSV spreadsheets must not execute camera names as formulas.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")) else value


def export_csv(report: dict) -> bytes:
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    for name, rows in report_tables(report):
        writer.writerow([name])
        writer.writerows([[_safe_text(value) if isinstance(value, str) else value for value in row] for row in rows])
        writer.writerow([])
    return stream.getvalue().encode("utf-8-sig")


def _xml_text(value) -> str:
    # XML 1.0 excludes control characters even when they occur in a camera name.
    return escape(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value)))


def export_xlsx(report: dict) -> bytes:
    """A standards-based OOXML workbook with typed numbers and literal strings."""
    stream = BytesIO()
    sheets = report_tables(report)
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    rel_ns = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        overrides = ''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, len(sheets)+1))
        archive.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'+overrides+'</Types>')
        archive.writestr('_rels/.rels', f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="{rel_ns}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr('xl/workbook.xml', f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="{ns}" xmlns:r="{rel_ns}"><sheets>'+''.join(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>' for i,(name,_) in enumerate(sheets,1))+'</sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="{rel_ns}/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(sheets)+1))+'</Relationships>')
        for i, (_, rows) in enumerate(sheets, 1):
            xml_rows = []
            for row_index, row in enumerate(rows, 1):
                cells = []
                for column, value in enumerate(row):
                    ref = f'{chr(65+column)}{row_index}'
                    cells.append(f'<c r="{ref}"><v>{value}</v></c>' if isinstance(value, (int, float)) else f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{_xml_text(value)}</t></is></c>')
                xml_rows.append(f'<row r="{row_index}">'+''.join(cells)+'</row>')
            archive.writestr(f'xl/worksheets/sheet{i}.xml', f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{ns}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="1" width="38" customWidth="1"/><col min="2" max="5" width="20" customWidth="1"/></cols><sheetData>'+''.join(xml_rows)+'</sheetData></worksheet>')
    return stream.getvalue()


def export_pdf(report: dict) -> bytes:
    """Paginated PDF, embedded Vietnamese font; no host font dependency."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    font_name = "TrafficDejaVu"
    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font_name, str(Path(__file__).parent / "assets" / "DejaVuSans.ttf")))
    stream = BytesIO()
    style = ParagraphStyle("TrafficReport", fontName=font_name, fontSize=8, leading=11)
    title_style = ParagraphStyle("TrafficTitle", parent=style, fontSize=13, leading=18, spaceAfter=10, keepWithNext=True)
    document = SimpleDocTemplate(stream, pagesize=landscape(A4), rightMargin=28, leftMargin=28,
                                 topMargin=28, bottomMargin=32, title="Báo cáo lưu lượng giao thông", author="Traffic AI")
    story = [Paragraph("BÁO CÁO LƯU LƯỢNG GIAO THÔNG", title_style)]
    for name, raw_rows in report_tables(report):
        section = {"Tong quan": "Tổng quan", "Luu luong": "Lưu lượng", "Camera": "Camera", "Loai xe": "Loại xe", "Gio cao diem": "Giờ cao điểm"}[name]
        story.append(Paragraph(section, title_style))
        columns = max(map(len, raw_rows))
        widths = [360, 100, 100, 100] if columns == 4 else [330, 110] if columns == 2 else [330, 105, 105, 105, 105] if columns == 5 else [760]
        if name == "Tong quan":
            # Metadata has a variable number of cells; wrap all values in two columns.
            raw_rows = [[row[0], " | ".join(str(value) for value in row[1:])] for row in raw_rows]
            widths = [125, 650]
        rows = [[Paragraph(_xml_text(value), style) for value in row] for row in raw_rows]
        table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),font_name),('VALIGN',(0,0),(-1,-1),'TOP'),
                                   ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e6eef8')),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#c6d0dc')),
                                   ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
        story.extend([table, Spacer(1, 15)])
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(font_name, 8)
        canvas.drawString(28, 16, f"Traffic AI | Thời điểm ghi nhận UTC+7 | Trang {doc.page}")
        canvas.restoreState()
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()
