# Discord ↔ Stoat Bridge

A lightweight bidirectional bridge that forwards messages between a Discord channel and a Stoat channel using webhooks and masquerades to preserve usernames and avatars on both sides.

## How it works

```
Discord user → Discord Bot → Stoat channel  (via Stoat masquerade)
Stoat user   → Stoat Bot   → Discord channel (via Discord webhook)
```

Messages are forwarded in real time. Usernames and avatars are carried over so it looks native on both platforms.

## Requirements

- Python 3.13+
- A Discord bot with the **Message Content**, **Guilds**, and **Webhooks** intents enabled
- A Stoat bot token

```
pip install discord.py stoat.py python-dotenv
```

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/your-username/discord-stoat-bridge.git
cd discord-stoat-bridge
```

**2. Create your `.env` file**
```bash
cp .env.example .env
```
Then fill in the values:

| Variable | Description |
|---|---|
| `DISCORD_BOT_TOKEN` | Token from the [Discord Developer Portal](https://discord.com/developers/applications) |
| `DISCORD_CHANNEL_IDS` | ID of the Discord channel to bridge, add multiple via comma-seperated values. |
| `STOAT_BOT_TOKEN` | Token from your Stoat bot settings |
| `STOAT_CHANNEL_IDS` | ID of the Stoat channel to bridge, add multiple via comma-seperated values.|

NOTE: Pos. 1 of DISCORD_CHANNEL_IDS will be linked to Pos. 1 of STOAT_CHANNEL_IDS, Pos. 2 of DC to Pos. 2 of Stoat and so on

**3. Discord bot permissions**

Make sure your bot has the following permissions in the target channel:
- Read Messages
- Send Messages
- Manage Webhooks

**4. Run**
```bash
python bridge.py
```

## Notes

- Do **not** rename `bridge.py` to `stoat.py` – it will conflict with the `stoat.py` library.
- The bridge creates a webhook named `Stoat Bridge` in your Discord channel automatically. If one already exists (from a previous run), it will be reused.
- Messages from the bridge itself are ignored to prevent loops.
