# .env Setup Guide for Law Discord Bot

## Overview

The Law Bot now supports configuration via a `.env` file, making it easy to manage sensitive credentials and settings without hardcoding them in your code.

## Quick Start

### 1. Install Dependencies

First, ensure you have `python-dotenv` installed:

```bash
pip install -r requirements.txt
```

This installs both `discord.py` and `python-dotenv`.

### 2. Create Your .env File

Copy the template and create your actual `.env` file:

```bash
cp .env.example .env
```

### 3. Add Your Bot Token

Edit `.env` and add your Discord bot token:

```env
DISCORD_TOKEN=your_actual_bot_token_here
```

### 4. Run the Bot

```bash
python main.py
```

The bot will automatically load environment variables from `.env` and start.

## Environment Variables Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DISCORD_TOKEN` | Your Discord bot token | `MzkyNzc4OTMwMzA3MDI...` |

### Optional Variables

#### Bot Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `BOT_STATUS` | Bot status message | `middleman services` |
| `BOT_PREFIX` | Command prefix (if overriding config.py) | `+` |

#### Role IDs (for role-based features)

| Variable | Description |
|----------|-------------|
| `STAFF_ROLE` | Staff role ID |
| `HELPER_ROLE` | Helper role ID |
| `MIDDLEMAN_ROLE` | Middleman role ID |
| `CLIENT_ROLE` | Client role ID |
| `HITTER_ROLE` | Hitter role ID |
| `VIP_ROLE` | VIP role ID |
| `MEMBER_ROLE` | Member role ID |

#### Channel IDs

| Variable | Description |
|----------|-------------|
| `TICKET_CATEGORY` | Ticket creation category |
| `LOG_CHANNEL` | Logging channel |
| `VOUCH_CHANNEL` | Vouches channel |
| `TRANSCRIPT_CHANNEL` | Transcript storage channel |
| `HITTER_WELCOME_CHANNEL` | Hitter welcome message channel |
| `BRAINROT_CATEGORY` | Brainrot category |
| `HIT_LOGGING_CHANNEL` | Sticky hit logging channel |

#### Feature Toggles

| Variable | Description | Values |
|----------|-------------|--------|
| `STICKY_HIT_LOGGING_ENABLED` | Enable sticky hit messages | `true` or `false` |

#### Image URLs

| Variable | Description |
|----------|-------------|
| `PANEL_THUMBNAIL` | MM panel thumbnail URL |
| `PANEL_IMAGE` | MM panel main image URL |
| `INDEX_THUMBNAIL` | Index panel thumbnail URL |
| `INDEX_IMAGE` | Index panel main image URL |
| `REPORT_THUMBNAIL` | Report panel thumbnail URL |
| `REPORT_IMAGE` | Report panel main image URL |

## Complete .env Example

```env
# REQUIRED
DISCORD_TOKEN=MzkyNzc4OTMwMzA3MDI0NzU1MzQ3Mjc5NDk=

# Optional Bot Configuration
BOT_STATUS=middleman services

# Role IDs
STAFF_ROLE=123456789
HELPER_ROLE=987654321
MIDDLEMAN_ROLE=456789123
CLIENT_ROLE=789123456
HITTER_ROLE=321456789
VIP_ROLE=654789123
MEMBER_ROLE=147258369

# Channel IDs
TICKET_CATEGORY=123456789
LOG_CHANNEL=987654321
VOUCH_CHANNEL=456789123
TRANSCRIPT_CHANNEL=789123456
HITTER_WELCOME_CHANNEL=321456789
BRAINROT_CATEGORY=654789123
HIT_LOGGING_CHANNEL=258369147

# Feature Toggles
STICKY_HIT_LOGGING_ENABLED=true

# Image URLs
PANEL_THUMBNAIL=https://imgur.com/abc123.png
PANEL_IMAGE=https://imgur.com/def456.png
INDEX_THUMBNAIL=https://imgur.com/ghi789.png
INDEX_IMAGE=https://imgur.com/jkl012.png
REPORT_THUMBNAIL=https://imgur.com/mno345.png
REPORT_IMAGE=https://imgur.com/pqr678.png
```

## Configuration Hierarchy

The bot loads configuration in this order (first match wins):

1. **Environment Variables** (.env file or system environment)
2. **config.py** (Python configuration file)
3. **Default values** (hardcoded in the code)

This means:
- Set sensitive data in `.env` (tokens, IDs)
- Set customization in `config.py` (text, colors, descriptions)
- .env values override config.py values if both exist

## Security Best Practices

### DO ✅

- ✅ Add `.env` to `.gitignore`
- ✅ Use strong, unique bot tokens
- ✅ Never commit `.env` to version control
- ✅ Keep your bot token secret
- ✅ Use `.env.example` for sharing templates

### DON'T ❌

- ❌ Commit `.env` file to Git
- ❌ Share your bot token
- ❌ Push credentials to public repositories
- ❌ Use the same token for multiple bots
- ❌ Leave `.env` unprotected on servers

## .gitignore Setup

Make sure your `.gitignore` includes:

```
# Environment variables
.env
.env.local
.env.*.local

# Keep the template but not the actual file
!.env.example
```

This ensures your `.env` file is never accidentally committed.

## How It Works

The bot uses `python-dotenv` to automatically load variables from `.env`:

```python
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Access variables
token = os.getenv("DISCORD_TOKEN")
```

When the bot starts, it:
1. Loads the `.env` file
2. Sets all variables as environment variables
3. Your code can access them with `os.getenv()`

## Troubleshooting

### "DISCORD_TOKEN not found!"

**Cause**: The bot couldn't find your token.

**Solutions**:
1. Check that `.env` file exists in the same directory as `main.py`
2. Verify `DISCORD_TOKEN=` is correctly formatted
3. Ensure no extra spaces: `DISCORD_TOKEN=token_here` (not `DISCORD_TOKEN = token_here`)
4. Restart the bot after editing `.env`

### Bot starts but variable not loading

**Cause**: Variable is not defined in `.env`.

**Solutions**:
1. Check spelling (case-sensitive on Linux/Mac)
2. Ensure variable is on its own line
3. No quotes needed: `STAFF_ROLE=123456` (not `STAFF_ROLE="123456"`)

### .env changes not reflected

**Cause**: Bot is still using cached values.

**Solution**: Restart the bot - changes to `.env` only load on startup.

## Accessing .env Variables in Code

### From main.py (already configured)

```python
import os
from dotenv import load_dotenv

load_dotenv()  # Already called at startup

token = os.getenv("DISCORD_TOKEN")
status = os.getenv("BOT_STATUS", "middleman services")  # With default
```

### From config.py

If you want to use .env variables in `config.py`:

```python
import os
from dotenv import load_dotenv

load_dotenv()

ROLES = {
    "STAFF_ROLE": int(os.getenv("STAFF_ROLE", 0)) or None,
    "HELPER_ROLE": int(os.getenv("HELPER_ROLE", 0)) or None,
    # ... etc
}
```

## Deployment

### Local Development
1. Copy `.env.example` to `.env`
2. Fill in your local values
3. Run: `python main.py`

### Docker Deployment
```dockerfile
# Pass .env to container
docker run --env-file .env your-bot-image
```

### Heroku Deployment
Set Config Vars in Heroku Dashboard:
```
Settings → Config Vars → Add:
DISCORD_TOKEN = your_token_here
STAFF_ROLE = 123456...
# etc
```

### Linux Server (systemd)
Create `/etc/systemd/system/law-bot.service`:
```ini
[Service]
EnvironmentFile=/path/to/.env
ExecStart=/usr/bin/python3 /path/to/main.py
```

## FAQ

**Q: Can I use .env for all configuration?**
A: Yes! You can override any config.py value by setting it in .env and updating the code.

**Q: Should I commit .env.example?**
A: Yes! It helps others know what variables they need to set.

**Q: Can I have multiple .env files?**
A: `load_dotenv()` loads `.env` by default. You can specify: `load_dotenv('.env.production')`

**Q: Does .env override config.py?**
A: Currently, .env sets environment variables that the code can read. To have them override config.py, you'd need to update config.py to check environment variables first.

**Q: Is it safe to use .env in production?**
A: Yes, if your `.env` file is not in your repository and proper file permissions are set (e.g., `chmod 600 .env`).

## Additional Resources

- [python-dotenv Documentation](https://python-dotenv.readthedocs.io/)
- [Discord.py Documentation](https://discordpy.readthedocs.io/)
- [Environment Variables Best Practices](https://12factor.net/config)

---

**Last Updated**: February 4, 2026
**Status**: ✅ Ready for Use
