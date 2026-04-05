import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import { CheckCheck, CheckCircle2 } from "lucide-react";
import {
  NotificationCard,
  NotificationEmpty,
  type Notification,
} from "./notification-card";

// ── Types ──

type WorkspaceTab = "pending" | "done";

interface WorkspacePageProps {
  notifications: Notification[];
  unreadCount: number;
  onNotificationClick?: (notification: Notification) => void;
  onOpenSession?: (notification: Notification) => void;
  onArchive?: (notification: Notification) => void;
  onExecuteAction?: (notificationId: string, actionType: string, deliverableIndex: number) => Promise<boolean>;
  onLoadDetail?: (notification: Notification) => void;
  onMarkAllRead?: () => void;
}

const DONE_STATUSES = new Set(["resolved", "archived", "dismissed"]);

// Animation duration in ms — must match CSS transition
const EXIT_DURATION = 380;

// ── Component ──

export function WorkspacePage({
  notifications,
  unreadCount,
  onNotificationClick,
  onOpenSession,
  onArchive,
  onExecuteAction,
  onLoadDetail,
  onMarkAllRead,
}: WorkspacePageProps) {
  const [tab, setTab] = useState<WorkspaceTab>("pending");

  // Track which notification IDs are currently animating out
  const [exitingIds, setExitingIds] = useState<Set<string>>(new Set());

  // Refs for measuring card heights (for smooth collapse)
  const cardRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const { pending, done } = useMemo(() => {
    const p: Notification[] = [];
    const d: Notification[] = [];
    for (const n of notifications) {
      if (DONE_STATUSES.has(n.status)) {
        d.push(n);
      } else {
        p.push(n);
      }
    }
    return { pending: p, done: d };
  }, [notifications]);

  // Include cards that are exiting (they need to stay rendered during animation)
  const activeList = tab === "pending" ? pending : done;

  // Detect when a card moved from pending → done (optimistic update)
  // and trigger the exit animation
  const prevPendingIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (tab !== "pending") {
      prevPendingIdsRef.current = new Set(pending.map((n) => n.id));
      return;
    }

    const prevIds = prevPendingIdsRef.current;
    const currentIds = new Set(pending.map((n) => n.id));

    // Find IDs that were in pending but no longer are
    const removedIds = new Set<string>();
    for (const id of prevIds) {
      if (!currentIds.has(id)) {
        removedIds.add(id);
      }
    }

    if (removedIds.size > 0) {
      setExitingIds((prev) => {
        const next = new Set(prev);
        for (const id of removedIds) next.add(id);
        return next;
      });

      // Clean up after animation completes
      setTimeout(() => {
        setExitingIds((prev) => {
          const next = new Set(prev);
          for (const id of removedIds) next.delete(id);
          return next;
        });
      }, EXIT_DURATION);
    }

    prevPendingIdsRef.current = currentIds;
  }, [pending, tab]);

  // Build the display list: active items + exiting items (from notifications)
  const displayList = useMemo(() => {
    if (tab !== "pending" || exitingIds.size === 0) return activeList;

    // Get the exiting notifications from the full list
    const exitingNotifs = notifications.filter((n) => exitingIds.has(n.id));
    // Merge: show both current pending AND exiting cards
    const merged = [...activeList];
    for (const exitNotif of exitingNotifs) {
      if (!merged.find((n) => n.id === exitNotif.id)) {
        merged.push(exitNotif);
      }
    }
    // Sort to maintain original order (by created_at descending)
    merged.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    return merged;
  }, [activeList, exitingIds, notifications, tab]);

  // Wrap onArchive to trigger exit animation
  const handleArchive = useCallback(
    (notification: Notification) => {
      onArchive?.(notification);
    },
    [onArchive]
  );

  // Wrap onExecuteAction (the parent already does optimistic update)
  const handleExecuteAction = useCallback(
    async (notificationId: string, actionType: string, deliverableIndex: number): Promise<boolean> => {
      if (!onExecuteAction) return false;
      return onExecuteAction(notificationId, actionType, deliverableIndex);
    },
    [onExecuteAction]
  );

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Page header — single row: title + tabs */}
      <div className="shrink-0 px-8 pt-0 pb-2">
        <div className="flex items-center justify-between max-w-4xl mx-auto">
          {/* Left: title + unread badge */}
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold text-foreground/85 tracking-tight">
              Workspace
            </h1>
            {tab === "pending" && unreadCount > 0 && (
              <span className="text-[11px] text-muted-foreground/40 tabular-nums bg-foreground/5 px-2 py-0.5 rounded-full">
                {unreadCount} unread
              </span>
            )}
            {tab === "pending" && unreadCount > 0 && onMarkAllRead && (
              <button
                onClick={onMarkAllRead}
                className="flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] text-muted-foreground/40 hover:text-foreground/70 hover:bg-muted/50 transition-colors"
              >
                <CheckCheck size={12} />
                <span>Mark all read</span>
              </button>
            )}
          </div>

          {/* Right: tab switcher */}
          <div className="flex items-center gap-0.5 bg-foreground/[0.03] rounded-lg p-0.5">
            <button
              onClick={() => setTab("pending")}
              className={`px-3 py-1 rounded-md text-[13px] font-medium transition-all ${
                tab === "pending"
                  ? "bg-background text-foreground/80 shadow-sm"
                  : "text-muted-foreground/40 hover:text-foreground/60"
              }`}
            >
              Pending
            </button>
            <button
              onClick={() => setTab("done")}
              className={`px-3 py-1 rounded-md text-[13px] font-medium transition-all ${
                tab === "done"
                  ? "bg-background text-foreground/80 shadow-sm"
                  : "text-muted-foreground/40 hover:text-foreground/60"
              }`}
            >
              Done
            </button>
          </div>
        </div>
      </div>

      {/* Notification cards */}
      <div className="flex-1 overflow-y-auto px-8 pb-8">
        <div className="max-w-4xl mx-auto flex flex-col gap-3">
          {displayList.length === 0 ? (
            tab === "pending" ? (
              <NotificationEmpty />
            ) : (
              <div className="flex flex-col items-center justify-center py-20 text-muted-foreground/30">
                <CheckCircle2 size={32} className="mb-3 opacity-50" />
                <p className="text-[14px]">No completed tasks yet</p>
              </div>
            )
          ) : (
            displayList.map((n) => {
              const isExiting = exitingIds.has(n.id);
              return (
                <div
                  key={n.id}
                  ref={(el) => {
                    if (el) cardRefs.current.set(n.id, el);
                    else cardRefs.current.delete(n.id);
                  }}
                  className={isExiting ? "notification-card-exit" : undefined}
                  style={isExiting ? { pointerEvents: "none" } : undefined}
                >
                  <NotificationCard
                    notification={n}
                    onOpenSession={(notif) => {
                      onNotificationClick?.(notif);
                      onOpenSession?.(notif);
                    }}
                    onArchive={tab === "pending" ? handleArchive : undefined}
                    onExecuteAction={tab === "pending" ? handleExecuteAction : undefined}
                    onLoadDetail={onLoadDetail}
                  />
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
