# 🚀 Replit Setup Guide for Law Discord Bot

## Step 1: Create a New Replit Project

1. Go to [replit.com](https://replit.com)
2. Click **"Create Repl"**
3. Select **Python** as the language
4. Name it: **Law-Discord-Bot**
5. Click **"Create Repl"**

---

## Step 2: Upload Files

### Files to Upload:
- `main.py` - Main bot code
- `config.py` - Configuration file (already updated!)
- `requirements.txt` - Dependencies
- `.env.example` - Template for environment variables

### How to Upload:
1. In Replit, click the **Files** icon (left sidebar)
2. Click **Upload file** button
3. Select and upload each file

---

## Step 3: Install Dependencies

In the Replit Shell (bottom terminal), run:

```bash
pip install -r requirements.txt
```

This will install:
- discord.py
- python-dotenv
- And any other required packages

---

## Step 4: Setup Environment Variables

### Option A: Using .env file (Recommended)

1. Copy the contents of `.env.example`
2. Create a new file called `.env`
3. Paste the contents
4. Replace `YOUR_DISCORD_TOKEN` with your actual bot token

```
DISCORD_TOKEN=your_bot_token_here
BOT_STATUS=middleman services
BOT_PREFIX=+
```

### Option B: Using Replit Secrets

1. Click the **Lock icon** in the left sidebar (Secrets)
2. Add each variable:
   - Key: `DISCORD_TOKEN`
   - Value: `your_bot_token_here`

---

## Step 5: Get Your Discord Bot Token

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"**
3. Name it **"Law"**
4. Go to **"Bot"** tab
5. Click **"Add Bot"**
6. Under **TOKEN**, click **"Copy"**
7. Paste it into your `.env` file or Replit Secrets

---

## Step 6: Enable Intents

In Discord Developer Portal:

1. Go to your bot's **"Bot"** tab
2. Scroll to **"GATEWAY INTENTS"**
3. Enable these intents:
   - ✅ Message Content Intent
   - ✅ Guild Members Intent
   - ✅ Server Members Intent
   - ✅ Guilds
   - ✅ Direct Messages

---

## Step 7: Get Your Bot Invite Link

1. Go to **"OAuth2"** → **"URL Generator"**
2. Select scopes: `bot`
3. Select permissions:
   - ✅ Send Messages
   - ✅ Embed Links
   - ✅ Manage Messages
   - ✅ Manage Channels
   - ✅ Manage Roles
   - ✅ Create Public Threads
   - ✅ Read Message History
   - ✅ Add Reactions

4. Copy the generated URL and open it to invite the bot to your server

---

## Step 8: Run the Bot

In Replit Shell:

```bash
python main.py
```

You should see:
```
✅ Bot is running...
🔌 Connected to Discord
```

---

## Step 9: Keep Bot Running 24/7 on Replit

### Free Option (Limited):
Replit keeps your bot running while you're active. After 1 hour of inactivity, it goes to sleep.

### Better Option: Use Uptimer Service

1. Go to [uptimerobot.com](https://uptimerobot.com)
2. Create free account
3. Add new monitor:
   - URL: Your Replit URL (found in top-right)
   - Interval: 5 minutes
4. This pings your bot every 5 minutes to keep it alive

### Best Option: Always-on

Upgrade your Replit account to **Replit Pro** for:
- Always-on deployment
- More storage
- Better performance

---

## Configuration in config.py

Your `config.py` has been updated with:

### Support Panel
- Custom title and description
- 4 ticket categories
- Clear rules and guidelines
- Customizable colors and images

### Index Panel
- Welcome message
- All 12 base types
- "How it works" steps
- Image support

### To Customize:
Edit `config.py` and change:

```python
SUPPORT_PANEL = {
    "TITLE": "Server Support",  # Change this
    "IMAGE": "https://i.imgur.com/...",  # Add your image
    "COLOR": 0x5B3BC5,  # Change color (hex)
}

INDEX_PANEL = {
    "TITLE": "📑 INDEXING SERVICE PANEL",  # Change this
    "IMAGE": "https://i.imgur.com/...",  # Add your image
}
```

---

## Testing Your Bot

### Test Commands:
```
+report           - Opens report panel
+embed            - Opens embed creator
+index            - Opens index service panel
+support          - Opens support panel
```

### Common Issues:

**Bot doesn't respond:**
- Check bot has MESSAGE_CONTENT intent enabled
- Check bot is in the server
- Check prefix is correct (+)

**Missing permissions:**
- Make sure bot role is above other roles
- Check bot has necessary Discord permissions

**Token error:**
- Double-check token in `.env` or Secrets
- Make sure no spaces or extra characters

---

## Files Overview

| File | Purpose |
|------|---------|
| `main.py` | Main bot code (2,000+ lines) |
| `config.py` | All configurations & customization |
| `requirements.txt` | Python dependencies |
| `.env` | Environment variables (keep private!) |
| `.env.example` | Template for `.env` |

---

## Next Steps

1. ✅ Upload files to Replit
2. ✅ Install dependencies
3. ✅ Setup `.env` with bot token
4. ✅ Enable intents in Discord Developer Portal
5. ✅ Run `python main.py`
6. ✅ Test commands in your Discord server
7. ✅ Setup uptimer for 24/7 uptime

---

## Support

If you have issues:

1. Check the `.env` file has your bot token
2. Verify all intents are enabled
3. Make sure bot is in your Discord server
4. Check file names are correct (case-sensitive on Linux)
5. Review error messages in the Replit console

---

**Your bot is ready to go! Happy hosting! 🎉**
