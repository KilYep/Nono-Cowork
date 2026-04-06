/**
 * FileCard — Document-tile style file component.
 *
 * Classic file icon look: folded corner (SVG), extension icon,
 * filename + status badge. On hover: full blur overlay with buttons.
 */

import { useState } from "react";
import { FolderOpen, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import type { DeliverableComponentProps } from "./registry";
import type { FileMetadata } from "./types";
import { syncPaths, getFileIcon, getFileName, getFileExtension } from "./utils";

// ── Standalone props ──

interface FileCardStandaloneProps {
  path: string;
  action?: "created" | "modified" | "deleted";
  size?: string;
  mode?: "compact";
}

type FileCardProps = DeliverableComponentProps | FileCardStandaloneProps;

function isStandalone(props: FileCardProps): props is FileCardStandaloneProps {
  return "path" in props && !("deliverable" in props);
}

const FOLD = 14; // fold corner size in px

// ── Component ──

export function FileCard(props: FileCardProps) {
  const [hovered, setHovered] = useState(false);

  let path: string;
  let absPath: string | undefined;
  let action: "created" | "modified" | "deleted";

  if (isStandalone(props)) {
    path = props.path;
    absPath = undefined;
    action = props.action || "created";
  } else {
    const meta = (props.deliverable.metadata || {}) as unknown as FileMetadata;
    path = meta.path || "";
    absPath = meta.abs_path;
    action = meta.action || "created";
  }

  const fileName = getFileName(path);
  const extension = getFileExtension(path);
  const FileIcon = getFileIcon(extension);

  const actionConfig = {
    created: { color: "text-emerald-600", label: "New", bgColor: "bg-emerald-500/10" },
    modified: { color: "text-blue-500", label: "Edit", bgColor: "bg-blue-500/10" },
    deleted: { color: "text-red-400", label: "Del", bgColor: "bg-red-400/10" },
  }[action];

  const handleOpenFile = async () => {
    if (!window.electronAPI?.openFile) {
      toast.error("Only available in desktop app");
      return;
    }
    const rawPath = absPath || path;
    const localPath = syncPaths.resolve(rawPath);


    // Warn if path wasn't actually resolved (still looks like a remote path)
    if (localPath.startsWith("/") && !localPath.match(/^[A-Z]:/i)) {
      toast.error("Cannot resolve remote path to local. Is Syncthing running?");
      return;
    }

    const result = await window.electronAPI.openFile(localPath);
    if (!result.success) {
      toast.error(`Cannot open file: ${result.error}`);
    }
  };

  const handleShowInExplorer = async () => {
    if (!window.electronAPI?.showInExplorer) {
      toast.error("Only available in desktop app");
      return;
    }
    const rawPath = absPath || path;
    const localPath = syncPaths.resolve(rawPath);


    // Warn if path wasn't actually resolved
    if (localPath.startsWith("/") && !localPath.match(/^[A-Z]:/i)) {
      toast.error("Cannot resolve remote path to local. Is Syncthing running?");
      return;
    }

    const result = await window.electronAPI.showInExplorer(localPath);
    if (!result.success) {
      toast.error(`Cannot open folder: ${result.error}`);
    }
  };

  const hasElectron = !!window.electronAPI?.openFile;
  const showOverlay = hovered && action !== "deleted" && hasElectron;

  return (
    <div
      className="relative w-[84px] shrink-0 cursor-default select-none"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* ── Card body ── */}
      <div
        className="rounded-lg border border-border/50 bg-card overflow-hidden"
        style={{ clipPath: `polygon(0 0, calc(100% - ${FOLD}px) 0, 100% ${FOLD}px, 100% 100%, 0 100%)` }}
      >
        {/* Icon area */}
        <div className="flex items-center justify-center w-full pt-5 pb-2.5">
          <FileIcon
            size={28}
            strokeWidth={1.2}
            className="text-muted-foreground/50"
          />
        </div>

        {/* Info: filename + badge */}
        <div className="flex flex-col items-center gap-1 px-1.5 pb-2 w-full border-t border-border/20">
          <span className="text-[10px] font-medium text-foreground/55 truncate w-full text-center leading-tight mt-1">
            {fileName}
          </span>
          <span className={`text-[8px] font-bold uppercase px-1.5 py-px rounded-full leading-none ${actionConfig.color} ${actionConfig.bgColor}`}>
            {actionConfig.label}
          </span>
        </div>
      </div>

      {/* ── Fold corner (SVG) ── */}
      <svg
        className="absolute top-[-0.5px] right-[-0.5px] pointer-events-none"
        width={FOLD + 1}
        height={FOLD + 1}
        viewBox={`0 0 ${FOLD + 1} ${FOLD + 1}`}
      >
        {/* Fold triangle — the "back of the paper" (darker to show depth) */}
        <polygon
          points={`0.5,1 ${FOLD},${FOLD} 0.5,${FOLD}`}
          className="fill-muted"
          fillOpacity="1"
        />
        {/* Fold border — left edge */}
        <line
          x1="0.5" y1="0" x2="0.5" y2={FOLD}
          className="stroke-border"
          strokeWidth="1"
          strokeOpacity="0.5"
        />
        {/* Fold border — bottom edge */}
        <line
          x1="0" y1={FOLD} x2={FOLD + 1} y2={FOLD}
          className="stroke-border"
          strokeWidth="1"
          strokeOpacity="0.5"
        />
        {/* Crease line (fold diagonal) */}
        <line
          x1="0.5" y1="0.5" x2={FOLD + 0.5} y2={FOLD + 0.5}
          className="stroke-border"
          strokeWidth="0.5"
          strokeOpacity="0.2"
        />
      </svg>

      {/* ── Full-card hover overlay (always in DOM for fade-out) ── */}
      {action !== "deleted" && hasElectron && (
        <div className={`absolute inset-0 z-10 flex flex-col items-center justify-center gap-0 rounded-lg rounded-tr-none transition-all duration-200 ease-in-out ${
          showOverlay
            ? "opacity-100 backdrop-blur-[6px] bg-background/75 pointer-events-auto"
            : "opacity-0 backdrop-blur-0 bg-background/0 pointer-events-none"
        }`}>
          <button
            onClick={handleOpenFile}
            className="flex flex-col items-center gap-0.5 p-1.5 rounded-md text-foreground/50 hover:text-foreground hover:bg-muted/50 transition-colors"
          >
            <ExternalLink size={20} strokeWidth={1.6} />
            <span className="text-[7px] font-semibold uppercase tracking-wide">Open</span>
          </button>
          <button
            onClick={handleShowInExplorer}
            className="flex flex-col items-center gap-0.5 p-1.5 rounded-md text-foreground/50 hover:text-foreground hover:bg-muted/50 transition-colors"
          >
            <FolderOpen size={20} strokeWidth={1.6} />
            <span className="text-[7px] font-semibold uppercase tracking-wide">Folder</span>
          </button>
        </div>
      )}
    </div>
  );
}
