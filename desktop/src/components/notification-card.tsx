import { getDeliverableComponent } from "./deliverables";
import {
  Mail,
  Clock as ClockIcon,
  FolderSync,
  Webhook,
  LayoutDashboard,
  MessageSquare,
  FileText,
  FilePlus,
  Send,
  Eye,
  ExternalLink,
  Paperclip,
  FileEdit,
  CheckCircle2,
  EyeOff,
} from "lucide-react";

// ═══════════════════════════════════════════
//  Types
// ═══════════════════════════════════════════

export interface DeliverableAction {
  label: string;
  action_type: string;
  primary?: boolean;
}

export interface Deliverable {
  type: string;
  label: string;
  description?: string;
  metadata?: Record<string, unknown>;
}

export interface Notification {
  id: string;
  session_id: string;
  source_type: "trigger" | "schedule" | "syncthing";
  source_id: string;
  source_name: string;
  title: string;
  category: string;
  status: "unread" | "read" | "dismissed" | "archived" | "resolved";
  summary: string;
  deliverables: Deliverable[];
  agent_provider: string;
  agent_duration_s: number;
  agent_tokens: number;
  user_id: string;
  created_at: string;
  read_at: string | null;
  // Legacy compat
  preview?: string;
}

// ═══════════════════════════════════════════
//  Icons
// ═══════════════════════════════════════════

const SOURCE_ICONS: Record<string, typeof Mail> = {
  trigger: Webhook,
  schedule: ClockIcon,
  syncthing: FolderSync,
};

const CATEGORY_ICONS: Record<string, typeof Mail> = {
  email: Mail,
  code: FileText,
  file: FolderSync,
  report: FileText,
};

const DELIVERABLE_ICONS: Record<string, typeof Paperclip> = {
  file: Paperclip,
  email_draft: FileEdit,
  draft: FileEdit,
  sent_email: Send,
  report: FileText,
  summary: Eye,
  data: FilePlus,
  link: ExternalLink,
};

// Action icons removed — each specialized component hardcodes its own buttons

function SourceIcon({ notification }: { notification: Notification }) {
  const Icon =
    CATEGORY_ICONS[notification.category] ||
    SOURCE_ICONS[notification.source_type] ||
    LayoutDashboard;
  return <Icon size={13} strokeWidth={1.5} />;
}

// ═══════════════════════════════════════════
//  Helpers
// ═══════════════════════════════════════════

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

function cleanSourceName(n: Notification): string {
  if (n.category === "email") return "Gmail";
  if (n.source_type === "schedule") return "Schedule";
  if (n.source_type === "syncthing") return "File Sync";
  return n.source_name.split("_")[0] || n.source_name;
}

function cleanTitle(title: string): string {
  return title.replace(/^[\p{Emoji_Presentation}\p{Emoji}\uFE0F]+\s*/u, "").trim();
}

// ═══════════════════════════════════════════
//  Deliverable Card (generic)
// ═══════════════════════════════════════════

function GenericDeliverableCard({
  deliverable,
  isUnread,
}: {
  deliverable: Deliverable;
  isUnread: boolean;
}) {
  const DelivIcon = DELIVERABLE_ICONS[deliverable.type] || CheckCircle2;

  return (
    <div
      className={`rounded-lg border px-3 py-2.5 transition-colors ${
        isUnread
          ? "bg-muted/30 border-border"
          : "bg-muted/15 border-border/70"
      }`}
    >
      {/* Deliverable header: icon + label + description */}
      <div className="flex items-center gap-2 text-[13px]">
        <span className="shrink-0 text-emerald-600">
          <DelivIcon size={14} strokeWidth={1.8} />
        </span>
        <span
          className={`font-medium truncate ${
            isUnread ? "text-foreground/85" : "text-foreground/60"
          }`}
        >
          {deliverable.label}
        </span>
        {deliverable.description && (
          <>
            <span className="text-muted-foreground/35">—</span>
            <span className="text-muted-foreground/55 truncate text-[12px]">
              {deliverable.description}
            </span>
          </>
        )}
      </div>
    </div>
  );
}

// EmailDraftCard removed — replaced by actions/EmailDraftAction

// ═══════════════════════════════════════════
//  Deliverable renderer (type router)
// ═══════════════════════════════════════════

function DeliverableCard({
  deliverable,
  isUnread,
  notification,
  onExecuteAction,
}: {
  deliverable: Deliverable;
  isUnread: boolean;
  notification: Notification;
  onExecuteAction?: (actionType: string) => Promise<boolean>;
}) {
  // Registry-based routing — new types only need registration in deliverables/registry.ts
  const SpecializedComponent = getDeliverableComponent(deliverable.type);

  if (SpecializedComponent) {
    return (
      <SpecializedComponent
        deliverable={deliverable}
        isUnread={isUnread}
        notification={notification}
        onExecuteAction={onExecuteAction}
        mode="full"
      />
    );
  }

  // Fallback for unknown types
  return <GenericDeliverableCard deliverable={deliverable} isUnread={isUnread} />;
}

// ═══════════════════════════════════════════
//  Notification Card (main component)
// ═══════════════════════════════════════════

interface NotificationCardProps {
  notification: Notification;
  onOpenSession?: (notification: Notification) => void;
  onArchive?: (notification: Notification) => void;
  onExecuteAction?: (notificationId: string, actionType: string, deliverableIndex: number) => Promise<boolean>;
  onLoadDetail?: (notification: Notification) => void;
}

export function NotificationCard({
  notification,
  onOpenSession,
  onArchive,
  onExecuteAction,
  onLoadDetail: _onLoadDetail,
}: NotificationCardProps) {
  const isUnread = notification.status === "unread";
  const summary = notification.summary || notification.preview || "";
  const deliverables = notification.deliverables || [];



  return (
    <div
      className={`rounded-xl border transition-all duration-200 hover:shadow-lg overflow-hidden ${
        isUnread
          ? "bg-white border-border shadow-[0_2px_12px_-2px_rgba(0,0,0,0.1)]"
          : "bg-white/90 border-border/70 shadow-[0_1px_6px_-1px_rgba(0,0,0,0.06)]"
      }`}
    >
      {/* ── Top bar: source + time + actions ── */}
      <div className="flex items-center gap-2 px-5 pt-3.5 pb-1">
        <div
          className={`flex items-center gap-1.5 text-[11.5px] ${
            isUnread ? "text-muted-foreground/70" : "text-muted-foreground/50"
          }`}
        >
          <SourceIcon notification={notification} />
          <span className="font-medium">{cleanSourceName(notification)}</span>
        </div>
        <span className="text-[11px] text-muted-foreground/30">·</span>
        <span className="text-[11px] text-muted-foreground/40">
          {relativeTime(notification.created_at)}
        </span>
        {isUnread && (
          <span className="w-2 h-2 rounded-full bg-blue-500 shrink-0" />
        )}

        {/* Actions — right side */}
        <div className="ml-auto flex items-center gap-1">
          {onOpenSession && notification.session_id && (
            <button
              onClick={() => onOpenSession(notification)}
              className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[11.5px] font-medium text-muted-foreground/50 hover:text-foreground/80 hover:bg-muted/40 transition-colors"
            >
              <MessageSquare size={11} />
              <span>Follow Up</span>
            </button>
          )}
          {notification.status !== "archived" && notification.status !== "dismissed" && onArchive && (
            <button
              onClick={() => onArchive(notification)}
              className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[11.5px] font-medium text-muted-foreground/35 hover:text-foreground/65 hover:bg-muted/40 transition-colors"
            >
              <EyeOff size={11} />
              <span>Skip</span>
            </button>
          )}
        </div>
      </div>

      {/* ── Title ── */}
      <div className="px-5 pt-1 pb-0.5">
        <h3
          className={`text-[14.5px] leading-snug ${
            isUnread ? "font-semibold text-foreground" : "font-medium text-foreground/75"
          }`}
        >
          {cleanTitle(notification.title)}
        </h3>
      </div>

      {/* ── Summary ── */}
      {summary && (
        <div className="px-5 pt-1.5 pb-2.5">
          <p
            className={`text-[13px] leading-relaxed ${
              isUnread ? "text-foreground/70" : "text-muted-foreground/55"
            }`}
            style={{
              display: "-webkit-box",
              WebkitLineClamp: 4,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {summary}
          </p>
        </div>
      )}

      {/* ── Deliverables — type-routed rendering ── */}
      {/* File-type cards display in a horizontal row; others stack vertically */}
      {deliverables.length > 0 && (
        <div className="px-5 pb-3 flex flex-col gap-2">
          {(() => {
            const groups: { type: "file-row" | "other"; items: { d: Deliverable; i: number }[] }[] = [];

            for (let i = 0; i < deliverables.length; i++) {
              const d = deliverables[i];
              const isFileType = d.type === "file";
              const lastGroup = groups[groups.length - 1];

              if (isFileType) {
                if (lastGroup?.type === "file-row") {
                  lastGroup.items.push({ d, i });
                } else {
                  groups.push({ type: "file-row", items: [{ d, i }] });
                }
              } else {
                groups.push({ type: "other", items: [{ d, i }] });
              }
            }

            return groups.map((group, gi) => {
              if (group.type === "file-row") {
                return (
                  <div key={`fg-${gi}`} className="flex flex-wrap gap-2">
                    {group.items.map(({ d, i }) => (
                      <DeliverableCard
                        key={i}
                        deliverable={d}
                        isUnread={isUnread}
                        notification={notification}
                        onExecuteAction={
                          onExecuteAction
                            ? (actionType: string) => onExecuteAction(notification.id, actionType, i)
                            : undefined
                        }
                      />
                    ))}
                  </div>
                );
              }

              const { d, i } = group.items[0];
              return (
                <DeliverableCard
                  key={i}
                  deliverable={d}
                  isUnread={isUnread}
                  notification={notification}
                  onExecuteAction={
                    onExecuteAction
                      ? (actionType: string) => onExecuteAction(notification.id, actionType, i)
                      : undefined
                  }
                />
              );
            });
          })()}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════
//  Empty state
// ═══════════════════════════════════════════

export function NotificationEmpty() {
  return (
    <div className="flex flex-col items-center justify-center text-muted-foreground/30 gap-3 py-20">
      <div className="p-4 rounded-2xl bg-muted/20">
        <LayoutDashboard size={32} strokeWidth={1.2} />
      </div>
      <div className="text-center">
        <p className="text-sm font-medium text-foreground/25">No activity yet</p>
        <p className="text-xs text-muted-foreground/20 mt-1.5 max-w-[260px] leading-relaxed">
          When triggers and schedules fire, agent work results will appear here
        </p>
      </div>
    </div>
  );
}
