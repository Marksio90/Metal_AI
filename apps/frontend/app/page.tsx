"use client";

import { useEffect, useMemo, useState } from "react";
import { ChatInput } from "../components/ChatInput";
import { ChatLayout } from "../components/ChatLayout";
import { Sidebar } from "../components/Sidebar";
import type { ChatMessage, ChatSummary } from "../lib/chat-types";

type ConfigResponse = {
  model: string;
};

type ChatResponse = {
  message: string;
  conversationId: string;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function HomePage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [model, setModel] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/config`);
        if (!response.ok) {
          throw new Error("Unable to load backend config.");
        }
        const json: ConfigResponse = await response.json();
        setModel(json.model);
      } catch {
        setError("Could not load backend configuration. Check backend connection.");
      }
    };

    void loadConfig();
  }, []);

  const placeholderConversations = useMemo<ChatSummary[]>(
    () => [
      {
        id: conversationId ?? "draft",
        title: conversationId ? `Chat ${conversationId.slice(0, 8)}` : "Current chat",
        subtitle: messages.length > 0 ? `${messages.length} messages` : "No messages yet"
      },
      { id: "placeholder-1", title: "Roadmap planning", subtitle: "Placeholder conversation" },
      { id: "placeholder-2", title: "Debug session", subtitle: "Placeholder conversation" }
    ],
    [conversationId, messages.length]
  );

  const startNewChat = () => {
    setConversationId(null);
    setMessages([]);
    setError("");
  };

  const handleSend = async (content: string) => {
    setError("");
    const nextMessages = [...messages, { role: "user", content } as ChatMessage];
    setMessages(nextMessages);
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: content,
          conversationId,
          history: messages
        })
      });

      if (!response.ok) {
        const errorData = (await response.json().catch(() => ({}))) as { detail?: string };
        throw new Error(errorData.detail ?? "Unknown backend error.");
      }

      const json: ChatResponse = await response.json();
      setConversationId(json.conversationId);
      setMessages((prev) => [...prev, { role: "assistant", content: json.message }]);
    } catch (requestError) {
      const fallback = "Cannot reach backend service. Ensure API key and backend are configured.";
      const detail = requestError instanceof Error ? requestError.message : fallback;
      setError(detail || fallback);
      setMessages(messages);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex h-screen bg-slate-950 text-slate-100">
      <Sidebar
        conversations={placeholderConversations}
        activeConversationId={conversationId}
        onNewChat={startNewChat}
        model={model}
      />

      <div className="flex flex-1 flex-col">
        <ChatLayout messages={messages} loading={loading} error={error} />
        <ChatInput onSend={handleSend} disabled={loading} />
      </div>
    </main>
  );
}
