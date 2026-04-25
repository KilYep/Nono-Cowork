"""
Dream module — nightly reflection over conversation history.

The agent reviews recent sessions to extract reusable patterns:
  - Skills     → high-frequency tasks the agent struggled with
  - Preferences → user habits and preferences
  - Routines   → periodic behaviors worth scheduling or suggesting

Stage 1 (current): read-only utilities over data/sessions/*.json.
"""
