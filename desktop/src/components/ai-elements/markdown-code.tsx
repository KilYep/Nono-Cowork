"use client";

import { cn } from "@/lib/utils";
import { CheckIcon, CopyIcon, ExternalLinkIcon, Maximize2Icon, Minimize2Icon, MinusIcon, PlusIcon, XIcon, RotateCcwIcon } from "lucide-react";
import type { AnchorHTMLAttributes, HTMLAttributes, ReactNode } from "react";
import {
  isValidElement,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { TransformWrapper, TransformComponent, useControls } from "react-zoom-pan-pinch";
import type { ReactZoomPanPinchRef } from "react-zoom-pan-pinch";

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

// ─── Typography elements ──────────────────────────────────────────────────────

const H1 = ({ children, ...props }: HTMLAttributes<HTMLHeadingElement>) => (
  <h1 className="mt-6 mb-3 text-xl font-bold text-foreground first:mt-0" {...props}>{children}</h1>
);
const H2 = ({ children, ...props }: HTMLAttributes<HTMLHeadingElement>) => (
  <h2 className="mt-5 mb-2.5 text-lg font-semibold text-foreground first:mt-0" {...props}>{children}</h2>
);
const H3 = ({ children, ...props }: HTMLAttributes<HTMLHeadingElement>) => (
  <h3 className="mt-4 mb-2 text-base font-semibold text-foreground first:mt-0" {...props}>{children}</h3>
);
const H4 = ({ children, ...props }: HTMLAttributes<HTMLHeadingElement>) => (
  <h4 className="mt-3 mb-1.5 text-sm font-semibold text-foreground first:mt-0" {...props}>{children}</h4>
);
const P = ({ children, ...props }: HTMLAttributes<HTMLParagraphElement>) => (
  <p className="my-2.5 leading-7 first:mt-0 last:mb-0" {...props}>{children}</p>
);
const Ul = ({ children, ...props }: HTMLAttributes<HTMLUListElement>) => (
  <ul className="my-2.5 ml-5 list-disc space-y-1" {...props}>{children}</ul>
);
const Ol = ({ children, ...props }: HTMLAttributes<HTMLOListElement>) => (
  <ol className="my-2.5 ml-5 list-decimal space-y-1" {...props}>{children}</ol>
);
const Li = ({ children, ...props }: HTMLAttributes<HTMLLIElement>) => (
  <li className="leading-7" {...props}>{children}</li>
);
const Blockquote = ({ children, ...props }: HTMLAttributes<HTMLQuoteElement>) => (
  <blockquote
    className="my-3 border-l-4 border-border pl-4 italic text-muted-foreground"
    {...props}
  >
    {children}
  </blockquote>
);
const Hr = () => <hr className="my-4 border-border" />;

// ─── Inline code ─────────────────────────────────────────────────────────────

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

// ─── Block code (pre wrapper) ─────────────────────────────────────────────────
// react-markdown calls this for every <pre> element.
// Language is extracted from the child <code> element's className (language-xxx).

const PreRenderer = ({
  children,
  className,
  style: _style,
  ...props
}: HTMLAttributes<HTMLPreElement>) => {
  const language = useMemo(() => {
    if (isValidElement(children)) {
      const codeProps = children.props as { className?: string };
      return /language-(\w+)/.exec(codeProps.className ?? "")?.[1] ?? null;
    }
    return null;
  }, [children]);

  if (language === "mermaid") {
    return <MermaidRenderer code={extractText(children)} />;
  }

  const isMarkdown = language === "markdown" || language === "md";

  const [copied, setCopied] = useState(false);
  const timeoutRef = useRef<number | null>(null);

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
          "font-mono text-[0.82rem] leading-relaxed",
          "whitespace-pre",
          className
        )}
        {...props}
      >
        {children}
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

// ─── Code element ─────────────────────────────────────────────────────────────
// Block code: has data-language (from rehype-pretty-code) or language-xxx class.
//   → Pass through as plain <code>; PreRenderer handles the outer wrapper.
// Inline code: no language markers → render as InlineCode pill.

// Block code inside <pre> always has a language-xxx className from remark.
// Inline code has no className → render as InlineCode pill.
const CodeRenderer = ({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLElement>) => {
  if (/^language-/.test(className ?? "")) {
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  }
  return <InlineCode>{children}</InlineCode>;
};

// ─── Table ────────────────────────────────────────────────────────────────────

const TableRenderer = ({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLTableElement>) => (
  <div className="my-3 overflow-x-auto">
    <table
      className={cn("w-full border-collapse text-sm", className)}
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
  <thead className={cn("border-b border-border/60", className)} {...props}>
    {children}
  </thead>
);

const TableBody = ({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLTableSectionElement>) => (
  <tbody className={cn("divide-y divide-border/40", className)} {...props}>
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
  <td className={cn("px-3 py-2 align-top text-foreground/90", className)} {...props}>
    {children}
  </td>
);

// ─── Link ─────────────────────────────────────────────────────────────────────

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
        "underline decoration-current/30 underline-offset-2",
        "rounded-sm -mx-0.5 px-0.5",
        "transition-all duration-150",
        "hover:bg-blue-500/10 dark:hover:bg-blue-400/10",
        className
      )}
      {...(isExternal ? { target: "_blank", rel: "noopener noreferrer" } : {})}
      {...props}
    >
      {children}
      {isExternal && (
        <ExternalLinkIcon className="inline size-3 shrink-0 opacity-50" />
      )}
    </a>
  );
};

// ─── Streaming math sanitizer ────────────────────────────────────────────────
// During streaming, $$ or $ blocks may arrive without a closing delimiter.
// remark-math then renders raw LaTeX as plain text, flipping to KaTeX once the
// delimiter arrives — causing a visible layout jump.
// Solution: strip any unclosed math block from the tail so the content before
// the formula renders stably until the full formula arrives.

export function sanitizeStreamingMath(content: string): string {
  // 1. Unclosed $$ block (even split-count = odd number of $$)
  const blockParts = content.split("$$");
  if (blockParts.length % 2 === 0) {
    return blockParts.slice(0, -1).join("$$");
  }

  // 2. Unclosed $ inline — strip complete pairs then look for a lone $
  const stripped = content
    .replace(/\$\$[\s\S]*?\$\$/g, "")  // remove complete block pairs
    .replace(/\$[^$\n]+\$/g, "");       // remove complete inline pairs
  if (!stripped.includes("$")) return content;

  // Find the last standalone $ (not part of $$) and trim before it
  for (let i = content.length - 1; i >= 0; i--) {
    if (content[i] !== "$") continue;
    const prev = i > 0 ? content[i - 1] : "";
    const next = i < content.length - 1 ? content[i + 1] : "";
    if (prev === "$" || next === "$") continue;
    return content.slice(0, i);
  }

  return content;
}

// ─── Mermaid renderer ─────────────────────────────────────────────────────────

type MermaidModule = typeof import("mermaid").default;
let mermaidSingleton: Promise<MermaidModule> | null = null;
let mermaidIdSeq = 0;

const getMermaid = (): Promise<MermaidModule> => {
  if (!mermaidSingleton) {
    mermaidSingleton = import("mermaid").then((m) => {
      m.default.initialize({ startOnLoad: false, theme: "neutral", suppressErrors: true });
      return m.default;
    });
  }
  return mermaidSingleton;
};

// Strip hardcoded dimensions from the SVG root so CSS controls the size via viewBox.
// Mermaid sets both width/height attributes AND max-width in the style attribute.
const normalizeSvgSize = (svg: string) =>
  svg
    .replace(/(<svg[^>]*)\swidth="[^"]*"/, "$1")
    .replace(/(<svg[^>]*)\sheight="[^"]*"/, "$1")
    .replace(/max-width:\s*[\d.]+\w+\s*;?\s*/g, "");

// ─── Mermaid skeleton ─────────────────────────────────────────────────────────

const MermaidSkeleton = () => (
  <div className="my-2 animate-pulse rounded-md bg-muted/50 px-3.5 py-5">
    <div className="mx-auto flex w-fit flex-col items-center gap-2">
      <div className="h-8 w-36 rounded-md bg-muted-foreground/15" />
      <div className="h-5 w-0.5 bg-muted-foreground/15" />
      <div className="flex gap-8">
        <div className="h-8 w-24 rounded-md bg-muted-foreground/15" />
        <div className="h-8 w-28 rounded-md bg-muted-foreground/15" />
      </div>
      <div className="flex gap-8">
        <div className="h-5 w-0.5 bg-muted-foreground/15" />
        <div className="h-5 w-0.5 bg-muted-foreground/15" />
      </div>
      <div className="flex gap-8">
        <div className="h-8 w-20 rounded-md bg-muted-foreground/15" />
        <div className="h-8 w-32 rounded-md bg-muted-foreground/15" />
      </div>
    </div>
  </div>
);

// ─── Mermaid toolbar (must be inside TransformWrapper) ────────────────────────

const MermaidToolbar = ({
  onReset,
  onFullscreen,
  onClose,
}: {
  onReset: () => void;
  onFullscreen?: () => void;
  onClose?: () => void;
}) => {
  const { zoomIn, zoomOut } = useControls();
  const btnCls =
    "flex size-6 items-center justify-center rounded text-muted-foreground/60 transition-colors hover:bg-background/80 hover:text-foreground";

  return (
    <div className="flex items-center justify-end gap-0.5 px-2 py-1">
      <button type="button" onClick={() => zoomIn()} className={btnCls} aria-label="放大">
        <PlusIcon className="size-3" />
      </button>
      <button type="button" onClick={() => zoomOut()} className={btnCls} aria-label="缩小">
        <MinusIcon className="size-3" />
      </button>
      <button type="button" onClick={onReset} className={btnCls} aria-label="重置">
        <RotateCcwIcon className="size-3" />
      </button>
      {onFullscreen && (
        <button type="button" onClick={onFullscreen} className={btnCls} aria-label="全屏">
          <Maximize2Icon className="size-3" />
        </button>
      )}
      {onClose && (
        <button type="button" onClick={onClose} className={btnCls} aria-label="关闭">
          <XIcon className="size-3.5" />
        </button>
      )}
    </div>
  );
};

// ─── Shared zoom canvas ───────────────────────────────────────────────────────

const MermaidCanvas = ({
  svg,
  height,
  onFullscreen,
  onClose,
}: {
  svg: string;
  height: string;
  onFullscreen?: () => void;
  onClose?: () => void;
}) => {
  const fitScaleRef = useRef<number>(1);
  const transformRef = useRef<ReactZoomPanPinchRef | null>(null);

  const handleInit = useCallback((ref: ReactZoomPanPinchRef) => {
    transformRef.current = ref;
    const wrapper = ref.instance.wrapperComponent;
    const content = ref.instance.contentComponent;
    if (!wrapper || !content) return;
    const scaleX = wrapper.offsetWidth / content.offsetWidth;
    const scaleY = wrapper.offsetHeight / content.offsetHeight;
    // fit entirely inside the container, never upscale beyond 100%
    fitScaleRef.current = Math.min(scaleX, scaleY, 1);
    ref.centerView(fitScaleRef.current);
  }, []);

  const handleReset = useCallback(() => {
    transformRef.current?.centerView(fitScaleRef.current);
  }, []);

  return (
    <TransformWrapper
      ref={transformRef}
      initialScale={1}
      minScale={0.1}
      maxScale={5}
      onInit={handleInit}
    >
      <div className="group/mermaid-canvas relative flex flex-col overflow-hidden rounded-lg">
        <TransformComponent
          wrapperStyle={{ width: "100%", height }}
          contentStyle={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}
        >
          <div
            className="max-w-2xl p-4 [&_svg]:h-auto [&_svg]:w-full"
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        </TransformComponent>
        {/* toolbar floats over the diagram, only visible on hover */}
        <div className="pointer-events-none absolute inset-x-0 top-0 opacity-0 transition-opacity duration-150 group-hover/mermaid-canvas:opacity-100 group-hover/mermaid-canvas:pointer-events-auto">
          <MermaidToolbar onReset={handleReset} onFullscreen={onFullscreen} onClose={onClose} />
        </div>
      </div>
    </TransformWrapper>
  );
};

// ─── Fullscreen overlay ───────────────────────────────────────────────────────

const MermaidFullscreen = ({ svg, onClose }: { svg: string; onClose: () => void }) => {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return createPortal(
    <div className="fixed inset-0 z-50 flex flex-col bg-background p-4">
      <MermaidCanvas svg={svg} height="calc(100vh - 2rem)" onClose={onClose} />
    </div>,
    document.body
  );
};

// ─── Mermaid renderer ─────────────────────────────────────────────────────────

const MermaidRenderer = ({ code }: { code: string }) => {
  const [svgId] = useState(() => `mermaid-${++mermaidIdSeq}`);
  const [svg, setSvg] = useState<string | null>(null);
  const [fullscreen, setFullscreen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setSvg(null);

    // Debounce: mermaid can't render partial syntax, so wait until the code
    // stops changing (streaming ends) before attempting to render.
    const timer = setTimeout(() => {
      getMermaid()
        .then((m) => m.render(svgId, code.trim()))
        .then(({ svg: rendered }) => {
          if (!cancelled) setSvg(normalizeSvgSize(rendered));
        })
        .catch(() => {
          // mermaid v10+ may inject an error div into the DOM on parse failure — remove it
          document.getElementById(svgId)?.remove();
          document.querySelector(`[id^="${svgId}"]`)?.closest("div")?.remove();
          if (!cancelled) setSvg("");
        });
    }, 400);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [code, svgId]);

  // Still streaming / debouncing — show skeleton placeholder
  if (svg === null) {
    return <MermaidSkeleton />;
  }

  // Render failed — fall back to raw code block
  if (svg === "") {
    return (
      <pre className="overflow-x-auto rounded-md bg-muted/50 px-3.5 py-2.5 font-mono text-[0.82rem] leading-relaxed text-foreground/90 whitespace-pre">
        <code>{code}</code>
      </pre>
    );
  }

  return (
    <>
      <div className="my-2">
        <MermaidCanvas svg={svg} height="460px" onFullscreen={() => setFullscreen(true)} />
      </div>
      {fullscreen && (
        <MermaidFullscreen svg={svg} onClose={() => setFullscreen(false)} />
      )}
    </>
  );
};

// ─── Exports ──────────────────────────────────────────────────────────────────

export const markdownComponents = {
  h1: H1,
  h2: H2,
  h3: H3,
  h4: H4,
  p: P,
  ul: Ul,
  ol: Ol,
  li: Li,
  blockquote: Blockquote,
  hr: Hr,
  a: LinkRenderer,
  pre: PreRenderer,
  code: CodeRenderer,
  table: TableRenderer,
  thead: TableHead,
  tbody: TableBody,
  tr: TableRow,
  th: TableHeaderCell,
  td: TableCell,
};
