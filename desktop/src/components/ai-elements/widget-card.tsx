import { useEffect, useRef } from "react";

interface WidgetCardProps {
  html: string;
  title?: string;
  height?: number;
}

export function WidgetCard({ html, title, height = 420 }: WidgetCardProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    function onMessage(e: MessageEvent) {
      if (e.data?.type === "widget-resize" && typeof e.data.height === "number") {
        const iframe = iframeRef.current;
        if (iframe) iframe.style.height = `${e.data.height}px`;
      }
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  return (
    <iframe
      ref={iframeRef}
      srcDoc={html}
      sandbox="allow-scripts allow-same-origin"
      style={{ height, border: "none", width: "100%", display: "block" }}
      title={title || "widget"}
    />
  );
}
