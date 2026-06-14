import { useEffect, useRef, useState } from "react";
import { querySession } from "../api";
import type { QueryResponse } from "../api";

interface Message {
  role: "user" | "assistant";
  text: string;
  layer?: QueryResponse["layer_used"];
}

interface Props {
  sessionId: string;
}

export default function Chat({ sessionId }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSubmit() {
    const question = input.trim();
    if (!question || loading) return;

    setInput("");
    setError(null);
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setLoading(true);

    try {
      const res = await querySession(sessionId, question);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: res.answer, layer: res.layer_used },
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Query failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-full bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="font-semibold text-gray-900">Ask a question</h2>
        <p className="text-xs text-gray-400 mt-0.5">About your syllabus</p>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 text-sm mt-8">
            <p>Try asking:</p>
            <div className="mt-3 space-y-2">
              {[
                "When is the midterm?",
                "What is the late work policy?",
                "How is the final grade calculated?",
                "When are office hours?",
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => setInput(q)}
                  className="block w-full text-left px-3 py-2 rounded-lg bg-gray-50 hover:bg-indigo-50 hover:text-indigo-700 transition-colors text-sm"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] ${msg.role === "user" ? "items-end" : "items-start"} flex flex-col gap-1`}>
              <div
                className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-indigo-600 text-white rounded-br-sm"
                    : "bg-gray-100 text-gray-800 rounded-bl-sm"
                }`}
              >
                {msg.text}
              </div>
              {msg.layer && (
                <span
                  className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    msg.layer === "structured"
                      ? "bg-green-100 text-green-700"
                      : "bg-blue-100 text-blue-700"
                  }`}
                >
                  {msg.layer === "structured" ? "Extracted data" : "Semantic search"}
                </span>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-3">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}

        {error && (
          <p className="text-center text-red-500 text-sm">{error}</p>
        )}

        <div ref={bottomRef} />
      </div>

      <form onSubmit={(e) => { e.preventDefault(); handleSubmit(); }} className="border-t border-gray-100 px-4 py-3 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your syllabus…"
          className="flex-1 rounded-lg border border-gray-200 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="bg-indigo-600 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Send
        </button>
      </form>
    </div>
  );
}
