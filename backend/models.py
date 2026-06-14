"""
models.py — Shared data structures used across the backend.

SyllabusStructure is a plain dataclass (no Pydantic) because it's internal state,
not an API boundary. Use dataclasses.asdict() to serialize it for JSON responses.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SyllabusStructure:
    course_name: Optional[str]
    instructor: Optional[dict]          # {"name": ..., "email": ..., "office": ...}
    exam_dates: list[dict]              # [{"name": "Midterm", "date": "2026-10-14"}]
    assignment_deadlines: list[dict]    # [{"name": "HW 1", "date": "2026-09-10"}]
    grade_weights: dict                 # {"Exams": 40, "Homework": 30, ...}
    late_policy: Optional[str]
    attendance_policy: Optional[str]
    office_hours: list[dict]            # [{"instructor": ..., "time": ..., "location": ...}]
