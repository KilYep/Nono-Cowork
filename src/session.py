"""
Session manager — manages independent conversation contexts for multiple users

All IM channels share the same SessionManager instance.
"""
import threading
import time


class SessionManager:
    """Manages independent sessions for multiple users."""

    def __init__(self):
        self._sessions: dict[str, dict] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def get_lock(self, user_id: str) -> threading.Lock:
        """Get a user-level lock (prevents concurrent Agent execution for the same user)."""
        with self._global_lock:
            if user_id not in self._locks:
                self._locks[user_id] = threading.Lock()
            return self._locks[user_id]

    def get_or_create(self, user_id: str) -> dict:
        """Get or create a user session."""
        with self._global_lock:
            if user_id not in self._sessions:
                from agent import make_system_prompt
                self._sessions[user_id] = {
                    "history": [
                        {"role": "system", "content": make_system_prompt()}
                    ],
                    "token_stats": {
                        "total_prompt_tokens": 0,
                        "total_completion_tokens": 0,
                        "total_tokens": 0,
                        "total_cached_tokens": 0,
                        "total_api_calls": 0,
                    },
                    "created_at": time.time(),
                    "last_active": time.time(),
                }
            session = self._sessions[user_id]
            session["last_active"] = time.time()
            return session

    def reset(self, user_id: str):
        """Reset a user session."""
        with self._global_lock:
            if user_id in self._sessions:
                del self._sessions[user_id]

    def list_sessions(self) -> dict[str, float]:
        """List all active sessions and their last active times."""
        with self._global_lock:
            return {uid: s["last_active"] for uid, s in self._sessions.items()}


# Global singleton
sessions = SessionManager()
