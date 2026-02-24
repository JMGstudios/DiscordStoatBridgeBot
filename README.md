# Discord ↔ Stoat Bridge
A lightweight bidirectional bridge that forwards messages between Discord and Stoat channels using webhooks and masquerade.

## How it works
```
Discord user → Discord Bot → Stoat channel  (via Stoat masquerade)
Stoat user   → Stoat Bot   → Discord channel (via Discord webhook)
```
Messages are forwarded in real time. Usernames and avatars are carried over so it looks native on both platforms.

### Replies
| Direction | Behaviour |
|---|---|
| Discord → Stoat | Native reply when the original message is in cache; quote fallback otherwise |
| Stoat → Discord | Quote fallback (`-# ↩ **Author**: *snippet*`) – Discord webhooks do not support native replies |

The bridge caches the last **500** message ID pairs in memory (configurable). Replies to messages older than that are sent without a reply indicator.

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

---

## Setup

### Requirements
- Python 3.10+
- A Discord bot with the **Message Content**, **Server Members**, **Guilds**, and **Webhooks** intents enabled
- A Stoat bot

### Install dependencies
```bash
pip install discord.py stoat.py aiohttp python-dotenv
```

---

### Local Setup

**1. Clone the repo**
```bash
git clone https://github.com/JMGstudios/DiscordStoatBridgeBot.git
cd DiscordStoatBridgeBot
```

**2. Run the bridge**
```bash
python main.py
```

If no `.env` file is found, or if required values are missing, the bridge will automatically start an **interactive setup wizard** on first launch:

```
============================================================
  Stoat ↔ Discord Bridge – First-Time / Repair Setup
============================================================

› Discord Bot Token
  Get it at: https://discord.com/developers/applications
  Discord Bot Token:
  ⌨  Typing is hidden for security – this is normal, just type and press Enter.
  >

› Stoat Bot Token
  ...

› Channel Pairs
  You will now link Discord channels to Stoat channels one pair at a time.

  ── Pair 1 (first pair) ──
  Discord Channel ID for pair 1: 123456789012345678
  Stoat   Channel ID for pair 1: ABCDEFGHIJ1234567890ABCDEF

  ✔  Pair 1 saved: Discord 123456789012345678 ↔ Stoat ABCDEFGHIJ1234567890ABCDEF

  Add another channel pair? [y/N]:

  ✔  Configuration saved to /your/path/.env
============================================================
```

The generated `.env` is saved next to `main.py`. On every subsequent start the bridge prints the config path so you always know which file it loaded:
```
Config loaded from: /your/path/.env
```

> **Note on token input:** when entering bot tokens the cursor won't move and nothing will appear on screen. This is intentional — input is hidden for security. Just type normally and press Enter.

**3. Discord bot permissions**

Make sure your bot has the following permissions in the target channel:
- Read Messages
- Send Messages
- Manage Webhooks

---

### Docker Setup

**1. Pull the image**
```bash
docker pull ghcr.io/jmgstudios/discordstoatbridgebot:latest
```

**2. Run it**
```bash
docker run -it ghcr.io/jmgstudios/discordstoatbridgebot:latest
```

On first launch the setup wizard will guide you through the configuration. The `-it` flag is required for the interactive prompts to work. The generated `.env` is saved inside the container and reused on every subsequent start.

---

### Configuration reference

| Variable | Required | Description |
|---|---|---|
| `DISCORD_BOT_TOKEN` | ✅ | Token from the [Discord Developer Portal](https://discord.com/developers/applications) |
| `STOAT_BOT_TOKEN` | ✅ | Token from your Stoat bot settings |
| `DISCORD_CHANNEL_IDS` | ✅ | Comma-separated Discord channel IDs |
| `STOAT_CHANNEL_IDS` | ✅ | Comma-separated Stoat channel IDs |
| `REVOLT_API_URL` | ➖ | Revolt API base URL. Defaults to `https://api.revolt.chat` |

**Channel pairing:** the IDs are matched by position — the first Discord ID is bridged with the first Stoat ID, the second with the second, and so on. Both lists must have the same length. The setup wizard handles this automatically when configuring pairs one by one.

---

## Notes
- The bridge creates a webhook named `Stoat Bridge` in your Discord channel automatically. If one already exists from a previous run it will be reused.
- Messages originating from the bridge webhook are ignored to prevent forwarding loops.
- Message deletion is synced in both directions. If a message is deleted on one platform it is automatically removed on the other.
- Stoat custom emoji names are resolved via the Stoat API and cached in memory for the duration of the process.
- First-time users on both platforms receive a one-time DM explaining what the bridge does and how their messages are handled.
