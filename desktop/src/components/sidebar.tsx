import { Plus, PanelLeftClose, Settings, MessageSquare } from "lucide-react";

// ── Types ──

export interface SessionItem {
  id: string;
  created_at: number;
  last_active: number;
  message_count: number;
  preview: string;
  is_current: boolean;
}

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  onNewChat: () => void;
  sessions: SessionItem[];
  onSelectSession: (id: string) => void;
}

// ── Date grouping ──

function groupByDate(sessions: SessionItem[]): [string, SessionItem[]][] {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const todayMs = today.getTime();
  const yesterdayMs = todayMs - 86_400_000;
  const weekMs = todayMs - 7 * 86_400_000;
  const monthMs = todayMs - 30 * 86_400_000;

  const groups = new Map<string, SessionItem[]>();
  const order = ["Today", "Yesterday", "Previous 7 Days", "Previous 30 Days", "Older"];

  for (const s of sessions) {
    const t = s.last_active * 1000;
    let group: string;
    if (t >= todayMs) group = "Today";
    else if (t >= yesterdayMs) group = "Yesterday";
    else if (t >= weekMs) group = "Previous 7 Days";
    else if (t >= monthMs) group = "Previous 30 Days";
    else group = "Older";

    if (!groups.has(group)) groups.set(group, []);
    groups.get(group)!.push(s);
  }

  return order.filter((g) => groups.has(g)).map((g) => [g, groups.get(g)!]);
}

// ── Component ──

export function Sidebar({
  isOpen,
  onToggle,
  onNewChat,
  sessions,
  onSelectSession,
}: SidebarProps) {
  const grouped = groupByDate(sessions);

  return (
    <aside
      className={`flex flex-col h-full bg-sidebar text-sidebar-foreground shrink-0 border-r overflow-hidden transition-[width] duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] ${
        isOpen ? "w-[260px] border-sidebar-border" : "w-0 border-transparent"
      }`}
    >
      <div className="flex flex-col h-full min-w-[260px]">
        {/* Drag area + header */}
        <div
          className="flex items-center justify-between px-3 h-11 shrink-0"
          style={{ WebkitAppRegion: "drag" } as React.CSSProperties}
        >
          <span className="text-[13px] font-medium text-sidebar-foreground/60">
            Nono CoWork
          </span>
          <button
            onClick={onToggle}
            className="p-1.5 rounded-md hover:bg-sidebar-accent text-sidebar-foreground/40 hover:text-sidebar-foreground/70 transition-colors"
            style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}
            aria-label="Close sidebar"
          >
            <PanelLeftClose size={16} />
          </button>
        </div>

        {/* New Chat button */}
        <div className="px-3 py-1">
          <button
            onClick={onNewChat}
            className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-[13px] text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground transition-colors"
            style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}
          >
            <Plus size={16} strokeWidth={1.5} />
            <span>New Chat</span>
          </button>
        </div>

        {/* Session list */}
        <div className="flex-1 overflow-y-auto px-2 py-1">
          {sessions.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-sidebar-foreground/25 gap-2">
              <MessageSquare size={28} strokeWidth={1.2} />
              <p className="text-xs">No conversations yet</p>
            </div>
          ) : (
            grouped.map(([group, items]) => (
              <div key={group} className="mb-2">
                <div className="px-2 py-1.5 text-[11px] font-medium text-sidebar-foreground/35 uppercase tracking-wider">
                  {group}
                </div>
                {items.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => !s.is_current && onSelectSession(s.id)}
                    className={`w-full text-left px-3 py-1.5 rounded-lg text-[13px] truncate transition-colors mb-0.5 ${
                      s.is_current
                        ? "bg-sidebar-accent text-sidebar-foreground/90"
                        : "text-sidebar-foreground/55 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground/80"
                    }`}
                  >
                    {s.preview || "New conversation"}
                  </button>
                ))}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="px-3 py-3 border-t border-sidebar-border">
          <button className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-[13px] text-sidebar-foreground/40 hover:bg-sidebar-accent hover:text-sidebar-foreground/70 transition-colors">
            <Settings size={15} strokeWidth={1.5} />
            <span>Settings</span>
          </button>
        </div>
      </div>
    </aside>
  );
}
