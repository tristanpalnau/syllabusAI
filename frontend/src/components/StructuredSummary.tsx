import { useState } from "react";
import { calendarUrl } from "../api";
import type { StructuredSummary as Summary } from "../api";

interface Props {
  summary: Summary;
  sessionId: string;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-2">{title}</h3>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-1 border-b border-gray-100 last:border-0">
      <span className="text-sm text-gray-600 truncate mr-2">{label}</span>
      <span className="text-sm font-medium text-gray-900 text-right whitespace-nowrap">{value}</span>
    </div>
  );
}

export default function StructuredSummary({ summary, sessionId }: Props) {
  const [copied, setCopied] = useState(false);
  const hasExams = summary.exam_dates.length > 0;
  const hasAssignments = summary.assignment_deadlines.length > 0;
  const hasGrades = Object.keys(summary.grade_weights).length > 0;
  const hasOfficeHours = summary.office_hours.length > 0;

  function copySubscribeUrl() {
    navigator.clipboard.writeText(calendarUrl(sessionId)).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 overflow-y-auto max-h-full">
      <div className="flex items-start justify-between mb-4">
        <div>
          {summary.course_name && (
            <h2 className="text-lg font-semibold text-gray-900">{summary.course_name}</h2>
          )}
          {summary.instructor && (
            <p className="text-sm text-gray-500">{summary.instructor.name}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <a
            href={calendarUrl(sessionId)}
            download
            className="flex items-center gap-1.5 text-xs text-indigo-600 hover:text-indigo-800 font-medium border border-indigo-200 rounded-lg px-3 py-1.5 hover:bg-indigo-50 transition-colors whitespace-nowrap"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Download .ics
          </a>
          <button
            onClick={copySubscribeUrl}
            className="flex items-center gap-1.5 text-xs text-gray-600 hover:text-gray-900 font-medium border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50 transition-colors whitespace-nowrap"
          >
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
            {copied ? "Copied!" : "Copy subscribe URL"}
          </button>
        </div>
      </div>

      {hasExams && (
        <Section title="Exams & Quizzes">
          {summary.exam_dates.map((e, i) => (
            <Row key={i} label={e.name} value={e.date} />
          ))}
        </Section>
      )}

      {hasAssignments && (
        <Section title="Assignment Deadlines">
          {summary.assignment_deadlines.map((a, i) => (
            <Row key={i} label={a.name} value={a.date} />
          ))}
        </Section>
      )}

      {hasGrades && (
        <Section title="Grade Weights">
          {Object.entries(summary.grade_weights).map(([cat, pct]) => (
            <Row key={cat} label={cat} value={`${pct}%`} />
          ))}
        </Section>
      )}

      {hasOfficeHours && (
        <Section title="Office Hours">
          {summary.office_hours.map((oh, i) => (
            <div key={i} className="py-1 border-b border-gray-100 last:border-0">
              <p className="text-sm font-medium text-gray-900">{oh.instructor}</p>
              <p className="text-xs text-gray-500">{oh.time} · {oh.location}</p>
            </div>
          ))}
        </Section>
      )}

      {summary.late_policy && (
        <Section title="Late Policy">
          <p className="text-sm text-gray-600">{summary.late_policy}</p>
        </Section>
      )}

      {summary.attendance_policy && (
        <Section title="Attendance Policy">
          <p className="text-sm text-gray-600">{summary.attendance_policy}</p>
        </Section>
      )}
    </div>
  );
}
