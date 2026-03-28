import { Plus, PanelLeftClose, Settings, MessageSquare } from "lucide-react";

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  onNewChat: () => void;
}

export function Sidebar({ isOpen, onToggle, onNewChat }: SidebarProps) {
  return (
    <aside
      className={`flex flex-col h-full bg-sidebar text-sidebar-foreground shrink-0 border-r overflow-hidden transition-[width] duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] ${
        isOpen ? "w-[260px] border-sidebar-border" : "w-0 border-transparent"
      }`}
    >
      <div className="flex flex-col h-full min-w-[260px]">
        {/* Drag area + header */}
        <div
          className="flex items-center justify-between px-3 h-11 shrink-0"
          style={{ WebkitAppRegion: "drag" } as React.CSSProperties}
        >
          <span className="text-[13px] font-medium text-sidebar-foreground/60">
            Nono CoWork
          </span>
          <button
            onClick={onToggle}
            className="p-1.5 rounded-md hover:bg-sidebar-accent text-sidebar-foreground/40 hover:text-sidebar-foreground/70 transition-colors"
            style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}
            aria-label="Close sidebar"
          >
            <PanelLeftClose size={16} />
          </button>
        </div>

        {/* New Chat button */}
        <div className="px-3 py-1">
          <button
            onClick={onNewChat}
            className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-[13px] text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground transition-colors"
            style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}
          >
            <Plus size={16} strokeWidth={1.5} />
            <span>New Chat</span>
          </button>
        </div>

        {/* Conversation list */}
        <div className="flex-1 overflow-y-auto px-2 py-2">
          <div className="flex flex-col items-center justify-center h-full text-sidebar-foreground/25 gap-2">
            <MessageSquare size={28} strokeWidth={1.2} />
            <p className="text-xs">No conversations yet</p>
          </div>
        </div>

        {/* Footer */}
        <div className="px-3 py-3 border-t border-sidebar-border">
          <button className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-[13px] text-sidebar-foreground/40 hover:bg-sidebar-accent hover:text-sidebar-foreground/70 transition-colors">
            <Settings size={15} strokeWidth={1.5} />
            <span>Settings</span>
          </button>
        </div>
      </div>
    </aside>
  );
}
