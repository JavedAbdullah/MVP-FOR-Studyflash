"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ChevronDown,
  Mail,
  MessageSquareText,
  RefreshCw,
  Send,
  User,
} from "lucide-react";

type Agent = {
  id: number;
  name: string;
  email: string;
  role: string;
};

type Message = {
  id: number;
  ticket_id: number;
  sender_type: "customer" | "agent" | string;
  body: string;
  outlook_message_id: string | null;
  created_at: string;
};

type Ticket = {
  id: number;
  subject: string;
  customer_email: string;
  status: string;
  category: string | null;
  priority: string | null;
  ai_draft: string | null;
  agent: Agent | null;
  messages: Message[];
  created_at: string;
};

const API_BASE = "http://localhost:8000";

function badgeClass(variant: "bug" | "refund" | "info" | "priority" | "neutral") {
  switch (variant) {
    case "bug":
      return "bg-red-50 text-red-700 ring-red-200";
    case "refund":
      return "bg-amber-50 text-amber-700 ring-amber-200";
    case "info":
      return "bg-sky-50 text-sky-700 ring-sky-200";
    case "priority":
      return "bg-slate-50 text-slate-700 ring-slate-200";
    default:
      return "bg-slate-50 text-slate-700 ring-slate-200";
  }
}

function Badge({ label, variant }: { label: string; variant: "bug" | "refund" | "info" | "priority" | "neutral" }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${badgeClass(
        variant
      )}`}
    >
      {label}
    </span>
  );
}

export default function Page() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [draftById, setDraftById] = useState<Record<number, string>>({});
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const sortedTickets = useMemo(() => {
    return [...tickets].sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
  }, [tickets]);

  async function fetchTickets(): Promise<void> {
    try {
      const res = await fetch(`${API_BASE}/tickets`, { cache: "no-store" });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = (await res.json()) as Ticket[];
      setTickets(data);
      setLastUpdated(new Date());
      setError(null);

      setDraftById((prev) => {
        const next: Record<number, string> = { ...prev };
        for (const t of data) {
          if (next[t.id] === undefined) {
            next[t.id] = t.ai_draft ?? "";
          }
        }
        return next;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void fetchTickets();
    const id = window.setInterval(() => {
      void fetchTickets();
    }, 5000);
    return () => window.clearInterval(id);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-slate-700">
        <RefreshCw className="h-4 w-4 animate-spin" />
        <span>Loading tickets…</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Tickets</h1>
          <p className="mt-1 text-sm text-slate-600">
            Auto-ingested via LangGraph (Ollama). Polling every 5 seconds.
          </p>
        </div>
        <div className="text-right text-xs text-slate-500">
          <div className="flex items-center justify-end gap-2">
            <RefreshCw className="h-3.5 w-3.5" />
            <button
              type="button"
              className="rounded-md px-2 py-1 text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
              onClick={() => void fetchTickets()}
            >
              Refresh
            </button>
          </div>
          {lastUpdated ? <div className="mt-1">Updated: {lastUpdated.toLocaleTimeString()}</div> : null}
        </div>
      </div>

      {error ? (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-700 ring-1 ring-red-200">
          Failed to load tickets: {error}
        </div>
      ) : null}

      {sortedTickets.length === 0 ? (
        <div className="rounded-md border border-dashed border-slate-200 p-6 text-sm text-slate-600">
          No tickets yet. The backend poller should create one every ~15 seconds.
        </div>
      ) : (
        <div className="space-y-3">
          {sortedTickets.map((t) => {
            const ticket: Ticket = t;
            const isOpen = openId === t.id;
            const category = (t.category ?? "info").toLowerCase();
            const categoryVariant = category === "bug" || category === "refund" || category === "info" ? (category as "bug" | "refund" | "info") : "info";
            const priorityLabel = t.priority ? `Priority: ${t.priority}` : "Priority: —";
            const agentName = t.agent?.name ?? "Unassigned";
            const firstCustomerMsg = ticket.messages.find((m: Message) => m.sender_type === "customer")?.body ?? "";

            return (
              <div key={t.id} className="rounded-lg border border-slate-200">
                <button
                  type="button"
                  className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-slate-50"
                  onClick={() => setOpenId(isOpen ? null : t.id)}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <Mail className="h-4 w-4 text-slate-500" />
                      <div className="truncate font-medium">{t.subject}</div>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <Badge label={(t.category ?? "info").toUpperCase()} variant={categoryVariant} />
                      <Badge label={priorityLabel} variant="priority" />
                      <span className="inline-flex items-center gap-1 text-xs text-slate-600">
                        <User className="h-3.5 w-3.5" />
                        {agentName}
                      </span>
                    </div>
                  </div>
                  <ChevronDown
                    className={`h-4 w-4 text-slate-500 transition-transform ${isOpen ? "rotate-180" : ""}`}
                  />
                </button>

                {isOpen ? (
                  <div className="space-y-4 border-t border-slate-200 px-4 py-4">
                    <div>
                      <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-800">
                        <MessageSquareText className="h-4 w-4 text-slate-500" />
                        Original customer message
                      </div>
                      <div className="whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-sm text-slate-700 ring-1 ring-slate-200">
                        {firstCustomerMsg || "(missing)"}
                      </div>
                    </div>

                    <div>
                      <div className="mb-2 text-sm font-medium text-slate-800">AI draft</div>
                      <textarea
                        className="min-h-[140px] w-full resize-y rounded-md border border-slate-200 bg-white p-3 text-sm text-slate-800 outline-none ring-0 focus:border-slate-300"
                        value={draftById[t.id] ?? ""}
                        onChange={(e) =>
                          setDraftById((prev) => ({
                            ...prev,
                            [t.id]: e.target.value,
                          }))
                        }
                      />
                      <div className="mt-3 flex items-center justify-end">
                        <button
                          type="button"
                          className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800"
                          onClick={() => {
                            // Placeholder for now
                            // eslint-disable-next-line no-console
                            console.log("send_response", { ticketId: t.id, draft: draftById[t.id] });
                          }}
                        >
                          <Send className="h-4 w-4" />
                          Send Response
                        </button>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
