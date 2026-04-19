import { useState, useCallback, useEffect } from "react";
import { createPortal } from "react-dom";
import { FolderPlus, Loader2, X } from "lucide-react";

// Dialog for creating a new workspace by picking a local folder.
// Wraps the existing Syncthing folder creation flow:
//   1) system folder picker
//   2) local Syncthing config (electronAPI.syncthingAddFolder)
//   3) VPS folder creation + workspace wrap (POST /api/sync/folders)
//
// On success, the caller receives the created workspace id so it can
// switch the UI into that workspace immediately.

interface NewWorkspaceDialogProps {
  open: boolean;
  onClose: () => void;
  apiBase: string;
  getHeaders: () => Record<string, string>;
  vpsDeviceId: string;
  onCreated: (workspaceId: string) => void;
}

export function NewWorkspaceDialog({
  open,
  onClose,
  apiBase,
  getHeaders,
  vpsDeviceId,
  onCreated,
}: NewWorkspaceDialogProps) {
  const [localPath, setLocalPath] = useState<string | null>(null);
  const [label, setLabel] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Reset state when the dialog opens
  useEffect(() => {
    if (open) {
      setLocalPath(null);
      setLabel("");
      setIsCreating(false);
      setErrorMsg(null);
    }
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !isCreating) onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, isCreating, onClose]);

  const pickFolder = useCallback(async () => {
    const electron = window.electronAPI;
    if (!electron?.dialogSelectFolder) {
      setErrorMsg("Folder picker is unavailable. Please relaunch Nono CoWork.");
      return;
    }
    try {
      const pick = await electron.dialogSelectFolder();
      if (!pick.success || !pick.path) return;
      setLocalPath(pick.path);
      if (!label) {
        const guess = pick.path.split(/[/\\]/).pop() || "Workspace";
        setLabel(guess);
      }
    } catch (e) {
      setErrorMsg(`Folder picker failed: ${String(e)}`);
    }
  }, [label]);

  const handleCreate = useCallback(async () => {
    const electron = window.electronAPI;
    if (!localPath || !electron?.syncthingAddFolder) return;
    if (!vpsDeviceId) {
      setErrorMsg("VPS is not paired yet. Wait for Syncthing to connect and try again.");
      return;
    }

    setIsCreating(true);
    setErrorMsg(null);
    try {
      // Step 1: add folder to local Syncthing
      const addResult = await electron.syncthingAddFolder({
        localPath,
        vpsDeviceId,
      });
      if (!addResult.success) {
        setErrorMsg("Failed to register the folder with local Syncthing.");
        return;
      }

      const folderId = addResult.folderId;
      const folderLabel = (label || addResult.folderLabel || "Workspace").trim();

      // Step 2: VPS creates receive folder AND auto-wraps it in a workspace
      const desktopDevice = await electron.syncthingLocalDevice?.();
      const res = await fetch(`${apiBase}/api/sync/folders`, {
        method: "POST",
        headers: { ...getHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({
          folder_id: folderId,
          folder_label: folderLabel,
          desktop_device_id: desktopDevice?.deviceId || "",
        }),
      });

      if (!res.ok) {
        const text = await res.text().catch(() => "");
        setErrorMsg(`Backend error: ${res.status} ${text}`);
        return;
      }

      const data = await res.json();
      const workspaceId: string | undefined = data?.workspace?.id;

      // Step 3: if the backend didn't auto-wrap, create explicitly
      let finalWsId = workspaceId;
      if (!finalWsId) {
        const createRes = await fetch(`${apiBase}/api/workspaces`, {
          method: "POST",
          headers: { ...getHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify({ label: folderLabel, folder_id: folderId }),
        });
        if (createRes.ok) {
          const ws = await createRes.json();
          finalWsId = ws?.id;
        }
      } else if (label && label !== folderLabel) {
        // Update the workspace label if the user overrode it
        await fetch(`${apiBase}/api/workspaces/${finalWsId}`, {
          method: "PATCH",
          headers: { ...getHeaders(), "Content-Type": "application/json" },
          body: JSON.stringify({ label: label.trim() }),
        }).catch(() => {});
      }

      if (!finalWsId) {
        setErrorMsg("Workspace created, but no id was returned.");
        return;
      }

      onCreated(finalWsId);
      onClose();
    } catch (e) {
      setErrorMsg(`Unexpected error: ${String(e)}`);
    } finally {
      setIsCreating(false);
    }
  }, [localPath, label, vpsDeviceId, apiBase, getHeaders, onCreated, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={() => {
        if (!isCreating) onClose();
      }}
    >
      <div
        className="relative w-[460px] max-w-[92vw] rounded-xl bg-background border border-border shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-5 pb-3">
          <div className="flex items-center gap-2">
            <FolderPlus size={18} className="text-muted-foreground" />
            <h2 className="text-[15px] font-medium">New Workspace</h2>
          </div>
          <button
            onClick={onClose}
            disabled={isCreating}
            className="p-1 rounded hover:bg-muted text-muted-foreground disabled:opacity-40"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 pb-5 space-y-4">
          <p className="text-[12px] text-muted-foreground leading-relaxed">
            Pick a local folder to become your new workspace. Files in this
            folder will sync with the agent on the VPS. One folder = one
            workspace — create another workspace later to keep contexts apart.
          </p>

          {/* Folder picker */}
          <div className="space-y-1.5">
            <label className="text-[12px] font-medium text-foreground/70">
              Folder
            </label>
            <button
              onClick={pickFolder}
              disabled={isCreating}
              className="flex items-center justify-between w-full px-3 py-2 rounded-md border border-border bg-muted/40 hover:bg-muted text-[13px] text-left disabled:opacity-50"
            >
              <span className={localPath ? "" : "text-muted-foreground"}>
                {localPath || "Choose a folder…"}
              </span>
              <FolderPlus size={14} className="text-muted-foreground shrink-0 ml-2" />
            </button>
          </div>

          {/* Label */}
          <div className="space-y-1.5">
            <label className="text-[12px] font-medium text-foreground/70">
              Label
            </label>
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              disabled={isCreating}
              placeholder="e.g. Client projects"
              className="w-full px-3 py-2 rounded-md border border-border bg-background text-[13px] focus:outline-none focus:ring-2 focus:ring-primary/40"
            />
            <p className="text-[11px] text-muted-foreground/80">
              The label shows up in the sidebar — you can rename it later.
            </p>
          </div>

          {errorMsg && (
            <div className="px-3 py-2 rounded-md bg-red-500/10 text-red-500 text-[12px] leading-relaxed">
              {errorMsg}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-5 pb-5">
          <button
            onClick={onClose}
            disabled={isCreating}
            className="px-3 py-1.5 rounded-md text-[13px] text-muted-foreground hover:bg-muted disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={!localPath || !label.trim() || isCreating}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-[13px] hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isCreating && <Loader2 size={13} className="animate-spin" />}
            {isCreating ? "Creating…" : "Create Workspace"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
