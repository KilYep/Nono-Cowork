"use client";

import { cn } from "@/lib/utils";
import { useState, useCallback, useRef, useEffect } from "react";
import { Check, ChevronLeft, ChevronRight } from "lucide-react";

interface AskUserOption {
  label: string;
  description?: string;
  value?: string;
}

export interface AskUserQuestion {
  question: string;
  options: AskUserOption[];
  allow_multiple?: boolean;
}

interface AskUserCardProps {
  questions: AskUserQuestion[];
  onSubmit: (answers: string[]) => void;
  onSkip: () => void;
}

interface QuestionState {
  selected: Set<number>;
  otherText: string;
}

function buildAnswer(q: AskUserQuestion, state: QuestionState): string {
  const parts: string[] = [];
  for (const idx of Array.from(state.selected).sort()) {
    const opt = q.options[idx];
    parts.push(opt.value || opt.label);
  }
  if (state.otherText.trim()) {
    parts.push(state.otherText.trim());
  }
  return parts.join(", ");
}

export function AskUserCard({
  questions,
  onSubmit,
  onSkip,
}: AskUserCardProps) {
  const total = questions.length;
  const [page, setPage] = useState(0);
  const [states, setStates] = useState<QuestionState[]>(() =>
    questions.map(() => ({ selected: new Set(), otherText: "" })),
  );
  const otherInputRef = useRef<HTMLInputElement>(null);

  const q = questions[page];
  const st = states[page];
  const isLast = page === total - 1;
  const hasOptions = q.options && q.options.length > 0;

  const updateState = useCallback(
    (updater: (prev: QuestionState) => QuestionState) => {
      setStates((prev) => {
        const next = [...prev];
        next[page] = updater(prev[page]);
        return next;
      });
    },
    [page],
  );

  const toggleOption = useCallback(
    (idx: number) => {
      updateState((prev) => {
        const next = new Set(prev.selected);
        if (q.allow_multiple) {
          if (next.has(idx)) next.delete(idx);
          else next.add(idx);
        } else {
          if (next.has(idx)) next.clear();
          else {
            next.clear();
            next.add(idx);
          }
        }
        return { ...prev, selected: next };
      });
    },
    [q.allow_multiple, updateState],
  );

  const canSubmitPage = st.selected.size > 0 || st.otherText.trim().length > 0;

  const handleNext = useCallback(() => {
    if (!canSubmitPage) return;
    if (isLast) {
      const answers = questions.map((qq, i) => buildAnswer(qq, states[i]));
      onSubmit(answers);
    } else {
      setPage((p) => p + 1);
    }
  }, [canSubmitPage, isLast, questions, states, onSubmit]);

  const handleBack = useCallback(() => {
    if (page > 0) setPage((p) => p - 1);
  }, [page]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleNext();
      }
    },
    [handleNext],
  );

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        handleNext();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handleNext]);

  return (
    <div className="rounded-xl border border-border/60 bg-card overflow-hidden shadow-sm">
      {/* Header */}
      <div className="px-5 pt-4 pb-3 flex items-start justify-between gap-3">
        <h4 className="text-[14px] font-bold text-foreground leading-snug">
          {q.question}
        </h4>
        {total > 1 && (
          <span className="shrink-0 text-[11px] font-medium text-muted-foreground/60 tabular-nums">
            {page + 1}/{total}
          </span>
        )}
      </div>

      {/* Options */}
      {hasOptions && (
        <div className="px-4 pb-2 flex flex-col gap-1">
          {q.options.map((opt, idx) => {
            const isSelected = st.selected.has(idx);
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

                <div className="shrink-0 mt-0.5">
                  {q.allow_multiple ? (
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
              st.otherText
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
                value={st.otherText}
                onChange={(e) => {
                  const val = e.target.value;
                  updateState((prev) => ({
                    ...prev,
                    otherText: val,
                    selected: !q.allow_multiple && val ? new Set() : prev.selected,
                  }));
                }}
                onKeyDown={handleKeyDown}
                className="w-full bg-muted/40 rounded-md px-3 py-1.5 text-[12px] text-foreground placeholder:text-muted-foreground/40 outline-none focus:ring-1 focus:ring-primary/30 transition-shadow"
              />
            </div>

            <div className="shrink-0 mt-0.5">
              {q.allow_multiple ? (
                <span
                  className={cn(
                    "flex items-center justify-center size-[18px] rounded border transition-colors",
                    st.otherText
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-muted-foreground/30",
                  )}
                >
                  {st.otherText && <Check className="size-3" strokeWidth={3} />}
                </span>
              ) : (
                <span
                  className={cn(
                    "flex items-center justify-center size-[22px] rounded-md text-[11px] font-bold transition-colors",
                    st.otherText
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted/60 text-muted-foreground",
                  )}
                >
                  {(q.options?.length ?? 0) + 1}
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between px-5 py-3 border-t border-border/30">
        <div>
          {total > 1 && page > 0 && (
            <button
              type="button"
              onClick={handleBack}
              className="flex items-center gap-1 px-2 py-1.5 text-[12px] font-medium text-muted-foreground hover:text-foreground rounded-md hover:bg-muted/60 transition-colors cursor-pointer"
            >
              <ChevronLeft className="size-3.5" />
              Back
            </button>
          )}
        </div>
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
            onClick={handleNext}
            disabled={!canSubmitPage}
            className={cn(
              "flex items-center gap-1 px-3 py-1.5 text-[12px] font-medium rounded-md transition-colors",
              canSubmitPage
                ? "text-foreground/80 hover:text-foreground hover:bg-muted/60 cursor-pointer"
                : "text-muted-foreground/30 cursor-not-allowed",
            )}
          >
            {isLast ? "Submit" : (
              <>
                Next
                <ChevronRight className="size-3.5" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
