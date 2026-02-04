# 🤖 MM Bot - Discord Middleman Trading Bot

A comprehensive Discord bot for managing middleman services, profit tracking, ticket systems, and automated messages.

## 📋 Features

### 🎫 MM Panel
- Beautiful embed with customizable images
- Deal type dropdown (Robux, Crypto, Game, Other)
- Modal form for trade details
- Auto-creates ticket channels with welcome message
- Claim/Unclaim/Close buttons in tickets

### 🎯 Hit Panel
- Recruit panel with "Join us" / "Not interested" buttons
- Auto-assigns client role when clicking "Join us"
- Shows "@user clicked no" when declining

### ⚙️ Fully Customizable via config.py
- All images (thumbnails, panel images)
- All text/messages
- Role IDs
- Channel IDs
- Colors
- Deal types
- And more!

---

## 🚀 Quick Start

### 1. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" → Name it → Create
3. Go to **Bot** → Click "Add Bot"
4. Enable these **Privileged Gateway Intents**:
   - ✅ Message Content Intent
   - ✅ Server Members Intent
5. Copy the bot token

### 2. Invite the Bot

1. Go to **OAuth2** → **URL Generator**
2. Select scopes: `bot`, `applications.commands`
3. Select permissions:
   - Manage Channels
   - Manage Roles
   - Send Messages
   - Embed Links
   - Add Reactions
   - Read Message History
   - Manage Messages
4. Open the generated URL to invite

### 3. Configure & Run

```bash
# Install dependencies
pip install -r requirements.txt

# Edit config.py with your settings (role IDs, channel IDs, images)

# Set your token
export DISCORD_TOKEN='your_bot_token_here'

# Run the bot
python main.py
```

---

## 📁 Files

| File | Description |
|------|-------------|
| `main.py` | Main bot code |
| `config.py` | **All customizable settings** |
| `requirements.txt` | Dependencies |
| `.env.example` | Environment template |

---

## ⚙️ Configuration (config.py)

### Prefixes
```python
PREFIXES = ["+", "?", "$"]  # Bot responds to all three
```

### Role IDs
```python
ROLES = {
    "STAFF_ROLE": 1234567890,        # Your staff role ID
    "HELPER_ROLE": 1234567890,       # Helper role ID
    "MIDDLEMAN_ROLE": 1234567890,    # MM role (pinged in tickets)
    "CLIENT_ROLE": 1234567890,       # Given when clicking "Join us"
}
```

### Channel IDs
```python
CHANNELS = {
    "TICKET_CATEGORY": 1234567890,   # Where tickets are created
    "LOG_CHANNEL": 1234567890,       # Logging channel
}
```

### Images
```python
IMAGES = {
    "PANEL_THUMBNAIL": "https://i.imgur.com/...",   # MM panel thumbnail
    "PANEL_IMAGE": "https://i.imgur.com/...",       # MM panel main image
    "TICKET_THUMBNAIL": "https://i.imgur.com/...",  # Ticket welcome image
    "HIT_THUMBNAIL": "https://i.imgur.com/...",     # Hit panel thumbnail
}
```

### Colors
```python
COLORS = {
    "PRIMARY": 0x9B59B6,    # Purple
    "SUCCESS": 0x2ECC71,    # Green
    "ERROR": 0xE74C3C,      # Red
    "WARNING": 0xF39C12,    # Orange
}
```

### Deal Types (Dropdown Options)
```python
DEAL_TYPES = [
    {"label": "Robux deal", "description": "Trading Robux", "emoji": "💎", "value": "robux"},
    {"label": "Crypto deal", "description": "Trading Cryptocurrency", "emoji": "🪙", "value": "crypto"},
    # Add more...
]
```

### Ticket Questions (Modal Fields)
```python
TICKET_QUESTIONS = [
    {"label": "Trade Details", "placeholder": "What are you trading?", "required": True, "style": "paragraph"},
    {"label": "Other User or ID", "placeholder": "Enter username or ID", "required": True, "style": "short"},
]
```

---

## 📜 Commands

### 🎫 MM Commands (Staff Only)
| Command | Description |
|---------|-------------|
| `+panel` | Post the MM request panel |
| `+mminfo` | Post MM information |
| `+hit` | Post recruit panel with buttons |
| `+claim` | Claim a ticket |
| `+unclaim` | Unclaim a ticket |
| `+transfer @user` | Transfer ticket |
| `+close` | Close a ticket |
| `+howto` | How to guide |
| `+fee` | Fee options |
| `+confirm` | Confirm trade |
| `+questions` | Trade questions |

### 💰 Profit Commands (Staff & Helpers)
| Command | Description |
|---------|-------------|
| `+search @user` | View profit summary |
| `+tprofit @user amount` | Set profit |
| `+addprofit @user amount` | Add to profit |
| `+reset @user` | Reset profile |

### 🎟️ Ticket Controls
| Command | Description |
|---------|-------------|
| `+add @user` or `+add <ID>` | Add user to ticket |
| `+remove @user` | Remove user |

### 🎉 Promo Commands (Staff Only)
| Command | Description |
|---------|-------------|
| `+promo @user @role` | Promote user |
| `+demo @user` | Demote user |

### 🤖 Auto Messages (Helpers)
| Command | Description |
|---------|-------------|
| `+autos` | View auto message status |
| `+vouch start/stop` | Control vouch messages |
| `+alert start/stop` | Control alerts |
| `+welcome start/stop` | Control welcome |
| `+vouchinterval <s>` | Set interval |

### ⚙️ Config (Admin Only)
| Command | Description |
|---------|-------------|
| `+set <key> <value>` | Set config at runtime |
| `+check` | Validate config |
| `+listvariables` | List config keys |
| `+viewvariables` | View current config |
| `+rules` | Post rules |
| `+tos` | Post TOS |
| `+scams` | Post scams guide |

### 📌 Meta
| Command | Description |
|---------|-------------|
| `+viewprefix` | Show prefixes |
| `+ping` | Bot latency |
| `+help` | Help menu |

---

## 🔧 Getting Role/Channel IDs

1. Enable Developer Mode in Discord (Settings → Advanced → Developer Mode)
2. Right-click a role or channel
3. Click "Copy ID"

---

## 📝 License

MIT License - Feel free to modify and use!
