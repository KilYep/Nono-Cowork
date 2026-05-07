import { useCallback, useEffect, useRef, useState } from "react";

interface WidgetCardProps {
  html: string;
  title?: string;
  height?: number;
}

// Watch the app's .dark class on <html> so widgets re-render on theme switch
function useIsDark() {
  const [isDark, setIsDark] = useState(
    () => document.documentElement.classList.contains("dark")
  );
  useEffect(() => {
    const obs = new MutationObserver(() =>
      setIsDark(document.documentElement.classList.contains("dark"))
    );
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => obs.disconnect();
  }, []);
  return isDark;
}

const BASE_STYLE = `<style>html,body{margin:0;padding:0;height:100%;background:transparent}</style>`;

// Inject app theme as window.__dk__ so widgets use the real theme,
// not prefers-color-scheme (which tracks the OS, not the app toggle).
// Style guide uses: const dk = window.__dk__ ?? window.matchMedia('...').matches;
function injectIntoHead(html: string, isDark: boolean): string {
  const themeScript = `<script>window.__dk__=${isDark};</script>`;
  const injection = BASE_STYLE + themeScript;
  const i = html.indexOf("</head>");
  if (i !== -1) return html.slice(0, i) + injection + html.slice(i);
  const j = html.indexOf("<body");
  if (j !== -1) return html.slice(0, j) + injection + html.slice(j);
  return injection + html;
}

export function WidgetCard({ html, title, height = 380 }: WidgetCardProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [actualHeight, setActualHeight] = useState(height);
  const isDark = useIsDark();

  const handleLoad = useCallback(() => {
    const iframe = iframeRef.current;
    if (!iframe?.contentDocument) return;
    const contentHeight = iframe.contentDocument.documentElement.scrollHeight;
    if (contentHeight > 0) setActualHeight(contentHeight);
  }, []);

  useEffect(() => {
    function onMessage(e: MessageEvent) {
      if (e.data?.type === "widget-resize" && typeof e.data.height === "number") {
        setActualHeight(e.data.height);
      }
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  return (
    <iframe
      ref={iframeRef}
      srcDoc={injectIntoHead(html, isDark)}
      sandbox="allow-scripts allow-same-origin"
      onLoad={handleLoad}
      style={{ height: actualHeight, border: "none", width: "100%", display: "block" }}
      title={title || "widget"}
    />
  );
}
