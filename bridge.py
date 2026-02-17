#!/usr/bin/env python3
"""
Discord <-> Stoat bidirectional bridge (multi-channel).

Requirements:
    pip install discord.py stoat.py python-dotenv

Configuration:
    Copy .env.example to .env and fill in your tokens and IDs.
    Multiple channel pairs are supported via comma-separated values:

        DISCORD_CHANNEL_IDS=111111111111,222222222222,333333333333
        STOAT_CHANNEL_IDS=aaa111,bbb222,ccc333

    Position 1 of Discord is bridged with position 1 of Stoat, and so on.

Usage:
    python bridge.py
"""

import asyncio
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv
import stoat

load_dotenv()

# ----------------------------------------------------------------------
#  CONFIGURATION  (set these in your .env file)
# ----------------------------------------------------------------------

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
STOAT_BOT_TOKEN   = os.getenv("STOAT_BOT_TOKEN", "")

# Parse channel ID lists from comma-separated env vars.
_discord_raw = os.getenv("DISCORD_CHANNEL_IDS")
_stoat_raw   = os.getenv("STOAT_CHANNEL_IDS")

DISCORD_CHANNEL_IDS: list[int] = [int(x.strip()) for x in _discord_raw.split(",") if x.strip()]
STOAT_CHANNEL_IDS:   list[str] = [x.strip() for x in _stoat_raw.split(",") if x.strip()]

# ----------------------------------------------------------------------
#  LOGGING
# ----------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bridge")

# ----------------------------------------------------------------------
#  SHARED STATE
#
#  Both dicts are keyed by the Discord channel ID (int) so that the
#  two bots share a common lookup key
#
#  discord_webhooks : discord_channel_id -> discord.Webhook
#  stoat_channels   : discord_channel_id -> stoat channel object
# ----------------------------------------------------------------------

# Build a bidirectional mapping at startup:
#   discord_channel_id <-> stoat_channel_id
if len(DISCORD_CHANNEL_IDS) != len(STOAT_CHANNEL_IDS):
    raise RuntimeError(
        f"Channel list length mismatch: "
        f"{len(DISCORD_CHANNEL_IDS)} Discord IDs vs {len(STOAT_CHANNEL_IDS)} Stoat IDs."
    )

PAIR_COUNT = len(DISCORD_CHANNEL_IDS)

# stoat_id -> discord_id  (used by StoatBot to look up the right webhook)
STOAT_TO_DISCORD: dict[str, int] = {
    s: d for d, s in zip(DISCORD_CHANNEL_IDS, STOAT_CHANNEL_IDS)
}
# discord_id -> stoat_id  (used by DiscordBot to look up the right stoat channel)
DISCORD_TO_STOAT: dict[int, str] = {
    d: s for d, s in zip(DISCORD_CHANNEL_IDS, STOAT_CHANNEL_IDS)
}

discord_webhooks: dict[int, discord.Webhook] = {}   # discord_channel_id -> Webhook
stoat_channels:  dict[str, object]           = {}   # stoat_channel_id   -> stoat channel

# ----------------------------------------------------------------------
#  STOAT BOT
# ----------------------------------------------------------------------

class StoatBot(stoat.Client):

    async def on_ready(self, event, /):
        logger.info(f"Stoat: connected as {self.me}")
        for stoat_id in STOAT_CHANNEL_IDS:
            try:
                ch = await self.fetch_channel(stoat_id)
                stoat_channels[stoat_id] = ch
                logger.info(f"Stoat: listening in #{ch.name} (id={stoat_id})")
            except Exception as e:
                logger.error(f"Stoat: could not fetch channel {stoat_id} – {e}")

    async def on_message_create(self, event: stoat.MessageCreateEvent, /):
        msg = event.message

        if msg.author_id == self.me.id:
            return
        stoat_id = msg.channel.id
        if stoat_id not in STOAT_TO_DISCORD:
            return
        if not msg.content:
            return

        discord_id  = STOAT_TO_DISCORD[stoat_id]
        webhook     = discord_webhooks.get(discord_id)

        if webhook is None:
            logger.warning(
                f"Stoat -> Discord: dropped (webhook for Discord channel "
                f"{discord_id} not ready)"
            )
            return

        author_name = msg.author.display_name or msg.author.name
        avatar      = msg.author.avatar
        avatar_url  = avatar.url() if avatar else None

        try:
            await webhook.send(
                content=msg.content[:2000],
                username=author_name[:80],
                avatar_url=avatar_url,
                wait=True,
            )
        except Exception as e:
            logger.error(f"Stoat -> Discord (channel {discord_id}): {e}")

# ----------------------------------------------------------------------
#  DISCORD BOT
# ----------------------------------------------------------------------

class DiscordBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.webhooks = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.loop.create_task(self._setup_webhooks())

    async def _setup_webhooks(self):
        await self.wait_until_ready()

        for discord_id in DISCORD_CHANNEL_IDS:
            try:
                channel = (
                    self.get_channel(discord_id)
                    or await self.fetch_channel(discord_id)
                )
                # Reuse an existing bridge webhook if one exists, otherwise create one.
                for wh in await channel.webhooks():
                    if wh.user == self.user:
                        discord_webhooks[discord_id] = wh
                        logger.info(
                            f"Discord: reusing webhook '{wh.name}' "
                            f"for channel {discord_id}"
                        )
                        break
                else:
                    wh = await channel.create_webhook(name="Stoat Bridge")
                    discord_webhooks[discord_id] = wh
                    logger.info(f"Discord: created webhook for channel {discord_id}")
            except Exception as e:
                logger.error(f"Discord: could not set up webhook for channel {discord_id} – {e}")

    async def on_ready(self):
        logger.info(f"Discord: connected as {self.user}")
        logger.info(f"Discord: bridging {PAIR_COUNT} channel pair(s)")

    async def on_message(self, message: discord.Message):
        if message.author.bot or message.webhook_id:
            return
        discord_id = message.channel.id
        if discord_id not in DISCORD_TO_STOAT:
            return
        if not message.content:
            return

        stoat_id = DISCORD_TO_STOAT[discord_id]
        ch       = stoat_channels.get(stoat_id)

        if ch is None:
            logger.warning(
                f"Discord -> Stoat: dropped (Stoat channel {stoat_id} not ready)"
            )
            return

        avatar_url = (
            str(message.author.avatar.url)
            if message.author.avatar
            else str(message.author.default_avatar.url)
        )

        try:
            await ch.send(
                content=message.content[:2000],
                masquerade=stoat.Masquerade(
                    name=message.author.display_name[:32],
                    avatar=avatar_url,
                ),
            )
        except Exception as e:
            logger.error(f"Discord -> Stoat (channel {stoat_id}): {e}")

# ----------------------------------------------------------------------
#  MAIN
# ----------------------------------------------------------------------

async def main():
    if not all([DISCORD_BOT_TOKEN, STOAT_BOT_TOKEN, DISCORD_CHANNEL_IDS, STOAT_CHANNEL_IDS]):
        raise RuntimeError("Missing configuration – check your .env file.")

    logger.info(f"Bridge starting with {PAIR_COUNT} channel pair(s)...")
    for i, (d, s) in enumerate(zip(DISCORD_CHANNEL_IDS, STOAT_CHANNEL_IDS), 1):
        logger.info(f"  Pair {i}: Discord {d} <-> Stoat {s}")

    await asyncio.gather(
        StoatBot(token=STOAT_BOT_TOKEN).start(),
        DiscordBot().start(DISCORD_BOT_TOKEN),
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bridge stopped")
