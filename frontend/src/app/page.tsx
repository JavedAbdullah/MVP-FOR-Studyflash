"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ChevronDown,
  Mail,
  MessageSquareText,
  RefreshCw,
  Send,
  Trash2,
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
  suggested_agent_id?: number | null;
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
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"open" | "closed">("open");
  const [simRunning, setSimRunning] = useState<boolean>(false);
  const [simLoading, setSimLoading] = useState<boolean>(false);
  const [nextInboxInS, setNextInboxInS] = useState<number | null>(null);
  const [cleanLoading, setCleanLoading] = useState<boolean>(false);
  const [openId, setOpenId] = useState<number | null>(null);
  const [draftById, setDraftById] = useState<Record<number, string>>({});
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [assigningById, setAssigningById] = useState<Record<number, boolean>>({});

  const sortedTickets = useMemo(() => {
    return [...tickets].sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
  }, [tickets]);

  const visibleTickets = useMemo(() => {
    const wanted = tab === "open" ? "open" : "closed";
    return sortedTickets.filter((t) => (t.status || "open").toLowerCase() === wanted);
  }, [sortedTickets, tab]);

  function showToast(message: string): void {
    setToast(message);
    window.setTimeout(() => setToast(null), 2200);
  }

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

  async function fetchAgents(): Promise<void> {
    try {
      const res = await fetch(`${API_BASE}/agents`, { cache: "no-store" });
      if (!res.ok) {
        return;
      }
      const data = (await res.json()) as Agent[];
      setAgents(Array.isArray(data) ? data : []);
    } catch {
      // ignore
    }
  }

  async function fetchSimulationStatus(): Promise<void> {
    try {
      const res = await fetch(`${API_BASE}/simulation/status`, { cache: "no-store" });
      if (!res.ok) {
        return;
      }
      const data = (await res.json()) as {
        running: boolean;
        next_in_s?: number | null;
      };
      setSimRunning(Boolean(data.running));
      setNextInboxInS(typeof data.next_in_s === "number" ? data.next_in_s : null);
    } catch {
      // ignore
    }
  }

  async function toggleSimulation(): Promise<void> {
    setSimLoading(true);
    try {
      const endpoint = simRunning ? "stop" : "start";
      const res = await fetch(`${API_BASE}/simulation/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = (await res.json()) as { running: boolean; next_in_s?: number | null };
      setSimRunning(Boolean(data.running));
      setNextInboxInS(typeof data.next_in_s === "number" ? data.next_in_s : null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSimLoading(false);
    }
  }

  async function cleanDb(): Promise<void> {
    setCleanLoading(true);
    try {
      const res = await fetch(`${API_BASE}/admin/clear`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = (await res.json()) as { running: boolean };
      setSimRunning(Boolean(data.running));
      setNextInboxInS(null);
      setOpenId(null);
      setDraftById({});
      await fetchTickets();
      showToast("Database cleaned");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setCleanLoading(false);
    }
  }

  async function sendReply(ticketId: number): Promise<void> {
    const body = (draftById[ticketId] ?? "").trim();
    if (!body) {
      setError("Reply body is empty");
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/tickets/${ticketId}/reply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body }),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      setDraftById((prev) => ({ ...prev, [ticketId]: "" }));
      await fetchTickets();
      showToast("Reply sent");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    }
  }

  async function closeTicket(ticketId: number): Promise<void> {
    try {
      const res = await fetch(`${API_BASE}/tickets/${ticketId}/close`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      setOpenId(null);
      await fetchTickets();
      showToast("Ticket closed");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    }
  }

  async function assignTicket(ticketId: number, agentId: number | null): Promise<void> {
    // Optimistic UI update (prevents the select from snapping back)
    setTickets((prev) => {
      const nextAgent = agentId === null ? null : agents.find((a) => a.id === agentId) ?? null;
      return prev.map((t) => (t.id === ticketId ? { ...t, agent: nextAgent } : t));
    });

    setAssigningById((prev) => ({ ...prev, [ticketId]: true }));
    try {
      const res = await fetch(`${API_BASE}/tickets/${ticketId}/assign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: agentId }),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      await fetchTickets();
      showToast("Assignee updated");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
      // Re-sync if the optimistic update was wrong.
      await fetchTickets();
    }
    setAssigningById((prev) => ({ ...prev, [ticketId]: false }))
  }

  useEffect(() => {
    if (!simRunning) {
      setNextInboxInS(null);
      return;
    }

    void fetchSimulationStatus();
    const id = window.setInterval(() => {
      void fetchSimulationStatus();
    }, 1000);
    return () => window.clearInterval(id);
  }, [simRunning]);

  useEffect(() => {
    void fetchTickets();
    void fetchAgents();
    void fetchSimulationStatus();
    const id = window.setInterval(() => {
      void fetchTickets();
    }, 5000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    setOpenId(null);
  }, [tab]);

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
      {toast ? (
        <div className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-800 ring-1 ring-emerald-200">
          {toast}
        </div>
      ) : null}

      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Tickets</h1>
          <p className="mt-1 text-sm text-slate-600">
            Auto-ingested via LangGraph. Polling every 5 seconds.
          </p>

          <div className="mt-4 inline-flex rounded-md ring-1 ring-slate-200">
            <button
              type="button"
              className={`px-3 py-1.5 text-sm font-medium ${
                tab === "open" ? "bg-slate-900 text-white" : "bg-white text-slate-700 hover:bg-slate-50"
              } rounded-l-md`}
              onClick={() => setTab("open")}
            >
              Open Tickets
            </button>
            <button
              type="button"
              className={`px-3 py-1.5 text-sm font-medium ${
                tab === "closed" ? "bg-slate-900 text-white" : "bg-white text-slate-700 hover:bg-slate-50"
              } rounded-r-md`}
              onClick={() => setTab("closed")}
            >
              Closed Tickets
            </button>
          </div>
        </div>
        <div className="text-right text-xs text-slate-500">
          {simRunning && nextInboxInS !== null ? (
            <div className="mb-2 text-xs text-slate-600">
              Next inbox in {Math.max(0, Math.ceil(nextInboxInS))}s
            </div>
          ) : null}
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 disabled:opacity-50"
              onClick={() => void cleanDb()}
              disabled={cleanLoading}
            >
              <Trash2 className="h-4 w-4" />
              Clean
            </button>
            <button
              type="button"
              className={`inline-flex items-center rounded-md px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50 ${
                simRunning ? "bg-red-600 hover:bg-red-700" : "bg-emerald-600 hover:bg-emerald-700"
              }`}
              onClick={() => void toggleSimulation()}
              disabled={simLoading}
            >
              {simRunning ? "Click to stop inbox simulation" : "Start inbox simulation"}
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

      {visibleTickets.length === 0 ? (
        <div className="rounded-md border border-dashed border-slate-200 p-6 text-sm text-slate-600">
          {tab === "open" ? "No open tickets." : "No closed tickets."}
        </div>
      ) : (
        <div className="space-y-3">
          {visibleTickets.map((t) => {
            const ticket: Ticket = t;
            const isOpen = openId === t.id;
            const category = (t.category ?? "info").toLowerCase();
            const categoryVariant = category === "bug" || category === "refund" || category === "info" ? (category as "bug" | "refund" | "info") : "info";
            const priorityLabel = t.priority ? `Priority: ${t.priority}` : "Priority: —";
            const agentName = t.agent?.name ?? "Unassigned";
            const suggestedAgent = typeof t.suggested_agent_id === "number" ? agents.find((a) => a.id === t.suggested_agent_id) : undefined;
            const messages = [...(ticket.messages ?? [])].sort((a, b) => (a.created_at < b.created_at ? -1 : 1));

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
                      <Badge label={`Assigned to ${agentName}`} variant="neutral" />
                    </div>
                  </div>
                  <ChevronDown
                    className={`h-4 w-4 text-slate-500 transition-transform ${isOpen ? "rotate-180" : ""}`}
                  />
                </button>

                {isOpen ? (
                  <div className="space-y-4 border-t border-slate-200 px-4 py-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="text-sm text-slate-700">
                        <span className="font-medium text-slate-800">Assigned to {agentName}</span>
                        {suggestedAgent ? (
                          <span className="ml-2 text-xs text-slate-500">Suggested: {suggestedAgent.name}</span>
                        ) : null}
                      </div>
                      <div className="flex items-center gap-2">
                        <select
                          className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-300"
                          value={t.agent?.id ? String(t.agent.id) : ""}
                          disabled={Boolean(assigningById[t.id])}
                          onChange={(e) => {
                            const raw = e.target.value;
                            const nextId = raw ? Number(raw) : null;
                            void assignTicket(t.id, Number.isFinite(nextId as number) ? (nextId as number) : null);
                          }}
                        >
                          <option value="">Unassigned</option>
                          {agents.map((a) => (
                            <option key={a.id} value={String(a.id)}>
                              {a.name} ({a.role})
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div>
                      <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-800">
                        <MessageSquareText className="h-4 w-4 text-slate-500" />
                        Conversation
                      </div>

                      <div className="space-y-2">
                        {messages.map((m) => {
                          const isAgent = (m.sender_type || "").toLowerCase() === "agent";
                          return (
                            <div key={m.id} className={`flex ${isAgent ? "justify-end" : "justify-start"}`}>
                              <div
                                className={`max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ring-1 ${
                                  isAgent
                                    ? "bg-sky-600 text-white ring-sky-700/20"
                                    : "bg-slate-50 text-slate-800 ring-slate-200"
                                }`}
                              >
                                {m.body}
                              </div>
                            </div>
                          );
                        })}
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
                      <div className="mt-3 flex items-center justify-between gap-2">
                        <button
                          type="button"
                          className="inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
                          onClick={() => void closeTicket(t.id)}
                        >
                          Close Ticket
                        </button>
                        <button
                          type="button"
                          className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800"
                          onClick={() => void sendReply(t.id)}
                        >
                          <Send className="h-4 w-4" />
                          Send Reply
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
