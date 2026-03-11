"""Syncthing REST API lightweight client + Agent tool functions"""

import os
import time
import requests


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


# ————— Singleton client —————
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = SyncthingClient()
    return _client


# ————— Agent tool functions —————

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
                folder_lines.append(
                    f"  📁 {f.get('label', fid)} (ID: {fid})\n"
                    f"     Path: {f['path']}\n"
                    f"     State: {state} | Files: {local_files}/{global_files}"
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
