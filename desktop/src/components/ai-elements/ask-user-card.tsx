"use client";

import { cn } from "@/lib/utils";
import { useState, useCallback, useRef, useEffect } from "react";
import { Check } from "lucide-react";

interface AskUserOption {
  label: string;
  description?: string;
  value?: string;
}

interface AskUserCardProps {
  question: string;
  options?: AskUserOption[];
  allowMultiple?: boolean;
  onSubmit: (answer: string) => void;
  onSkip: () => void;
}

export function AskUserCard({
  question,
  options,
  allowMultiple = false,
  onSubmit,
  onSkip,
}: AskUserCardProps) {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [otherText, setOtherText] = useState("");
  const otherInputRef = useRef<HTMLInputElement>(null);

  const hasOptions = options && options.length > 0;

  const toggleOption = useCallback(
    (idx: number) => {
      setSelected((prev) => {
        const next = new Set(prev);
        if (allowMultiple) {
          if (next.has(idx)) next.delete(idx);
          else next.add(idx);
        } else {
          if (next.has(idx)) next.clear();
          else {
            next.clear();
            next.add(idx);
          }
        }
        return next;
      });
    },
    [allowMultiple],
  );

  const buildAnswer = useCallback(() => {
    const parts: string[] = [];
    if (hasOptions) {
      for (const idx of Array.from(selected).sort()) {
        const opt = options![idx];
        parts.push(opt.value || opt.label);
      }
    }
    if (otherText.trim()) {
      parts.push(otherText.trim());
    }
    return parts.join(", ");
  }, [hasOptions, options, selected, otherText]);

  const canSubmit = selected.size > 0 || otherText.trim().length > 0;

  const handleSubmit = useCallback(() => {
    const ans = buildAnswer();
    if (!ans) return;
    onSubmit(ans);
  }, [buildAnswer, onSubmit]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  // Keyboard shortcut: Cmd/Ctrl+Enter to submit
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        handleSubmit();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handleSubmit]);

  return (
    <div className="rounded-xl border border-border/60 bg-card overflow-hidden shadow-sm">
      {/* Header */}
      <div className="px-5 pt-4 pb-3">
        <h4 className="text-[14px] font-bold text-foreground leading-snug">{question}</h4>
      </div>

      {/* Options */}
      {hasOptions && (
        <div className="px-4 pb-2 flex flex-col gap-1">
          {options!.map((opt, idx) => {
            const isSelected = selected.has(idx);
            return (
              <button
                key={idx}
                type="button"
                onClick={() => toggleOption(idx)}
                className={cn(
                  "flex items-start gap-3 w-full text-left rounded-lg px-4 py-3 transition-all border cursor-pointer group",
                  isSelected
                    ? "border-primary/40 bg-primary/5"
                    : "border-transparent hover:bg-muted/50",
                )}
              >
                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-semibold text-foreground leading-snug">
                    {opt.label}
                  </div>
                  {opt.description && (
                    <div className="text-[12px] text-muted-foreground mt-0.5 leading-snug">
                      {opt.description}
                    </div>
                  )}
                </div>

                {/* Indicator: numbered badge (single) or checkbox (multi) */}
                <div className="shrink-0 mt-0.5">
                  {allowMultiple ? (
                    <span
                      className={cn(
                        "flex items-center justify-center size-[18px] rounded border transition-colors",
                        isSelected
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-muted-foreground/30 group-hover:border-muted-foreground/50",
                      )}
                    >
                      {isSelected && <Check className="size-3" strokeWidth={3} />}
                    </span>
                  ) : (
                    <span
                      className={cn(
                        "flex items-center justify-center size-[22px] rounded-md text-[11px] font-bold transition-colors",
                        isSelected
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted/60 text-muted-foreground group-hover:bg-muted",
                      )}
                    >
                      {idx + 1}
                    </span>
                  )}
                </div>
              </button>
            );
          })}

          {/* Other option */}
          <div
            className={cn(
              "flex items-start gap-3 w-full rounded-lg px-4 py-3 transition-all border",
              otherText
                ? "border-primary/40 bg-primary/5"
                : "border-transparent",
            )}
          >
            <div className="flex-1 min-w-0">
              <div className="text-[13px] font-semibold text-foreground leading-snug mb-1.5">
                Other
              </div>
              <input
                ref={otherInputRef}
                type="text"
                placeholder="Type your own answer here"
                value={otherText}
                onChange={(e) => {
                  setOtherText(e.target.value);
                  if (!allowMultiple && e.target.value) {
                    setSelected(new Set());
                  }
                }}
                onKeyDown={handleKeyDown}
                className="w-full bg-muted/40 rounded-md px-3 py-1.5 text-[12px] text-foreground placeholder:text-muted-foreground/40 outline-none focus:ring-1 focus:ring-primary/30 transition-shadow"
              />
            </div>

            <div className="shrink-0 mt-0.5">
              {allowMultiple ? (
                <span
                  className={cn(
                    "flex items-center justify-center size-[18px] rounded border transition-colors",
                    otherText
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-muted-foreground/30",
                  )}
                >
                  {otherText && <Check className="size-3" strokeWidth={3} />}
                </span>
              ) : (
                <span
                  className={cn(
                    "flex items-center justify-center size-[22px] rounded-md text-[11px] font-bold transition-colors",
                    otherText
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted/60 text-muted-foreground",
                  )}
                >
                  {(options?.length ?? 0) + 1}
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between px-5 py-3 border-t border-border/30">
        <div />
        <div className="flex items-center gap-3">
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
              "flex items-center gap-2 px-3 py-1.5 text-[12px] font-medium rounded-md transition-colors",
              canSubmit
                ? "text-foreground/80 hover:text-foreground hover:bg-muted/60 cursor-pointer"
                : "text-muted-foreground/30 cursor-not-allowed",
            )}
          >
            Submit
            <kbd className={cn(
              "text-[10px] font-mono px-1 py-0.5 rounded border transition-colors",
              canSubmit
                ? "border-border/60 text-muted-foreground/60"
                : "border-border/20 text-muted-foreground/20",
            )}>⌘↵</kbd>
          </button>
        </div>
      </div>
    </div>
  );
}
