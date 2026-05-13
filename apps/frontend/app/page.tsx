import { BackendStatus } from "../components/BackendStatus";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-4 p-8">
      <h1 className="text-3xl font-bold">Metal AI</h1>
      <p>Next.js frontend scaffold for UI and workflow orchestration.</p>
      <BackendStatus />
    </main>
  );
}
