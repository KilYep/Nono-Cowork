"""
Telegram channel adapter — uses Polling mode to receive messages

Start: .venv/bin/python src/channels/telegram.py
Config: Set TELEGRAM_BOT_TOKEN in .env

Get a Token:
  1. Search for @BotFather in Telegram
  2. Send /newbot and follow the prompts
  3. Copy the Token into .env
"""
import os
import sys
import re
import logging

# Ensure src/ is on the Python path
_src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import telebot
from dotenv import load_dotenv

from channels.base import Channel
from formatter import clean_agent_output, split_long_text

load_dotenv()

logger = logging.getLogger("channel.telegram")

# ========== Config ==========
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Optional: restrict allowed Telegram user IDs (numeric)
ALLOWED_USERS_STR = os.getenv("TELEGRAM_ALLOWED_USERS", "")
ALLOWED_USERS: set[int] = set(
    int(u.strip()) for u in ALLOWED_USERS_STR.split(",") if u.strip()
)

MAX_MSG_LEN = 4096  # Telegram single message length limit


# ========== Telegram Markdown adaptation ==========
def _adapt_md_for_telegram(text: str) -> str:
    """Convert standard Markdown to Telegram MarkdownV2 format.

    Telegram MarkdownV2 supports: *bold*, _italic_, ~strikethrough~,
    `code`, ```code blocks```, [links](url)
    Not supported: # headings, tables
    """
    text = _convert_tables_to_text(text)

    lines = text.split("\n")
    result = []
    in_code_block = False

    for line in lines:
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            result.append(line)
            continue
        if in_code_block:
            result.append(line)
            continue

        # --- horizontal rule → blank line
        if re.match(r"^-{3,}\s*$", line.strip()):
            result.append("")
            continue

        # ### heading → *heading* (Telegram uses single * for bold)
        header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if header_match:
            title = header_match.group(2)
            # Remove existing ** bold markers to avoid nesting
            title = title.replace("**", "")
            result.append(f"*{title}*")
            continue

        # **bold** → *bold* (Telegram MarkdownV2 uses single *)
        line = re.sub(r"\*\*(.+?)\*\*", r"*\1*", line)

        result.append(line)

    return "\n".join(result)


def _convert_tables_to_text(text: str) -> str:
    """Convert Markdown tables → plain text."""
    lines = text.split("\n")
    result = []
    in_code_block = False
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            result.append(line)
            i += 1
            continue
        if in_code_block:
            result.append(line)
            i += 1
            continue

        if re.match(r"^\s*\|.*\|", line):
            table_lines = []
            while i < len(lines) and re.match(r"^\s*\|.*\|", lines[i]):
                table_lines.append(lines[i])
                i += 1

            parsed_rows = []
            for tl in table_lines:
                cells = [c.strip() for c in tl.strip().strip("|").split("|")]
                if all(re.match(r"^[-:]+$", c) for c in cells):
                    continue
                parsed_rows.append(cells)

            if parsed_rows:
                header = parsed_rows[0]
                result.append("*" + " | ".join(header) + "*")
                for row in parsed_rows[1:]:
                    result.append(" | ".join(row))
                result.append("")
            continue

        result.append(line)
        i += 1

    return "\n".join(result)


def _escape_markdown_v2(text: str) -> str:
    """Escape special characters for MarkdownV2 (skip inside code blocks)."""
    special_chars = r"_[]()~`>#+-=|{}.!"

    lines = text.split("\n")
    result = []
    in_code_block = False

    for line in lines:
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            result.append(line)
            continue
        if in_code_block:
            result.append(line)
            continue

        # Protect existing markdown format markers
        # Protect *bold* (single-asterisk bold)
        protected = []
        parts = re.split(r"(\*[^*]+\*)", line)
        for part in parts:
            if re.match(r"^\*[^*]+\*$", part):
                # This is a bold marker, escape inner special chars (excluding *)
                inner = part[1:-1]
                inner_escaped = ""
                for ch in inner:
                    if ch in special_chars and ch != "*":
                        inner_escaped += "\\" + ch
                    else:
                        inner_escaped += ch
                protected.append(f"*{inner_escaped}*")
            else:
                # Normal text, protect backtick-wrapped inline code
                code_parts = re.split(r"(`[^`]+`)", part)
                for cp in code_parts:
                    if re.match(r"^`[^`]+`$", cp):
                        protected.append(cp)  # inline code: no escaping
                    else:
                        escaped = ""
                        for ch in cp:
                            if ch in special_chars:
                                escaped += "\\" + ch
                            else:
                                escaped += ch
                        protected.append(escaped)
            result_line = "".join(protected)
            protected = []

        result.append(result_line)

    return "\n".join(result)


def format_for_telegram(text: str) -> str:
    """Full Telegram formatting pipeline."""
    text = clean_agent_output(text)
    text = _adapt_md_for_telegram(text)
    return text


# ========== Telegram channel ==========
class TelegramChannel(Channel):
    name = "telegram"

    def __init__(self):
        self.bot = None

    # ---- Channel interface implementation ----

    def start(self):
        if not BOT_TOKEN:
            print("❌ Error: Please set TELEGRAM_BOT_TOKEN in .env")
            print("\nSteps:")
            print("  1. Search for @BotFather in Telegram")
            print("  2. Send /newbot to create a bot")
            print("  3. Copy the Token into .env:")
            print("     TELEGRAM_BOT_TOKEN=123456:ABC-DEF...")
            print("  TELEGRAM_ALLOWED_USERS=12345,67890  (optional)")
            return

        self.bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

        # Register message handler
        @self.bot.message_handler(func=lambda msg: True, content_types=["text"])
        def on_text_message(message):
            self._on_message(message)

        # Get bot info
        try:
            bot_info = self.bot.get_me()
            bot_name = bot_info.username
        except Exception as e:
            print(f"❌ Invalid token or network error: {e}")
            return

        print("=" * 50)
        print("🚀 Telegram Bot started (Polling mode)")
        print(f"   Bot: @{bot_name}")
        print(f"   Allowed users: {'not set' if not ALLOWED_USERS else f'{len(ALLOWED_USERS)} user(s)'}")
        print("=" * 50)
        print("Waiting for Telegram messages...\n")

        # Blocking polling mode (auto-reconnect)
        self.bot.infinity_polling(timeout=30, long_polling_timeout=30)

    def send_reply(self, user_id: str, text: str):
        """Send Agent reply (try Markdown, fallback to plain text)."""
        chat_id = int(user_id)
        text = format_for_telegram(text)
        if not text:
            return

        if len(text) <= MAX_MSG_LEN:
            self._send_message(chat_id, text)
        else:
            chunks = split_long_text(text, MAX_MSG_LEN)
            for i, chunk in enumerate(chunks):
                if len(chunks) > 1:
                    chunk = f"📄 [{i + 1}/{len(chunks)}]\n{chunk}"
                self._send_message(chat_id, chunk)

    def send_status(self, user_id: str, text: str):
        """Send plain text status update."""
        chat_id = int(user_id)
        try:
            self.bot.send_message(chat_id, text)
        except Exception as e:
            logger.error(f"Failed to send status: {e}")

    # ---- Telegram-specific internal methods ----

    def _on_message(self, message):
        """Handle Telegram message."""
        try:
            user_id = message.from_user.id
            chat_id = message.chat.id
            user_text = message.text or ""

            # Permission check
            if ALLOWED_USERS and user_id not in ALLOWED_USERS:
                logger.warning(f"Unauthorized user: {user_id}")
                self.bot.send_message(chat_id, "⛔ You are not authorized to use this bot.")
                return

            # Handle /start command
            if user_text.startswith("/start"):
                self.bot.send_message(
                    chat_id,
                    "👋 Hi! I'm the VPS Agent bot.\n\n"
                    "Send text commands directly and I'll execute them on the server.\n"
                    "Send /help for help."
                )
                return

            # Strip @bot_name suffix
            user_text = re.sub(r"@\w+bot\b", "", user_text, flags=re.IGNORECASE).strip()

            # Dispatch to base class
            self.dispatch(str(user_id), user_text)

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)

    def _send_message(self, chat_id: int, text: str):
        """Send message: try MarkdownV2 first, fallback to plain text."""
        try:
            # Try MarkdownV2
            escaped = _escape_markdown_v2(text)
            self.bot.send_message(chat_id, escaped, parse_mode="MarkdownV2")
        except Exception:
            try:
                # Fallback to plain text
                self.bot.send_message(chat_id, text)
            except Exception as e:
                logger.error(f"Failed to send message: {e}")


# ========== Entry point ==========
def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    channel = TelegramChannel()
    channel.start()


if __name__ == "__main__":
    main()
