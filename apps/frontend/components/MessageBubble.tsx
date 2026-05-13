import type { ChatMessage } from "../lib/chat-types";

type MessageBubbleProps = {
  message: ChatMessage;
};

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-2xl rounded-2xl px-4 py-3 text-sm leading-relaxed shadow ${
          isUser
            ? "bg-blue-600 text-white"
            : "border border-slate-700 bg-slate-800 text-slate-100"
        }`}
      >
        {message.content}
      </div>
    </div>
  );
}
