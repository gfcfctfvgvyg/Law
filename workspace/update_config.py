import re

# Read the current config.py
with open('config.py', 'r') as f:
    content = f.read()

# New SUPPORT_PANEL configuration matching the design image
support_panel_text = '''SUPPORT_PANEL = {
    "TITLE": "Server Support",
    "DESCRIPTION": """Need assistance or facing an issue? Choose an option below to open a ticket.

**How it works:** Select the correct option and our staff will respond promptly.

**:banhammerpasuta_n4u: Server Issues**
Problems with server channels, roles, or bot errors.

**:emoji_2: Appeals**
Disagree with a warning, mute, or ban? Open an appeal ticket.

**:XXX: Report**
Report scams, suspicious users, or rule violations.

**:ArrowGold: Ticket Rules**
• No trolling or false reports
• Abuse may result in punishment
• Be respectful and provide evidence""",
    "IMAGE": "https://i.imgur.com/your_support_image.png",
    "FOOTER": "Support • Trolls will be banned instantly.",
    "COLOR": 0x5B3BC5,
    "BUTTON_LABEL": "Open Support Ticket",
    "BUTTON_EMOJI": "🆘",
}'''

# New INDEX_PANEL configuration matching the design image
index_panel_text = '''INDEX_PANEL = {
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

**How it works**
1️⃣ Pick a base from dropdown
2️⃣ Ticket opens automatically
3️⃣ Admin helps you""",
    "THUMBNAIL": "https://i.imgur.com/your_index_thumbnail.png",
    "IMAGE": "https://i.imgur.com/your_index_image.png",
    "FOOTER": "Index System • Fast • Secure • Professional",
    "COLOR": 0xD4A574,
    "BUTTON_LABEL": "Create Index Ticket",
    "BUTTON_EMOJI": "📑",
}'''

# Find and replace SUPPORT_PANEL
support_pattern = r'SUPPORT_PANEL = \{[^}]*(?:\{[^}]*\}[^}]*)*\}'
content = re.sub(support_pattern, support_panel_text, content)

# Find and replace INDEX_PANEL (first occurrence only)
index_pattern = r'INDEX_PANEL = \{[^}]*(?:\{[^}]*\}[^}]*)*\}(?=\n\n# Index)'
content = re.sub(index_pattern, index_panel_text, content)

# Write back
with open('config.py', 'w') as f:
    f.write(content)

print("✅ Config updated successfully!")
