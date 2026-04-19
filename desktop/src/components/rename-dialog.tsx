import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

// Small inline-renaming modal. Replaces window.prompt() which is
// disabled by default in Electron. Used for workspace rename today,
// intended to be reusable for any "enter a new name" flow.

interface RenameDialogProps {
  open: boolean;
  title?: string;
  label?: string;
  initialValue: string;
  /** Minimum non-whitespace characters required. Defaults to 1. */
  minLength?: number;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: (nextValue: string) => void | Promise<void>;
  onCancel: () => void;
  busy?: boolean;
}

export function RenameDialog({
  open,
  title = "Rename",
  label = "Name",
  initialValue,
  minLength = 1,
  confirmLabel = "Save",
  cancelLabel = "Cancel",
  onConfirm,
  onCancel,
  busy = false,
}: RenameDialogProps) {
  const [value, setValue] = useState(initialValue);
  const inputRef = useRef<HTMLInputElement>(null);

  // Reset value whenever the dialog re-opens
  useEffect(() => {
    if (open) {
      setValue(initialValue);
      // Focus + select on next paint so the user can start typing
      const t = setTimeout(() => {
        inputRef.current?.focus();
        inputRef.current?.select();
      }, 20);
      return () => clearTimeout(t);
    }
  }, [open, initialValue]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (busy) return;
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, busy, onCancel]);

  if (!open) return null;

  const trimmed = value.trim();
  const valid = trimmed.length >= minLength;
  const unchanged = trimmed === initialValue.trim();

  const handleSubmit = () => {
    if (!valid || unchanged || busy) return;
    const result = onConfirm(trimmed);
    // Caller may return a Promise; we don't wait here — caller is
    // responsible for flipping `busy` while it's in flight.
    void result;
  };

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
        if (e.target === e.currentTarget && !busy) onCancel();
      }}
    >
      <form
        className="rounded-lg"
        onSubmit={(e) => {
          e.preventDefault();
          handleSubmit();
        }}
        style={{
          background: "#FFFFFF",
          border: "1px solid #EAE8E6",
          boxShadow: "0 12px 36px rgba(0, 0, 0, 0.15)",
          padding: 20,
          width: 400,
          maxWidth: "92vw",
          fontFamily: "Inter, sans-serif",
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <h2 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: "#1F1E1D" }}>
            {title}
          </h2>
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

        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 500, color: "#5A5856" }}>{label}</span>
          <input
            ref={inputRef}
            type="text"
            value={value}
            onChange={(e) => setValue(e.currentTarget.value)}
            disabled={busy}
            style={{
              padding: "8px 10px",
              border: "1px solid #EAE8E6",
              borderRadius: 6,
              fontSize: 13,
              fontFamily: "Inter, sans-serif",
              color: "#1F1E1D",
              outline: "none",
              background: busy ? "#F7F6F5" : "#FFFFFF",
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "#0B57D0";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "#EAE8E6";
            }}
          />
        </label>

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
            type="submit"
            disabled={!valid || unchanged || busy}
            style={{
              padding: "6px 14px",
              borderRadius: 6,
              border: "none",
              background: (!valid || unchanged || busy) ? "#A8A6A4" : "#1F1E1D",
              color: "#FFFFFF",
              fontSize: 13,
              fontWeight: 500,
              cursor: (!valid || unchanged || busy) ? "not-allowed" : "pointer",
              fontFamily: "Inter, sans-serif",
            }}
          >
            {confirmLabel}
          </button>
        </div>
      </form>
    </div>,
    document.body,
  );
}
