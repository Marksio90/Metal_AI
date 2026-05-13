export type Role = "user" | "assistant";

export type ChatMessage = {
  role: Role;
  content: string;
};

export type ChatSummary = {
  id: string;
  title: string;
  subtitle: string;
};
