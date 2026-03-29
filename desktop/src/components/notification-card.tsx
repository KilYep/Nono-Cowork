import { useState } from "react";
import {
  Mail,
  Clock as ClockIcon,
  FolderSync,
  Webhook,
  Zap,
  ChevronDown,
  MessageSquare,
  CheckCircle2,
  Download,
  FileEdit,
  Send,
  Eye,
  Trash2,
  Filter,
  ArrowRight,
  Loader2,
} from "lucide-react";

// ── Types ──

export interface NotificationAction {
  type: string;   // "download" | "draft" | "reply" | "analyze" | "read" | "skip" | "delete" | ...
  detail: string; // Human-readable description
}

export interface Notification {
  id: string;
  session_id: string;
  source_type: "trigger" | "schedule" | "syncthing";
  source_id: string;
  source_name: string;
  title: string;
  preview: string;
  category: string;
  status: "unread" | "read" | "actioned" | "dismissed";
  agent_provider: string;
  agent_duration_s: number;
  agent_tokens: number;
  user_id: string;
  created_at: string;
  read_at: string | null;
  delivered_channels: string[];
  // Agent's actions — what it actually DID (hero content)
  actions_taken?: NotificationAction[];
  // Populated when detail is loaded (full agent log)
  agent_log?: { step: number; action: string; result: string }[];
}

// ── Action type → icon mapping ──

const ACTION_ICONS: Record<string, typeof Download> = {
  download: Download,
  draft: FileEdit,
  reply: Send,
  send: Send,
  analyze: Eye,
  read: Eye,
  skip: ArrowRight,
  delete: Trash2,
  filter: Filter,
};

function ActionIcon({ type }: { type: string }) {
  const Icon = ACTION_ICONS[type] || CheckCircle2;
  return <Icon size={13} strokeWidth={1.8} />;
}

// ── Source labels ──

const SOURCE_ICONS: Record<string, typeof Mail> = {
  trigger: Webhook,
  schedule: ClockIcon,
  syncthing: FolderSync,
};

const CATEGORY_ICONS: Record<string, typeof Mail> = {
  email: Mail,
};

function SourceIcon({ notification }: { notification: Notification }) {
  const Icon =
    CATEGORY_ICONS[notification.category] ||
    SOURCE_ICONS[notification.source_type] ||
    Zap;
  return <Icon size={13} strokeWidth={1.5} />;
}

// ── Relative time ──

function relativeTime(isoString: string): string {
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diff = Math.max(0, now - then);

  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;

  return new Date(isoString).toLocaleDateString();
}

// ── Notification Card ──

interface NotificationCardProps {
  notification: Notification;
  onOpenSession?: (notification: Notification) => void;
  onLoadDetail?: (notification: Notification) => void;
}

export function NotificationCard({
  notification,
  onOpenSession,
  onLoadDetail,
}: NotificationCardProps) {
  const [processExpanded, setProcessExpanded] = useState(false);
  const isUnread = notification.status === "unread";
  const actions = notification.actions_taken || [];

  const handleExpandProcess = () => {
    if (!processExpanded && !notification.agent_log && onLoadDetail) {
      onLoadDetail(notification);
    }
    setProcessExpanded((p) => !p);
  };

  return (
    <div
      className={`rounded-xl border transition-all duration-200 ${
        isUnread
          ? "bg-card border-border/80 shadow-sm"
          : "bg-card/50 border-border/30"
      }`}
    >
      {/* ── Top bar: source + time ── */}
      <div className="flex items-center gap-2 px-4 pt-3 pb-1">
        <div className={`flex items-center gap-1.5 text-[11px] ${
          isUnread ? "text-muted-foreground/50" : "text-muted-foreground/35"
        }`}>
          <SourceIcon notification={notification} />
          <span>{notification.source_name.replace(/_/g, " ").toLowerCase()}</span>
        </div>
        <span className="text-[11px] text-muted-foreground/25">·</span>
        <span className="text-[11px] text-muted-foreground/30">
          {relativeTime(notification.created_at)}
        </span>
        {isUnread && (
          <span className="ml-auto w-2 h-2 rounded-full bg-blue-500 shrink-0" />
        )}
      </div>

      {/* ── Title: what event triggered this ── */}
      <div className="px-4 pt-1 pb-2">
        <h3
          className={`text-[14px] leading-snug ${
            isUnread ? "font-semibold text-foreground/90" : "font-medium text-foreground/65"
          }`}
        >
          {notification.title}
        </h3>
      </div>

      {/* ── Hero: What the agent DID ── */}
      {actions.length > 0 && (
        <div className="px-4 pb-3">
          <div className="flex flex-col gap-1.5">
            {actions.map((action, i) => (
              <div
                key={i}
                className="flex items-start gap-2 text-[13px]"
              >
                <span className="mt-0.5 shrink-0 text-emerald-500/70">
                  <ActionIcon type={action.type} />
                </span>
                <span className={isUnread ? "text-foreground/70" : "text-foreground/50"}>
                  {action.detail}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Preview: agent's summary (if no actions, show preview as fallback) ── */}
      {actions.length === 0 && notification.preview && (
        <div className="px-4 pb-3">
          <p
            className={`text-[13px] leading-relaxed ${
              isUnread ? "text-foreground/55" : "text-muted-foreground/45"
            }`}
            style={{
              display: "-webkit-box",
              WebkitLineClamp: 3,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {notification.preview}
          </p>
        </div>
      )}

      {/* ── Footer: actions ── */}
      <div className="flex items-center gap-1 px-3 pb-3">
        <button
          onClick={handleExpandProcess}
          className="flex items-center gap-1 px-2 py-1 rounded-md text-[12px] text-muted-foreground/40 hover:text-foreground/60 hover:bg-muted/40 transition-colors"
        >
          <ChevronDown
            size={13}
            className={`transition-transform duration-200 ${processExpanded ? "rotate-180" : ""}`}
          />
          <span>Agent process</span>
          {notification.agent_duration_s > 0 && (
            <span className="text-muted-foreground/25">
              · {notification.agent_duration_s}s
            </span>
          )}
        </button>

        <div className="flex-1" />

        {onOpenSession && notification.session_id && (
          <button
            onClick={() => onOpenSession(notification)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[12px] text-muted-foreground/40 hover:text-foreground/70 hover:bg-muted/40 transition-colors"
          >
            <MessageSquare size={12} />
            <span>Continue</span>
          </button>
        )}
      </div>

      {/* ── Expanded: Full agent process log ── */}
      {processExpanded && (
        <div className="mx-4 mb-4 pt-3 border-t border-border/20">
          {notification.agent_log ? (
            <div className="flex flex-col gap-2">
              {notification.agent_log.map((step, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2.5 text-[12px]"
                >
                  <span className="shrink-0 w-5 h-5 flex items-center justify-center rounded-full bg-muted/40 text-muted-foreground/35 text-[10px] font-medium mt-0.5">
                    {step.step}
                  </span>
                  <div className="min-w-0">
                    <span className="font-medium text-foreground/45">
                      {step.action}
                    </span>
                    {step.result && (
                      <p className="text-muted-foreground/35 mt-0.5 leading-snug break-words">
                        {step.result}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center gap-2 text-[12px] text-muted-foreground/30 py-2">
              <Loader2 size={12} className="animate-spin" />
              <span>Loading agent activity...</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Empty state ──

export function NotificationEmpty() {
  return (
    <div className="flex flex-col items-center justify-center text-muted-foreground/30 gap-3 py-20">
      <div className="p-4 rounded-2xl bg-muted/20">
        <Zap size={32} strokeWidth={1.2} />
      </div>
      <div className="text-center">
        <p className="text-sm font-medium text-foreground/25">No activity yet</p>
        <p className="text-xs text-muted-foreground/20 mt-1.5 max-w-[260px] leading-relaxed">
          When your triggers and schedules fire, agent work results will appear here automatically
        </p>
      </div>
    </div>
  );
}
