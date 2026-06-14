"""
calendar_export.py — Generate a .ics calendar file from structured syllabus data.

Exports exam dates and assignment deadlines as all-day events.
Dates in ISO 8601 (YYYY-MM-DD) are used directly; unparseable dates are recorded
in CalendarResult.skipped so callers can surface them to the user.

Run directly to test: python calendar_export.py path/to/syllabus.pdf
"""

import sys
from dataclasses import dataclass, field
from datetime import date
from icalendar import Calendar, Event
from models import SyllabusStructure


@dataclass
class CalendarResult:
    ics_bytes: bytes
    skipped: list[dict] = field(default_factory=list)  # [{"name": ..., "date": ..., "type": "exam"|"assignment"}]


def _parse_date(date_str: str) -> date | None:
    """Parse ISO 8601 date string. Returns None if unparseable (verbatim syllabus text)."""
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None


def generate_ics(structure: SyllabusStructure) -> CalendarResult:
    """
    Build a .ics file from exam_dates and assignment_deadlines.
    Returns CalendarResult with ics_bytes and a list of events that had unparseable dates.
    """
    cal = Calendar()
    cal.add("prodid", "-//SyllabusAI//syllabusai//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")

    course = structure.course_name or "Course"
    skipped = []

    for exam in structure.exam_dates:
        d = _parse_date(exam.get("date", ""))
        if d is None:
            skipped.append({"name": exam["name"], "date": exam.get("date", ""), "type": "exam"})
            continue
        event = Event()
        event.add("summary", f"{exam['name']} — {course}")
        event.add("dtstart", d)
        event.add("dtend", d)
        cal.add_component(event)

    for assignment in structure.assignment_deadlines:
        d = _parse_date(assignment.get("date", ""))
        if d is None:
            skipped.append({"name": assignment["name"], "date": assignment.get("date", ""), "type": "assignment"})
            continue
        event = Event()
        event.add("summary", f"{assignment['name']} due — {course}")
        event.add("dtstart", d)
        event.add("dtend", d)
        cal.add_component(event)

    return CalendarResult(ics_bytes=cal.to_ical(), skipped=skipped)


# ── quick smoke test when run directly ────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python calendar_export.py <path_to_pdf>")
        sys.exit(1)

    from dotenv import load_dotenv
    from ingest import extract_text_by_page
    from extract import extract_structure

    load_dotenv()

    pdf_path = sys.argv[1]
    pages = extract_text_by_page(pdf_path)
    full_text = "\n\n".join(p["text"] for p in pages)
    structure = extract_structure(full_text)

    result = generate_ics(structure)

    out_path = "test_output.ics"
    with open(out_path, "wb") as f:
        f.write(result.ics_bytes)

    exported = (len(structure.exam_dates) + len(structure.assignment_deadlines)) - len(result.skipped)
    print(f"Wrote {out_path}")
    print(f"  {exported} event(s) exported")
    if result.skipped:
        print(f"  {len(result.skipped)} skipped (no parseable date):")
        for s in result.skipped:
            print(f"    [{s['type']}] {s['name']!r} — date was: {s['date']!r}")
