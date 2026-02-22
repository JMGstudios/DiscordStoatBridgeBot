# Discord ↔ Stoat Bridge
A lightweight bidirectional bridge that forwards messages between Discord and Stoat channels using webhooks and masquerade.

> **Note:** The bridge is a **discord.py Cog** and must be loaded into an existing bot. It does not run standalone.

## How it works
```
Discord user → Discord Bot → Stoat channel  (via Stoat masquerade)
Stoat user   → Stoat Bot   → Discord channel (via Discord webhook)
```
Messages are forwarded in real time. Usernames and avatars are carried over so it looks native on both platforms.

### Replies
| Direction | Behaviour |
|---|---|
| Discord → Stoat | Native reply when the original message is in cache; sent without reply otherwise |
| Stoat → Discord | Quote fallback (`-# ↩ **Author**: *snippet*`) – Discord webhooks do not support native replies |

The bridge caches the last **500** message ID pairs in memory (you can change this value). Replies to messages older than that are sent without a reply indicator.

### Files & attachments
| Direction | Behaviour |
|---|---|
| Discord → Stoat | The bare attachment URL is appended to the message text |
| Stoat → Discord | File is downloaded into RAM and re-uploaded as a Discord attachment. Files larger than **25 MiB** are sent as a fallback link instead |

### Mention & emoji resolution
| Direction | What gets resolved |
|---|---|
| Discord → Stoat | `<@id>` → `@Nickname`, `<#id>` → `#channel-name`, `<@&id>` → `@role-name`, `<:n:id>` → `:n:` |
| Stoat → Discord | `<@ULID>` → `@DisplayName`, `:ULID:` → `:emoji-name:` |

## Requirements
- Python 3.10+
- A Discord bot with the **Message Content**, **Server Members**, **Guilds**, and **Webhooks** intents enabled
- A Stoat bot
```
pip install discord.py stoat.py aiohttp python-dotenv
```

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/JMGstudios/DiscordStoatBridgeBot.git
cd DiscordStoatBridgeBot
git checkout cog-extension
```

**2. Create your `.env` file**
```bash
cp .env.example .env
```
Then fill in the values:

| Variable | Description |
|---|---|
| `STOAT_BOT_TOKEN` | Token from your Stoat bot settings |
| `DISCORD_CHANNEL_IDS` | Comma-separated Discord channel IDs to bridge |
| `STOAT_CHANNEL_IDS` | Comma-separated Stoat channel IDs to bridge |
| `REVOLT_API_URL` | *(optional)* Revolt API base URL. Defaults to `https://api.revolt.chat` |

> `DISCORD_BOT_TOKEN` is **not** needed here — the cog uses the token of your existing host bot.

> **Pairing:** position 1 of `DISCORD_CHANNEL_IDS` is bridged with position 1 of `STOAT_CHANNEL_IDS`, position 2 with position 2, and so on. The two lists must have the same length.

The `.env` file must be in the **working directory** from which you start your bot (typically your project root next to `main.py`).

**3. Discord bot permissions**

Make sure your bot has the following permissions in the target channel:
- Read Messages
- Send Messages
- Manage Webhooks

**4. Load the cog**

In your host bot's `main.py` (or wherever you load extensions):
```python
await bot.load_extension("bridge_cog")
```

**5. Logging**

The cog uses its own `bridge` logger but does **not** configure the root logger. Make sure your host bot sets up logging before loading the cog, e.g.:
```python
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("discord").setLevel(logging.WARNING)  # suppress Discord gateway debug spam
```

## Notes
- The bridge creates a webhook named `Stoat Bridge` in your Discord channel automatically. If one already exists from a previous run it will be reused.
- Messages originating from the bridge webhook are ignored to prevent forwarding loops.
- The Stoat bot is started internally by the cog (`cog_load`) and stopped cleanly on unload (`cog_unload`).
- Stoat custom emoji names are resolved via the Stoat API and cached in memory for the duration of the process.
