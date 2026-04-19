import { useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { FolderHeart, FolderSearch, Loader2, X } from "lucide-react";

// Onboarding dialog for first-launch. Shown when the user has zero
// workspaces — they choose between a one-click default (~/Nono-Workspace)
// or picking their own folder.
//
// Both paths converge on the same create flow used by NewWorkspaceDialog:
//   1) ensure the local folder exists
//   2) electronAPI.syncthingAddFolder → register with local Syncthing
//   3) POST /api/sync/folders          → VPS creates receive folder, wraps as workspace
//   4) PATCH /api/workspaces/:id       → mark as default

const DEFAULT_FOLDER_NAME = "Nono-Workspace";

interface OnboardingDialogProps {
  open: boolean;
  onClose: () => void;
  apiBase: string;
  getHeaders: () => Record<string, string>;
  vpsDeviceId: string;
  /**
   * If true, the user already has some workspaces but none is the
   * safety-net default — the dialog uses "Set up your default workspace"
   * wording so it doesn't look like a first-launch dialog.
   */
  existingWorkspaces?: boolean;
  /** Called with the workspace_id after success; caller should refresh workspaces. */
  onCreated: (workspaceId: string) => void;
}

export function OnboardingDialog({
  open,
  onClose,
  apiBase,
  getHeaders,
  vpsDeviceId,
  existingWorkspaces = false,
  onCreated,
}: OnboardingDialogProps) {
  const [isWorking, setIsWorking] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [mode, setMode] = useState<"default" | "custom" | null>(null);

  // Reset state each time we open
  useEffect(() => {
    if (open) {
      setIsWorking(false);
      setErrorMsg(null);
      setMode(null);
    }
  }, [open]);

  // Esc to dismiss (only when not mid-operation)
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !isWorking) onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, isWorking, onClose]);

  // Shared creation pipeline used by both onboarding paths.
  const createWorkspaceAt = useCallback(
    async (localPath: string, labelOverride?: string): Promise<string | null> => {
      const electron = window.electronAPI;
      if (!electron?.syncthingAddFolder) {
        setErrorMsg("Syncthing bridge unavailable. Please relaunch Nono CoWork.");
        return null;
      }
      if (!vpsDeviceId) {
        setErrorMsg("VPS not paired yet. Finish sync setup first.");
        return null;
      }

      // 1. Register folder with local Syncthing
      const addResult = await electron.syncthingAddFolder({ localPath, vpsDeviceId });
      if (!addResult.success) {
        setErrorMsg(addResult.error || "Could not register folder with local Syncthing.");
        return null;
      }
      const folderId = addResult.folderId;
      const folderLabel = labelOverride || addResult.folderLabel || "Workspace";

      // 2. Tell VPS to create matching receive folder (auto-wraps into a workspace)
      const desktopDevice = await electron.syncthingLocalDevice?.();
      const createRes = await fetch(`${apiBase}/api/sync/folders`, {
        method: "POST",
        headers: { ...getHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({
          folder_id: folderId,
          folder_label: folderLabel,
          desktop_device_id: desktopDevice?.deviceId || "",
        }),
      });
      if (!createRes.ok) {
        const errBody = await createRes.json().catch(() => ({}));
        setErrorMsg(errBody.error || `VPS rejected folder: HTTP ${createRes.status}`);
        return null;
      }
      const createBody = await createRes.json();
      const workspaceId: string | undefined =
        createBody.workspace?.id || createBody.workspace_id;
      if (!workspaceId) {
        setErrorMsg("Backend did not return a workspace id.");
        return null;
      }

      // 3. Mark as default (best-effort; label override too if provided)
      try {
        await fetch(`${apiBase}/api/workspaces/${workspaceId}`, {
          method: "PATCH",
          headers: { ...getHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify({
            is_default: true,
            ...(labelOverride ? { label: labelOverride } : {}),
          }),
        });
      } catch {
        // Non-fatal: default flag will fall back to "first workspace".
      }

      return workspaceId;
    },
    [apiBase, getHeaders, vpsDeviceId],
  );

  // "Use default" flow: ~/Nono-Workspace
  const handleUseDefault = useCallback(async () => {
    const electron = window.electronAPI;
    if (!electron?.getHomeDir || !electron?.ensureDir) {
      setErrorMsg("Default workspace requires an updated Electron shell. Pick a folder instead.");
      return;
    }
    setMode("default");
    setIsWorking(true);
    setErrorMsg(null);
    try {
      const home = await electron.getHomeDir();
      if (!home.success || !home.path) {
        setErrorMsg("Could not resolve home directory.");
        return;
      }
      // Use forward slash for internal bookkeeping; Syncthing/Electron handle
      // platform-native paths downstream.
      const localPath = `${home.path.replace(/[\\/]+$/, "")}/${DEFAULT_FOLDER_NAME}`;
      const mkdir = await electron.ensureDir(localPath);
      if (!mkdir.success) {
        setErrorMsg(mkdir.error || "Could not create default workspace folder.");
        return;
      }
      const wsId = await createWorkspaceAt(localPath, DEFAULT_FOLDER_NAME);
      if (wsId) {
        onCreated(wsId);
        onClose();
      }
    } finally {
      setIsWorking(false);
    }
  }, [createWorkspaceAt, onCreated, onClose]);

  // "Pick your own" flow
  const handlePickCustom = useCallback(async () => {
    const electron = window.electronAPI;
    if (!electron?.dialogSelectFolder) {
      setErrorMsg("Folder picker is unavailable. Please relaunch Nono CoWork.");
      return;
    }
    setMode("custom");
    setErrorMsg(null);
    try {
      const pick = await electron.dialogSelectFolder();
      if (!pick.success || !pick.path) {
        setMode(null);
        return;
      }
      setIsWorking(true);
      const wsId = await createWorkspaceAt(pick.path);
      if (wsId) {
        onCreated(wsId);
        onClose();
      }
    } finally {
      setIsWorking(false);
    }
  }, [createWorkspaceAt, onCreated, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0, 0, 0, 0.35)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
      }}
    >
      <div
        className="rounded-lg"
        style={{
          background: "#FFFFFF",
          border: "1px solid #EAE8E6",
          boxShadow: "0 12px 36px rgba(0, 0, 0, 0.15)",
          padding: 24,
          width: 460,
          maxWidth: "92vw",
          fontFamily: "Inter, sans-serif",
          display: "flex",
          flexDirection: "column",
          gap: 18,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: "#1F1E1D" }}>
            {existingWorkspaces ? "Set up your default workspace" : "Set up your first workspace"}
          </h2>
          <button
            type="button"
            aria-label="Close"
            onClick={() => !isWorking && onClose()}
            disabled={isWorking}
            style={{
              border: "none",
              background: "transparent",
              padding: 2,
              cursor: isWorking ? "not-allowed" : "pointer",
              color: "#8A8886",
            }}
          >
            <X size={16} />
          </button>
        </div>

        <p style={{ margin: 0, fontSize: 13, color: "#5A5856", lineHeight: 1.5 }}>
          {existingWorkspaces
            ? "Your default workspace is a safety-net that can't be deleted, so there's always somewhere for new chats to land. Pick one now — your existing workspaces stay untouched."
            : "A workspace pairs a local folder with Nono CoWork so your agent can read and edit files there. You can always change or add more later."}
        </p>

        {/* Option 1: default */}
        <button
          type="button"
          onClick={handleUseDefault}
          disabled={isWorking}
          className="w-full text-left transition-colors hover:bg-[#F7F6F5]"
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 12,
            padding: 14,
            borderRadius: 8,
            border: "1px solid #EAE8E6",
            background: mode === "default" ? "#F7F6F5" : "#FFFFFF",
            cursor: isWorking ? "not-allowed" : "pointer",
          }}
        >
          {mode === "default" && isWorking ? (
            <Loader2 size={18} className="animate-spin" style={{ color: "#0B57D0", marginTop: 2, flexShrink: 0 }} />
          ) : (
            <FolderHeart size={18} style={{ color: "#0B57D0", marginTop: 2, flexShrink: 0 }} />
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: "#1F1E1D" }}>
              Use the default workspace
            </span>
            <span style={{ fontSize: 12, color: "#8A8886" }}>
              We'll create <code style={{ fontFamily: "ui-monospace, Menlo, monospace" }}>~/{DEFAULT_FOLDER_NAME}</code> for you.
            </span>
          </div>
        </button>

        {/* Option 2: custom */}
        <button
          type="button"
          onClick={handlePickCustom}
          disabled={isWorking}
          className="w-full text-left transition-colors hover:bg-[#F7F6F5]"
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 12,
            padding: 14,
            borderRadius: 8,
            border: "1px solid #EAE8E6",
            background: mode === "custom" ? "#F7F6F5" : "#FFFFFF",
            cursor: isWorking ? "not-allowed" : "pointer",
          }}
        >
          {mode === "custom" && isWorking ? (
            <Loader2 size={18} className="animate-spin" style={{ color: "#333333", marginTop: 2, flexShrink: 0 }} />
          ) : (
            <FolderSearch size={18} style={{ color: "#333333", marginTop: 2, flexShrink: 0 }} />
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: "#1F1E1D" }}>
              Pick an existing folder
            </span>
            <span style={{ fontSize: 12, color: "#8A8886" }}>
              Point the agent at a project folder you already have.
            </span>
          </div>
        </button>

        {errorMsg && (
          <div
            style={{
              padding: "8px 10px",
              borderRadius: 6,
              background: "#FDECEC",
              border: "1px solid #F5C2C2",
              color: "#A12121",
              fontSize: 12,
            }}
          >
            {errorMsg}
          </div>
        )}

        <p style={{ margin: 0, fontSize: 11, color: "#A8A6A4" }}>
          Your default workspace cannot be deleted, but it can be renamed
          anytime from the sidebar.
        </p>
      </div>
    </div>,
    document.body,
  );
}
