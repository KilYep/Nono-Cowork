"""Syncthing REST API lightweight client + Agent tool functions"""

import os
import json
import time
import requests
from tools.registry import tool


class SyncthingClient:
    """Lightweight Syncthing REST API client, wrapping only the functionality needed by Agent."""

    def __init__(self, url=None, api_key=None):
        self.url = (url or os.getenv("SYNCTHING_URL", "http://localhost:8384")).rstrip("/")
        self.api_key = api_key or os.getenv("SYNCTHING_API_KEY", "")
        self.headers = {"X-API-Key": self.api_key} if self.api_key else {}

    def _get(self, path, **params):
        r = requests.get(f"{self.url}{path}", headers=self.headers, params=params, timeout=10)
        r.raise_for_status()
        return r.json()

    def _post(self, path, **params):
        r = requests.post(f"{self.url}{path}", headers=self.headers, params=params, timeout=10)
        r.raise_for_status()
        return r.json() if r.content else {}

    def _post_json(self, path, data, **params):
        """POST with a JSON body."""
        r = requests.post(
            f"{self.url}{path}", headers={**self.headers, "Content-Type": "application/json"},
            params=params, data=json.dumps(data), timeout=10,
        )
        r.raise_for_status()
        return r.json() if r.content else {}

    def _patch(self, path, data):
        """PATCH with a JSON body (for config updates)."""
        r = requests.patch(
            f"{self.url}{path}", headers={**self.headers, "Content-Type": "application/json"},
            data=json.dumps(data), timeout=10,
        )
        r.raise_for_status()
        return r.json() if r.content else {}

    def get_system_status(self):
        return self._get("/rest/system/status")

    def get_connections(self):
        return self._get("/rest/system/connections")

    def get_folders(self):
        return self._get("/rest/config/folders")

    def get_folder_status(self, folder_id):
        return self._get("/rest/db/status", folder=folder_id)

    def scan(self, folder_id, sub_path=None):
        params = {"folder": folder_id}
        if sub_path:
            params["sub"] = sub_path
        return self._post("/rest/db/scan", **params)

    def is_idle(self, folder_id):
        status = self.get_folder_status(folder_id)
        return status.get("state") == "idle"

    def wait_for_sync(self, folder_id, timeout=30):
        start = time.time()
        while time.time() - start < timeout:
            if self.is_idle(folder_id):
                return True
            time.sleep(1)
        return False

    # ——— Versioning ———

    def get_versions(self, folder_id):
        """List archived file versions that can be restored."""
        return self._get("/rest/folder/versions", folder=folder_id)

    def restore_versions(self, folder_id, file_version_map: dict):
        """Restore files to archived versions.

        Args:
            folder_id: Folder ID
            file_version_map: {"path/to/file": "2024-01-01T12:00:00+08:00", ...}
        """
        return self._post_json("/rest/folder/versions", file_version_map, folder=folder_id)

    # ——— Pause / Resume ———

    def pause_folder(self, folder_id):
        """Pause syncing for a folder."""
        return self._patch(f"/rest/config/folders/{folder_id}", {"paused": True})

    def resume_folder(self, folder_id):
        """Resume syncing for a folder."""
        return self._patch(f"/rest/config/folders/{folder_id}", {"paused": False})

    # ——— Error checking ———

    def get_folder_errors(self, folder_id):
        """Get sync errors for a folder."""
        return self._get("/rest/folder/errors", folder=folder_id)

    # ——— Auto-setup ———

    def ensure_versioning(self, max_age_days: int = 180):
        """Auto-enable Staggered File Versioning on all folders that don't have it.

        This is idempotent — if versioning is already configured, it skips that folder.
        Called automatically on first client init so the user never needs to configure it manually.
        """
        try:
            folders = self.get_folders()
            for f in folders:
                fid = f["id"]
                current = f.get("versioning", {}).get("type", "")
                if current:
                    continue  # Already has versioning, don't touch it

                self._patch(f"/rest/config/folders/{fid}", {
                    "versioning": {
                        "type": "staggered",
                        "params": {
                            "maxAge": str(max_age_days * 86400),  # Convert days to seconds
                            "cleanInterval": "3600",
                        },
                    }
                })
                print(f"  📦 Auto-enabled file versioning for folder '{f.get('label', fid)}'")
        except Exception:
            pass  # Non-critical — don't break agent startup if Syncthing is unreachable


# ————— Singleton client —————
_client = None
_initialized = False

def _get_client():
    global _client, _initialized
    if _client is None:
        _client = SyncthingClient()
    if not _initialized:
        _initialized = True
        _client.ensure_versioning()
    return _client


# ————— Agent tool functions —————

@tool(
    name="sync_status",
    description="Check Syncthing synchronization status. Displays all synced folder paths, their sync status, and whether the user's device is online. Call this before operating on synced folders to confirm synchronization is healthy.",
    parameters={
        "type": "object",
        "properties": {},
    },
)
def sync_status() -> str:
    """Check Syncthing sync status.

    Displays synced folder list, paths, sync state, and whether the user's device is online.
    Call this before operating on synced folders to confirm sync is healthy.
    """
    try:
        st = _get_client()

        # Connection status
        conns = st.get_connections().get("connections", {})
        online_devices = []
        for dev_id, info in conns.items():
            if info.get("connected"):
                name = info.get("clientVersion", "unknown")
                online_devices.append(f"  🟢 {dev_id[:12]}... ({name})")
            else:
                online_devices.append(f"  🔴 {dev_id[:12]}... (offline)")

        # Folder list
        folders = st.get_folders()
        folder_lines = []
        for f in folders:
            fid = f["id"]
            try:
                status = st.get_folder_status(fid)
                state = status.get("state", "unknown")
                local_files = status.get("localFiles", 0)
                global_files = status.get("globalFiles", 0)
                paused = f.get("paused", False)
                versioning = f.get("versioning", {}).get("type", "none")
                pause_tag = " ⏸️ PAUSED" if paused else ""
                folder_lines.append(
                    f"  📁 {f.get('label', fid)} (ID: {fid}){pause_tag}\n"
                    f"     Path: {f['path']}\n"
                    f"     State: {state} | Files: {local_files}/{global_files}\n"
                    f"     Versioning: {versioning}"
                )
            except Exception:
                folder_lines.append(f"  📁 {f.get('label', fid)} (ID: {fid}) - failed to get status")

        result = "📡 Syncthing Sync Status\n\n"
        result += "Device connections:\n" + ("\n".join(online_devices) if online_devices else "  (no remote devices)") + "\n\n"
        result += "Synced folders:\n" + "\n".join(folder_lines)
        return result

    except requests.ConnectionError:
        return "❌ Cannot connect to Syncthing (http://localhost:8384). Is the Syncthing service running?"
    except Exception as e:
        return f"❌ Failed to get sync status: {e}"


@tool(
    name="sync_wait",
    description="Wait for file synchronization to complete. Call this after modifying files in a synced folder to ensure changes have been synced to the user's local machine.",
    parameters={
        "type": "object",
        "properties": {
            "folder_id": {
                "type": "string",
                "description": "Synced folder ID, obtainable via sync_status(). Default is 'default'.",
                "default": "default",
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum number of seconds to wait. Default is 30.",
                "default": 30,
            },
        },
    },
)
def sync_wait(folder_id: str = "default", timeout: int = 30) -> str:
    """Wait for a folder to finish syncing.

    Call this after modifying files in a synced folder to ensure changes
    have been transferred to the user's local machine.

    Args:
        folder_id: Synced folder ID, default "default". Use sync_status() to see all folder IDs.
        timeout: Maximum seconds to wait, default 30
    """
    try:
        st = _get_client()

        # Trigger a scan first to speed up change detection
        try:
            st.scan(folder_id)
        except Exception:
            pass

        if st.wait_for_sync(folder_id, timeout):
            status = st.get_folder_status(folder_id)
            return (
                f"✅ Folder '{folder_id}' sync complete\n"
                f"  Local files: {status.get('localFiles', '?')}\n"
                f"  Global files: {status.get('globalFiles', '?')}"
            )
        else:
            return f"⏳ Folder '{folder_id}' still syncing after {timeout}s. It may have large changes, please check again later."

    except requests.ConnectionError:
        return "❌ Cannot connect to Syncthing. Is the service running?"
    except Exception as e:
        return f"❌ Failed to wait for sync: {e}"


@tool(
    name="sync_versions",
    description="List recoverable file versions in a synced folder. Syncthing keeps old versions when files are modified or deleted (if versioning is enabled). Use this to find files that can be restored.",
    parameters={
        "type": "object",
        "properties": {
            "folder_id": {
                "type": "string",
                "description": "Synced folder ID. Default is 'default'.",
                "default": "default",
            },
        },
    },
)
def sync_versions(folder_id: str = "default") -> str:
    """List archived file versions that can be restored."""
    try:
        st = _get_client()
        versions = st.get_versions(folder_id)

        if not versions:
            return (
                "📂 No archived versions found.\n\n"
                "This could mean:\n"
                "  - File versioning is not enabled (enable it in Syncthing Web UI → Folder → Edit → File Versioning)\n"
                "  - No files have been modified/deleted by remote devices yet"
            )

        result = f"📂 Archived versions in folder '{folder_id}':\n\n"
        for filepath, version_list in versions.items():
            result += f"  📄 {filepath}\n"
            for v in version_list:
                vtime = v.get("versionTime", "?")
                mod_time = v.get("modTime", "?")
                size = v.get("size", 0)
                size_str = f"{size / 1024:.1f}KB" if size >= 1024 else f"{size}B"
                result += f"     ⏱️ {vtime} (last modified: {mod_time}, size: {size_str})\n"

        result += (
            f"\nTo restore a file, use sync_restore(folder_id=\"{folder_id}\", "
            f"file_path=\"<path>\", version_time=\"<timestamp>\")"
        )
        return result

    except requests.ConnectionError:
        return "❌ Cannot connect to Syncthing. Is the service running?"
    except Exception as e:
        return f"❌ Failed to list versions: {e}"


@tool(
    name="sync_restore",
    description="Restore a file to a previous version. Use sync_versions() first to see available versions and their timestamps.",
    parameters={
        "type": "object",
        "properties": {
            "folder_id": {
                "type": "string",
                "description": "Synced folder ID.",
            },
            "file_path": {
                "type": "string",
                "description": "Relative path of the file to restore (as shown in sync_versions output).",
            },
            "version_time": {
                "type": "string",
                "description": "Timestamp of the version to restore (as shown in sync_versions output, e.g. '2024-01-15T10:30:00+08:00').",
            },
        },
        "required": ["folder_id", "file_path", "version_time"],
    },
)
def sync_restore(folder_id: str, file_path: str, version_time: str) -> str:
    """Restore a file to a previous archived version."""
    try:
        st = _get_client()
        result = st.restore_versions(folder_id, {file_path: version_time})

        # The API returns errors as {"path": "error message"}, empty = success
        if not result:
            return f"✅ Restored '{file_path}' to version from {version_time}"

        errors = [f"  {path}: {err}" for path, err in result.items() if err]
        if errors:
            return f"❌ Restore failed:\n" + "\n".join(errors)

        return f"✅ Restored '{file_path}' to version from {version_time}"

    except requests.ConnectionError:
        return "❌ Cannot connect to Syncthing. Is the service running?"
    except Exception as e:
        return f"❌ Failed to restore: {e}"


@tool(
    name="sync_pause",
    description="Pause syncing for a folder. Use this BEFORE batch file operations (renaming many files, large refactors, etc.) to prevent the user from seeing half-finished changes. Always call sync_resume() after the operation is complete.",
    parameters={
        "type": "object",
        "properties": {
            "folder_id": {
                "type": "string",
                "description": "Synced folder ID. Default is 'default'.",
                "default": "default",
            },
        },
    },
)
def sync_pause(folder_id: str = "default") -> str:
    """Pause syncing for a folder before batch operations."""
    try:
        st = _get_client()
        st.pause_folder(folder_id)
        return (
            f"⏸️ Folder '{folder_id}' sync paused.\n"
            f"⚠️ Remember to call sync_resume(\"{folder_id}\") when done!"
        )
    except requests.ConnectionError:
        return "❌ Cannot connect to Syncthing. Is the service running?"
    except Exception as e:
        return f"❌ Failed to pause sync: {e}"


@tool(
    name="sync_resume",
    description="Resume syncing for a paused folder. Call this after batch file operations are complete so changes can sync to the user's machine.",
    parameters={
        "type": "object",
        "properties": {
            "folder_id": {
                "type": "string",
                "description": "Synced folder ID. Default is 'default'.",
                "default": "default",
            },
        },
    },
)
def sync_resume(folder_id: str = "default") -> str:
    """Resume syncing for a paused folder."""
    try:
        st = _get_client()

        # Trigger scan to pick up all changes, then resume
        try:
            st.scan(folder_id)
        except Exception:
            pass

        st.resume_folder(folder_id)
        return f"▶️ Folder '{folder_id}' sync resumed. Changes will now sync to the user."
    except requests.ConnectionError:
        return "❌ Cannot connect to Syncthing. Is the service running?"
    except Exception as e:
        return f"❌ Failed to resume sync: {e}"
