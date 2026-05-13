import type { ChatSummary } from "../lib/chat-types";

type SidebarProps = {
  conversations: ChatSummary[];
  activeConversationId: string | null;
  onNewChat: () => void;
  model?: string;
};

export function Sidebar({ conversations, activeConversationId, onNewChat, model }: SidebarProps) {
  return (
    <aside className="flex h-full w-80 flex-col border-r border-slate-800 bg-slate-950/80 p-4">
      <button
        type="button"
        onClick={onNewChat}
        className="rounded-lg bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-900 transition hover:bg-white"
      >
        + New Chat
      </button>

      <div className="mt-6 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Conversations</h2>
        {model ? (
          <span className="rounded-full border border-emerald-700/70 bg-emerald-900/50 px-2 py-1 text-xs text-emerald-300">
            {model}
          </span>
        ) : null}
      </div>

      <ul className="mt-3 space-y-2 overflow-y-auto">
        {conversations.length === 0 ? (
          <li className="rounded-lg border border-dashed border-slate-700 p-3 text-sm text-slate-400">
            No chats yet. Start a new conversation.
          </li>
        ) : (
          conversations.map((chat) => {
            const isActive = activeConversationId === chat.id;
            return (
              <li
                key={chat.id}
                className={`rounded-lg border p-3 text-sm transition ${
                  isActive
                    ? "border-slate-500 bg-slate-800 text-slate-100"
                    : "border-slate-800 bg-slate-900 text-slate-300"
                }`}
              >
                <p className="truncate font-medium">{chat.title}</p>
                <p className="mt-1 text-xs text-slate-400">{chat.subtitle}</p>
              </li>
            );
          })
        )}
      </ul>
    </aside>
  );
}
