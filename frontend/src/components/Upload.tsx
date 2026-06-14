import { useRef, useState } from "react";
import { uploadSyllabus } from "../api";
import type { UploadResponse } from "../api";


interface Props {
  onUpload: (result: UploadResponse) => void;
}

export default function Upload({ onUpload }: Props) {
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Only PDF files are supported.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const result = await uploadSyllabus(file);
      onUpload(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setLoading(false);
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50 px-4">
      <div className="max-w-lg w-full">
        <h1 className="text-4xl font-bold text-gray-900 mb-2 text-center">
          SyllabusAI
        </h1>
        <p className="text-gray-500 text-center mb-8">
          Upload your course syllabus and ask questions about it.
        </p>

        <div
          className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
            dragging
              ? "border-indigo-500 bg-indigo-50"
              : "border-gray-300 hover:border-indigo-400 bg-white"
          }`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          {loading ? (
            <div className="flex flex-col items-center gap-3">
              <svg className="animate-spin h-8 w-8 text-indigo-500" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              <p className="text-gray-600">Processing syllabus…</p>
              <p className="text-gray-400 text-sm">Extracting dates, grades, and policies</p>
            </div>
          ) : (
            <>
              <svg className="mx-auto h-12 w-12 text-gray-400 mb-4" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <p className="text-lg font-medium text-gray-700 mb-1">Drop your syllabus PDF here</p>
              <p className="text-gray-400 text-sm">or click to browse</p>
            </>
          )}
        </div>

        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />

        {error && (
          <p className="mt-4 text-center text-red-600 text-sm">{error}</p>
        )}
      </div>
    </div>
  );
}
