"use client";

import { cn } from "@/lib/utils";
import { useState, useRef, useEffect, useCallback } from "react";
import { KeyRound, Eye, EyeOff } from "lucide-react";

interface CredentialCardProps {
  keyName: string;
  serviceName: string;
  serviceDescription: string;
  onSubmit: (value: string) => void;
  onSkip: () => void;
}

export function CredentialCard({
  keyName,
  serviceName,
  serviceDescription,
  onSubmit,
  onSkip,
}: CredentialCardProps) {
  const [value, setValue] = useState("");
  const [visible, setVisible] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const canSubmit = value.trim().length > 0;

  const handleSubmit = useCallback(() => {
    if (canSubmit) onSubmit(value.trim());
  }, [canSubmit, value, onSubmit]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  return (
    <div className="rounded-xl border border-border/60 bg-card overflow-hidden shadow-sm">
      {/* Header */}
      <div className="px-5 pt-4 pb-3">
        <div className="flex items-center gap-2 mb-1.5">
          <KeyRound className="size-4 text-primary/70" />
          <h4 className="text-[14px] font-bold text-foreground leading-snug">
            {serviceName}
          </h4>
        </div>
        <p className="text-[12px] text-muted-foreground leading-snug">
          {serviceDescription}
        </p>
      </div>

      {/* Input */}
      <div className="px-5 pb-3">
        <label className="block text-[11px] font-medium text-muted-foreground/70 mb-1.5">
          {keyName}
        </label>
        <div className="relative">
          <input
            ref={inputRef}
            type={visible ? "text" : "password"}
            placeholder="Paste your API key here"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            autoComplete="off"
            spellCheck={false}
            className="w-full bg-muted/40 rounded-lg px-3 py-2.5 pr-10 text-[13px] text-foreground font-mono placeholder:text-muted-foreground/40 outline-none focus:ring-1 focus:ring-primary/30 transition-shadow"
          />
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/50 hover:text-muted-foreground transition-colors cursor-pointer"
          >
            {visible ? (
              <EyeOff className="size-3.5" />
            ) : (
              <Eye className="size-3.5" />
            )}
          </button>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-end gap-3 px-5 py-3 border-t border-border/30">
        <button
          type="button"
          onClick={onSkip}
          className="px-3 py-1.5 text-[12px] font-medium text-muted-foreground hover:text-foreground rounded-md hover:bg-muted/60 transition-colors cursor-pointer"
        >
          Skip
        </button>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit}
          className={cn(
            "px-4 py-1.5 text-[12px] font-medium rounded-md transition-colors",
            canSubmit
              ? "bg-primary text-primary-foreground hover:bg-primary/90 cursor-pointer"
              : "bg-muted text-muted-foreground/30 cursor-not-allowed",
          )}
        >
          Save
        </button>
      </div>
    </div>
  );
}
