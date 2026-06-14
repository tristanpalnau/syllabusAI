import { useState, useEffect } from "react";
import Upload from "./components/Upload";
import Chat from "./components/Chat";
import StructuredSummary from "./components/StructuredSummary";
import type { UploadResponse } from "./api";
import { pingSession } from "./api";
import "./index.css";

const SESSION_KEY = "syllabusai_session";

function loadSession(): UploadResponse | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as UploadResponse) : null;
  } catch {
    return null;
  }
}

export default function App() {
  const [session, setSession] = useState<UploadResponse | null>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    const stored = loadSession();
    if (!stored) return;

    setSession(stored);
    setChecking(true);
    pingSession(stored.session_id).then((valid) => {
      if (!valid) {
        localStorage.removeItem(SESSION_KEY);
        setSession(null);
      }
      setChecking(false);
    });
  }, []);

  function handleUpload(data: UploadResponse) {
    localStorage.setItem(SESSION_KEY, JSON.stringify(data));
    setSession(data);
  }

  function handleReset() {
    localStorage.removeItem(SESSION_KEY);
    setSession(null);
  }

  if (checking) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <span className="text-gray-400 text-sm">Loading session…</span>
      </div>
    );
  }

  if (!session) {
    return <Upload onUpload={handleUpload} />;
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <span className="font-semibold text-gray-900">SyllabusAI</span>
        <button
          onClick={handleReset}
          className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
        >
          Upload another
        </button>
      </header>

      <main className="flex-1 grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-4 p-4 max-w-6xl mx-auto w-full">
        <div className="lg:max-h-[calc(100vh-80px)] overflow-hidden">
          <StructuredSummary
            summary={session.structured_summary}
            sessionId={session.session_id}
          />
        </div>
        <div className="h-150 lg:h-[calc(100vh-80px)]">
          <Chat sessionId={session.session_id} />
        </div>
      </main>
    </div>
  );
}
