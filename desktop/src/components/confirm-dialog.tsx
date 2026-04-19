import { useEffect } from "react";
import { createPortal } from "react-dom";
import { AlertTriangle, X } from "lucide-react";

// Reusable "are you sure?" modal. Replaces window.confirm() which is
// disabled by default in Electron. Keep the API small and declarative
// so callers don't have to hand-roll confirmation UIs.

export type ConfirmTone = "neutral" | "danger";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: ConfirmTone;
  onConfirm: () => void;
  onCancel: () => void;
  /** If true the confirm/cancel buttons are disabled (e.g. request in flight). */
  busy?: boolean;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "neutral",
  onConfirm,
  onCancel,
  busy = false,
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (busy) return;
      if (e.key === "Escape") onCancel();
      if (e.key === "Enter") onConfirm();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, busy, onCancel, onConfirm]);

  if (!open) return null;

  const confirmBg = tone === "danger" ? "#D14343" : "#1F1E1D";
  const confirmHover = tone === "danger" ? "#B83838" : "#000000";

  return createPortal(
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0, 0, 0, 0.35)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 10000,
      }}
      onMouseDown={(e) => {
        // Click on backdrop = cancel (but not when busy).
        if (e.target === e.currentTarget && !busy) onCancel();
      }}
    >
      <div
        className="rounded-lg"
        style={{
          background: "#FFFFFF",
          border: "1px solid #EAE8E6",
          boxShadow: "0 12px 36px rgba(0, 0, 0, 0.15)",
          padding: 20,
          width: 420,
          maxWidth: "92vw",
          fontFamily: "Inter, sans-serif",
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
          {tone === "danger" && (
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: "50%",
                background: "#FDECEC",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <AlertTriangle size={16} style={{ color: "#D14343" }} />
            </div>
          )}
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: "#1F1E1D" }}>
              {title}
            </h2>
            {description && (
              <div
                style={{
                  marginTop: 6,
                  fontSize: 13,
                  color: "#5A5856",
                  lineHeight: 1.5,
                }}
              >
                {description}
              </div>
            )}
          </div>
          <button
            type="button"
            aria-label="Close"
            onClick={() => !busy && onCancel()}
            disabled={busy}
            style={{
              border: "none",
              background: "transparent",
              padding: 2,
              cursor: busy ? "not-allowed" : "pointer",
              color: "#8A8886",
            }}
          >
            <X size={16} />
          </button>
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            style={{
              padding: "6px 14px",
              borderRadius: 6,
              border: "1px solid #EAE8E6",
              background: "#FFFFFF",
              color: "#333333",
              fontSize: 13,
              fontWeight: 500,
              cursor: busy ? "not-allowed" : "pointer",
              fontFamily: "Inter, sans-serif",
            }}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="transition-colors"
            style={{
              padding: "6px 14px",
              borderRadius: 6,
              border: "none",
              background: busy ? "#A8A6A4" : confirmBg,
              color: "#FFFFFF",
              fontSize: 13,
              fontWeight: 500,
              cursor: busy ? "not-allowed" : "pointer",
              fontFamily: "Inter, sans-serif",
            }}
            onMouseEnter={(e) => {
              if (!busy) (e.currentTarget as HTMLButtonElement).style.background = confirmHover;
            }}
            onMouseLeave={(e) => {
              if (!busy) (e.currentTarget as HTMLButtonElement).style.background = confirmBg;
            }}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
