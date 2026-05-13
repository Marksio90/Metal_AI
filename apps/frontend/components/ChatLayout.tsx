import type { ChatMessage } from "../lib/chat-types";
import { MessageBubble } from "./MessageBubble";

type ChatLayoutProps = {
  messages: ChatMessage[];
  loading: boolean;
  error?: string;
};

export function ChatLayout({ messages, loading, error }: ChatLayoutProps) {
  return (
    <section className="flex-1 overflow-y-auto bg-slate-900 px-6 py-6">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
        {messages.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-700 p-8 text-center text-sm text-slate-400">
            Start chatting to see messages here.
          </div>
        ) : (
          messages.map((message, index) => <MessageBubble key={`${message.role}-${index}`} message={message} />)
        )}

        {loading ? <p className="text-sm text-slate-400">Assistant is thinking...</p> : null}

        {error ? (
          <div className="rounded-lg border border-red-800 bg-red-950/50 p-3 text-sm text-red-300">{error}</div>
        ) : null}
      </div>
    </section>
  );
}
