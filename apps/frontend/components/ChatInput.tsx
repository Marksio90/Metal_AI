import { useState } from "react";

type ChatInputProps = {
  onSend: (content: string) => Promise<void>;
  disabled?: boolean;
};

export function ChatInput({ onSend, disabled = false }: ChatInputProps) {
  const [value, setValue] = useState("");

  const submit = async () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) {
      return;
    }
    setValue("");
    await onSend(trimmed);
  };

  return (
    <div className="border-t border-slate-800 bg-slate-900 p-4">
      <div className="mx-auto flex max-w-3xl items-end gap-3">
        <textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="Write a message..."
          rows={2}
          disabled={disabled}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void submit();
            }
          }}
          className="min-h-12 flex-1 resize-none rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-70"
        />
        <button
          type="button"
          disabled={disabled || value.trim().length === 0}
          onClick={() => void submit()}
          className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-700"
        >
          Send
        </button>
      </div>
    </div>
  );
}
