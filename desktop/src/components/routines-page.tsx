import { useState, useEffect } from "react";
import { Clock, Zap, Play, Trash2, CalendarClock, Loader2, Plus, Edit2 } from "lucide-react";

// ── Types ──

export type AutomationType = "cron" | "trigger";

export interface Automation {
  id: string;
  type: AutomationType;
  name: string;
  description: string;
  schedule: string;
  enabled: boolean;
  model: string;
  channel_name: string;
  user_id: string;
  created_at: string;
  last_run_at: string | null;
  last_result: string;
  next_run_at: string | null;
  config: Record<string, unknown>;
}

interface AutomationsResponse {
  automations: Automation[];
  total: number;
  counts: { cron: number; trigger: number };
}

// ── Config ──

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8080";
const API_TOKEN = import.meta.env.VITE_API_TOKEN || "";

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { ...extra };
  if (API_TOKEN) {
    headers["Authorization"] = `Bearer ${API_TOKEN}`;
  }
  return headers;
}

// ── Simple Switch Component ──
function Switch({ checked, onChange, disabled }: { checked: boolean; onChange: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onChange}
      disabled={disabled}
      className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background ${
        disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"
      } ${checked ? "bg-blue-500/80" : "bg-muted-foreground/20"}`}
      aria-checked={checked}
      role="switch"
    >
      <span
        className={`pointer-events-none block h-4 w-4 rounded-full bg-white shadow-lg ring-0 transition-transform ${
          checked ? "translate-x-4" : "translate-x-0.5"
        }`}
      />
    </button>
  );
}

// ── Component ──

export function RoutinesPage() {
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [counts, setCounts] = useState({ cron: 0, trigger: 0 });
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "cron" | "trigger">("all");
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});

  useEffect(() => {
    fetchAutomations();
  }, []);

  const fetchAutomations = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/automations`, {
        headers: authHeaders({ "Content-Type": "application/json" }),
      });
      if (res.ok) {
        const data: AutomationsResponse = await res.json();
        setAutomations(data.automations);
        setCounts(data.counts || { cron: 0, trigger: 0 });
      }
    } catch (e) {
      console.error("Failed to fetch automations", e);
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (a: Automation) => {
    const isCron = a.type === "cron";
    const endpoint = isCron ? `/api/tasks/${a.id}/toggle` : `/api/triggers/${a.id}/toggle`;

    setActionLoading((p) => ({ ...p, [a.id]: true }));
    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "PATCH",
        headers: authHeaders({ "Content-Type": "application/json" }),
      });
      if (res.ok) {
        const data = await res.json();
        setAutomations((prev) =>
          prev.map((item) => {
            if (item.id === a.id) {
              return { ...item, enabled: data.enabled, id: data.id || item.id, next_run_at: data.next_run_at || item.next_run_at };
            }
            return item;
          })
        );
      }
    } catch (e) {
      console.error("Failed to toggle", e);
    } finally {
      setActionLoading((p) => ({ ...p, [a.id]: false }));
    }
  };

  const handleDelete = async (a: Automation) => {
    if (!confirm(`Are you sure you want to delete "${a.name}"?`)) return;

    const isCron = a.type === "cron";
    const endpoint = isCron ? `/api/tasks/${a.id}` : `/api/triggers/${a.id}`;

    setActionLoading((p) => ({ ...p, [a.id]: true }));
    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      if (res.ok) {
        setAutomations((prev) => prev.filter((item) => item.id !== a.id));
        setCounts((prev) => ({ ...prev, [a.type]: prev[a.type] - 1 }));
      }
    } catch (e) {
      console.error("Failed to delete", e);
      setActionLoading((p) => ({ ...p, [a.id]: false }));
    }
  };

  const handleRun = async (a: Automation) => {
    if (a.type !== "cron") return;

    setActionLoading((p) => ({ ...p, [`${a.id}-run`]: true }));
    try {
      const res = await fetch(`${API_BASE}/api/tasks/${a.id}/run`, {
        method: "POST",
        headers: authHeaders(),
      });
      if (res.ok) {
        // Just let it manually trigger, no direct UI update except maybe a toast or checkmark
        alert("Task triggered successfully. Output will appear in Workspace.");
      }
    } catch (e) {
      console.error("Failed to trigger task", e);
    } finally {
      setActionLoading((p) => ({ ...p, [`${a.id}-run`]: false }));
    }
  };

  const filteredAutomations = automations.filter(
    (a) => filter === "all" || a.type === filter
  );

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-background">
      {/* Header */}
      <div className="shrink-0 px-8 pt-6 pb-4">
        <div className="max-w-3xl mx-auto flex items-end justify-between">
          <div>
            <h1 className="text-xl font-semibold text-foreground/85 tracking-tight flex items-center gap-2">
              <CalendarClock size={20} className="text-muted-foreground" />
              Routines
            </h1>
            <p className="text-[13px] text-muted-foreground/50 mt-1">
              Automated scheduled tasks and background triggers
            </p>
          </div>
          <button
            className="flex items-center gap-1.5 px-3 py-1.5 bg-foreground/5 hover:bg-foreground/10 text-foreground/80 rounded-lg text-xs font-medium transition-colors cursor-pointer"
            onClick={() => alert("Task creation wizard coming soon.")}
          >
            <Plus size={14} />
            <span>New Routine</span>
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="px-8 shrink-0 border-b border-border/40">
        <div className="max-w-3xl mx-auto flex items-center gap-6">
          {(["all", "cron", "trigger"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              className={`pb-3 text-[13px] font-medium transition-colors relative ${
                filter === tab ? "text-foreground" : "text-muted-foreground/60 hover:text-foreground/80"
              }`}
            >
              {tab === "all" ? "All" : tab === "cron" ? "Scheduled Tasks" : "Triggers"}
              <span className="ml-1.5 text-[10px] text-muted-foreground bg-muted hover:bg-muted/80 px-1.5 py-0.5 rounded-full">
                {tab === "all" ? automations.length : counts[tab] || 0}
              </span>
              {filter === tab && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-foreground rounded-t-full" />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="max-w-3xl mx-auto flex flex-col gap-4">
          {loading ? (
            <div className="flex flex-col items-center justify-center p-12 text-muted-foreground space-y-3">
              <Loader2 className="animate-spin size-6 opacity-50" />
              <span className="text-sm">Loading automations...</span>
            </div>
          ) : filteredAutomations.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-12 text-center border border-dashed rounded-xl bg-muted/20">
              <div className="size-12 bg-muted/50 rounded-full flex items-center justify-center mb-4">
                <CalendarClock size={24} className="text-muted-foreground/60" />
              </div>
              <p className="text-sm font-medium text-foreground/80">No routines found</p>
              <p className="text-xs text-muted-foreground mt-1 max-w-[250px]">
                Create a scheduled task or add an event trigger to automate your workflows.
              </p>
            </div>
          ) : (
            filteredAutomations.map((a) => {
              const Icon = a.type === "cron" ? Clock : Zap;
              const isEnabled = a.enabled;

              return (
                <div
                  key={a.id}
                  className="group relative flex flex-col rounded-xl border bg-card p-4 shadow-sm transition-all hover:shadow-md"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex items-start gap-4">
                      {/* Icon */}
                      <div
                        className={`size-10 rounded-lg flex items-center justify-center shrink-0 ${
                          isEnabled
                            ? a.type === "cron"
                              ? "bg-blue-500/10 text-blue-500"
                              : "bg-amber-500/10 text-amber-500"
                            : "bg-muted text-muted-foreground/50"
                        }`}
                      >
                        <Icon size={20} strokeWidth={2} />
                      </div>

                      {/* Info */}
                      <div>
                        <div className="flex items-center gap-2">
                          <h3
                            className={`text-[15px] font-semibold tracking-tight ${
                              isEnabled ? "text-foreground" : "text-muted-foreground/70"
                            }`}
                          >
                            {a.name}
                          </h3>
                        </div>
                        <p className="text-[13px] text-muted-foreground mt-1 line-clamp-1 leading-relaxed">
                          {a.description}
                        </p>

                        <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground/80 font-medium">
                          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-muted/50 border">
                            <span className="text-muted-foreground font-mono">{a.schedule}</span>
                          </div>
                          {a.type === "cron" && (
                            <>
                              {a.next_run_at ? (
                                <span>Next: {new Date(a.next_run_at).toLocaleString(undefined, {
                                    month: 'short', day: 'numeric', hour: '2-digit', minute:'2-digit'
                                })}</span>
                              ) : (
                                <span>Task Disabled</span>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Right side Toggle */}
                    <div className="flex items-center h-10 shrink-0">
                      <div className="flex items-center gap-2 mr-3 px-3">
                         <span className={`text-[11px] font-medium uppercase tracking-wider ${isEnabled ? "text-foreground/70" : "text-muted-foreground/50"}`}>
                           {isEnabled ? "ON" : "OFF"}
                         </span>
                         <Switch
                           checked={isEnabled}
                           onChange={() => handleToggle(a)}
                           disabled={actionLoading[a.id]}
                         />
                      </div>
                    </div>
                  </div>

                  {/* Actions hover overlay */}
                  <div className="absolute right-4 bottom-4 flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    {a.type === "cron" && (
                      <button
                        onClick={() => handleRun(a)}
                        disabled={actionLoading[`${a.id}-run`]}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-foreground/70 hover:text-foreground hover:bg-muted rounded-md transition-colors"
                      >
                        {actionLoading[`${a.id}-run`] ? (
                          <Loader2 size={14} className="animate-spin" />
                        ) : (
                          <Play size={14} />
                        )}
                        Run Now
                      </button>
                    )}
                    <button
                      onClick={() => alert("Edition coming soon. For now please delete and recreate via chat.")}
                      className="px-2 py-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded-md transition-colors"
                      aria-label="Edit"
                    >
                      <Edit2 size={15} />
                    </button>
                    <button
                      onClick={() => handleDelete(a)}
                      disabled={actionLoading[a.id]}
                      className="px-2 py-1.5 text-muted-foreground hover:text-red-500 hover:bg-red-500/10 rounded-md transition-colors"
                      aria-label="Delete"
                    >
                      {actionLoading[a.id] ? (
                        <Loader2 size={15} className="animate-spin" />
                      ) : (
                        <Trash2 size={15} />
                      )}
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
