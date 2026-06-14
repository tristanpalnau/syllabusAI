"""
extract.py — Layer 1: structured extraction via Claude tool use.

Tool use forces schema-conforming output — Claude cannot return free-form text
when tool_choice is pinned to a specific tool. No JSON parsing, no regex.

Run directly to test: python extract.py path/to/syllabus.pdf
"""

import os
import sys
from anthropic import Anthropic
from models import SyllabusStructure


_TOOL_NAME = "extract_syllabus_structure"

_TOOL_SCHEMA = {
    "name": _TOOL_NAME,
    "description": (
        "Extract structured data from a course syllabus. "
        "Use null for any field not present. Use [] for empty lists."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "course_name": {
                "type": ["string", "null"],
                "description": "Full course name and number, e.g. 'MATH 2202 - Calculus II'",
            },
            "instructor": {
                "type": ["object", "null"],
                "description": "Primary instructor contact info",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "office": {"type": "string"},
                },
            },
            "exam_dates": {
                "type": "array",
                "description": "All exams, quizzes, and tests with their dates",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "e.g. 'Midterm 1', 'Final Exam'"},
                        "date": {
                            "type": "string",
                            "description": "ISO 8601 YYYY-MM-DD when year is known; otherwise verbatim text from syllabus",
                        },
                    },
                    "required": ["name", "date"],
                },
            },
            "assignment_deadlines": {
                "type": "array",
                "description": "Named assignments and projects with due dates",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "date": {"type": "string"},
                    },
                    "required": ["name", "date"],
                },
            },
            "grade_weights": {
                "type": "object",
                "description": "Grade components mapped to their percentage weights, e.g. {'Exams': 40, 'Homework': 30}",
                "additionalProperties": {"type": "number"},
            },
            "late_policy": {
                "type": ["string", "null"],
                "description": "Full text of the late work or makeup policy",
            },
            "attendance_policy": {
                "type": ["string", "null"],
                "description": "Full text of the attendance policy",
            },
            "office_hours": {
                "type": "array",
                "description": "Office hours for instructor and any TAs",
                "items": {
                    "type": "object",
                    "properties": {
                        "instructor": {"type": "string"},
                        "time": {"type": "string"},
                        "location": {"type": "string"},
                    },
                    "required": ["instructor", "time"],
                },
            },
        },
        "required": [
            "course_name",
            "instructor",
            "exam_dates",
            "assignment_deadlines",
            "grade_weights",
            "late_policy",
            "attendance_policy",
            "office_hours",
        ],
    },
}


def extract_structure(full_text: str) -> SyllabusStructure:
    """
    Call Claude with a pinned tool to extract structured fields from syllabus text.

    Forcing tool_choice to a specific tool means Claude must populate the schema —
    it cannot fall back to prose. The response is always a valid tool_use block.
    """
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        tools=[_TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": _TOOL_NAME},
        messages=[
            {
                "role": "user",
                "content": (
                    "Extract all structured data from this course syllabus. "
                    "Use null for fields not found. Use [] for empty lists. "
                    "For dates, prefer ISO 8601 format (YYYY-MM-DD) when the year "
                    "is determinable; otherwise use the text exactly as written.\n\n"
                    f"Syllabus:\n{full_text}"
                ),
            }
        ],
    )

    # tool_choice={"type": "tool"} guarantees a tool_use block is present
    tool_block = next(b for b in response.content if b.type == "tool_use")
    data = tool_block.input

    return SyllabusStructure(
        course_name=data.get("course_name"),
        instructor=data.get("instructor"),
        exam_dates=data.get("exam_dates") or [],
        assignment_deadlines=data.get("assignment_deadlines") or [],
        grade_weights=data.get("grade_weights") or {},
        late_policy=data.get("late_policy"),
        attendance_policy=data.get("attendance_policy"),
        office_hours=data.get("office_hours") or [],
    )


# ── quick smoke test when run directly ────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract.py <path_to_pdf>")
        sys.exit(1)

    from dotenv import load_dotenv
    from ingest import extract_text_by_page

    load_dotenv()

    pdf_path = sys.argv[1]
    pages = extract_text_by_page(pdf_path)
    full_text = "\n\n".join(p["text"] for p in pages)
    print(f"Extracted {len(full_text)} chars from {len(pages)} pages.")
    print("Calling Claude for structured extraction...\n")

    result = extract_structure(full_text)

    print(f"Course:      {result.course_name}")
    print(f"Instructor:  {result.instructor}")
    print(f"Exam dates:  {result.exam_dates}")
    print(f"Grade weights: {result.grade_weights}")
    print(f"Late policy: {(result.late_policy or '')[:200]}")
    print(f"Office hours: {result.office_hours}")
