import { useState, useCallback, useRef, useEffect } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import {
  Message,
  MessageContent,
  MessageResponse,
} from "@/components/ai-elements/message";
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputFooter,
  PromptInputButton,
} from "@/components/ai-elements/prompt-input";

// ── Types ──

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface SessionStatus {
  active: boolean;
  model?: string;
  context_pct?: number;
  prompt_tokens?: number;
  context_limit?: number;
  is_running?: boolean;
}

// ── Config ──

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8080";

// ── App ──

function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [statusText, setStatusText] = useState("");
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>({
    active: false,
  });
  const [connected, setConnected] = useState<boolean | null>(null);
  const idCounter = useRef(0);

  // Health check on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/health`)
      .then((r) => r.json())
      .then((data) => {
        setConnected(true);
        setSessionStatus((prev) => ({ ...prev, model: data.model }));
      })
      .catch(() => setConnected(false));
  }, []);

  // Generate unique ID
  const nextId = useCallback(() => {
    idCounter.current += 1;
    return `msg-${idCounter.current}`;
  }, []);

  // Fetch session status
  const refreshStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/status`);
      const data = await res.json();
      setSessionStatus(data);
    } catch {
      // ignore
    }
  }, []);

  // Send message
  const handleSubmit = useCallback(async () => {
    const text = input.trim();
    if (!text || isStreaming) return;

    // Add user message
    const userMsg: ChatMessage = { id: nextId(), role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsStreaming(true);
    setStatusText("💭 Thinking...");

    // Prepare assistant message placeholder
    const assistantId = nextId();
    let assistantContent = "";

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      // Parse SSE stream
      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE events from buffer
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // Keep incomplete line in buffer

        let eventType = "";
        for (const line of lines) {
          if (line.startsWith("event:")) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            const dataStr = line.slice(5).trim();
            if (!dataStr) continue;

            try {
              const data = JSON.parse(dataStr);

              if (eventType === "status") {
                setStatusText(data.text);
              } else if (eventType === "reply") {
                assistantContent = data.text;
                setMessages((prev) => {
                  const existing = prev.find((m) => m.id === assistantId);
                  if (existing) {
                    return prev.map((m) =>
                      m.id === assistantId
                        ? { ...m, content: assistantContent }
                        : m
                    );
                  } else {
                    return [
                      ...prev,
                      {
                        id: assistantId,
                        role: "assistant" as const,
                        content: assistantContent,
                      },
                    ];
                  }
                });
              } else if (eventType === "done") {
                // If no reply was received, don't add empty message
                break;
              }
            } catch {
              // Not valid JSON, skip (could be heartbeat comment)
            }
          }
        }
      }
    } catch (err) {
      // Show error as assistant message
      setMessages((prev) => [
        ...prev,
        {
          id: assistantId,
          role: "assistant",
          content: `❌ Connection error: ${err instanceof Error ? err.message : "Unknown error"}`,
        },
      ]);
    } finally {
      setIsStreaming(false);
      setStatusText("");
      refreshStatus();
    }
  }, [input, isStreaming, nextId, refreshStatus]);

  // Slash commands
  const handleCommand = useCallback(
    async (cmd: string) => {
      try {
        const res = await fetch(`${API_BASE}/api/command/${cmd}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        });
        const data = await res.json();

        if (cmd === "reset") {
          setMessages([]);
        }

        if (data.result) {
          setStatusText(data.result);
          setTimeout(() => setStatusText(""), 5000);
        }

        refreshStatus();
      } catch {
        setStatusText(`❌ Failed to execute /${cmd}`);
      }
    },
    [refreshStatus]
  );

  // Connection indicator color
  const connColor =
    connected === true
      ? "text-green-500"
      : connected === false
        ? "text-red-500"
        : "text-yellow-500";
  const connLabel =
    connected === true
      ? "Connected"
      : connected === false
        ? "Disconnected"
        : "Connecting...";

  // Context bar
  const ctxPct = sessionStatus.context_pct ?? 0;
  const ctxColor =
    ctxPct < 50
      ? "bg-green-500"
      : ctxPct < 80
        ? "bg-yellow-500"
        : "bg-red-500";

  return (
    <TooltipProvider>
      <div className="flex flex-col h-screen bg-background text-foreground">
        {/* Header */}
        <header className="flex items-center justify-between px-4 py-2 border-b border-border">
          <div className="flex items-center gap-3">
            <h1 className="text-sm font-semibold">Nono CoWork</h1>
            <span className={`text-xs ${connColor}`}>● {connLabel}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              {sessionStatus.model || "..."}
            </span>
            <button
              onClick={() => handleCommand("reset")}
              className="text-xs px-2 py-1 rounded hover:bg-muted text-muted-foreground"
              disabled={isStreaming}
            >
              Reset
            </button>
            <button
              onClick={() => handleCommand("stop")}
              className="text-xs px-2 py-1 rounded hover:bg-muted text-muted-foreground"
              disabled={!isStreaming}
            >
              Stop
            </button>
          </div>
        </header>

        {/* Chat area */}
        <Conversation className="flex-1">
          <ConversationContent>
            {messages.length === 0 && !isStreaming && (
              <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-2">
                <p className="text-lg">👋 Ready to chat</p>
                <p className="text-sm">
                  Send a message to start a conversation
                </p>
              </div>
            )}
            {messages.map((msg) => (
              <Message key={msg.id} from={msg.role}>
                <MessageContent>
                  {msg.role === "assistant" ? (
                    <MessageResponse>{msg.content}</MessageResponse>
                  ) : (
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  )}
                </MessageContent>
              </Message>
            ))}
            {isStreaming && statusText && (
              <div className="text-sm text-muted-foreground animate-pulse px-1">
                {statusText}
              </div>
            )}
          </ConversationContent>
          <ConversationScrollButton />
        </Conversation>

        {/* Input area */}
        <div className="border-t border-border p-3">
          <PromptInput
            value={input}
            onValueChange={setInput}
            onSubmit={handleSubmit}
            isLoading={isStreaming}
          >
            <PromptInputTextarea placeholder="Type a message..." />
            <PromptInputFooter>
              <PromptInputButton type="submit" disabled={isStreaming || !input.trim()} />
            </PromptInputFooter>
          </PromptInput>
        </div>

        {/* Footer: context bar */}
        {sessionStatus.active && (
          <footer className="flex items-center gap-3 px-4 py-1.5 border-t border-border text-xs text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <div className="w-24 h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${ctxColor}`}
                  style={{ width: `${ctxPct}%` }}
                />
              </div>
              <span>{ctxPct.toFixed(0)}% context</span>
            </div>
          </footer>
        )}
      </div>
    </TooltipProvider>
  );
}

export default App;
