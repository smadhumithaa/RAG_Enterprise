import { useEffect, useRef, useState } from "react";

const API_BASE = "http://localhost:8000";

type Source = { filename: string; page: string | number };

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  timestamp: Date;
};

const uuid = () => Math.random().toString(36).slice(2);

async function askQuestion(question: string, sessionId: string) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, session_id: sessionId }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function uploadFile(file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/upload`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function getSources() {
  const res = await fetch(`${API_BASE}/sources`);
  return res.json();
}

function SourceBadge({ source }: { source: Source }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
      SOURCE {source.filename} · p.{source.page}
    </span>
  );
}

function ChatMessage({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  return (
    <div className={`mb-4 flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[75%] ${isUser ? "order-2" : "order-1"}`}>
        {!isUser && (
          <div className="mb-1 flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-purple-600 text-xs font-bold text-white">
              R
            </div>
            <span className="text-xs font-medium text-gray-500">EnterpriseRAG</span>
          </div>
        )}
        <div
          className={`whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? "rounded-tr-sm bg-blue-600 text-white"
              : "rounded-tl-sm border border-gray-200 bg-white text-gray-800 shadow-sm"
          }`}
        >
          {msg.content}
        </div>
        {msg.sources && msg.sources.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {msg.sources.map((s, i) => (
              <SourceBadge key={i} source={s} />
            ))}
          </div>
        )}
        <div className="mt-1 px-1 text-xs text-gray-400">
          {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </div>
      </div>
    </div>
  );
}

function UploadPanel({
  onUpload,
  sources,
}: {
  onUpload: (file: File) => Promise<void>;
  sources: string[];
}) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    setUploading(true);
    setUploadMsg("");
    try {
      await onUpload(file);
      setUploadMsg(`OK: ${file.name} ingested successfully`);
    } catch (e: unknown) {
      const err = e as Error;
      setUploadMsg(`ERROR: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div>
        <h2 className="mb-1 text-sm font-semibold text-gray-700">Upload Documents</h2>
        <p className="text-xs text-gray-400">PDF, DOCX, TXT supported</p>
      </div>

      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const file = e.dataTransfer.files[0];
          if (file) handleFile(file);
        }}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-6 text-center transition-colors ${
          dragging
            ? "border-blue-400 bg-blue-50"
            : "border-gray-300 hover:border-blue-300 hover:bg-gray-50"
        }`}
      >
        <div className="mb-2 text-2xl">{uploading ? "..." : "FILE"}</div>
        <p className="text-xs text-gray-500">{uploading ? "Ingesting..." : "Click or drag and drop"}</p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
          }}
        />
      </div>

      {uploadMsg && <p className="rounded border bg-gray-50 px-2 py-1 text-xs text-gray-600">{uploadMsg}</p>}

      <div>
        <h3 className="mb-2 text-xs font-semibold text-gray-600">Ingested Documents ({sources.length})</h3>
        {sources.length === 0 ? (
          <p className="text-xs italic text-gray-400">No documents yet</p>
        ) : (
          <ul className="space-y-1">
            {sources.map((s, i) => (
              <li key={i} className="flex items-center gap-2 rounded bg-gray-50 px-2 py-1 text-xs text-gray-600">
                <span>DOC</span>
                <span className="truncate">{s}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: uuid(),
      role: "assistant",
      content:
        "Hi! I am EnterpriseRAG.\n\nUpload your documents on the left, then ask questions. Answers include source citations.",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => uuid());
  const [sources, setSources] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const refreshSources = async () => {
    try {
      const data = await getSources();
      setSources(data.sources || []);
    } catch {
      setSources([]);
    }
  };

  const handleUpload = async (file: File) => {
    await uploadFile(file);
    await refreshSources();
  };

  const handleSend = async () => {
    const q = input.trim();
    if (!q || loading) return;

    const userMsg: Message = { id: uuid(), role: "user", content: q, timestamp: new Date() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const data = await askQuestion(q, sessionId);
      const assistantMsg: Message = {
        id: uuid(),
        role: "assistant",
        content: data.answer,
        sources: data.sources,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e: unknown) {
      const err = e as Error;
      setMessages((prev) => [
        ...prev,
        {
          id: uuid(),
          role: "assistant",
          content: `ERROR: ${err.message}`,
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-gray-100 font-sans">
      <div className="flex w-72 flex-col border-r border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-100 px-4 py-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 text-sm font-bold text-white">
              R
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-800">EnterpriseRAG</p>
              <p className="text-xs text-gray-400">Powered by Gemini 1.5 Pro</p>
            </div>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          <UploadPanel onUpload={handleUpload} sources={sources} />
        </div>
      </div>

      <div className="flex flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-3 shadow-sm">
          <div>
            <h1 className="font-semibold text-gray-800">Knowledge Assistant</h1>
            <p className="text-xs text-gray-400">Ask anything about your internal documents</p>
          </div>
          <button
            onClick={refreshSources}
            className="rounded-lg border border-blue-200 px-3 py-1.5 text-xs text-blue-500 transition-colors hover:bg-blue-50 hover:text-blue-700"
          >
            Refresh Sources
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {messages.map((msg) => (
            <ChatMessage key={msg.id} msg={msg} />
          ))}
          {loading && (
            <div className="mb-4 flex justify-start">
              <div className="rounded-2xl rounded-tl-sm border border-gray-200 bg-white px-4 py-3 shadow-sm">
                <div className="flex items-center gap-1">
                  <div className="h-2 w-2 animate-bounce rounded-full bg-blue-400" style={{ animationDelay: "0ms" }} />
                  <div
                    className="h-2 w-2 animate-bounce rounded-full bg-blue-400"
                    style={{ animationDelay: "150ms" }}
                  />
                  <div
                    className="h-2 w-2 animate-bounce rounded-full bg-blue-400"
                    style={{ animationDelay: "300ms" }}
                  />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="border-t border-gray-200 bg-white px-6 py-4">
          <div className="flex items-end gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Ask a question about your documents..."
              rows={1}
              className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 text-sm transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-400"
              style={{ minHeight: "46px", maxHeight: "120px" }}
            />
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className="flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-300"
            >
              {loading ? "..." : "Send ->"}
            </button>
          </div>
          <p className="mt-2 text-center text-xs text-gray-400">
            Press Enter to send | Shift+Enter for new line
          </p>
        </div>
      </div>
    </div>
  );
}
