"""
Workspace manager — groups sessions by their associated sync folder.

Design (see develop_docs/workspace_as_project_plan.md for full context):
  - 1 workspace = 1 Syncthing folder (V1 simplification)
  - Sessions belong to exactly one workspace for their lifetime
  - Agent's _resolve_workspace() reads from the current session's workspace
  - Sidebar groups sessions by workspace

Persistence:
  data/workspaces.json     — single JSON file with a list of workspace records

A workspace record:
  {
    "id":          "ws_<hex>",       # stable identity independent of folder id
    "label":       "My Projects",    # user-facing, editable
    "folder_id":   "nono-2e7ad66a",  # Syncthing folder id (1:1 in V1)
    "is_default":  false,            # the safety-net workspace (cannot be deleted)
    "created_at":  1776525471.0,
    "last_active": 1776529000.0,
  }
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import threading
import time
from typing import Iterable

from config import SESSIONS_DIR

logger = logging.getLogger("workspace")


# ─── Paths ──────────────────────────────────────────────────────

# data/workspaces.json sits next to data/sessions/
_DATA_DIR = os.path.dirname(SESSIONS_DIR)
WORKSPACES_FILE = os.path.join(_DATA_DIR, "workspaces.json")


# ─── Helpers ────────────────────────────────────────────────────

def _new_workspace_id() -> str:
    return "ws_" + secrets.token_hex(4)


def _safe_label_from_folder(folder: dict) -> str:
    """Derive a human label from a Syncthing folder config."""
    label = (folder.get("label") or "").strip()
    if label:
        return label
    # Fall back to basename of path
    path = folder.get("path") or ""
    base = os.path.basename(path.rstrip("/\\"))
    return base or folder.get("id") or "Workspace"


# ─── Manager ────────────────────────────────────────────────────

class WorkspaceManager:
    """Thread-safe workspace registry persisted to data/workspaces.json."""

    def __init__(self):
        self._lock = threading.RLock()
        self._workspaces: list[dict] = []
        self._loaded = False

    # ── Disk I/O ──

    # Bump this any time we change the shape or semantics of the stored
    # workspace records. `_load` compares it to the on-disk value and
    # applies one-off migrations when it's lower.
    CURRENT_SCHEMA_VERSION = 2

    def _load(self) -> None:
        if self._loaded:
            return
        on_disk_version = 0
        try:
            if os.path.exists(WORKSPACES_FILE):
                with open(WORKSPACES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._workspaces = list(data.get("workspaces", []))
                on_disk_version = int(data.get("schema_version", 1))
                logger.info(
                    "Loaded %d workspace(s) from %s (schema_version=%d)",
                    len(self._workspaces), WORKSPACES_FILE, on_disk_version,
                )
            else:
                self._workspaces = []
                logger.info("No workspaces.json yet (fresh install)")
        except Exception as e:
            logger.error("Failed to load workspaces.json: %s", e)
            self._workspaces = []

        # One-shot migrations. Do them before declaring "loaded" so any
        # derived state is consistent.
        if self._workspaces and on_disk_version < 2:
            # v1 → v2: bootstrap used to auto-promote the first Syncthing
            # folder to `is_default=True`. That conflates "first folder I
            # ever synced" with "safety-net default workspace", and lets
            # users lose their delete button on a workspace they never
            # asked to be permanent. Demote every existing default so the
            # user goes through onboarding again and picks/creates a real
            # default.
            demoted = 0
            for w in self._workspaces:
                if w.get("is_default"):
                    w["is_default"] = False
                    demoted += 1
            if demoted:
                logger.info(
                    "Migration v1→v2: demoted %d auto-promoted default "
                    "workspace(s); user will be prompted to set a real default",
                    demoted,
                )
            self._save_unlocked()
        elif not self._workspaces and on_disk_version < 2:
            # Empty file — just stamp the new version so we don't keep
            # re-running this migration.
            self._save_unlocked()

        self._loaded = True

    def _save_unlocked(self) -> None:
        """Persist to disk. Caller must hold the lock."""
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
            tmp_path = WORKSPACES_FILE + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "schema_version": self.CURRENT_SCHEMA_VERSION,
                        "workspaces": self._workspaces,
                    },
                    f, ensure_ascii=False, indent=2,
                )
            os.replace(tmp_path, WORKSPACES_FILE)
        except Exception as e:
            logger.error("Failed to save workspaces.json: %s", e)

    # ── Queries ──

    def list(self) -> list[dict]:
        with self._lock:
            self._load()
            # Sort: default first, then by last_active desc
            return sorted(
                (dict(w) for w in self._workspaces),
                key=lambda w: (not w.get("is_default", False), -w.get("last_active", 0)),
            )

    def get(self, workspace_id: str) -> dict | None:
        with self._lock:
            self._load()
            for w in self._workspaces:
                if w["id"] == workspace_id:
                    return dict(w)
            return None

    def get_by_folder(self, folder_id: str) -> dict | None:
        with self._lock:
            self._load()
            for w in self._workspaces:
                if w.get("folder_id") == folder_id:
                    return dict(w)
            return None

    def get_default(self) -> dict | None:
        """Return the workspace explicitly marked `is_default=True`, or None.

        Note: this is a STRICT lookup. Callers that just need "some
        workspace to fall back to" (e.g. to anchor an orphan session)
        should use `get_any_fallback()` instead — that one will pick a
        non-default workspace when no real default has been set.
        """
        with self._lock:
            self._load()
            for w in self._workspaces:
                if w.get("is_default"):
                    return dict(w)
            return None

    def get_any_fallback(self) -> dict | None:
        """Return a workspace suitable as a soft internal fallback.

        Prefers the real default; otherwise picks the most-recently-active
        workspace so orphan sessions don't crash during agent resolution.
        This is intentionally separate from `get_default()` — the UI only
        shows the "default" badge (and hides the delete button) for the
        actual default.
        """
        with self._lock:
            self._load()
            for w in self._workspaces:
                if w.get("is_default"):
                    return dict(w)
            if not self._workspaces:
                return None
            ordered = sorted(
                self._workspaces,
                key=lambda w: -w.get("last_active", 0),
            )
            return dict(ordered[0])

    # ── Mutations ──

    def create(
        self,
        label: str,
        folder_id: str,
        is_default: bool = False,
    ) -> dict:
        """Create a workspace bound to a Syncthing folder.

        If a workspace for this folder_id already exists, it is returned
        (idempotent for bootstrap).
        """
        with self._lock:
            self._load()
            # Idempotent by folder_id
            for w in self._workspaces:
                if w.get("folder_id") == folder_id:
                    return dict(w)

            now = time.time()
            workspace = {
                "id": _new_workspace_id(),
                "label": label or "Workspace",
                "folder_id": folder_id,
                "is_default": bool(is_default),
                "created_at": now,
                "last_active": now,
            }
            # Only one default allowed
            if is_default:
                for w in self._workspaces:
                    w["is_default"] = False
            self._workspaces.append(workspace)
            self._save_unlocked()
            logger.info(
                "Created workspace %s (label=%s folder=%s default=%s)",
                workspace["id"], workspace["label"],
                workspace["folder_id"], workspace["is_default"],
            )
            return dict(workspace)

    def update(self, workspace_id: str, **fields) -> dict | None:
        """Update editable fields (label, last_active, is_default)."""
        ALLOWED = {"label", "last_active", "is_default"}
        with self._lock:
            self._load()
            for w in self._workspaces:
                if w["id"] == workspace_id:
                    for k, v in fields.items():
                        if k in ALLOWED:
                            w[k] = v
                    # Uniqueness of is_default
                    if fields.get("is_default"):
                        for other in self._workspaces:
                            if other["id"] != workspace_id:
                                other["is_default"] = False
                    self._save_unlocked()
                    return dict(w)
            return None

    def touch(self, workspace_id: str) -> None:
        """Update last_active timestamp (cheap, no disk flush throttling)."""
        with self._lock:
            self._load()
            for w in self._workspaces:
                if w["id"] == workspace_id:
                    w["last_active"] = time.time()
                    self._save_unlocked()
                    return

    def delete(self, workspace_id: str) -> tuple[bool, str]:
        """Delete a workspace.

        Refuses to delete the default workspace (safety net).
        Returns (success, message).
        """
        with self._lock:
            self._load()
            target = None
            for w in self._workspaces:
                if w["id"] == workspace_id:
                    target = w
                    break
            if target is None:
                return False, "workspace not found"
            if target.get("is_default"):
                return False, "cannot delete the default workspace"
            self._workspaces = [
                w for w in self._workspaces if w["id"] != workspace_id
            ]
            self._save_unlocked()
            logger.info("Deleted workspace %s", workspace_id)
            return True, "deleted"

    # ── Bootstrap (one-time per install) ──

    def bootstrap_from_syncthing(self) -> list[dict]:
        """Ensure every Syncthing folder has a corresponding workspace.

        Called at service startup. Idempotent — existing workspaces are
        left alone; only new folders get wrapped.

        Returns the full list after bootstrap.
        """
        with self._lock:
            self._load()

        try:
            from tools.syncthing import SyncthingClient
            st = SyncthingClient()
            folders = st.get_folders()
        except Exception as e:
            logger.info("Syncthing not reachable at bootstrap: %s", e)
            return self.list()

        with self._lock:
            existing_folder_ids = {
                w.get("folder_id") for w in self._workspaces if w.get("folder_id")
            }
            created_any = False
            for f in folders:
                fid = f.get("id")
                if not fid or fid in existing_folder_ids:
                    continue
                label = _safe_label_from_folder(f)
                now = time.time()
                workspace = {
                    "id": _new_workspace_id(),
                    "label": label,
                    "folder_id": fid,
                    # IMPORTANT: never auto-promote a bootstrapped folder
                    # to default. "Default" is a deliberate, user-chosen
                    # safety-net workspace; we must not steal that status
                    # from whichever folder happens to be first in the
                    # Syncthing config.
                    "is_default": False,
                    "created_at": now,
                    "last_active": now,
                }
                self._workspaces.append(workspace)
                created_any = True
                logger.info(
                    "Bootstrapped workspace %s for existing folder %s",
                    workspace["id"], fid,
                )

            if created_any:
                self._save_unlocked()

            return sorted(
                (dict(w) for w in self._workspaces),
                key=lambda w: (
                    not w.get("is_default", False),
                    -w.get("last_active", 0),
                ),
            )

    # ── Session backfill ──

    def resolve_session_workspace(
        self, workspace_id: str | None,
    ) -> dict | None:
        """Given a possibly-missing session.workspace_id, return the effective workspace.

        - If workspace_id matches an existing workspace → return it
        - Otherwise fall back to the soft "any workspace" fallback
          (default if set, else most-recently-active)
        - If no workspaces exist at all → return None

        This is the data-layer resolver. The UI-level strict default
        check (used to decide whether to show the delete button, open
        onboarding, etc.) should use `get_default()` directly.
        """
        if workspace_id:
            w = self.get(workspace_id)
            if w:
                return w
        return self.get_any_fallback()


# Global singleton
workspaces = WorkspaceManager()


# ─── Convenience wrappers ───────────────────────────────────────

def resolve_folder_path_for_session(session: dict | None) -> str | None:
    """Return the absolute folder path for a session's workspace, or None.

    Used by prompt / sync tools to scope operations to the session's folder.
    """
    if not session:
        return None
    ws = workspaces.resolve_session_workspace(session.get("workspace_id"))
    if not ws:
        return None
    folder_id = ws.get("folder_id")
    if not folder_id:
        return None
    try:
        from tools.syncthing import SyncthingClient
        st = SyncthingClient()
        for f in st.get_folders():
            if f.get("id") == folder_id:
                return f.get("path")
    except Exception:
        pass
    return None


def resolve_folder_id_for_session(session: dict | None) -> str | None:
    """Return the Syncthing folder_id for a session's workspace, or None."""
    if not session:
        return None
    ws = workspaces.resolve_session_workspace(session.get("workspace_id"))
    if not ws:
        return None
    return ws.get("folder_id")


def all_folder_ids() -> set[str]:
    """Set of folder_ids currently bound to workspaces."""
    return {
        w.get("folder_id") for w in workspaces.list()
        if w.get("folder_id")
    }
