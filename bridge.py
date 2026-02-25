#!/usr/bin/env python3
"""
Discord / Stoat Bidirectional Bridge

     ██╗ ███╗   ███╗  ██████╗
     ██║ ████╗ ████║ ██╔════╝
     ██║ ██╔████╔██║ ██║  ███╗
██   ██║ ██║╚██╔╝██║ ██║   ██║
╚█████╔╝ ██║ ╚═╝ ██║ ╚██████╔╝
 ╚════╝  ╚═╝     ╚═╝  ╚═════╝

 Thank you for downloading!

 Please refer to readme.md for more info.

 GitHub: https://github.com/JMGstudios/DiscordStoatBridgeBot
 
 Support stoat server: https://stt.gg/FH10z8eP

 Support discord server: https://discord.gg/QTVRxUDSMq

"""

import asyncio
import io
import json
import logging
import os
import re
from collections import OrderedDict
from pathlib import Path
from types import SimpleNamespace

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv, set_key, dotenv_values
import stoat

# ──────────────────────────────────────────────────────────────────────────────
#  INTERACTIVE .env SETUP
# ──────────────────────────────────────────────────────────────────────────────

ENV_FILE = Path(".env")


def _prompt(label: str, secret: bool = False, allow_empty: bool = False) -> str:
    """Prompt the user on the terminal until a non-empty value is entered."""
    import getpass
    while True:
        try:
            if secret:
                print(f"  {label}:")
                print("  ⌨  Typing is hidden for security – this is normal, just type and press Enter.")
                value = getpass.getpass("  > ").strip()
            else:
                value = input(f"  {label}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSetup aborted.")
            raise SystemExit(1)
        if value or allow_empty:
            return value
        print("    ⚠  Value cannot be empty, please try again.")


def _prompt_channel_pairs() -> tuple[str, str]:
    """
    Ask the user to configure channel pairs one-by-one.
    Returns (discord_ids_csv, stoat_ids_csv).
    """
    print("  You will now link Discord channels to Stoat channels one pair at a time.")
    print("  Each pair bridges one Discord channel with one Stoat channel.\n")

    discord_ids: list[str] = []
    stoat_ids:   list[str] = []
    pair_num = 1

    while True:
        print(f"  ── Pair {pair_num} {'(first pair)' if pair_num == 1 else ''} ──")
        d_id = _prompt(f"  Discord Channel ID for pair {pair_num}")
        s_id = _prompt(f"  Stoat   Channel ID for pair {pair_num}")
        discord_ids.append(d_id.strip())
        stoat_ids.append(s_id.strip())

        print(f"\n  ✔  Pair {pair_num} saved: Discord {d_id.strip()} ↔ Stoat {s_id.strip()}")

        if pair_num >= 2:
            print(f"\n  Current pairs:")
            for i, (d, s) in enumerate(zip(discord_ids, stoat_ids), 1):
                print(f"    {i}. Discord {d} ↔ Stoat {s}")

        print()
        try:
            again = input("  Add another channel pair? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nSetup aborted.")
            raise SystemExit(1)

        if again in ("y", "yes"):
            pair_num += 1
        else:
            break

    return ",".join(discord_ids), ",".join(stoat_ids)


def _validate_channel_pairs(discord_raw: str, stoat_raw: str) -> bool:
    """Return True when both lists are non-empty and equal in length."""
    d = [x.strip() for x in discord_raw.split(",") if x.strip()]
    s = [x.strip() for x in stoat_raw.split(",")   if x.strip()]
    return bool(d) and bool(s) and len(d) == len(s)


def interactive_env_setup() -> None:
    """
    - .env does not exist → create it from scratch via prompts
    - .env exists but is corrupted / unparseable → prompt for all values
    - .env exists but specific keys are missing or empty → prompt only for those
    - .env exists but DISCORD_CHANNEL_IDS / STOAT_CHANNEL_IDS are mismatched → re-prompt for both
    """

    existing: dict[str, str] = {}
    if ENV_FILE.exists():
        try:
            existing = {k: (v or "") for k, v in dotenv_values(ENV_FILE).items()}
        except Exception as exc:
            print(f"⚠  Could not parse {ENV_FILE}: {exc}")
            print("   Starting fresh – you will be asked for all values.\n")


    needs_discord_token = not existing.get("DISCORD_BOT_TOKEN", "").strip()
    needs_stoat_token   = not existing.get("STOAT_BOT_TOKEN",   "").strip()

    discord_raw  = existing.get("DISCORD_CHANNEL_IDS", "")
    stoat_raw    = existing.get("STOAT_CHANNEL_IDS",   "")
    needs_channels = not _validate_channel_pairs(discord_raw, stoat_raw)

    needs_revolt_url = not existing.get("REVOLT_API_URL", "").strip()

    anything_missing = any([
        needs_discord_token, needs_stoat_token, needs_channels, needs_revolt_url,
    ])

    if not anything_missing:
        load_dotenv(ENV_FILE)
        print(f"Config loaded from: {ENV_FILE.resolve()}")
        return  # All good – no interaction needed

    banner = "=" * 60
    print(f"\n{banner}")
    print("  Stoat ↔ Discord Bridge – First-Time / Repair Setup")
    print(banner)

    if not ENV_FILE.exists():
        print("  ℹ  No .env file found – let's create one.")
    else:
        missing_keys = []
        if needs_discord_token: missing_keys.append("DISCORD_BOT_TOKEN")
        if needs_stoat_token:   missing_keys.append("STOAT_BOT_TOKEN")
        if needs_channels:      missing_keys.append("DISCORD_CHANNEL_IDS / STOAT_CHANNEL_IDS")
        if needs_revolt_url:    missing_keys.append("REVOLT_API_URL")
        print(f"  ⚠  Missing or invalid keys: {', '.join(missing_keys)}")
    print("  Press Ctrl-C at any time to abort.\n")

    # Discord bot token
    if needs_discord_token:
        print("› Discord Bot Token")
        print("  Get it at: https://discord.com/developers/applications")
        existing["DISCORD_BOT_TOKEN"] = _prompt("Discord Bot Token", secret=True)
        print()

    # Stoat bot token
    if needs_stoat_token:
        print("› Stoat Bot Token")
        print("  Get it in your Stoat server's bot settings.")
        existing["STOAT_BOT_TOKEN"] = _prompt("Stoat Bot Token", secret=True)
        print()

    # Channel pairs – collected one pair at a time
    if needs_channels:
        print("› Channel Pairs")
        d_raw, s_raw = _prompt_channel_pairs()
        existing["DISCORD_CHANNEL_IDS"] = d_raw
        existing["STOAT_CHANNEL_IDS"]   = s_raw
        print()

    # Revolt API URL (optional – has a sensible default)
    if needs_revolt_url:
        print("› Revolt / Stoat API URL")
        print("  Press Enter to accept the default!")
        url = _prompt("API URL  [https://api.revolt.chat]", allow_empty=True)
        existing["REVOLT_API_URL"] = url or "https://api.revolt.chat"
        print()

    # ── 4. Write / update the .env file ─────────────────────────────────────
    ENV_FILE.touch(exist_ok=True)
    for key, value in existing.items():
        set_key(str(ENV_FILE), key, value)

    print(f"  ✔  Configuration saved to {ENV_FILE.resolve()}")
    print(f"{banner}\n")

    # ── 5. Re-load so os.getenv() picks up the freshly written values ────────
    load_dotenv(ENV_FILE, override=True)


interactive_env_setup()

# ──────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
STOAT_BOT_TOKEN   = os.getenv("STOAT_BOT_TOKEN", "")

_discord_raw = os.getenv("DISCORD_CHANNEL_IDS", "")
_stoat_raw   = os.getenv("STOAT_CHANNEL_IDS", "")

DISCORD_CHANNEL_IDS: list[int] = [int(x.strip()) for x in _discord_raw.split(",") if x.strip()]
STOAT_CHANNEL_IDS:   list[str] = [x.strip()      for x in _stoat_raw.split(",")   if x.strip()]

REVOLT_API_URL = os.getenv("REVOLT_API_URL", "https://api.revolt.chat").rstrip("/")

if len(DISCORD_CHANNEL_IDS) != len(STOAT_CHANNEL_IDS):
    raise RuntimeError(
        f"Channel list length mismatch: "
        f"{len(DISCORD_CHANNEL_IDS)} Discord IDs vs {len(STOAT_CHANNEL_IDS)} Stoat IDs."
    )

PAIR_COUNT = len(DISCORD_CHANNEL_IDS)

STOAT_TO_DISCORD: dict[str, int] = {s: d for d, s in zip(DISCORD_CHANNEL_IDS, STOAT_CHANNEL_IDS)}
DISCORD_TO_STOAT: dict[int, str] = {d: s for d, s in zip(DISCORD_CHANNEL_IDS, STOAT_CHANNEL_IDS)}

# 25MB file size limit due to discord's restrictions
MAX_FILE_SIZE  = 25 * 1024 * 1024

# The amount of messages that are being stored in cache for reply support
MSG_CACHE_SIZE = 500

# ──────────────────────────────────────────────────────────────────────────────
#  LOGGING
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bridge")

# ──────────────────────────────────────────────────────────────────────────────
#  FIRST-TIME USER NOTIFICATION  (persisted to JSON)
# ──────────────────────────────────────────────────────────────────────────────

NOTIFIED_USERS_FILE = Path("notified_users.json")

# Structure: { "discord": ["123456", ...], "stoat": ["ABCDEF...", ...] }
_notified_users: dict[str, list[str]] = {"discord": [], "stoat": []}


def _load_notified_users() -> None:
    global _notified_users
    if NOTIFIED_USERS_FILE.exists():
        try:
            with NOTIFIED_USERS_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                _notified_users["discord"] = list(data.get("discord", []))
                _notified_users["stoat"]   = list(data.get("stoat", []))
            logger.info(
                f"Loaded {len(_notified_users['discord'])} Discord "
                f"and {len(_notified_users['stoat'])} Stoat notified users."
            )
        except Exception as exc:
            logger.error(f"Could not load {NOTIFIED_USERS_FILE}: {exc}")


def _save_notified_users() -> None:
    try:
        with NOTIFIED_USERS_FILE.open("w", encoding="utf-8") as f:
            json.dump(_notified_users, f, indent=2)
    except Exception as exc:
        logger.error(f"Could not save {NOTIFIED_USERS_FILE}: {exc}")


def _is_notified(platform: str, uid: str) -> bool:
    return uid in _notified_users[platform]


def _mark_notified(platform: str, uid: str) -> None:
    if uid not in _notified_users[platform]:
        _notified_users[platform].append(uid)
        _save_notified_users()


# DM texts ─────────────────────────────────────────────────────────────────────

DISCORD_WELCOME_DM = """\
👋 **Hey! You just used the Stoat↔Discord Bridge Bot.**

This bot connects a Discord channel to a channel on **Stoat** (https://stoat.chat), \
forwarding messages between both platforms in real time.

**What happens to your messages?**
• Your **display name** and **profile picture** are shown on the other platform.
• The **content** of your messages (text and attachments) is transferred to the other platform.
• Attachments are briefly buffered in the bot's memory for forwarding and discarded immediately afterwards.
• **No** messages are stored permanently on the bot's server.

**Deletion:**
If you delete a message, it will automatically be deleted on the other platform as well.

If you don't want to use the bridge / your messages to be transfered, simply stop writing in the bridged channel — \
your messages will not be forwarded.
"""

STOAT_WELCOME_DM = """\
👋 **Hey! You just used the Stoat↔Discord Bridge Bot.**

This bot connects a Stoat channel to a channel on **Discord** (https://discord.gg), \
forwarding messages between both platforms in real time.

**What happens to your messages?**
• Your **display name** and **profile picture** are shown on the other platform.
• The **content** of your messages (text and attachments) is transferred to the other platform.
• Attachments are briefly buffered in the bot's memory for forwarding and discarded immediately afterwards.
• **No** messages are stored permanently on the bot's server.

**Deletion:**
If you delete a message, it will automatically be deleted on the other platform as well.

If you don't want to use the bridge / your messages to be transfered, simply stop writing in the bridged channel — \
your messages will not be forwarded.
"""

# ──────────────────────────────────────────────────────────────────────────────
#  SHARED STATE
# ──────────────────────────────────────────────────────────────────────────────

discord_webhooks: dict[int, discord.Webhook] = {}
stoat_channels:  dict[str, object]           = {}

_d2s: OrderedDict[int, str] = OrderedDict()   # discord_msg_id → stoat_msg_id
_s2d: OrderedDict[str, int] = OrderedDict()   # stoat_msg_id   → discord_msg_id

# Discord message IDs that were sent via webhook (Stoat → Discord direction).
# Regular user messages (Discord → Stoat direction) are NOT in this set.
# Used in on_message_delete to choose the right deletion method.
_webhook_discord_ids: set[int] = set()

# IDs the bridge is currently deleting itself – used to break deletion loops.
_discord_deleting: set[int] = set()   # discord msg IDs we are about to delete
_stoat_deleting:   set[str] = set()   # stoat   msg IDs we are about to delete


def _cache_pair(discord_id: int, stoat_id: str, *, from_webhook: bool = False) -> None:
    for cache, key, val in ((_d2s, discord_id, stoat_id), (_s2d, stoat_id, discord_id)):
        if key in cache:
            cache.move_to_end(key)
        cache[key] = val
        if len(cache) > MSG_CACHE_SIZE:
            cache.popitem(last=False)
    if from_webhook:
        _webhook_discord_ids.add(discord_id)


def _extract_id(obj) -> str | None:
    """Pull an ID string from a raw dict, object, or plain string."""
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj or None
    if isinstance(obj, dict):
        v = obj.get("_id") or obj.get("id")
        return str(v) if v else None
    v = getattr(obj, "_id", None) or getattr(obj, "id", None)
    return str(v) if v else None


def _stoat_asset_url(asset) -> str | None:
    """asset.url is a METHOD on stoat Asset objects – call it safely."""
    if asset is None:
        return None
    url_attr = getattr(asset, "url", None)
    try:
        return url_attr() if callable(url_attr) else str(url_attr)
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────────
#  FILE HELPERS  (Stoat → Discord direction only)
# ──────────────────────────────────────────────────────────────────────────────


async def fetch_bytes(session: aiohttp.ClientSession, url: str) -> tuple[bytes, str] | None:
    """Download url into RAM. Returns (data, filename) or None on any error."""
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                logger.warning(f"File fetch {url} -> HTTP {resp.status}")
                return None
            cl = resp.headers.get("Content-Length")
            if cl and int(cl) > MAX_FILE_SIZE:
                logger.warning(f"Skipping oversized file ({cl} B): {url}")
                return None
            data = await resp.read()
            if len(data) > MAX_FILE_SIZE:
                logger.warning(f"Skipping oversized file ({len(data)} B) after download")
                return None
            filename = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1] or "file"
            return data, filename
    except Exception as exc:
        logger.error(f"File fetch error for {url}: {exc}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
#  REVOLT MESSAGE FETCH  (for reply quotes)
# ──────────────────────────────────────────────────────────────────────────────


async def fetch_stoat_message(
    channel_id: str,
    message_id: str,
    stoat_client: "StoatBot",
) -> SimpleNamespace | None:

    def _build(raw: dict) -> SimpleNamespace:
        masquerade = raw.get("masquerade") or {}
        display_name = (
            masquerade.get("name")
            or _nested_get(raw, "author", "display_name")
            or _nested_get(raw, "author", "username")
            or "unknown"
        )
        return SimpleNamespace(
            content=raw.get("content") or "",
            author=SimpleNamespace(display_name=display_name),
        )

    def _nested_get(d, *keys):
        cur = d
        for k in keys:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(k)
        return cur

    ch = stoat_channels.get(channel_id)
    if ch is not None:
        for attr in ("fetch_message", "get_message"):
            method = getattr(ch, attr, None)
            if not method:
                continue
            try:
                result = await method(message_id)
                if result is None:
                    continue
                if not isinstance(result, dict):
                    masq = getattr(result, "masquerade", None)
                    masq_name = (
                        masq.get("name") if isinstance(masq, dict)
                        else getattr(masq, "name", None)
                    ) if masq else None
                    author = getattr(result, "author", None)
                    display_name = (
                        masq_name
                        or getattr(author, "display_name", None)
                        or getattr(author, "name", None)
                        or "unknown"
                    )
                    return SimpleNamespace(
                        content=getattr(result, "content", "") or "",
                        author=SimpleNamespace(display_name=display_name),
                    )
                return _build(result)
            except Exception as exc:
                logger.debug(f"fetch_stoat_message via ch.{attr}: {exc}")

    http = getattr(stoat_client, "http", None)
    if http is not None:
        request_fn = getattr(http, "request", None)
        if request_fn:
            try:
                data = await request_fn("GET", f"/channels/{channel_id}/messages/{message_id}")
                if isinstance(data, dict):
                    return _build(data)
            except Exception as exc:
                logger.debug(f"fetch_stoat_message via http.request: {exc}")

    logger.warning(f"fetch_stoat_message: could not fetch {channel_id}/{message_id}")
    return None


# ──────────────────────────────────────────────────────────────────────────────
#  STOAT MESSAGE DELETION HELPER
# ──────────────────────────────────────────────────────────────────────────────


async def delete_stoat_message(channel_id: str, message_id: str, stoat_client: "StoatBot") -> bool:
    """Delete a message on Stoat via direct REST call with the bot token."""
    session = stoat_client._http_session
    if session is None:
        logger.warning("delete_stoat_message: HTTP session not ready")
        return False
    try:
        async with session.delete(
            f"{REVOLT_API_URL}/channels/{channel_id}/messages/{message_id}",
            headers={"x-bot-token": STOAT_BOT_TOKEN},
        ) as resp:
            if resp.status in (200, 204):
                return True
            body = await resp.text()
            logger.warning(
                f"delete_stoat_message: HTTP {resp.status} for "
                f"{channel_id}/{message_id} – {body[:200]}"
            )
            return False
    except Exception as exc:
        logger.error(f"delete_stoat_message: {channel_id}/{message_id}: {exc}")
        return False


# ──────────────────────────────────────────────────────────────────────────────
#  MENTION / EMOJI HELPERS
# ──────────────────────────────────────────────────────────────────────────────

_RE_DISCORD_USER    = re.compile(r"<@!?(\d+)>")
_RE_DISCORD_CHANNEL = re.compile(r"<#(\d+)>")
_RE_DISCORD_ROLE    = re.compile(r"<@&(\d+)>")
_RE_DISCORD_EMOJI   = re.compile(r"<a?:([A-Za-z0-9_]+):\d+>")

_RE_REVOLT_USER       = re.compile(r"<@([A-Z0-9]{26})>")
_RE_REVOLT_CUSTOM_EMO = re.compile(r":([A-Z0-9]{26}):")

_emoji_name_cache: dict[str, str] = {}


async def resolve_revolt_emoji(emoji_id: str, session: aiohttp.ClientSession, token: str) -> str:
    if emoji_id in _emoji_name_cache:
        return _emoji_name_cache[emoji_id]
    try:
        async with session.get(
            f"{REVOLT_API_URL}/custom/emoji/{emoji_id}",
            headers={"x-bot-token": token},
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                name = data.get("name") or emoji_id
                _emoji_name_cache[emoji_id] = name
                return name
    except Exception as exc:
        logger.debug(f"Could not resolve Stoat emoji {emoji_id}: {exc}")
    return emoji_id


async def clean_discord_content(content: str, message: discord.Message) -> str:
    """Resolve Discord markup to plain text before forwarding to Stoat."""
    guild  = message.guild
    result = content

    for m in reversed(list(_RE_DISCORD_USER.finditer(result))):
        uid  = int(m.group(1))
        name = f"@user{uid}"
        if guild:
            member = guild.get_member(uid)
            if member is None:
                try:
                    member = await guild.fetch_member(uid)
                except Exception:
                    member = None
            if member:
                name = f"@{member.display_name}"
        result = result[: m.start()] + name + result[m.end() :]

    def _channel(m: re.Match) -> str:
        ch = guild.get_channel(int(m.group(1))) if guild else None
        return f"#{ch.name}" if ch else "#channel"

    result = _RE_DISCORD_CHANNEL.sub(_channel, result)

    def _role(m: re.Match) -> str:
        role = guild.get_role(int(m.group(1))) if guild else None
        return f"@{role.name}" if role else "@role"

    result = _RE_DISCORD_ROLE.sub(_role, result)
    result = _RE_DISCORD_EMOJI.sub(lambda m: f":{m.group(1)}:", result)
    return result


async def clean_stoat_content(
    content: str,
    session: aiohttp.ClientSession,
    token: str,
) -> str:
    """Resolve Stoat markup to plain text before forwarding to Discord."""
    result = content

    for m in reversed(list(_RE_REVOLT_USER.finditer(result))):
        uid  = m.group(1)
        name = "@user"
        try:
            async with session.get(
                f"{REVOLT_API_URL}/users/{uid}",
                headers={"x-bot-token": token},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    name = "@" + (data.get("display_name") or data.get("username") or uid)
        except Exception as exc:
            logger.debug(f"Could not resolve Revolt user {uid}: {exc}")
        result = result[: m.start()] + name + result[m.end() :]

    matches = list(_RE_REVOLT_CUSTOM_EMO.finditer(result))
    if matches:
        names = await asyncio.gather(
            *[resolve_revolt_emoji(m.group(1), session, token) for m in matches]
        )
        for m, name in zip(reversed(matches), reversed(names)):
            result = result[: m.start()] + f":{name}:" + result[m.end() :]

    return result


# ──────────────────────────────────────────────────────────────────────────────
#  STOAT BOT
# ──────────────────────────────────────────────────────────────────────────────


class StoatBot(stoat.Client):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._http_session: aiohttp.ClientSession | None = None
        self._discord_bot: "DiscordBot | None" = None  # set in main()

        # Watchdog tracking
        self._ready_received:        bool  = False
        self._connection_attempt_time: float = 0.0   # set by restart wrapper
        self._last_event_time:        float = 0.0    # set by restart wrapper

    async def on_ready(self, event, /):
        # Close any leftover HTTP session from a previous connection cycle
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
        self._http_session = aiohttp.ClientSession()

        # Mark connection as alive
        self._ready_received  = True
        self._last_event_time = asyncio.get_event_loop().time()

        logger.info(f"Stoat: connected as {self.me}")

        # Clear stale channel refs before repopulating (important on reconnect)
        stoat_channels.clear()

        for stoat_id in STOAT_CHANNEL_IDS:
            try:
                ch = await self.fetch_channel(stoat_id)
                stoat_channels[stoat_id] = ch
                logger.info(f"Stoat: listening in #{ch.name} (id={stoat_id})")
            except Exception as exc:
                logger.error(f"Stoat: could not fetch channel {stoat_id} - {exc}")

    # ── Send a DM on Stoat ────────────────────────────────────────────────────

    async def _try_send_stoat_dm(self, user_id: str) -> None:
        """Send a DM to a Stoat user."""
        session = self._http_session
        if session is None:
            return
        try:
            # Open (or fetch existing) DM channel with the user
            async with session.get(
                f"{REVOLT_API_URL}/users/{user_id}/dm",
                headers={"x-bot-token": STOAT_BOT_TOKEN},
            ) as resp:
                if resp.status != 200:
                    logger.debug(f"Stoat: open DM channel failed for {user_id}: HTTP {resp.status}")
                    return
                dm_data = await resp.json()

            dm_channel_id = dm_data.get("_id") or dm_data.get("id")
            if not dm_channel_id:
                logger.debug(f"Stoat: no channel ID in DM response for {user_id}")
                return

            # Send the welcome message into the DM channel
            async with session.post(
                f"{REVOLT_API_URL}/channels/{dm_channel_id}/messages",
                headers={"x-bot-token": STOAT_BOT_TOKEN},
                json={"content": STOAT_WELCOME_DM[:2000]},
            ) as resp:
                if resp.status in (200, 201):
                    logger.info(f"Stoat: sent welcome DM to user {user_id}")
                else:
                    body = await resp.text()
                    logger.debug(f"Stoat: DM send failed for {user_id}: HTTP {resp.status} – {body[:200]}")

        except Exception as exc:
            logger.debug(f"Stoat: could not DM user {user_id}: {exc}")

    async def on_message_create(self, event: stoat.MessageCreateEvent, /):
        self._last_event_time = asyncio.get_event_loop().time()
        msg = event.message

        if msg.author_id == self.me.id:
            return

        stoat_id = msg.channel.id
        if stoat_id not in STOAT_TO_DISCORD:
            return

        # ── First-time DM ─────────────────────────────────────────────────────
        uid = str(msg.author_id)
        if not _is_notified("stoat", uid):
            _mark_notified("stoat", uid)
            asyncio.create_task(self._try_send_stoat_dm(uid))

        discord_id = STOAT_TO_DISCORD[stoat_id]
        webhook    = discord_webhooks.get(discord_id)
        if webhook is None:
            logger.warning(f"Stoat -> Discord: webhook for {discord_id} not ready, dropped")
            return

        # ── Clean content ─────────────────────────────────────────────────────
        content = await clean_stoat_content(
            msg.content or "", self._http_session, STOAT_BOT_TOKEN
        )

        # ── Reply → quote fallback ────────────────────────────────────────────
        replies_raw = getattr(msg, "replies", None) or []
        reply_id: str | None = None
        if replies_raw:
            first    = replies_raw[0]
            reply_id = _extract_id(first) or (str(first) if isinstance(first, str) else None)

        if reply_id:
            orig = await fetch_stoat_message(stoat_id, reply_id, self)
            if orig is not None:
                orig_author  = orig.author.display_name[:50]
                orig_snippet = (orig.content or "")[:80].replace("\n", " ")
                content = f"-# ↩ **{orig_author}**: *{orig_snippet}*\n{content}"
            else:
                logger.warning(f"Stoat -> Discord: could not fetch reply target '{reply_id}'")

        # ── Attachments ───────────────────────────────────────────────────────
        discord_files: list[discord.File] = []
        for att in getattr(msg, "attachments", None) or []:
            url      = _stoat_asset_url(att)
            filename = getattr(att, "filename", None) or "file"
            if not url:
                continue
            result = await fetch_bytes(self._http_session, url)
            if result is None:
                content += f"\n{url}"
                continue
            data, fname = result
            discord_files.append(discord.File(io.BytesIO(data), filename=filename or fname))
            del data

        if not content.strip() and not discord_files:
            return

        author_name = (
            getattr(msg.author, "display_name", None)
            or getattr(msg.author, "name", None)
            or "unknown"
        )[:80]
        avatar_url = _stoat_asset_url(getattr(msg.author, "avatar", None))

        try:
            sent = await webhook.send(
                content    = content[:2000] if content.strip() else discord.utils.MISSING,
                username   = author_name,
                avatar_url = avatar_url,
                files      = discord_files or discord.utils.MISSING,
                wait       = True,
            )
            _cache_pair(sent.id, str(msg.id), from_webhook=True)
            logger.debug(f"Stoat -> Discord: cached discord={sent.id} <-> stoat={msg.id}")
        except Exception as exc:
            logger.error(f"Stoat -> Discord (channel {discord_id}): {exc}")
        finally:
            for f in discord_files:
                f.fp.close()

    # ── Message deletion: Stoat → delete on Discord ───────────────────────────

    async def on_message_delete(self, event, /):
        """When a Stoat message is deleted, remove the mirrored Discord message."""
        try:
            msg_id     = _extract_id(getattr(event, "message_id", None) or getattr(event, "id", None))
            channel_id = _extract_id(getattr(event, "channel_id", None))

            if msg_id is None:
                # Some library versions give us the full message object
                msg_obj    = getattr(event, "message", None)
                msg_id     = _extract_id(msg_obj)
                channel_id = channel_id or _extract_id(getattr(msg_obj, "channel", None))

            if msg_id is None:
                return

            # Loop-break: if we triggered this deletion ourselves, ignore it.
            if msg_id in _stoat_deleting:
                _stoat_deleting.discard(msg_id)
                return

            discord_msg_id = _s2d.get(str(msg_id))
            if discord_msg_id is None:
                return  # Not a bridged message

            # Resolve the Discord channel ID
            stoat_ch_id   = channel_id or next(
                (s for s, d in STOAT_TO_DISCORD.items() if d in discord_webhooks), None
            )
            discord_ch_id = STOAT_TO_DISCORD.get(stoat_ch_id) if stoat_ch_id else None

            _discord_deleting.add(discord_msg_id)

            # ── Case 1: message was originally sent via webhook (Stoat→Discord) ──
            if discord_msg_id in _webhook_discord_ids:
                webhook = discord_webhooks.get(discord_ch_id) if discord_ch_id else None
                if webhook is None:
                    # Fall back: try every webhook
                    for _, wh in discord_webhooks.items():
                        try:
                            await wh.delete_message(discord_msg_id)
                            _webhook_discord_ids.discard(discord_msg_id)
                            return
                        except discord.NotFound:
                            _discord_deleting.discard(discord_msg_id)
                            return
                        except Exception:
                            pass
                    _discord_deleting.discard(discord_msg_id)
                    return
                try:
                    await webhook.delete_message(discord_msg_id)
                    _webhook_discord_ids.discard(discord_msg_id)
                except discord.NotFound:
                    _discord_deleting.discard(discord_msg_id)
                    logger.debug(f"Discord webhook message {discord_msg_id} already gone")
                except Exception as exc:
                    _discord_deleting.discard(discord_msg_id)
                    logger.error(f"Stoat -> Discord: could not delete webhook msg {discord_msg_id}: {exc}")

            # ── Case 2: message was originally sent by a Discord user (Discord→Stoat) ──
            else:
                if self._discord_bot is None or discord_ch_id is None:
                    logger.warning(
                        "Stoat -> Discord: cannot delete user message – "
                        "discord_bot reference or channel ID missing"
                    )
                    _discord_deleting.discard(discord_msg_id)
                    return
                try:
                    ch = (
                        self._discord_bot.get_channel(discord_ch_id)
                        or await self._discord_bot.fetch_channel(discord_ch_id)
                    )
                    msg = ch.get_partial_message(discord_msg_id)
                    await msg.delete()
                except discord.NotFound:
                    _discord_deleting.discard(discord_msg_id)
                    logger.debug(f"Discord user message {discord_msg_id} already gone")
                except Exception as exc:
                    _discord_deleting.discard(discord_msg_id)
                    logger.error(f"Stoat -> Discord: could not delete user msg {discord_msg_id}: {exc}")

        except Exception as exc:
            logger.error(f"on_message_delete (Stoat): unexpected error: {exc}")


# ──────────────────────────────────────────────────────────────────────────────
#  STOAT CONNECTION WATCHDOG & RESTART WRAPPER
# ──────────────────────────────────────────────────────────────────────────────

# How long after a connection attempt to wait for on_ready before giving up
_READY_TIMEOUT_S:   int = 30
# How long a fully-connected bot may stay silent before we assume it's dead
_SILENCE_TIMEOUT_S: int = 300   # 5 minutes
# How often the watchdog checks
_WATCHDOG_INTERVAL: int = 20


async def _stoat_watchdog(stoat_bot: "StoatBot") -> None:
    """
    Background task: periodically checks that the Stoat WebSocket connection is
    healthy and forces a reconnect if it goes stale.

    Two scenarios are detected:
      1. on_ready never fired within _READY_TIMEOUT_S seconds of the connection
         attempt  →  the WebSocket connected but authentication/setup silently
         stalled (the intermittent bug reported by the user).
      2. on_ready fired but then no further events arrived for _SILENCE_TIMEOUT_S
         →  the connection silently dropped after initial setup.

    In both cases we call stoat_bot.close(), which makes the running start()
    coroutine return, triggering the restart loop in _run_stoat_with_restart().
    """
    logger.debug("Stoat watchdog: started")
    while True:
        await asyncio.sleep(_WATCHDOG_INTERVAL)
        now = asyncio.get_event_loop().time()

        if not stoat_bot._ready_received:
            elapsed = now - stoat_bot._connection_attempt_time
            if stoat_bot._connection_attempt_time > 0 and elapsed > _READY_TIMEOUT_S:
                logger.warning(
                    f"Stoat watchdog: no Ready event after {elapsed:.0f}s "
                    f"(threshold={_READY_TIMEOUT_S}s) – forcing reconnect"
                )
                try:
                    await stoat_bot.close()
                except Exception as exc:
                    logger.debug(f"Stoat watchdog: close() error: {exc}")
        else:
            elapsed = now - stoat_bot._last_event_time
            if stoat_bot._last_event_time > 0 and elapsed > _SILENCE_TIMEOUT_S:
                logger.warning(
                    f"Stoat watchdog: connection silent for {elapsed:.0f}s "
                    f"(threshold={_SILENCE_TIMEOUT_S}s) – forcing reconnect"
                )
                try:
                    await stoat_bot.close()
                except Exception as exc:
                    logger.debug(f"Stoat watchdog: close() error: {exc}")


async def _run_stoat_with_restart(stoat_bot: "StoatBot") -> None:
    """
    Runs stoat_bot.start() in an infinite restart loop.
    Resets watchdog state before every connection attempt so the watchdog
    can accurately detect a stuck or dropped connection.
    """
    RESTART_DELAY = 5
    while True:
        # Reset watchdog state for the new connection attempt
        stoat_bot._ready_received         = False
        stoat_bot._connection_attempt_time = asyncio.get_event_loop().time()
        stoat_bot._last_event_time         = asyncio.get_event_loop().time()

        logger.info("Stoat: (re)starting WebSocket connection…")
        try:
            await stoat_bot.start()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(f"Stoat: connection error – {exc}")
        finally:
            # Always clean up the HTTP session so on_ready can create a fresh one
            if stoat_bot._http_session and not stoat_bot._http_session.closed:
                try:
                    await stoat_bot._http_session.close()
                except Exception:
                    pass
                stoat_bot._http_session = None
            stoat_channels.clear()

        logger.warning(f"Stoat: disconnected – restarting in {RESTART_DELAY}s…")
        await asyncio.sleep(RESTART_DELAY)


# ──────────────────────────────────────────────────────────────────────────────
#  DISCORD BOT
# ──────────────────────────────────────────────────────────────────────────────


class DiscordBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds          = True
        intents.webhooks        = True
        intents.members         = True
        super().__init__(command_prefix="!", intents=intents)

        # Keep a reference to the StoatBot so we can call delete on it
        self._stoat_bot: StoatBot | None = None

    async def setup_hook(self):
        self.loop.create_task(self._setup_webhooks())

    async def _setup_webhooks(self):
        await self.wait_until_ready()
        for discord_id in DISCORD_CHANNEL_IDS:
            try:
                channel = self.get_channel(discord_id) or await self.fetch_channel(discord_id)
                for wh in await channel.webhooks():
                    if wh.user == self.user:
                        discord_webhooks[discord_id] = wh
                        logger.info(f"Discord: reusing webhook '{wh.name}' for channel {discord_id}")
                        break
                else:
                    wh = await channel.create_webhook(name="Stoat Bridge")
                    discord_webhooks[discord_id] = wh
                    logger.info(f"Discord: created webhook for channel {discord_id}")
            except Exception as exc:
                logger.error(f"Discord: could not set up webhook for channel {discord_id} - {exc}")

    async def on_ready(self):
        logger.info(f"Discord: connected as {self.user}")
        logger.info(f"Discord: bridging {PAIR_COUNT} channel pair(s)")

    # ── Send a DM on Discord ──────────────────────────────────────────────────

    async def _try_send_discord_dm(self, user: discord.User | discord.Member) -> None:
        """DM the user a welcome embed the first time they write in a bridged channel."""
        try:
            embed = discord.Embed(
                title="📡 Stoat ↔ Discord Bridge",
                description=DISCORD_WELCOME_DM,
                colour=discord.Colour.from_str("#FF6B35"),
            )
            embed.set_footer(text="This message was sent once because you wrote in a bridged channel.")
            await user.send(embed=embed)
            logger.info(f"Discord: sent welcome DM to {user} ({user.id})")
        except discord.Forbidden:
            logger.debug(f"Discord: DMs disabled for {user} ({user.id})")
        except Exception as exc:
            logger.debug(f"Discord: could not DM {user}: {exc}")

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return

        if message.webhook_id is not None:
            if message.webhook_id in {wh.id for wh in discord_webhooks.values()}:
                return

        discord_id = message.channel.id
        if discord_id not in DISCORD_TO_STOAT:
            return

        # ── First-time DM ─────────────────────────────────────────────────────
        uid = str(message.author.id)
        if not _is_notified("discord", uid):
            _mark_notified("discord", uid)
            asyncio.create_task(self._try_send_discord_dm(message.author))

        stoat_id = DISCORD_TO_STOAT[discord_id]
        ch       = stoat_channels.get(stoat_id)
        if ch is None:
            logger.warning(f"Discord -> Stoat: channel {stoat_id} not ready, dropped")
            return

        # ── Content ───────────────────────────────────────────────────────────
        content = await clean_discord_content(message.content or "", message)

        # ── Reply ─────────────────────────────────────────────────────────────
        stoat_replies: list = []
        if message.reference and message.reference.message_id:
            ref_discord_id  = message.reference.message_id
            cached_stoat_id = _d2s.get(ref_discord_id)

            if cached_stoat_id:
                stoat_replies = [SimpleNamespace(id=cached_stoat_id, mention=False)]
                logger.debug(
                    f"Discord -> Stoat: native reply to stoat_id={cached_stoat_id} "
                    f"(from discord ref={ref_discord_id})"
                )
            else:
                logger.debug(
                    f"Discord -> Stoat: reply ref={ref_discord_id} not in cache, using quote"
                )
                try:
                    ref_msg = (
                        message.reference.resolved
                        if isinstance(message.reference.resolved, discord.Message)
                        else await message.channel.fetch_message(ref_discord_id)
                    )
                    ref_author  = ref_msg.author.display_name[:50]
                    ref_snippet = (ref_msg.content or "")[:80].replace("\n", " ")
                    content = f"-# ↩ **{ref_author}**: *{ref_snippet}*\n{content}"
                except Exception as exc:
                    logger.debug(f"Could not fetch Discord reply target {ref_discord_id}: {exc}")

        # ── Attachments ───────────────────────────────────────────────────────
        for att in message.attachments:
            content += f" {att.url}"

        if not content.strip():
            return

        avatar_url = (
            str(message.author.avatar.url)
            if message.author.avatar
            else str(message.author.default_avatar.url)
        )

        send_kwargs: dict = {
            "masquerade": stoat.Masquerade(
                name=message.author.display_name[:32],
                avatar=avatar_url,
            ),
            "content": content[:2000],
        }
        if stoat_replies:
            send_kwargs["replies"] = stoat_replies

        try:
            sent = await ch.send(**send_kwargs)

            sent_id = _extract_id(sent)
            if sent_id:
                _cache_pair(message.id, sent_id)
                logger.debug(f"Discord -> Stoat: cached discord={message.id} <-> stoat={sent_id}")
            else:
                logger.warning(
                    f"Discord -> Stoat: could not extract ID from sent object "
                    f"type={type(sent).__name__!r} repr={sent!r:.200}"
                )
        except Exception as exc:
            logger.error(f"Discord -> Stoat (channel {stoat_id}): {exc}")

    # ── Message deletion: Discord → delete on Stoat ───────────────────────────

    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        """When any Discord message is deleted remove the mirrored Stoat message."""
        discord_msg_id = payload.message_id

        # Loop-break: if we triggered this deletion ourselves, ignore it.
        if discord_msg_id in _discord_deleting:
            _discord_deleting.discard(discord_msg_id)
            return

        discord_ch_id = payload.channel_id
        if discord_ch_id not in DISCORD_TO_STOAT:
            return

        stoat_msg_id = _d2s.get(discord_msg_id)
        if stoat_msg_id is None:
            return  # Not a bridged message

        stoat_ch_id = DISCORD_TO_STOAT[discord_ch_id]

        if self._stoat_bot is None:
            logger.warning("Discord -> Stoat: _stoat_bot reference not set, cannot delete")
            return

        _stoat_deleting.add(stoat_msg_id)
        success = await delete_stoat_message(stoat_ch_id, stoat_msg_id, self._stoat_bot)
        if not success:
            _stoat_deleting.discard(stoat_msg_id)


# ──────────────────────────────────────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────────────────────────────────────


async def main():
    if not all([DISCORD_BOT_TOKEN, STOAT_BOT_TOKEN, DISCORD_CHANNEL_IDS, STOAT_CHANNEL_IDS]):
        raise RuntimeError("Missing configuration – check your .env file.")

    _load_notified_users()

    logger.info(f"Bridge starting with {PAIR_COUNT} channel pair(s)...")
    for i, (d, s) in enumerate(zip(DISCORD_CHANNEL_IDS, STOAT_CHANNEL_IDS), 1):
        logger.info(f"  Pair {i}: Discord {d} <-> Stoat {s}")

    stoat_bot   = StoatBot(token=STOAT_BOT_TOKEN)
    discord_bot = DiscordBot()
    discord_bot._stoat_bot = stoat_bot   # cross-reference for deletion
    stoat_bot._discord_bot = discord_bot  # cross-reference for user-message deletion

    await asyncio.gather(
        _run_stoat_with_restart(stoat_bot),
        _stoat_watchdog(stoat_bot),
        discord_bot.start(DISCORD_BOT_TOKEN),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bridge stopped")