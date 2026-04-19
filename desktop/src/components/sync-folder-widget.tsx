import { useState, useEffect, useCallback, useRef } from "react";
import { createPortal } from "react-dom";
import {
  Folder,
  Check,
  X,
  RefreshCw,
  ChevronRight,
  ArrowUpFromLine,
  ArrowDownToLine,
} from "lucide-react";

// ── Status badge folder icon (matches pencil prototype: folder-icons-set) ──

type SyncIconState = "syncing" | "idle" | "error";

function SyncFolderIcon({ state, size = 16 }: { state: SyncIconState; size?: number }) {
  const badgeSize = Math.round(size * 0.625); // 10px at 16px icon
  const iconSize = Math.round(size * 0.5);    // 8px at 16px icon

  const badgeConfig = {
    syncing: { color: "#0B57D0", Icon: RefreshCw, animate: true },
    idle:    { color: "#15A362", Icon: Check,     animate: false },
    error:   { color: "#D14343", Icon: X,         animate: false },
  }[state];

  const { color, Icon, animate } = badgeConfig;

  return (
    <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
      <Folder size={size} style={{ color: "#A8A6A4" }} />
      {/* Status badge — bottom-right overlay */}
      <div
        style={{
          position: "absolute",
          right: -2,
          bottom: -2,
          width: badgeSize,
          height: badgeSize,
          borderRadius: "50%",
          background: "#FFFFFF",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Icon
          size={iconSize}
          style={{ color }}
          className={animate ? "animate-spin" : undefined}
        />
      </div>
    </div>
  );
}

// ── Types ──

interface SyncFileEvent {
  path: string;
  abs_path: string;
  action: "added" | "modified" | "deleted";
  direction: "inbound" | "outbound";
  state: "syncing" | "done" | "error";
  progress: number | null;
  time_ago: string;
  timestamp: number;
  folder_id: string;
}

interface FolderStatus {
  id: string;
  label: string;
  path: string;
  state: "pending" | "syncing" | "idle" | "error";
  completion: number;
}

// Minimal shape — only the bits the widget needs from the active workspace.
// Kept loose so App.tsx can pass its WorkspaceItem directly.
interface ActiveWorkspace {
  id: string;
  label: string;
  folder_id: string | null;
}

interface SyncFolderWidgetProps {
  apiBase: string;
  getHeaders: () => Record<string, string>;
  syncState: "connected" | "syncing" | "disconnected" | "loading";
  /** The workspace whose folder we should show — usually the active chat's workspace. */
  activeWorkspace: ActiveWorkspace | null;
}

// ── File sync row ──
// A single compact row: direction arrow + filename + progress/time.
// Chronological mixed list (no grouping); the ↑/↓ arrow differentiates direction.

function FileSyncRow({ evt }: { evt: SyncFileEvent }) {
  // Direction arrow:
  //   inbound  = "from you" (user → VPS)   → ↑ (sending up)
  //   outbound = "to you"   (VPS → user)   → ↓ (receiving down)
  const DirectionIcon = evt.direction === "inbound" ? ArrowUpFromLine : ArrowDownToLine;
  const directionColor = "#A8A6A4";

  // Progress may be null even when syncing (transfer not yet reported);
  // render ellipsis in that case instead of a bogus percentage.
  const progressLabel =
    evt.state === "syncing"
      ? (evt.progress != null ? `${evt.progress}%` : "…")
      : evt.state === "done"
      ? (evt.time_ago || "Done")
      : "Fail";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        width: "100%",
        gap: 8,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0, flex: 1 }}>
        <DirectionIcon size={11} style={{ color: directionColor, flexShrink: 0 }} />
        {evt.state === "syncing" && (
          <RefreshCw size={11} className="animate-spin" style={{ color: "#0B57D0", flexShrink: 0 }} />
        )}
        {evt.state === "done" && (
          <Check size={11} style={{ color: "#15A362", flexShrink: 0 }} />
        )}
        {evt.state === "error" && (
          <X size={11} style={{ color: "#D14343", flexShrink: 0 }} />
        )}
        <span
          title={evt.path}
          style={{
            fontSize: 12,
            color: evt.state === "done" || evt.state === "error" ? "#8A8886" : "#333333",
            fontFamily: "Inter, sans-serif",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {evt.path}
        </span>
      </div>
      <span
        style={{
          fontSize: 11,
          fontWeight: evt.state === "syncing" || evt.state === "error" ? 600 : "normal",
          color: evt.state === "syncing" ? "#0B57D0"
            : evt.state === "error" ? "#D14343"
            : "#A8A6A4",
          fontFamily: "Inter, sans-serif",
          flexShrink: 0,
          textAlign: "right",
        }}
      >
        {progressLabel}
      </span>
    </div>
  );
}

// ── Component ──
//
// Workspace-as-project model (post-refactor): each workspace is bound 1:1 to
// one Syncthing folder. The widget no longer adds/removes folders — that's
// handled by the workspace create/delete flows in the sidebar. Here we only
// surface sync status for the active workspace's folder.

export function SyncFolderWidget({
  apiBase,
  getHeaders,
  syncState,
  activeWorkspace,
}: SyncFolderWidgetProps) {
  const [folderStatus, setFolderStatus] = useState<FolderStatus | null>(null);
  const [syncEvents, setSyncEvents] = useState<SyncFileEvent[]>([]);
  const [totalSyncing, setTotalSyncing] = useState(0);
  const [showPanel, setShowPanel] = useState(false);
  const [panelPos, setPanelPos] = useState({ bottom: 0, left: 0 });
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const folderId = activeWorkspace?.folder_id || null;

  // Recalculate panel position whenever it opens
  useEffect(() => {
    if (!showPanel || !buttonRef.current) return;
    const rect = buttonRef.current.getBoundingClientRect();
    setPanelPos({
      bottom: window.innerHeight - rect.top + 6,
      left: rect.left,
    });
  }, [showPanel]);

  // Close panel on outside click
  useEffect(() => {
    if (!showPanel) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      const clickedPanel = panelRef.current?.contains(target);
      const clickedButton = buttonRef.current?.contains(target);
      if (!clickedPanel && !clickedButton) setShowPanel(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showPanel]);

  // Poll folder status for just the active workspace's folder.
  const fetchFolderStatus = useCallback(async () => {
    if (!folderId) {
      setFolderStatus(null);
      return;
    }
    try {
      const res = await fetch(`${apiBase}/api/sync/folders`, {
        headers: getHeaders(),
      });
      if (!res.ok) return;
      const data = await res.json();
      const match = (data.folders || []).find((f: any) => f.id === folderId);
      if (!match) {
        setFolderStatus(null);
        return;
      }
      setFolderStatus({
        id: match.id,
        label: match.label,
        path: match.path || "",
        state: match.state === "idle" ? "idle"
          : match.state === "error" ? "error"
          : match.state === "pending" ? "pending"
          : "syncing",
        completion: match.completion ?? 100,
      });
    } catch {
      // Silently fail — retry on next poll
    }
  }, [apiBase, getHeaders, folderId]);

  // Fetch recent sync events scoped to this workspace's folder.
  const fetchSyncEvents = useCallback(async () => {
    if (!folderId) {
      setSyncEvents([]);
      setTotalSyncing(0);
      return;
    }
    try {
      const url = `${apiBase}/api/sync/events?minutes=30&limit=10&folder_id=${encodeURIComponent(folderId)}`;
      const res = await fetch(url, { headers: getHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      setSyncEvents(data.events || []);
      setTotalSyncing(data.total_syncing || 0);
    } catch {
      // Silently fail
    }
  }, [apiBase, getHeaders, folderId]);

  // Poll every 3s while active, 10s when idle. Resets when workspace switches.
  useEffect(() => {
    fetchFolderStatus();
    fetchSyncEvents();
    const isBusy = folderStatus?.state === "syncing" || folderStatus?.state === "pending";
    const interval = setInterval(() => {
      fetchFolderStatus();
      if (showPanel || isBusy) fetchSyncEvents();
    }, isBusy ? 3000 : 10000);
    return () => clearInterval(interval);
  }, [fetchFolderStatus, fetchSyncEvents, showPanel, folderStatus?.state, folderId]);

  // Refresh sync events when panel opens
  useEffect(() => {
    if (showPanel) fetchSyncEvents();
  }, [showPanel, fetchSyncEvents]);

  const isDisconnected = syncState === "disconnected" || syncState === "loading";
  const hasElectron = !!window.electronAPI?.dialogSelectFolder;

  // Don't show the button at all if not in Electron
  if (!hasElectron) return null;

  // No active workspace → nothing meaningful to show. Hide the pill entirely
  // so the prompt footer doesn't carry a ghost control.
  if (!activeWorkspace) return null;

  // Derive pill icon state from folder + events
  const pillIconState: SyncIconState = (() => {
    if (folderStatus?.state === "error" || syncEvents.some((e) => e.state === "error")) {
      return "error";
    }
    if (
      folderStatus?.state === "syncing" ||
      folderStatus?.state === "pending" ||
      syncEvents.some((e) => e.state === "syncing") ||
      totalSyncing > 0
    ) {
      return "syncing";
    }
    return "idle";
  })();

  const displayLabel = folderStatus?.label || activeWorkspace.label;
  const displayPath = folderStatus?.path || "";

  // Chronological mixed list — cap at 6 rows for a compact panel.
  const displayedEvents = syncEvents.slice(0, 6);
  const hasEvents = displayedEvents.length > 0;
  const barPct = Math.max(0, Math.min(100, folderStatus?.completion ?? 0));
  const barColor = folderStatus?.state === "error" ? "#D14343"
    : folderStatus?.state === "idle" ? "#15A362"
    : "#0B57D0";

  return (
    <>
      {/* folder-status-pop panel via portal */}
      {showPanel && createPortal(
        <div
          ref={panelRef}
          style={{ position: "fixed", bottom: panelPos.bottom, left: panelPos.left }}
          className="z-[9999]"
        >
          <div
            className="w-[280px] rounded-lg overflow-hidden"
            style={{
              background: "#FFFFFF",
              border: "1px solid #EAE8E6",
              boxShadow: "0 8px 24px rgba(0, 0, 0, 0.09)",
              padding: 12,
              display: "flex",
              flexDirection: "column",
              gap: 10,
            }}
          >
            {/* ── Workspace folder header ── */}
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ padding: "0 2px" }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: "#8A8886", fontFamily: "Inter, sans-serif" }}>
                  Workspace folder
                </span>
              </div>
              <div
                style={{
                  padding: "6px 8px",
                  borderRadius: 6,
                  background: "#F7F6F5",
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                  <Folder size={16} style={{ color: "#333333", flexShrink: 0 }} />
                  <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0, flex: 1 }}>
                    <span
                      style={{
                        fontSize: 13,
                        color: "#333333",
                        fontFamily: "Inter, sans-serif",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {displayLabel}
                    </span>
                    {displayPath && (
                      <span
                        style={{
                          fontSize: 11,
                          color: "#8A8886",
                          fontFamily: "Inter, sans-serif",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                        title={displayPath}
                      >
                        {displayPath}
                      </span>
                    )}
                  </div>
                  {folderStatus && folderStatus.state !== "idle" && (
                    <span
                      style={{
                        fontSize: 11,
                        color: "#8A8886",
                        fontFamily: "Inter, sans-serif",
                        minWidth: 32,
                        textAlign: "right",
                        flexShrink: 0,
                      }}
                    >
                      {Math.round(barPct)}%
                    </span>
                  )}
                </div>
                {folderStatus && folderStatus.state !== "idle" && (
                  <div style={{ height: 2, borderRadius: 1, background: "#F0EEEC", overflow: "hidden" }}>
                    <div
                      style={{
                        height: "100%",
                        width: `${barPct}%`,
                        background: barColor,
                        transition: "width 0.3s ease",
                      }}
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Divider */}
            <div style={{ height: 1, width: "100%", background: "#F7F6F5" }} />

            {/* ── File Sync Status section ── */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: "#8A8886", fontFamily: "Inter, sans-serif" }}>
                File Sync Status
              </span>
            </div>

            {/* File sync rows — chronological mixed list, per-row ↑/↓ arrow */}
            {hasEvents ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {displayedEvents.map((evt, i) => (
                  <FileSyncRow key={`${evt.path}-${evt.timestamp}-${i}`} evt={evt} />
                ))}
              </div>
            ) : (
              <div style={{ padding: "4px 0" }}>
                <span style={{ fontSize: 12, color: "#A8A6A4", fontFamily: "Inter, sans-serif" }}>
                  No recent sync activity
                </span>
              </div>
            )}

            {/* Divider + View all (only if there are events) */}
            {hasEvents && (
              <>
                <div style={{ height: 1, width: "100%", background: "#F7F6F5" }} />
                <button
                  type="button"
                  className="w-full transition-colors hover:bg-[#F7F6F5]"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "4px 0",
                    border: "none",
                    background: "transparent",
                    cursor: "pointer",
                    width: "100%",
                  }}
                >
                  <span style={{ fontSize: 11, fontWeight: 600, color: "#A8A6A4", fontFamily: "Inter, sans-serif" }}>
                    {totalSyncing > 0
                      ? `View all ${totalSyncing} syncing files...`
                      : `View all ${syncEvents.length} recent files...`
                    }
                  </span>
                  <ChevronRight size={12} style={{ color: "#D6D4D2" }} />
                </button>
              </>
            )}
          </div>
        </div>,
        document.body
      )}

      {/* ── Pill trigger button — transparent background, dynamic icon state ── */}
      <button
        type="button"
        ref={buttonRef}
        onClick={() => setShowPanel((v) => !v)}
        disabled={isDisconnected}
        className="flex items-center gap-1.5 transition-colors rounded-md hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
        style={{
          padding: "4px 8px",
          border: "none",
          background: "transparent",
        }}
        title={displayPath || displayLabel}
      >
        <SyncFolderIcon state={pillIconState} size={16} />
        <span
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: "#5A5856",
            fontFamily: "Inter, sans-serif",
            maxWidth: 160,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {displayLabel}
        </span>
        {totalSyncing > 0 && (
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: "#FFFFFF",
              background: "#0B57D0",
              padding: "1px 6px",
              borderRadius: 10,
              fontFamily: "Inter, sans-serif",
              lineHeight: 1.4,
            }}
          >
            {totalSyncing}
          </span>
        )}
      </button>
    </>
  );
}
