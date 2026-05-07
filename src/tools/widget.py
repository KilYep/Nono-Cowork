"""
widget_show tool — render an interactive HTML widget in the chat UI.

The HTML is injected into a sandboxed iframe via srcdoc. ECharts (and any
other CDN library) can be loaded inside the widget because the iframe has
allow-scripts and allow-same-origin sandbox flags.
"""

from tools.registry import tool

_STYLE_GUIDE = """
WIDGET STYLE GUIDE — follow every rule strictly, no exceptions.

━━ THEME SETUP (paste this snippet at the top of every <script>) ━━
const dk = window.matchMedia('(prefers-color-scheme: dark)').matches;
const T = {
  text:    dk ? '#eef0f5' : '#111827',
  sub:     dk ? '#9ca3af' : '#6b7280',
  grid:    dk ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
  axis:    dk ? 'rgba(255,255,255,0.10)' : 'rgba(0,0,0,0.10)',
  ttBg:    dk ? '#252830' : '#ffffff',
  ttBd:    dk ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)',
};

━━ COLOR PALETTE (use in order, no substitutions) ━━
['#6366f1','#34d399','#fbbf24','#f87171','#a78bfa','#22d3ee']

━━ LAYOUT ━━
- html, body { margin:0; padding:0; height:100%; overflow:hidden; background:transparent; }  ← both height:100% and overflow:hidden are REQUIRED
- Chart div: width:100%; height:100%;  (inherits iframe height this way)
- Never use position:fixed.

━━ ECHARTS BASE CONFIG (apply to every chart) ━━
backgroundColor: 'transparent',
animation: true, animationDuration: 500, animationEasing: 'cubicOut',
textStyle: { fontFamily: 'system-ui, sans-serif', fontSize: 12, color: T.sub },

━━ AXES ━━
axisLine:  { show: false },
axisTick:  { show: false },
splitLine: { lineStyle: { color: T.grid } },
axisLabel: { color: T.sub, fontSize: 11 },

━━ TITLE (only when necessary) ━━
textStyle: { fontSize: 13, fontWeight: 'normal', color: T.text }, left: 'left', top: 12,

━━ LEGEND ━━
icon: 'circle', itemWidth: 7, itemHeight: 7,
textStyle: { color: T.sub, fontSize: 11 }, top: 12,

━━ TOOLTIP ━━
backgroundColor: T.ttBg, borderColor: T.ttBd, borderWidth: 0.5,
textStyle: { color: T.text, fontSize: 12 }, padding: [8,12],

━━ SERIES RULES ━━
Bar:  barMaxWidth:32, borderRadius:[2,2,0,0], no shadow in itemStyle
Line: smooth:true, lineStyle:{width:2}, no areaStyle unless explicitly requested
Pie:  radius:['48%','68%'], labelLine:{show:false} — use legend instead of labels

━━ FORBIDDEN ━━
✗ No gradients (no LinearGradient, no CSS gradient)
✗ No shadows (shadowBlur, shadowColor, box-shadow, text-shadow)
✗ No background on ANY element — html/body/div/card/container must all stay transparent or unset
✗ No border on wrapper divs — no .card, .container, .chart-container, .stat-card style wrappers with background or border
✗ No decorative border-radius on wrapper elements
✗ No emoji
✗ No HTML comments
✗ No axis border lines (axisLine must be hidden)
✗ No area fill on line charts by default
✗ No custom font stacks — only system-ui, sans-serif
✗ Do not use brand colors (e.g. #76b900 for NVIDIA, #0071c5 for Intel) — always use the palette above
"""


@tool(
    name="widget_show",
    description=(
        "Render an interactive ECharts chart or HTML widget in the chat UI via a sandboxed iframe.\n\n"
        "The `html` parameter must be a complete self-contained HTML document. "
        "Load ECharts from: https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js\n\n"
        "Height guidelines: most charts → 380px; dashboards → 500px+.\n\n"
        + _STYLE_GUIDE
    ),
    parameters={
        "type": "object",
        "properties": {
            "html": {
                "type": "string",
                "description": "Complete self-contained HTML document. Must follow the style guide above.",
            },
            "title": {
                "type": "string",
                "description": "Short label for this widget (e.g. 'Monthly Revenue'). Optional.",
            },
            "height": {
                "type": "integer",
                "description": "iframe height in pixels. Default: 380.",
                "default": 380,
            },
        },
        "required": ["html"],
    },
    tags=["read"],
)
def widget_show(html: str, title: str = "", height: int = 380) -> str:
    from channels.desktop import channel
    channel.show_widget(html=html, title=title, height=height)
    return f"Widget rendered."
