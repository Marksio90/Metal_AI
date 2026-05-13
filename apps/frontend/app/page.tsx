"use client";

import { useEffect, useState } from "react";

type ConfigResponse = { model: string };
type RFQAnalyzeResponse = {
  rfqId: string;
  detectedParts: Array<Record<string, unknown>>;
  missingInformation: string[];
  suggestedRoute: string[];
  riskFlags: string[];
  internalNotes: string[];
  customerQuestions: string[];
  draftCustomerReply: string;
  confidence: number;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function HomePage() {
  const [model, setModel] = useState("");
  const [customer, setCustomer] = useState("Example Customer");
  const [quantity, setQuantity] = useState<number>(50);
  const [message, setMessage] = useState("Please quote 50 pcs from S235 steel, 3 mm sheet, laser cut, bent twice, powder coated black RAL 9005.");
  const [attachments, setAttachments] = useState("drawing.pdf");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [result, setResult] = useState<RFQAnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/config`)
      .then((r) => r.json() as Promise<ConfigResponse>)
      .then((c) => setModel(c.model))
      .catch(() => setError("Could not load backend configuration."));
  }, []);

  const analyze = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/rfq/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer,
          message,
          quantity,
          attachments: attachments ? attachments.split(",").map((a) => a.trim()).filter(Boolean) : []
        })
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail ?? "RFQ analysis failed.");
      }
      const analyzed = (await response.json()) as RFQAnalyzeResponse;
      setResult(analyzed);
      if (selectedFile && result?.rfqId) {
        const form = new FormData();
        form.append("rfq_id", result.rfqId);
        form.append("file", selectedFile);
        await fetch(`${API_BASE_URL}/api/rfq/upload-attachment`, { method: "POST", body: form });
      }

    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        <h1 className="text-3xl font-bold">Metal_AI RFQ Analysis</h1>
        <p className="text-slate-300">Primary RFQ workflow (model: {model || "loading..."}).</p>

        <section className="bg-slate-900 p-4 rounded-xl space-y-3">
          <input className="w-full bg-slate-800 p-2 rounded" value={customer} onChange={(e) => setCustomer(e.target.value)} placeholder="Customer name" />
          <input className="w-full bg-slate-800 p-2 rounded" type="number" value={quantity} onChange={(e) => setQuantity(Number(e.target.value))} placeholder="Quantity" />
          <textarea className="w-full bg-slate-800 p-2 rounded min-h-36" value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Paste RFQ text" />
          <input className="w-full bg-slate-800 p-2 rounded" value={attachments} onChange={(e) => setAttachments(e.target.value)} placeholder="Attachment placeholders (comma separated)" />
          <input className="w-full bg-slate-800 p-2 rounded" type="file" onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)} />
          <button className="bg-blue-600 px-4 py-2 rounded disabled:opacity-50" disabled={loading} onClick={analyze}>{loading ? "Analyzing..." : "Analyze RFQ"}</button>
          {error && <p className="text-red-400">{error}</p>}
        </section>

        {result && (
          <section className="grid md:grid-cols-2 gap-4">
            <Card title="Detected Data"><pre>{JSON.stringify(result.detectedParts, null, 2)}</pre></Card>
            <Card title="Missing Information"><List items={result.missingInformation} empty="No missing fields detected." /></Card>
            <Card title="Suggested Manufacturing Route"><List items={result.suggestedRoute} empty="No route suggested." /></Card>
            <Card title="Risks"><List items={result.riskFlags} empty="No risk flags." /></Card>
            <Card title="Questions to Customer"><List items={result.customerQuestions} empty="No follow-up questions." /></Card>
            <Card title="Internal Notes"><List items={result.internalNotes} empty="No notes." /></Card>
            <Card title="Draft Customer Reply"><p>{result.draftCustomerReply}</p></Card>
            <Card title="Confidence"><p>{Math.round(result.confidence * 100)}%</p></Card>
          </section>
        )}
      </div>
    </main>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="bg-slate-900 p-4 rounded-xl"><h2 className="font-semibold mb-2">{title}</h2><div className="text-sm text-slate-200">{children}</div></div>;
}

function List({ items, empty }: { items: string[]; empty: string }) {
  if (!items.length) return <p>{empty}</p>;
  return <ul className="list-disc pl-5 space-y-1">{items.map((i) => <li key={i}>{i}</li>)}</ul>;
}
