"use client";

import { cn } from "@/lib/utils";
import { useState, useCallback, useRef, useEffect } from "react";
import { MessageCircleQuestion, Check, CornerDownLeft } from "lucide-react";

interface AskUserOption {
  label: string;
  value?: string;
}

interface AskUserCardProps {
  question: string;
  options?: AskUserOption[];
  allowMultiple?: boolean;
  answered?: boolean;
  answer?: string;
  onSubmit: (answer: string) => void;
  onSkip: () => void;
}

export function AskUserCard({
  question,
  options,
  allowMultiple = false,
  answered = false,
  answer,
  onSubmit,
  onSkip,
}: AskUserCardProps) {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [otherText, setOtherText] = useState("");
  const [isOtherFocused, setIsOtherFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const freeInputRef = useRef<HTMLInputElement>(null);

  const hasOptions = options && options.length > 0;

  const toggleOption = useCallback(
    (idx: number) => {
      if (answered) return;
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
    [allowMultiple, answered],
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

  const handleSubmit = useCallback(() => {
    if (answered) return;
    const ans = hasOptions ? buildAnswer() : (freeInputRef.current?.value || "").trim();
    if (!ans) return;
    onSubmit(ans);
  }, [answered, hasOptions, buildAnswer, onSubmit]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  // Auto-focus free input when no options
  useEffect(() => {
    if (!hasOptions && !answered && freeInputRef.current) {
      freeInputRef.current.focus();
    }
  }, [hasOptions, answered]);

  if (answered) {
    return (
      <div className="flex items-start gap-2 py-2 px-3 rounded-lg bg-muted/30 border border-border/40">
        <MessageCircleQuestion className="size-4 text-muted-foreground mt-0.5 shrink-0" />
        <div className="flex flex-col gap-0.5 min-w-0">
          <span className="text-[13px] text-muted-foreground">{question}</span>
          <span className="text-[13px] font-medium text-foreground">{answer}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border/60 bg-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border/40 bg-muted/20">
        <MessageCircleQuestion className="size-4 text-primary shrink-0" />
        <h4 className="text-[13px] font-semibold text-foreground flex-1">{question}</h4>
      </div>

      {/* Body */}
      <div className="px-4 py-3 flex flex-col gap-2">
        {hasOptions && (
          <>
            {options!.map((opt, idx) => {
              const isSelected = selected.has(idx);
              return (
                <button
                  key={idx}
                  type="button"
                  onClick={() => toggleOption(idx)}
                  className={cn(
                    "flex items-center gap-3 w-full text-left rounded-md px-3 py-2.5 transition-colors border cursor-pointer",
                    isSelected
                      ? "border-primary/50 bg-primary/8"
                      : "border-border/40 bg-transparent hover:bg-muted/40",
                  )}
                >
                  {/* Radio / Checkbox indicator */}
                  <span
                    className={cn(
                      "shrink-0 flex items-center justify-center transition-colors",
                      allowMultiple
                        ? "size-4 rounded-sm border"
                        : "size-4 rounded-full border",
                      isSelected
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-muted-foreground/40",
                    )}
                  >
                    {isSelected && (
                      allowMultiple
                        ? <Check className="size-3" />
                        : <span className="size-2 rounded-full bg-primary-foreground" />
                    )}
                  </span>
                  <span className="text-[13px] text-foreground">{opt.label}</span>
                </button>
              );
            })}

            {/* Other / free-text row */}
            <div
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 border transition-colors",
                isOtherFocused || otherText
                  ? "border-primary/50 bg-primary/8"
                  : "border-border/40 bg-transparent",
              )}
            >
              <span
                className={cn(
                  "shrink-0 flex items-center justify-center",
                  allowMultiple
                    ? "size-4 rounded-sm border"
                    : "size-4 rounded-full border",
                  otherText
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-muted-foreground/40",
                )}
              >
                {otherText && (
                  allowMultiple
                    ? <Check className="size-3" />
                    : <span className="size-2 rounded-full bg-primary-foreground" />
                )}
              </span>
              <input
                ref={inputRef}
                type="text"
                placeholder="Type your own answer here"
                value={otherText}
                onChange={(e) => setOtherText(e.target.value)}
                onFocus={() => setIsOtherFocused(true)}
                onBlur={() => setIsOtherFocused(false)}
                onKeyDown={handleKeyDown}
                className="flex-1 bg-transparent text-[13px] text-foreground placeholder:text-muted-foreground/50 outline-none"
              />
            </div>
          </>
        )}

        {/* Free-text only (no options) */}
        {!hasOptions && (
          <div className="flex items-center gap-2 rounded-md border border-border/40 px-3 py-2 focus-within:border-primary/50 transition-colors">
            <input
              ref={freeInputRef}
              type="text"
              placeholder="Type your answer..."
              onKeyDown={handleKeyDown}
              className="flex-1 bg-transparent text-[13px] text-foreground placeholder:text-muted-foreground/50 outline-none"
            />
            <button
              type="button"
              onClick={() => {
                const val = freeInputRef.current?.value || "";
                if (val.trim()) onSubmit(val.trim());
              }}
              className="shrink-0 text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
            >
              <CornerDownLeft className="size-4" />
            </button>
          </div>
        )}
      </div>

      {/* Footer */}
      {hasOptions && (
        <div className="flex items-center justify-end gap-2 px-4 py-2.5 border-t border-border/40 bg-muted/10">
          <button
            type="button"
            onClick={onSkip}
            className="px-3 py-1 text-[12px] font-medium text-muted-foreground hover:text-foreground rounded-md hover:bg-muted/60 transition-colors cursor-pointer"
          >
            Skip
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={selected.size === 0 && !otherText.trim()}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1 text-[12px] font-medium rounded-md transition-colors cursor-pointer",
              selected.size > 0 || otherText.trim()
                ? "text-primary hover:bg-primary/10"
                : "text-muted-foreground/40 cursor-not-allowed",
            )}
          >
            Submit
            <kbd className="text-[10px] text-muted-foreground/50 font-mono">Enter</kbd>
          </button>
        </div>
      )}
    </div>
  );
}
