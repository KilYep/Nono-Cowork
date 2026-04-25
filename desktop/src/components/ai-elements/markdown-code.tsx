"use client";

import { cn } from "@/lib/utils";
import { CheckIcon, CopyIcon, ExternalLinkIcon } from "lucide-react";
import type { AnchorHTMLAttributes, HTMLAttributes, ReactNode } from "react";
import {
  isValidElement,
  useCallback,
  useMemo,
  useRef,
  useState,
} from "react";

const extractText = (node: ReactNode): string => {
  if (node == null || node === false) return "";
  if (typeof node === "string") return node;
  if (typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (isValidElement(node)) {
    const props = node.props as { children?: ReactNode };
    return extractText(props.children);
  }
  return "";
};

type CodeRendererProps = HTMLAttributes<HTMLElement> & {
  "data-block"?: string;
};

const InlineCode = ({ className, children, ...props }: HTMLAttributes<HTMLElement>) => (
  <code
    className={cn(
      "rounded bg-muted/70 px-[0.35em] py-[0.12em] font-mono text-[0.88em] text-foreground/90",
      className
    )}
    {...props}
  >
    {children}
  </code>
);

const BlockCode = ({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) => {
  const [copied, setCopied] = useState(false);
  const timeoutRef = useRef<number | null>(null);

  const match = /language-([\w-]+)/.exec(className ?? "");
  const language = match?.[1] ?? null;
  const isMarkdown = language === "markdown" || language === "md";

  const rawCode = useMemo(() => extractText(children), [children]);

  const handleCopy = useCallback(() => {
    if (!navigator?.clipboard) return;
    navigator.clipboard
      .writeText(rawCode)
      .then(() => {
        setCopied(true);
        if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
        timeoutRef.current = window.setTimeout(() => setCopied(false), 1500);
      })
      .catch(() => {});
  }, [rawCode]);

  const Icon = copied ? CheckIcon : CopyIcon;

  return (
    <div className="group/code relative my-2">
      <pre
        className={cn(
          "overflow-x-auto rounded-md bg-muted/50 px-3.5 py-2.5",
          "font-mono text-[0.82rem] leading-relaxed text-foreground/90",
          "whitespace-pre"
        )}
      >
        <code className="block">{children}</code>
      </pre>
      <div className="absolute right-1.5 top-1.5 flex items-center gap-1.5 opacity-0 transition-opacity group-hover/code:opacity-100">
        {language && !isMarkdown ? (
          <span className="select-none font-mono text-[10px] uppercase tracking-wider text-muted-foreground/50">
            {language}
          </span>
        ) : null}
        <button
          type="button"
          onClick={handleCopy}
          className="flex size-6 items-center justify-center rounded text-muted-foreground/70 transition-colors hover:bg-background hover:text-foreground"
          aria-label={copied ? "Copied" : "Copy code"}
        >
          <Icon className="size-3.5" />
        </button>
      </div>
    </div>
  );
};

// Streamdown marks block code elements with `data-block="true"` via its pre
// renderer. We use that flag to pick inline-pill vs. flat-block rendering.
const CodeRenderer = ({
  className,
  children,
  "data-block": dataBlock,
  ...props
}: CodeRendererProps) => {
  if (dataBlock == null) {
    return (
      <InlineCode className={className} {...props}>
        {children}
      </InlineCode>
    );
  }
  return <BlockCode className={className}>{children}</BlockCode>;
};

// Flat table — replaces Streamdown's nested bg-sidebar + bg-background card.
const TableRenderer = ({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLTableElement>) => (
  <div className="my-3 overflow-x-auto">
    <table
      className={cn(
        "w-full border-collapse text-sm",
        className
      )}
      {...props}
    >
      {children}
    </table>
  </div>
);

const TableHead = ({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLTableSectionElement>) => (
  <thead
    className={cn("border-b border-border/60", className)}
    {...props}
  >
    {children}
  </thead>
);

const TableBody = ({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLTableSectionElement>) => (
  <tbody
    className={cn("divide-y divide-border/40", className)}
    {...props}
  >
    {children}
  </tbody>
);

const TableRow = ({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLTableRowElement>) => (
  <tr className={cn(className)} {...props}>
    {children}
  </tr>
);

const TableHeaderCell = ({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLTableCellElement>) => (
  <th
    className={cn(
      "whitespace-nowrap px-3 py-2 text-left align-top font-medium text-muted-foreground",
      className
    )}
    {...props}
  >
    {children}
  </th>
);

const TableCell = ({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLTableCellElement>) => (
  <td
    className={cn("px-3 py-2 align-top text-foreground/90", className)}
    {...props}
  >
    {children}
  </td>
);

const LinkRenderer = ({
  className,
  children,
  href,
  ...props
}: AnchorHTMLAttributes<HTMLAnchorElement>) => {
  const isExternal = href?.startsWith("http") || href?.startsWith("//");

  return (
    <a
      href={href}
      className={cn(
        "inline-flex items-center gap-0.5 cursor-pointer",
        "text-blue-500 dark:text-blue-400",
        "underline decoration-blue-500/30 dark:decoration-blue-400/30 underline-offset-2",
        "rounded-sm -mx-0.5 px-0.5",
        "transition-all duration-150",
        "hover:text-blue-600 dark:hover:text-blue-300",
        "hover:decoration-blue-500/70 dark:hover:decoration-blue-300/70",
        "hover:bg-blue-500/10 dark:hover:bg-blue-400/10",
        className
      )}
      {...(isExternal
        ? { target: "_blank", rel: "noopener noreferrer" }
        : {})}
      {...props}
    >
      {children}
      {isExternal && (
        <ExternalLinkIcon className="inline size-3 shrink-0 opacity-50" />
      )}
    </a>
  );
};

export const markdownComponents = {
  a: LinkRenderer,
  code: CodeRenderer,
  table: TableRenderer,
  thead: TableHead,
  tbody: TableBody,
  tr: TableRow,
  th: TableHeaderCell,
  td: TableCell,
};
