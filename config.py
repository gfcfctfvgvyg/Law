"""
MM Bot Configuration File
Edit these values to customize your bot!

NOTE: Role IDs and Channel IDs set here are DEFAULTS.
Use +set commands in each server to configure per-server settings.
Per-server settings override these defaults.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# BOT SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

# Command prefixes (bot responds to all of these)
PREFIXES = ["+", "?", "$"]

# Bot status message
BOT_STATUS = "middleman services"

# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULT ROLE IDS - These are defaults, use +set in each server to override
# ═══════════════════════════════════════════════════════════════════════════════

ROLES = {
    "STAFF_ROLE": None,           # Staff role ID (e.g., 1234567890)
    "HELPER_ROLE": None,          # Helper role ID
    "MIDDLEMAN_ROLE": None,       # Middleman team role ID (pinged in tickets)
    "CLIENT_ROLE": None,          # Role given when clicking "Join us" on mercy panel
    "HITTER_ROLE": None,          # Role given when accepting hitter invite
    "VIP_ROLE": None,             # VIP role ID
    "MEMBER_ROLE": None,          # Default member role ID
}

# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULT CHANNEL IDS - These are defaults, use +set in each server to override
# ═══════════════════════════════════════════════════════════════════════════════

CHANNELS = {
    "TICKET_CATEGORY": None,      # Category ID where tickets are created
    "LOG_CHANNEL": None,          # Logging channel ID
    "VOUCH_CHANNEL": None,        # Vouches channel ID
    "TRANSCRIPT_CHANNEL": None,   # Ticket transcripts channel ID
    "HITTER_WELCOME_CHANNEL": None,  # Channel where hitter welcome message is sent
    "BRAINROT_CATEGORY": None,    # Category for brainrot index tickets
}

# ═══════════════════════════════════════════════════════════════════════════════
# EMBED IMAGES & BRANDING
# ═══════════════════════════════════════════════════════════════════════════════

IMAGES = {
    # MM Panel Images
    "PANEL_THUMBNAIL": "https://i.imgur.com/your_thumbnail.png",
    "PANEL_IMAGE": "https://i.imgur.com/your_main_image.png",
    
    # Ticket Welcome Images
    "TICKET_THUMBNAIL": "https://i.imgur.com/your_ticket_thumb.png",
    
    # Mercy Panel Images
    "MERCY_THUMBNAIL": "https://i.imgur.com/your_mercy_thumb.png",
    "MERCY_IMAGE": "https://i.imgur.com/your_mercy_image.png",
    
    # MM Info Images
    "MMINFO_THUMBNAIL": "https://i.imgur.com/your_mminfo_thumb.png",
    
    # Fee Panel Images
    "FEE_THUMBNAIL": "https://i.imgur.com/your_fee_thumb.png",
    
    # Brainrot Index Images
    "BRAINROT_THUMBNAIL": "https://i.imgur.com/your_brainrot_thumb.png",
    "BRAINROT_IMAGE": "https://i.imgur.com/your_brainrot_image.png",
    
    # General Images
    "BOT_AVATAR": "https://i.imgur.com/your_avatar.png",
    "RULES_IMAGE": "https://i.imgur.com/your_rules.png",
}

# ═══════════════════════════════════════════════════════════════════════════════
# EMBED COLORS (Hex values)
# ═══════════════════════════════════════════════════════════════════════════════

COLORS = {
    "PRIMARY": 0x9B59B6,          # Purple - main embeds
    "SUCCESS": 0x2ECC71,          # Green - success messages
    "ERROR": 0xE74C3C,            # Red - error messages
    "WARNING": 0xF39C12,          # Orange - warnings
    "INFO": 0x3498DB,             # Blue - info messages
    "TICKET": 0x9B59B6,           # Purple - ticket embeds
    "DARK": 0x2C2F33,             # Dark - professional embeds
    "BRAINROT": 0xFF6B6B,         # Red/Pink - brainrot tickets
}

# ═══════════════════════════════════════════════════════════════════════════════
# MM PANEL CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

MM_PANEL = {
    "TITLE": "Middleman Request – Roblox Trade",
    "DESCRIPTION": """• : To request a middleman from this server, click the blue "Request Middleman" button on this message.

**How does middleman work?**
•   : Example: Trade is 500m/s Dragon Cannelloni for Robux.
Seller gives 500m/s Dragon Cannelloni to middleman
Buyer pays seller robux (After middleman confirms receiving Dragon Cannelloni)
Middleman gives buyer 500m/s Dragon Cannelloni(After seller confirmed receiving robux)

**NOTES:**
You must both agree on the deal before using a middleman. Troll tickets will have consequences.
Specify what you're trading (e.g. FR Frost Dragon in Adopt me > $20 USD LTC).
Don't just put "adopt me" in the embed.""",
    "FOOTER": "Halo's MM Team!",
    "BUTTON_LABEL": "Request a middleman",
    "BUTTON_EMOJI": "🎫",
}

# ═══════════════════════════════════════════════════════════════════════════════
# INDEX TICKET PANEL CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

INDEX_PANEL = {
    "TITLE": "📑 INDEXING SERVICE PANEL",
    "DESCRIPTION": """Welcome to the official indexing system!

🎯 **Select a base from the menu below to open a ticket.**

⚡ Our admins will assist you quickly.
🔐 Your ticket will be private.

**Available Bases:**
💎 Diamond Base 
🌈 Rainbow Base
🍭 Candy Base
🌋 Lava Base
🌌 Galaxy Base
👻 Cursed Base
🌊 Aqua Base
🌮 Taco Base
🎄 Christmas Base
🎃 Halloween Base
☯️ Ying Yang Base
☢️ Radioactive Base

Click the button below to get started!""",
    "FOOTER": "Index System • Fast • Secure • Professional",
    "BUTTON_LABEL": "Create Index Ticket",
    "BUTTON_EMOJI": "📑",
}

# Index base options (dropdown)
INDEX_BASES = [
    {"label": "💎 Diamond Base", "description": "Diamond themed base", "emoji": "💎", "value": "diamond"},
    {"label": "🌈 Rainbow Base", "description": "Rainbow themed base", "emoji": "🌈", "value": "rainbow"},
    {"label": "🍭 Candy Base", "description": "Candy themed base", "emoji": "🍭", "value": "candy"},
    {"label": "🌋 Lava Base", "description": "Lava themed base", "emoji": "🌋", "value": "lava"},
    {"label": "🌌 Galaxy Base", "description": "Galaxy themed base", "emoji": "🌌", "value": "galaxy"},
    {"label": "👻 Cursed Base", "description": "Cursed themed base", "emoji": "👻", "value": "cursed"},
    {"label": "🌊 Aqua Base", "description": "Aqua themed base", "emoji": "🌊", "value": "aqua"},
    {"label": "🌮 Taco Base", "description": "Taco themed base", "emoji": "🌮", "value": "taco"},
    {"label": "🎄 Christmas Base", "description": "Christmas themed base", "emoji": "🎄", "value": "christmas"},
    {"label": "🎃 Halloween Base", "description": "Halloween themed base", "emoji": "🎃", "value": "halloween"},
    {"label": "☯️ Ying Yang Base", "description": "Ying Yang themed base", "emoji": "☯️", "value": "yingyang"},
    {"label": "☢️ Radioactive Base", "description": "Radioactive themed base", "emoji": "☢️", "value": "radioactive"},
]

# Index ticket form questions
INDEX_QUESTIONS = [
    {
        "label": "What is your Payment?",
        "placeholder": "5 Garamas",
        "required": True,
        "style": "short",
        "max_length": 200
    },
    {
        "label": "What is your Collateral?",
        "placeholder": "Dragon Cannelloni",
        "required": True,
        "style": "short",
        "max_length": 200
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# SUPPORT TICKET PANEL CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

SUPPORT_PANEL = {
    "TITLE": "🆘 Server Support",
    "DESCRIPTION": """Need assistance or facing an issue? Choose an option below to open a ticket.

**How it works:** Select the correct option and our staff will respond promptly.

⚠️ **Disclaimer:** Trolls will be banned instantly.

Click the button below to get started!""",
    "FOOTER": "Support • Professional Service",
    "BUTTON_LABEL": "Open Support Ticket",
    "BUTTON_EMOJI": "🆘",
}

# Support ticket form questions
SUPPORT_QUESTIONS = [
    {
        "label": "Describe your issue in detail",
        "placeholder": "Provide as much detail as possible...",
        "required": True,
        "style": "paragraph",
        "max_length": 1000
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# BRAINROT INDEX PANEL CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

BRAINROT_PANEL = {
    "TITLE": "🧠 Steal a Brainrot Index",
    "DESCRIPTION": """Welcome to the Brainrot Index stealing service!

**How it works:**
1. Select your base type below
2. Fill out the required information
3. Wait for a staff member to assist you

**Requirements:**
• Valid payment method ready
• Collateral if required
• Be patient and responsive

Click the button below to get started!""",
    "FOOTER": "Brainrot Index Services",
    "BUTTON_LABEL": "Create Request",
    "BUTTON_EMOJI": "🧠",
}

# Brainrot base options (dropdown)
BRAINROT_BASES = [
    {
        "label": "Skibidi Base",
        "description": "Skibidi toilet themed base",
        "emoji": "🚽",
        "value": "skibidi"
    },
    {
        "label": "Sigma Base",
        "description": "Sigma grindset themed base",
        "emoji": "💪",
        "value": "sigma"
    },
    {
        "label": "Ohio Base",
        "description": "Only in Ohio themed base",
        "emoji": "🌽",
        "value": "ohio"
    },
    {
        "label": "Rizz Base",
        "description": "Maximum rizz themed base",
        "emoji": "😎",
        "value": "rizz"
    },
    {
        "label": "Gyatt Base",
        "description": "Gyatt themed base",
        "emoji": "🍑",
        "value": "gyatt"
    },
    {
        "label": "Other Base",
        "description": "Other custom base",
        "emoji": "❓",
        "value": "other"
    },
]

# Brainrot ticket form questions
BRAINROT_QUESTIONS = [
    {
        "label": "What is your payment?",
        "placeholder": "e.g., 500 Robux, $10 PayPal, Crypto, etc.",
        "required": True,
        "style": "short",
        "max_length": 200
    },
    {
        "label": "What is your collateral?",
        "placeholder": "e.g., FR Frost Dragon, Godly MM2, etc. (or N/A if none)",
        "required": True,
        "style": "short",
        "max_length": 200
    },
    {
        "label": "Additional details",
        "placeholder": "Any other information we should know?",
        "required": False,
        "style": "paragraph",
        "max_length": 500
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# MM INFO CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

MMINFO_PANEL = {
    "TITLE": "✦ :  What is a MM?",
    "DESCRIPTION": """A MM is a trusted member of our server handpicked by server owners. MM's are required to follow Discord's Terms of Service.

**How does middleman work?**
× :  Example: Trade is NFR Crow for Robux.
• Seller gives NFR Crow to middleman
• Buyer pays seller robux (After middleman confirms receiving pet)
• Middleman gives buyer NFR Crow (After seller confirmed receiving robux)

**NOTES:**
1. You must both agree on the deal before using a middleman. Troll tickets will have consequences.
2. Specify what you're trading (e.g. FR Frost Dragon in Adopt me > $20 USD LTC). Don't just put "adopt me" in the embed.""",
    "UNDERSTAND_BUTTON": "I understand",
    "DONT_UNDERSTAND_BUTTON": "I don't understand",
}

# ═══════════════════════════════════════════════════════════════════════════════
# FEE PANEL CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

FEE_PANEL = {
    "TITLE": "💵 Middleman Service Fee",
    "DESCRIPTION": """Please be patient while the Middleman calculates the exact service fee.

📝 Before proceeding, agree on how the fee will be covered:

**Options:**
• Split Payment (50/50)
• Full Payment (100%)

⚠️ Once you confirm, this cannot be reversed.

🔒 Your items are securely held during the trade.""",
    "SPLIT_BUTTON": "50/50",
    "SPLIT_EMOJI": "⚖️",
    "FULL_BUTTON": "100%",
    "FULL_EMOJI": "💰",
}

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIRM PANEL CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

CONFIRM_PANEL = {
    "TITLE": "🔐 Trade Confirmation",
    "DESCRIPTION": """Before we finalize this trade, both parties must confirm.

**By confirming, you acknowledge:**
• All items/payments have been received as agreed
• You have verified the items are correct
• You release the middleman from holding

⏳ Waiting for both traders to confirm...""",
    "CONFIRM_BUTTON": "Confirm Trade",
    "CONFIRM_EMOJI": "✅",
    "CANCEL_BUTTON": "Cancel",
    "CANCEL_EMOJI": "❌",
    "CONFIRMED_MESSAGE": "✅ {user} has confirmed the trade.",
    "CANCELLED_MESSAGE": "❌ {user} has cancelled. Please contact staff.",
    "BOTH_CONFIRMED": "🎉 **Trade Complete!** Both parties have confirmed. Thank you for using our services!",
}

# ═══════════════════════════════════════════════════════════════════════════════
# DEAL TYPES (Dropdown options when creating ticket)
# ═══════════════════════════════════════════════════════════════════════════════

DEAL_TYPES = [
    {
        "label": "Robux deal",
        "description": "Trading Robux",
        "emoji": "💎",
        "value": "robux"
    },
    {
        "label": "Crypto deal",
        "description": "Trading Cryptocurrency",
        "emoji": "🪙",
        "value": "crypto"
    },
    {
        "label": "Game deal",
        "description": "Trading in-game items",
        "emoji": "🎮",
        "value": "game"
    },
    {
        "label": "Other deal",
        "description": "Other types of trades",
        "emoji": "📦",
        "value": "other"
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# TICKET CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

TICKET = {
    "WELCOME_TITLE": "Welcome to your Ticket!",
    "PING_ROLE": True,
    "AUTO_CLOSE_HOURS": 1,
    "TICKET_PREFIX": "ticket-",
    "BRAINROT_PREFIX": "brainrot-",
    "LOCK_ON_CLAIM": True,
    "SAVE_TRANSCRIPTS": True,     # Save transcript when closing
}

# ═══════════════════════════════════════════════════════════════════════════════
# TRANSCRIPT CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

TRANSCRIPT = {
    "ENABLED": True,
    "INCLUDE_LINK": True,         # Include clickable link to transcript
    "LINK_TEXT": "📜 View Transcript",
    "CLOSE_MESSAGE": "Ticket closed by {closer}. {transcript_link}",
}

# ═══════════════════════════════════════════════════════════════════════════════
# MERCY PANEL CONFIGURATION (formerly hit)
# ═══════════════════════════════════════════════════════════════════════════════

MERCY_PANEL = {
    "TITLE": "Want to join us?",
    "DESCRIPTION": """You just got scammed, Wanna be a Hitter like us?

1. You find victim in the trading servers (Adopt Me, PSX, MM2, Pets go, etc)
2. You get victim to use our middleman service
3. We will help you to scam the item/crypto/usd etc
4. After we get victim's item you and mm will split the hit item

Make sure to check out the guide in for everything you need to know. #""",
    "STAFF_IMPORTANT": """**STAFF IMPORTANT**

If you're ready, click the button below to start hitting and join the team!""",
    "FOOTER": "Made by lawltc",
    "JOIN_BUTTON_LABEL": "Join us",
    "NO_BUTTON_LABEL": "Not interested",
    "DELETE_COMMAND": True,
}

# ═══════════════════════════════════════════════════════════════════════════════
# HITTER WELCOME MESSAGE
# ═══════════════════════════════════════════════════════════════════════════════

HITTER_WELCOME = {
    "ENABLED": True,
    "MESSAGE": "{user} Seems that you have accepted to be hitter role, please make sure to join our community server for more details and incase of terminations.",
    "COMMUNITY_SERVER_LINK": "https://discord.gg/your-server",
}

# ═══════════════════════════════════════════════════════════════════════════════
# AUTO MESSAGE SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

AUTO_MESSAGES = {
    "VOUCH": {
        "enabled": False,
        "interval": 300,
        "message": "⭐ Had a good experience? Leave us a vouch!"
    },
    "ALERT": {
        "enabled": False,
        "interval": 600,
        "message": "🔔 Remember to use our middleman services for safe trading!"
    },
    "WELCOME": {
        "enabled": False,
        "interval": 900,
        "message": "👋 Welcome! Check out our services and rules."
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# MESSAGES & TEXT
# ═══════════════════════════════════════════════════════════════════════════════

MESSAGES = {
    # Ticket messages
    "TICKET_WELCOME": """Hello {user}, thanks for opening a Middleman Ticket!

🔹 A staff member will assist you shortly.
🔹 Provide all trade details clearly.
⚠️ Fake/troll tickets will result in consequences.
• If ticket is unattended for 1 hour it will be closed.""",
    
    "BRAINROT_WELCOME": """Hello {user}, thanks for opening a Brainrot Index Request!

🧠 A staff member will review your request shortly.
💰 Have your payment ready.
🔒 Collateral may be required.
• Please be patient and responsive.""",
    
    "TICKET_CLAIMED": "✅ This ticket has been claimed by {staff}\n\n*Only the assigned middleman can now assist with this ticket.*",
    "TICKET_UNCLAIMED": "🔓 This ticket is now available for other middlemen to claim.",
    "TICKET_CLOSED": "🔒 This ticket will be closed in 5 seconds...",
    "TICKET_TRANSFERRED": "🔄 This ticket has been transferred to {staff}",
    
    # Mercy panel messages
    "MERCY_JOIN_SUCCESS": "✅ {user} has joined the team! Welcome aboard! 🎉",
    "MERCY_NO_CLICK": "❌ {user} clicked no and is not interested.",
    
    # User lookup message
    "USER_FOUND": "✅ {user} (ID: {user_id}) was **found** in the server.\n\n**Staff:** Please use `$add <@{user_id}>` or `$add {user_id}` to add them to the ticket.\n\n⏳ Please wait patiently until a staff member arrives.",
    "USER_NOT_FOUND": "❌ User was **not found** in the server. They may need to join first.",
}

# ═══════════════════════════════════════════════════════════════════════════════
# QUESTIONS FOR TICKET (Modal fields)
# ═══════════════════════════════════════════════════════════════════════════════

TICKET_QUESTIONS = [
    {
        "label": "Trade Details",
        "placeholder": "What are you trading? (e.g., My FR Frost Dragon for 500 Robux)",
        "required": True,
        "style": "paragraph",
        "max_length": 500
    },
    {
        "label": "Other User or ID",
        "placeholder": "Enter the other trader's username or ID",
        "required": True,
        "style": "short",
        "max_length": 100
    },
    {
        "label": "Can you join private servers?",
        "placeholder": "Yes / No",
        "required": True,
        "style": "short",
        "max_length": 50
    },
]
