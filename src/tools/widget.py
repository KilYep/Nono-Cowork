"""
widget_show tool — render an interactive HTML widget in the chat UI.

The HTML is injected into a sandboxed iframe via srcdoc. ECharts (and any
other CDN library) can be loaded inside the widget because the iframe has
allow-scripts and allow-same-origin sandbox flags.
"""

from tools.registry import tool


@tool(
    name="widget_show",
    description=(
        "Render an interactive HTML widget in the chat UI using a sandboxed iframe. "
        "Use this to display charts, diagrams, tables, or any rich visual content. "
        "ECharts is the preferred charting library — load it from CDN: "
        "https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js\n\n"
        "The `html` parameter must be a complete, self-contained HTML document "
        "(including <!DOCTYPE html>, <head>, and <body>). All scripts and styles "
        "must be inline or loaded from CDN — no relative paths.\n\n"
        "Height guidelines: charts/graphs → 400px; tables → auto; dashboards → 500px+. "
        "Set the body/chart container height explicitly in CSS.\n\n"
        "Best practices:\n"
        "- Set body margin:0 and background transparent or matching the app theme\n"
        "- Use ECharts responsive: chart.resize() on window resize\n"
        "- For dark-mode compatibility, use CSS var(--foreground) / var(--background) "
        "or explicit neutral colors (e.g. #e5e7eb for dark backgrounds)"
    ),
    parameters={
        "type": "object",
        "properties": {
            "html": {
                "type": "string",
                "description": "Complete self-contained HTML document to render in the iframe.",
            },
            "title": {
                "type": "string",
                "description": "Short human-readable title shown above the widget (e.g. 'Monthly Revenue Chart'). Optional.",
            },
            "height": {
                "type": "integer",
                "description": "iframe height in pixels. Default: 420. Increase for tall dashboards.",
                "default": 420,
            },
        },
        "required": ["html"],
    },
    tags=["read"],
)
def widget_show(html: str, title: str = "", height: int = 420) -> str:
    from channels.desktop import channel
    channel.show_widget(html=html, title=title, height=height)
    return f"Widget '{title or 'chart'}' rendered successfully."
