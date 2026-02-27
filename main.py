"""
MM Bot - Discord Middleman Trading Bot
A comprehensive bot for managing middleman services, profit tracking, and ticket systems.
Per-server configuration support included.
"""

import discord
from discord.ext import commands, tasks
from discord import ui, app_commands
import json
import os
import asyncio
import re
from datetime import datetime
from typing import Optional
import io

# Import configuration
import config

# Import blockchain and webhook modules
from blockchain.rpc_client import RPCClient, NetworkType
from blockchain.wallet_manager import WalletManager
import aiohttp
from aiohttp import web

# ═══════════════════════════════════════════════════════════════════════════════
# DATA STORAGE (Per-Server)
# ═══════════════════════════════════════════════════════════════════════════════

DATA_FILE = "bot_data.json"

def load_data():
    """Load persistent data from JSON file."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "guilds": {},  # Per-server configuration
        "global": {
            "profits": {},
            "confirmations": {},
        }
    }

def save_data(data):
    """Save persistent data to JSON file."""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_guild_data(guild_id: int):
    """Get or create guild-specific data."""
    guild_id_str = str(guild_id)
    if guild_id_str not in bot_data["guilds"]:
        bot_data["guilds"][guild_id_str] = {
            "config": {},
            "tickets": {},
            "autos": {
                "vouch": {"enabled": False, "interval": 300, "channel": None},
                "alert": {"enabled": False, "interval": 600, "channel": None},
                "welcome": {"enabled": False, "interval": 900, "channel": None}
            }
        }
        save_data(bot_data)
    return bot_data["guilds"][guild_id_str]

# Load initial data
bot_data = load_data()

# Initialize blockchain and webhook components
rpc_client: Optional[RPCClient] = None
wallet_manager: Optional[WalletManager] = None
webhook_server: Optional[web.AppRunner] = None
webhook_app: Optional[web.Application] = None

# Migrate old data format if needed
if "guilds" not in bot_data:
    old_data = bot_data.copy()
    bot_data = {
        "guilds": {},
        "global": {
            "profits": old_data.get("profits", {}),
            "confirmations": old_data.get("confirmations", {}),
        }
    }
    save_data(bot_data)

# ═══════════════════════════════════════════════════════════════════════════════
# BOT SETUP
# ═══════════════════════════════════════════════════════════════════════════════

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(
    command_prefix=config.PREFIXES,
    intents=intents,
    help_command=None
)

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS (Per-Server Aware)
# ═══════════════════════════════════════════════════════════════════════════════

def get_guild_config(guild_id: int, key: str):
    """Get a config value for a specific guild."""
    guild_data = get_guild_data(guild_id)
    # Check guild-specific config first, then fall back to global defaults
    value = guild_data.get("config", {}).get(key)
    if value is not None:
        return value
    # Fall back to config.py defaults
    if key in config.ROLES:
        return config.ROLES.get(key)
    if key in config.CHANNELS:
        return config.CHANNELS.get(key)
    return None

def set_guild_config(guild_id: int, key: str, value):
    """Set a config value for a specific guild."""
    guild_data = get_guild_data(guild_id)
    if "config" not in guild_data:
        guild_data["config"] = {}
    guild_data["config"][key] = value
    save_data(bot_data)

def get_role(guild, key: str):
    """Get a role from guild-specific config."""
    role_id = get_guild_config(guild.id, key)
    if role_id:
        return guild.get_role(int(role_id))
    return None

def get_channel_from_config(guild, key: str):
    """Get a channel from guild-specific config."""
    channel_id = get_guild_config(guild.id, key)
    if channel_id:
        return guild.get_channel(int(channel_id))
    return None

def get_guild_tickets(guild_id: int):
    """Get tickets for a specific guild."""
    guild_data = get_guild_data(guild_id)
    return guild_data.get("tickets", {})

def set_guild_ticket(guild_id: int, channel_id: str, ticket_data: dict):
    """Set ticket data for a specific guild."""
    guild_data = get_guild_data(guild_id)
    if "tickets" not in guild_data:
        guild_data["tickets"] = {}
    guild_data["tickets"][channel_id] = ticket_data
    save_data(bot_data)

def delete_guild_ticket(guild_id: int, channel_id: str):
    """Delete ticket data for a specific guild."""
    guild_data = get_guild_data(guild_id)
    if "tickets" in guild_data and channel_id in guild_data["tickets"]:
        del guild_data["tickets"][channel_id]
        save_data(bot_data)

def create_embed(title: str, description: str, color: int = None):
    """Create a styled embed."""
    if color is None:
        color = config.COLORS["PRIMARY"]
    embed = discord.Embed(title=title, description=description, color=color)
    embed.timestamp = datetime.utcnow()
    return embed

def is_staff():
    """Check if user has staff permissions."""
    async def predicate(ctx):
        staff_role = get_role(ctx.guild, "STAFF_ROLE")
        if staff_role and staff_role in ctx.author.roles:
            return True
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)

def is_helper():
    """Check if user has helper permissions."""
    async def predicate(ctx):
        for role_key in ["HELPER_ROLE", "STAFF_ROLE"]:
            role = get_role(ctx.guild, role_key)
            if role and role in ctx.author.roles:
                return True
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)

async def find_user(guild, user_input: str):
    """Find a user by mention, ID, or username."""
    mention_match = re.match(r'<@!?(\d+)>', user_input)
    if mention_match:
        user_id = int(mention_match.group(1))
        return guild.get_member(user_id)
    
    if user_input.isdigit():
        member = guild.get_member(int(user_input))
        if member:
            return member
        try:
            return await guild.fetch_member(int(user_input))
        except:
            pass
    
    user_input_lower = user_input.lower()
    for member in guild.members:
        if member.name.lower() == user_input_lower or (member.nick and member.nick.lower() == user_input_lower):
            return member
    
    return None

async def create_transcript(channel: discord.TextChannel) -> tuple:
    """Create a transcript of the channel and return (content, message_count)."""
    messages = []
    async for message in channel.history(limit=500, oldest_first=True):
        timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
        author = f"{message.author.name}#{message.author.discriminator}" if message.author.discriminator != "0" else message.author.name
        content = message.content or "[No text content]"
        
        # Handle embeds
        if message.embeds:
            for embed in message.embeds:
                if embed.title:
                    content += f"\n[Embed: {embed.title}]"
                if embed.description:
                    content += f"\n{embed.description[:200]}..."
        
        # Handle attachments
        if message.attachments:
            for att in message.attachments:
                content += f"\n[Attachment: {att.filename}]"
        
        messages.append(f"[{timestamp}] {author}: {content}")
    
    transcript_text = f"Transcript for #{channel.name}\n"
    transcript_text += f"Created: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
    transcript_text += "=" * 50 + "\n\n"
    transcript_text += "\n".join(messages)
    
    return transcript_text, len(messages)

# ═══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS - MM PANEL
# ═══════════════════════════════════════════════════════════════════════════════

class DealTypeSelect(ui.Select):
    """Dropdown for selecting deal type."""
    
    def __init__(self):
        options = []
        for deal in config.DEAL_TYPES:
            options.append(discord.SelectOption(
                label=deal["label"],
                description=deal["description"],
                emoji=deal["emoji"],
                value=deal["value"]
            ))
        
        super().__init__(
            placeholder="Select deal type",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        deal_info = next((d for d in config.DEAL_TYPES if d["value"] == selected), None)
        modal = TicketModal(deal_type=selected, deal_label=deal_info["label"] if deal_info else selected)
        await interaction.response.send_modal(modal)

class DealTypeView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(DealTypeSelect())

class TicketModal(ui.Modal):
    """Modal for entering ticket details."""
    
    def __init__(self, deal_type: str, deal_label: str):
        super().__init__(title=f"{deal_label} - Trade Details")
        self.deal_type = deal_type
        self.deal_label = deal_label
        
        for i, question in enumerate(config.TICKET_QUESTIONS):
            style = discord.TextStyle.paragraph if question.get("style") == "paragraph" else discord.TextStyle.short
            field = ui.TextInput(
                label=question["label"],
                placeholder=question.get("placeholder", ""),
                required=question.get("required", True),
                style=style,
                max_length=question.get("max_length", 1000)
            )
            self.add_item(field)
    
    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = get_channel_from_config(guild, "TICKET_CATEGORY")
        
        ticket_name = f"{config.TICKET['TICKET_PREFIX']}{interaction.user.name.lower()[:10]}"
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, manage_permissions=True)
        }
        
        staff_role = get_role(guild, "STAFF_ROLE")
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        mm_role = get_role(guild, "MIDDLEMAN_ROLE")
        if mm_role:
            overwrites[mm_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        try:
            if category:
                ticket_channel = await guild.create_text_channel(name=ticket_name, category=category, overwrites=overwrites)
            else:
                ticket_channel = await guild.create_text_channel(name=ticket_name, overwrites=overwrites)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to create channels!", ephemeral=True)
            return
        
        # Store ticket data (per-guild)
        set_guild_ticket(guild.id, str(ticket_channel.id), {
            "user_id": interaction.user.id,
            "deal_type": self.deal_type,
            "ticket_type": "mm",
            "created_at": datetime.utcnow().isoformat(),
            "claimed_by": None
        })
        
        answers = {}
        for i, child in enumerate(self.children):
            if isinstance(child, ui.TextInput):
                answers[config.TICKET_QUESTIONS[i]["label"]] = child.value
        
        welcome_text = config.MESSAGES["TICKET_WELCOME"].format(user=interaction.user.mention)
        welcome_embed = discord.Embed(title=config.TICKET["WELCOME_TITLE"], description=welcome_text, color=config.COLORS["TICKET"])
        
        if config.IMAGES.get("TICKET_THUMBNAIL"):
            welcome_embed.set_thumbnail(url=config.IMAGES["TICKET_THUMBNAIL"])
        
        details_text = ""
        for label, value in answers.items():
            details_text += f"**{label}:**\n{value}\n"
        
        details_embed = discord.Embed(description=details_text, color=config.COLORS["TICKET"])
        
        other_user_input = answers.get("Other User or ID", "")
        other_user = await find_user(guild, other_user_input) if other_user_input else None
        
        if other_user:
            user_status = config.MESSAGES["USER_FOUND"].format(user=other_user.mention, user_id=other_user.id)
            status_embed = discord.Embed(description=user_status, color=config.COLORS["SUCCESS"])
        else:
            user_status = config.MESSAGES["USER_NOT_FOUND"]
            status_embed = discord.Embed(description=user_status, color=config.COLORS["WARNING"])
        
        ticket_view = TicketControlView()
        
        ping_content = ""
        if config.TICKET["PING_ROLE"] and mm_role:
            ping_content = mm_role.mention
        
        await ticket_channel.send(content=ping_content, embed=welcome_embed)
        await ticket_channel.send(embed=details_embed)
        await ticket_channel.send(embed=status_embed, view=ticket_view)
        
        await interaction.response.send_message(f"Your ticket has been created! {ticket_channel.mention}", ephemeral=True)

class MMPanelButton(ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label=config.MM_PANEL["BUTTON_LABEL"],
            emoji=config.MM_PANEL["BUTTON_EMOJI"],
            custom_id="mm_request_button"
        )
    
    async def callback(self, interaction: discord.Interaction):
        view = DealTypeView()
        await interaction.response.send_message("Select deal type", view=view, ephemeral=True)

class MMPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(MMPanelButton())

# ═══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS - BRAINROT INDEX PANEL
# ═══════════════════════════════════════════════════════════════════════════════

class BrainrotBaseSelect(ui.Select):
    """Dropdown for selecting brainrot base type."""
    
    def __init__(self):
        options = []
        for base in config.BRAINROT_BASES:
            options.append(discord.SelectOption(
                label=base["label"],
                description=base["description"],
                emoji=base["emoji"],
                value=base["value"]
            ))
        
        super().__init__(
            placeholder="Select your base type",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        base_info = next((b for b in config.BRAINROT_BASES if b["value"] == selected), None)
        modal = BrainrotModal(base_type=selected, base_label=base_info["label"] if base_info else selected)
        await interaction.response.send_modal(modal)

class BrainrotBaseView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(BrainrotBaseSelect())

class BrainrotModal(ui.Modal):
    """Modal for entering brainrot request details."""
    
    def __init__(self, base_type: str, base_label: str):
        super().__init__(title=f"{base_label} - Request Details")
        self.base_type = base_type
        self.base_label = base_label
        
        for i, question in enumerate(config.BRAINROT_QUESTIONS):
            style = discord.TextStyle.paragraph if question.get("style") == "paragraph" else discord.TextStyle.short
            field = ui.TextInput(
                label=question["label"],
                placeholder=question.get("placeholder", ""),
                required=question.get("required", True),
                style=style,
                max_length=question.get("max_length", 1000)
            )
            self.add_item(field)
    
    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = get_channel_from_config(guild, "BRAINROT_CATEGORY") or get_channel_from_config(guild, "TICKET_CATEGORY")
        
        ticket_name = f"{config.TICKET.get('BRAINROT_PREFIX', 'brainrot-')}{interaction.user.name.lower()[:10]}"
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, manage_permissions=True)
        }
        
        staff_role = get_role(guild, "STAFF_ROLE")
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        try:
            if category:
                ticket_channel = await guild.create_text_channel(name=ticket_name, category=category, overwrites=overwrites)
            else:
                ticket_channel = await guild.create_text_channel(name=ticket_name, overwrites=overwrites)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to create channels!", ephemeral=True)
            return
        
        # Store ticket data (per-guild)
        set_guild_ticket(guild.id, str(ticket_channel.id), {
            "user_id": interaction.user.id,
            "base_type": self.base_type,
            "ticket_type": "brainrot",
            "created_at": datetime.utcnow().isoformat(),
            "claimed_by": None
        })
        
        answers = {}
        for i, child in enumerate(self.children):
            if isinstance(child, ui.TextInput):
                answers[config.BRAINROT_QUESTIONS[i]["label"]] = child.value
        
        welcome_text = config.MESSAGES["BRAINROT_WELCOME"].format(user=interaction.user.mention)
        welcome_embed = discord.Embed(
            title=f"🧠 Brainrot Request - {self.base_label}",
            description=welcome_text,
            color=config.COLORS["BRAINROT"]
        )
        
        if config.IMAGES.get("BRAINROT_THUMBNAIL"):
            welcome_embed.set_thumbnail(url=config.IMAGES["BRAINROT_THUMBNAIL"])
        
        details_text = f"**Selected Base:** {self.base_label}\n\n"
        for label, value in answers.items():
            details_text += f"**{label}:**\n{value}\n\n"
        
        details_embed = discord.Embed(description=details_text, color=config.COLORS["BRAINROT"])
        
        ticket_view = TicketControlView()
        
        ping_content = ""
        if staff_role:
            ping_content = staff_role.mention
        
        await ticket_channel.send(content=ping_content, embed=welcome_embed)
        await ticket_channel.send(embed=details_embed, view=ticket_view)
        
        await interaction.response.send_message(f"Your brainrot request has been created! {ticket_channel.mention}", ephemeral=True)

class BrainrotPanelButton(ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.danger,
            label=config.BRAINROT_PANEL["BUTTON_LABEL"],
            emoji=config.BRAINROT_PANEL["BUTTON_EMOJI"],
            custom_id="brainrot_request_button"
        )
    
    async def callback(self, interaction: discord.Interaction):
        view = BrainrotBaseView()
        await interaction.response.send_message("Select your base type", view=view, ephemeral=True)

class BrainrotPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(BrainrotPanelButton())

# ═══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS - INDEX PANEL
# ═══════════════════════════════════════════════════════════════════════════════

class IndexBaseSelect(ui.Select):
    """Dropdown for selecting index base type."""
    
    def __init__(self):
        options = []
        for base in config.INDEX_BASES:
            options.append(discord.SelectOption(
                label=base["label"],
                description=base["description"],
                emoji=base["emoji"],
                value=base["value"]
            ))
        
        super().__init__(
            placeholder="Select a base",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        base_info = next((b for b in config.INDEX_BASES if b["value"] == selected), None)
        modal = IndexModal(base_type=selected, base_label=base_info["label"] if base_info else selected)
        await interaction.response.send_modal(modal)

class IndexBaseView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(IndexBaseSelect())

class IndexModal(ui.Modal):
    """Modal for entering index ticket details."""
    
    def __init__(self, base_type: str, base_label: str):
        super().__init__(title=f"Index Ticket - {base_label}")
        self.base_type = base_type
        self.base_label = base_label
        
        for i, question in enumerate(config.INDEX_QUESTIONS):
            style = discord.TextStyle.paragraph if question.get("style") == "paragraph" else discord.TextStyle.short
            field = ui.TextInput(
                label=question["label"],
                placeholder=question.get("placeholder", ""),
                required=question.get("required", True),
                style=style,
                max_length=question.get("max_length", 1000)
            )
            self.add_item(field)
    
    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = get_channel_from_config(guild, "TICKET_CATEGORY")
        
        ticket_name = f"index-{interaction.user.name.lower()[:10]}"
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, manage_permissions=True)
        }
        
        staff_role = get_role(guild, "STAFF_ROLE")
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        try:
            if category:
                ticket_channel = await guild.create_text_channel(name=ticket_name, category=category, overwrites=overwrites)
            else:
                ticket_channel = await guild.create_text_channel(name=ticket_name, overwrites=overwrites)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to create channels!", ephemeral=True)
            return
        
        set_guild_ticket(guild.id, str(ticket_channel.id), {
            "user_id": interaction.user.id,
            "base_type": self.base_type,
            "ticket_type": "index",
            "created_at": datetime.utcnow().isoformat(),
            "claimed_by": None
        })
        
        answers = {}
        for i, child in enumerate(self.children):
            if isinstance(child, ui.TextInput):
                answers[config.INDEX_QUESTIONS[i]["label"]] = child.value
        
        welcome_text = f"Hello {interaction.user.mention}, thanks for opening an Index Ticket!\n\n⚡ A staff member will assist you quickly.\n🔐 Your ticket will be private."
        welcome_embed = discord.Embed(title=f"📑 Index Ticket - {self.base_label}", description=welcome_text, color=config.COLORS["TICKET"])
        
        details_text = ""
        for label, value in answers.items():
            details_text += f"**{label}:**\n{value}\n\n"
        
        details_embed = discord.Embed(description=details_text, color=config.COLORS["TICKET"])
        
        ticket_view = TicketControlView()
        
        ping_content = ""
        if config.TICKET["PING_ROLE"] and staff_role:
            ping_content = staff_role.mention
        
        await ticket_channel.send(content=ping_content, embed=welcome_embed)
        await ticket_channel.send(embed=details_embed)
        await ticket_channel.send(embed=discord.Embed(description="Use the buttons below to manage this ticket.", color=config.COLORS["INFO"]), view=ticket_view)
        
        await interaction.response.send_message(f"Your index ticket has been created! {ticket_channel.mention}", ephemeral=True)

class IndexPanelButton(ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label=config.INDEX_PANEL["BUTTON_LABEL"],
            emoji=config.INDEX_PANEL["BUTTON_EMOJI"],
            custom_id="index_request_button"
        )
    
    async def callback(self, interaction: discord.Interaction):
        view = IndexBaseView()
        await interaction.response.send_message("Select a base", view=view, ephemeral=True)

class IndexPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(IndexPanelButton())

# ═══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS - SUPPORT PANEL
# ═══════════════════════════════════════════════════════════════════════════════

class SupportModal(ui.Modal):
    """Modal for entering support ticket details."""
    
    def __init__(self):
        super().__init__(title="Support Ticket")
        
        for i, question in enumerate(config.SUPPORT_QUESTIONS):
            style = discord.TextStyle.paragraph if question.get("style") == "paragraph" else discord.TextStyle.short
            field = ui.TextInput(
                label=question["label"],
                placeholder=question.get("placeholder", ""),
                required=question.get("required", True),
                style=style,
                max_length=question.get("max_length", 1000)
            )
            self.add_item(field)
    
    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = get_channel_from_config(guild, "TICKET_CATEGORY")
        
        ticket_name = f"support-{interaction.user.name.lower()[:10]}"
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, manage_permissions=True)
        }
        
        staff_role = get_role(guild, "STAFF_ROLE")
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        try:
            if category:
                ticket_channel = await guild.create_text_channel(name=ticket_name, category=category, overwrites=overwrites)
            else:
                ticket_channel = await guild.create_text_channel(name=ticket_name, overwrites=overwrites)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to create channels!", ephemeral=True)
            return
        
        set_guild_ticket(guild.id, str(ticket_channel.id), {
            "user_id": interaction.user.id,
            "ticket_type": "support",
            "created_at": datetime.utcnow().isoformat(),
            "claimed_by": None
        })
        
        answers = {}
        for i, child in enumerate(self.children):
            if isinstance(child, ui.TextInput):
                answers[config.SUPPORT_QUESTIONS[i]["label"]] = child.value
        
        welcome_text = f"Hello {interaction.user.mention}, thanks for opening a Support Ticket!\n\nNeed assistance or facing an issue? Our staff will respond promptly.\n\n⚠️ Please provide as much detail as possible."
        welcome_embed = discord.Embed(title="🆘 Support Ticket", description=welcome_text, color=config.COLORS["TICKET"])
        
        details_text = ""
        for label, value in answers.items():
            details_text += f"**{label}:**\n{value}\n\n"
        
        details_embed = discord.Embed(description=details_text, color=config.COLORS["TICKET"])
        
        ticket_view = TicketControlView()
        
        ping_content = ""
        if config.TICKET["PING_ROLE"] and staff_role:
            ping_content = staff_role.mention
        
        await ticket_channel.send(content=ping_content, embed=welcome_embed)
        await ticket_channel.send(embed=details_embed)
        await ticket_channel.send(embed=discord.Embed(description="Use the buttons below to manage this ticket.", color=config.COLORS["INFO"]), view=ticket_view)
        
        await interaction.response.send_message(f"Your support ticket has been created! {ticket_channel.mention}", ephemeral=True)

class SupportPanelButton(ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.danger,
            label=config.SUPPORT_PANEL["BUTTON_LABEL"],
            emoji=config.SUPPORT_PANEL["BUTTON_EMOJI"],
            custom_id="support_request_button"
        )
    
    async def callback(self, interaction: discord.Interaction):
        modal = SupportModal()
        await interaction.response.send_modal(modal)

class SupportPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(SupportPanelButton())

# ═══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS - TICKET CONTROLS
# ═══════════════════════════════════════════════════════════════════════════════

class TicketControlView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="Claim Ticket", style=discord.ButtonStyle.success, emoji="✅", custom_id="ticket_claim")
    async def claim_button(self, interaction: discord.Interaction, button: ui.Button):
        channel_id = str(interaction.channel.id)
        guild_tickets = get_guild_tickets(interaction.guild.id)
        
        staff_role = get_role(interaction.guild, "STAFF_ROLE")
        mm_role = get_role(interaction.guild, "MIDDLEMAN_ROLE")
        
        is_authorized = interaction.user.guild_permissions.administrator
        if staff_role and staff_role in interaction.user.roles:
            is_authorized = True
        if mm_role and mm_role in interaction.user.roles:
            is_authorized = True
        
        if not is_authorized:
            await interaction.response.send_message("You don't have permission to claim tickets!", ephemeral=True)
            return
        
        ticket_data = guild_tickets.get(channel_id, {})
        if ticket_data.get("claimed_by"):
            await interaction.response.send_message("This ticket is already claimed!", ephemeral=True)
            return
        
        ticket_data["claimed_by"] = interaction.user.id
        ticket_data["claimed_at"] = datetime.utcnow().isoformat()
        set_guild_ticket(interaction.guild.id, channel_id, ticket_data)
        
        if config.TICKET.get("LOCK_ON_CLAIM", True):
            ticket_owner_id = ticket_data.get("user_id")
            
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, manage_permissions=True),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            }
            
            if ticket_owner_id:
                ticket_owner = interaction.guild.get_member(ticket_owner_id)
                if ticket_owner:
                    overwrites[ticket_owner] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            if mm_role:
                overwrites[mm_role] = discord.PermissionOverwrite(read_messages=False)
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=False)
            
            try:
                await interaction.channel.edit(overwrites=overwrites)
            except discord.Forbidden:
                pass
        
        embed = create_embed("Ticket Claimed", config.MESSAGES["TICKET_CLAIMED"].format(staff=interaction.user.mention), config.COLORS["SUCCESS"])
        await interaction.response.send_message(embed=embed)
    
    @ui.button(label="Unclaim Ticket", style=discord.ButtonStyle.secondary, emoji="🔓", custom_id="ticket_unclaim")
    async def unclaim_button(self, interaction: discord.Interaction, button: ui.Button):
        channel_id = str(interaction.channel.id)
        guild_tickets = get_guild_tickets(interaction.guild.id)
        ticket_data = guild_tickets.get(channel_id, {})
        
        if ticket_data.get("claimed_by") != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only the middleman who claimed this ticket can unclaim it!", ephemeral=True)
            return
        
        ticket_data["claimed_by"] = None
        set_guild_ticket(interaction.guild.id, channel_id, ticket_data)
        
        if config.TICKET.get("LOCK_ON_CLAIM", True):
            ticket_owner_id = ticket_data.get("user_id")
            
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, manage_permissions=True),
            }
            
            if ticket_owner_id:
                ticket_owner = interaction.guild.get_member(ticket_owner_id)
                if ticket_owner:
                    overwrites[ticket_owner] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            staff_role = get_role(interaction.guild, "STAFF_ROLE")
            mm_role = get_role(interaction.guild, "MIDDLEMAN_ROLE")
            
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            if mm_role:
                overwrites[mm_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            try:
                await interaction.channel.edit(overwrites=overwrites)
            except discord.Forbidden:
                pass
        
        embed = create_embed("Ticket Unclaimed", config.MESSAGES["TICKET_UNCLAIMED"], config.COLORS["WARNING"])
        await interaction.response.send_message(embed=embed)
    
    @ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="❌", custom_id="ticket_close")
    async def close_button(self, interaction: discord.Interaction, button: ui.Button):
        channel_id = str(interaction.channel.id)
        guild_tickets = get_guild_tickets(interaction.guild.id)
        ticket_data = guild_tickets.get(channel_id, {})
        
        staff_role = get_role(interaction.guild, "STAFF_ROLE")
        is_authorized = interaction.user.guild_permissions.administrator
        if staff_role and staff_role in interaction.user.roles:
            is_authorized = True
        if ticket_data.get("user_id") == interaction.user.id:
            is_authorized = True
        if ticket_data.get("claimed_by") == interaction.user.id:
            is_authorized = True
        
        if not is_authorized:
            await interaction.response.send_message("You don't have permission to close this ticket!", ephemeral=True)
            return
        
        # Create transcript
        transcript_link = ""
        if config.TRANSCRIPT.get("ENABLED", True):
            transcript_channel = get_channel_from_config(interaction.guild, "TRANSCRIPT_CHANNEL")
            if transcript_channel:
                transcript_text, msg_count = await create_transcript(interaction.channel)
                
                # Create file
                file = discord.File(
                    io.BytesIO(transcript_text.encode()),
                    filename=f"transcript-{interaction.channel.name}.txt"
                )
                
                # Send to transcript channel
                transcript_embed = discord.Embed(
                    title=f"📜 Ticket Transcript",
                    description=f"**Channel:** #{interaction.channel.name}\n**Closed by:** {interaction.user.mention}\n**Messages:** {msg_count}\n**Ticket Type:** {ticket_data.get('ticket_type', 'mm')}",
                    color=config.COLORS["INFO"]
                )
                transcript_embed.timestamp = datetime.utcnow()
                
                transcript_msg = await transcript_channel.send(embed=transcript_embed, file=file)
                transcript_link = f"[{config.TRANSCRIPT.get('LINK_TEXT', '📜 View Transcript')}]({transcript_msg.jump_url})"
        
        # Send close message with transcript link
        close_msg = config.TRANSCRIPT.get("CLOSE_MESSAGE", "Ticket closed by {closer}. {transcript_link}")
        close_msg = close_msg.format(closer=interaction.user.mention, transcript_link=transcript_link)
        
        embed = create_embed("Closing Ticket", f"{config.MESSAGES['TICKET_CLOSED']}\n\n{transcript_link}", config.COLORS["ERROR"])
        await interaction.response.send_message(embed=embed)
        
        delete_guild_ticket(interaction.guild.id, channel_id)
        
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to delete this channel.")

# ═══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS - MERCY PANEL
# ═══════════════════════════════════════════════════════════════════════════════

class MercyPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="Join us", style=discord.ButtonStyle.success, emoji="✅", custom_id="mercy_join")
    async def join_button(self, interaction: discord.Interaction, button: ui.Button):
        hitter_role = get_role(interaction.guild, "HITTER_ROLE") or get_role(interaction.guild, "CLIENT_ROLE")
        
        if hitter_role:
            try:
                await interaction.user.add_roles(hitter_role)
            except discord.Forbidden:
                await interaction.response.send_message("I couldn't assign the role. Check my permissions!", ephemeral=True)
                return
        
        embed = create_embed("Welcome to the Team!", config.MESSAGES["MERCY_JOIN_SUCCESS"].format(user=interaction.user.mention), config.COLORS["SUCCESS"])
        await interaction.response.send_message(embed=embed)
        
        if config.HITTER_WELCOME.get("ENABLED", True):
            welcome_channel_id = get_guild_config(interaction.guild.id, "HITTER_WELCOME_CHANNEL")
            if welcome_channel_id:
                welcome_channel = interaction.guild.get_channel(int(welcome_channel_id))
                if welcome_channel:
                    welcome_msg = config.HITTER_WELCOME["MESSAGE"].format(user=interaction.user.mention)
                    try:
                        await welcome_channel.send(welcome_msg)
                    except discord.Forbidden:
                        pass
    
    @ui.button(label="Not interested", style=discord.ButtonStyle.danger, emoji="❌", custom_id="mercy_no")
    async def no_button(self, interaction: discord.Interaction, button: ui.Button):
        message = config.MESSAGES["MERCY_NO_CLICK"].format(user=interaction.user.mention)
        await interaction.response.send_message(message)

# ═══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS - FEE, MMINFO, CONFIRM PANELS
# ═══════════════════════════════════════════════════════════════════════════════

class FeePanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="50/50", style=discord.ButtonStyle.primary, emoji="⚖️", custom_id="fee_split")
    async def split_button(self, interaction: discord.Interaction, button: ui.Button):
        embed = create_embed("Fee Split Selected", f"{interaction.user.mention} has chosen **50/50 split**.\n\nBoth parties will pay half of the service fee.", config.COLORS["INFO"])
        await interaction.response.send_message(embed=embed)
    
    @ui.button(label="100%", style=discord.ButtonStyle.danger, emoji="💰", custom_id="fee_full")
    async def full_button(self, interaction: discord.Interaction, button: ui.Button):
        embed = create_embed("Full Payment Selected", f"{interaction.user.mention} has chosen **100% payment**.\n\nOne party will pay the full service fee.", config.COLORS["WARNING"])
        await interaction.response.send_message(embed=embed)

class MMInfoView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="I understand", style=discord.ButtonStyle.success, emoji="✅", custom_id="mminfo_understand")
    async def understand_button(self, interaction: discord.Interaction, button: ui.Button):
        embed = create_embed("Understood", f"{interaction.user.mention} has confirmed they understand how middleman works.", config.COLORS["SUCCESS"])
        await interaction.response.send_message(embed=embed)
    
    @ui.button(label="I don't understand", style=discord.ButtonStyle.danger, emoji="❌", custom_id="mminfo_dontunderstand")
    async def dont_understand_button(self, interaction: discord.Interaction, button: ui.Button):
        embed = create_embed("Need Help", f"{interaction.user.mention} needs more clarification on how middleman works.\n\n**Staff:** Please assist this user.", config.COLORS["WARNING"])
        await interaction.response.send_message(embed=embed)

class ConfirmView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="Confirm Trade", style=discord.ButtonStyle.success, emoji="✅", custom_id="confirm_trade")
    async def confirm_button(self, interaction: discord.Interaction, button: ui.Button):
        channel_id = str(interaction.channel.id)
        
        if "confirmations" not in bot_data["global"]:
            bot_data["global"]["confirmations"] = {}
        if channel_id not in bot_data["global"]["confirmations"]:
            bot_data["global"]["confirmations"][channel_id] = {"users": []}
        
        if interaction.user.id in bot_data["global"]["confirmations"][channel_id]["users"]:
            await interaction.response.send_message("You have already confirmed!", ephemeral=True)
            return
        
        bot_data["global"]["confirmations"][channel_id]["users"].append(interaction.user.id)
        save_data(bot_data)
        
        confirmed_count = len(bot_data["global"]["confirmations"][channel_id]["users"])
        
        msg = config.CONFIRM_PANEL["CONFIRMED_MESSAGE"].format(user=interaction.user.mention)
        embed = create_embed("Trade Confirmed", msg, config.COLORS["SUCCESS"])
        await interaction.response.send_message(embed=embed)
        
        if confirmed_count >= 2:
            complete_embed = create_embed("Trade Complete", config.CONFIRM_PANEL["BOTH_CONFIRMED"], config.COLORS["SUCCESS"])
            await interaction.channel.send(embed=complete_embed)
            bot_data["global"]["confirmations"][channel_id] = {"users": []}
            save_data(bot_data)
    
    @ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌", custom_id="cancel_trade")
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        msg = config.CONFIRM_PANEL["CANCELLED_MESSAGE"].format(user=interaction.user.mention)
        embed = create_embed("Trade Cancelled", msg, config.COLORS["ERROR"])
        await interaction.response.send_message(embed=embed)
        
        channel_id = str(interaction.channel.id)
        if channel_id in bot_data["global"].get("confirmations", {}):
            bot_data["global"]["confirmations"][channel_id] = {"users": []}
            save_data(bot_data)

# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOK EVENT HANDLER & BACKGROUND TASKS
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_blockchain_webhook(request: web.Request) -> web.Response:
    """Handle incoming blockchain webhook events from monitoring services.
    
    Expected webhook payload:
    {
        "event_id": "unique_event_id",
        "network": "ETH|BTC|SOL|LTC",
        "tx_hash": "transaction_hash",
        "status": "pending|confirmed|failed|cancelled",
        "confirmations": 0,
        "trade_id": "associated_trade_id"
    }
    """
    try:
        data = await request.json()
        
        # Validate required fields
        required_fields = ["event_id", "network", "tx_hash", "status", "trade_id"]
        if not all(field in data for field in required_fields):
            return web.json_response(
                {"error": "Missing required fields"},
                status=400
            )
        
        # Store webhook event in bot_data for processing
        if "webhook_events" not in bot_data["global"]:
            bot_data["global"]["webhook_events"] = {}
        
        event_id = data["event_id"]
        bot_data["global"]["webhook_events"][event_id] = {
            "event_id": event_id,
            "network": data["network"],
            "tx_hash": data["tx_hash"],
            "status": data["status"],
            "confirmations": data.get("confirmations", 0),
            "trade_id": data["trade_id"],
            "received_at": datetime.utcnow().isoformat(),
            "processed": False
        }
        save_data(bot_data)
        
        return web.json_response(
            {"success": True, "event_id": event_id},
            status=200
        )
    
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return web.json_response(
            {"error": str(e)},
            status=500
        )


async def process_webhook_events():
    """Background task to process webhook events and update trade states.
    
    Runs continuously, checking for unprocessed webhook events and updating
    the corresponding trade data in bot_data.json.
    """
    await bot.wait_until_ready()
    
    while not bot.is_closed():
        try:
            if "webhook_events" not in bot_data["global"]:
                bot_data["global"]["webhook_events"] = {}
            
            # Process unprocessed events
            for event_id, event_data in list(bot_data["global"]["webhook_events"].items()):
                if not event_data.get("processed"):
                    trade_id = event_data.get("trade_id")
                    status = event_data.get("status")
                    
                    # Update trade state based on webhook event
                    if "trades" not in bot_data["global"]:
                        bot_data["global"]["trades"] = {}
                    
                    if trade_id not in bot_data["global"]["trades"]:
                        bot_data["global"]["trades"][trade_id] = {
                            "id": trade_id,
                            "status": "pending",
                            "events": []
                        }
                    
                    # Update trade status based on webhook event
                    if status == "confirmed":
                        bot_data["global"]["trades"][trade_id]["status"] = "confirmed"
                    elif status == "failed":
                        bot_data["global"]["trades"][trade_id]["status"] = "failed"
                    elif status == "cancelled":
                        bot_data["global"]["trades"][trade_id]["status"] = "cancelled"
                    
                    # Add event to trade history
                    bot_data["global"]["trades"][trade_id]["events"].append({
                        "event_id": event_id,
                        "network": event_data.get("network"),
                        "tx_hash": event_data.get("tx_hash"),
                        "status": status,
                        "confirmations": event_data.get("confirmations", 0),
                        "timestamp": event_data.get("received_at")
                    })
                    
                    # Mark event as processed
                    event_data["processed"] = True
                    save_data(bot_data)
            
            # Sleep before next check
            await asyncio.sleep(5)
        
        except Exception as e:
            print(f"❌ Error processing webhook events: {e}")
            await asyncio.sleep(10)


# ═══════════════════════════════════════════════════════════════════════════════
# EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    global rpc_client, wallet_manager, webhook_server, webhook_app
    
    print(f"{'='*50}")
    print(f"  MM Bot Online!")
    print(f"  Logged in as: {bot.user.name}")
    print(f"  Bot ID: {bot.user.id}")
    print(f"  Prefixes: {', '.join(config.PREFIXES)}")
    print(f"  Servers: {len(bot.guilds)}")
    print(f"  Per-server config: ENABLED")
    print(f"{'='*50}")
    
    # Initialize RPC client for blockchain connectivity
    try:
        rpc_client = RPCClient(
            eth_rpc_url=os.getenv("ETH_RPC_URL"),
            btc_rpc_url=os.getenv("BTC_RPC_URL"),
            sol_rpc_url=os.getenv("SOL_RPC_URL"),
            ltc_rpc_url=os.getenv("LTC_RPC_URL"),
            timeout=10.0,
            max_retries=3
        )
        await rpc_client.connect()
        print("✓ RPC client initialized")
    except Exception as e:
        print(f"✗ Failed to initialize RPC client: {e}")
    
    # Initialize wallet manager for trade wallet generation
    try:
        wallet_manager = WalletManager(
            data_file=DATA_FILE,
            encryption_key=os.getenv("WALLET_ENCRYPTION_KEY")
        )
        print("✓ Wallet manager initialized")
    except Exception as e:
        print(f"✗ Failed to initialize wallet manager: {e}")
    
    # Initialize webhook server for blockchain event processing
    try:
        webhook_app = web.Application()
        webhook_app.router.add_post('/webhook/blockchain', handle_blockchain_webhook)
        webhook_server = web.AppRunner(webhook_app)
        await webhook_server.setup()
        webhook_port = int(os.getenv("WEBHOOK_PORT", "8080"))
        site = web.TCPSite(webhook_server, "0.0.0.0", webhook_port)
        await site.start()
        print(f"✓ Webhook server started on port {webhook_port}")
    except Exception as e:
        print(f"✗ Failed to start webhook server: {e}")
    
    # Start background event processor task
    if not bot.loop.is_running():
        bot.loop.create_task(process_webhook_events())
    
    bot.add_view(MMPanelView())
    bot.add_view(TicketControlView())
    bot.add_view(MercyPanelView())
    bot.add_view(FeePanelView())
    bot.add_view(MMInfoView())
    bot.add_view(ConfirmView())
    bot.add_view(IndexPanelView())
    bot.add_view(SupportPanelView())
    
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=config.BOT_STATUS))

@bot.event
async def on_shutdown():
    """Cleanup when bot shuts down."""
    global rpc_client, webhook_server
    
    try:
        if rpc_client:
            await rpc_client.close()
            print("✓ RPC client closed")
    except Exception as e:
        print(f"✗ Error closing RPC client: {e}")
    
    try:
        if webhook_server:
            await webhook_server.cleanup()
            print("✓ Webhook server closed")
    except Exception as e:
        print(f"✗ Error closing webhook server: {e}")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(embed=create_embed("Permission Denied", "You don't have permission.", config.COLORS["ERROR"]))
    elif isinstance(error, commands.CheckFailure):
        await ctx.send(embed=create_embed("Access Denied", "You don't have the required role.", config.COLORS["ERROR"]))
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=create_embed("Missing Argument", f"Missing: `{error.param.name}`", config.COLORS["ERROR"]))
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"Error: {error}")

# ═══════════════════════════════════════════════════════════════════════════════
# MM COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="panel")
@is_staff()
async def panel(ctx):
    """Post the MM request panel."""
    embed = discord.Embed(title=config.MM_PANEL["TITLE"], description=config.MM_PANEL["DESCRIPTION"], color=config.COLORS["PRIMARY"])
    if config.IMAGES.get("PANEL_THUMBNAIL"):
        embed.set_thumbnail(url=config.IMAGES["PANEL_THUMBNAIL"])
    if config.IMAGES.get("PANEL_IMAGE"):
        embed.set_image(url=config.IMAGES["PANEL_IMAGE"])
    embed.set_footer(text=config.MM_PANEL["FOOTER"])
    await ctx.send(embed=embed, view=MMPanelView())

@bot.command(name="mminfo")
@is_staff()
async def mminfo(ctx):
    """Post MM info with buttons."""
    embed = discord.Embed(title=config.MMINFO_PANEL["TITLE"], description=config.MMINFO_PANEL["DESCRIPTION"], color=config.COLORS["DARK"])
    if config.IMAGES.get("MMINFO_THUMBNAIL"):
        embed.set_thumbnail(url=config.IMAGES["MMINFO_THUMBNAIL"])
    await ctx.send(embed=embed, view=MMInfoView())

@bot.command(name="index")
@is_staff()
async def index(ctx):
    """Post the Index panel."""
    embed = discord.Embed(title=config.INDEX_PANEL["TITLE"], description=config.INDEX_PANEL["DESCRIPTION"], color=config.COLORS["PRIMARY"])
    embed.set_footer(text=config.INDEX_PANEL["FOOTER"])
    await ctx.send(embed=embed, view=IndexPanelView())

@bot.command(name="support")
@is_staff()
async def support(ctx):
    """Post the Support panel."""
    embed = discord.Embed(title=config.SUPPORT_PANEL["TITLE"], description=config.SUPPORT_PANEL["DESCRIPTION"], color=config.COLORS["DARK"])
    embed.set_footer(text=config.SUPPORT_PANEL["FOOTER"])
    await ctx.send(embed=embed, view=SupportPanelView())

@bot.command(name="mercy")
@is_staff()
async def mercy(ctx):
    """Post mercy recruit panel."""
    if config.MERCY_PANEL.get("DELETE_COMMAND", True):
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
    
    embed = discord.Embed(title=config.MERCY_PANEL["TITLE"], description=config.MERCY_PANEL["DESCRIPTION"], color=config.COLORS["PRIMARY"])
    embed.add_field(name="\u200b", value=config.MERCY_PANEL["STAFF_IMPORTANT"], inline=False)
    if config.IMAGES.get("MERCY_THUMBNAIL"):
        embed.set_thumbnail(url=config.IMAGES["MERCY_THUMBNAIL"])
    if config.IMAGES.get("MERCY_IMAGE"):
        embed.set_image(url=config.IMAGES["MERCY_IMAGE"])
    embed.set_footer(text=config.MERCY_PANEL["FOOTER"])
    await ctx.send(embed=embed, view=MercyPanelView())

@bot.command(name="claim")
@is_staff()
async def claim(ctx):
    """Claim a ticket."""
    channel_id = str(ctx.channel.id)
    guild_tickets = get_guild_tickets(ctx.guild.id)
    ticket_data = guild_tickets.get(channel_id, {})
    
    if ticket_data.get("claimed_by"):
        await ctx.send(embed=create_embed("Already Claimed", "This ticket is already claimed.", config.COLORS["ERROR"]))
        return
    
    ticket_data["claimed_by"] = ctx.author.id
    ticket_data["claimed_at"] = datetime.utcnow().isoformat()
    set_guild_ticket(ctx.guild.id, channel_id, ticket_data)
    
    if config.TICKET.get("LOCK_ON_CLAIM", True):
        ticket_owner_id = ticket_data.get("user_id")
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, manage_permissions=True),
            ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        if ticket_owner_id:
            ticket_owner = ctx.guild.get_member(ticket_owner_id)
            if ticket_owner:
                overwrites[ticket_owner] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        mm_role = get_role(ctx.guild, "MIDDLEMAN_ROLE")
        staff_role = get_role(ctx.guild, "STAFF_ROLE")
        if mm_role:
            overwrites[mm_role] = discord.PermissionOverwrite(read_messages=False)
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=False)
        try:
            await ctx.channel.edit(overwrites=overwrites)
        except discord.Forbidden:
            pass
    
    embed = create_embed("Ticket Claimed", config.MESSAGES["TICKET_CLAIMED"].format(staff=ctx.author.mention), config.COLORS["SUCCESS"])
    await ctx.send(embed=embed)

@bot.command(name="unclaim")
@is_staff()
async def unclaim(ctx):
    """Unclaim a ticket."""
    channel_id = str(ctx.channel.id)
    guild_tickets = get_guild_tickets(ctx.guild.id)
    ticket_data = guild_tickets.get(channel_id, {})
    
    if ticket_data.get("claimed_by") != ctx.author.id and not ctx.author.guild_permissions.administrator:
        await ctx.send(embed=create_embed("Cannot Unclaim", "Only the claimer can unclaim!", config.COLORS["ERROR"]))
        return
    
    ticket_data["claimed_by"] = None
    set_guild_ticket(ctx.guild.id, channel_id, ticket_data)
    
    if config.TICKET.get("LOCK_ON_CLAIM", True):
        ticket_owner_id = ticket_data.get("user_id")
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, manage_permissions=True),
        }
        if ticket_owner_id:
            ticket_owner = ctx.guild.get_member(ticket_owner_id)
            if ticket_owner:
                overwrites[ticket_owner] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        staff_role = get_role(ctx.guild, "STAFF_ROLE")
        mm_role = get_role(ctx.guild, "MIDDLEMAN_ROLE")
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        if mm_role:
            overwrites[mm_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        try:
            await ctx.channel.edit(overwrites=overwrites)
        except discord.Forbidden:
            pass
    
    embed = create_embed("Ticket Unclaimed", config.MESSAGES["TICKET_UNCLAIMED"], config.COLORS["WARNING"])
    await ctx.send(embed=embed)

@bot.command(name="transfer")
@is_staff()
async def transfer(ctx, user: discord.Member):
    """Transfer a ticket."""
    channel_id = str(ctx.channel.id)
    guild_tickets = get_guild_tickets(ctx.guild.id)
    ticket_data = guild_tickets.get(channel_id, {})
    
    ticket_data["claimed_by"] = user.id
    ticket_data["claimed_at"] = datetime.utcnow().isoformat()
    ticket_data["transferred_from"] = ctx.author.id
    set_guild_ticket(ctx.guild.id, channel_id, ticket_data)
    
    if config.TICKET.get("LOCK_ON_CLAIM", True):
        ticket_owner_id = ticket_data.get("user_id")
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, manage_permissions=True),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        if ticket_owner_id:
            ticket_owner = ctx.guild.get_member(ticket_owner_id)
            if ticket_owner:
                overwrites[ticket_owner] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        mm_role = get_role(ctx.guild, "MIDDLEMAN_ROLE")
        staff_role = get_role(ctx.guild, "STAFF_ROLE")
        if mm_role:
            overwrites[mm_role] = discord.PermissionOverwrite(read_messages=False)
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=False)
        try:
            await ctx.channel.edit(overwrites=overwrites)
        except discord.Forbidden:
            pass
    
    embed = create_embed("Ticket Transferred", config.MESSAGES["TICKET_TRANSFERRED"].format(staff=user.mention), config.COLORS["INFO"])
    await ctx.send(embed=embed)

@bot.command(name="close")
@is_staff()
async def close(ctx):
    """Close a ticket."""
    channel_id = str(ctx.channel.id)
    guild_tickets = get_guild_tickets(ctx.guild.id)
    ticket_data = guild_tickets.get(channel_id, {})
    
    transcript_link = ""
    if config.TRANSCRIPT.get("ENABLED", True):
        transcript_channel = get_channel_from_config(ctx.guild, "TRANSCRIPT_CHANNEL")
        if transcript_channel:
            transcript_text, msg_count = await create_transcript(ctx.channel)
            file = discord.File(io.BytesIO(transcript_text.encode()), filename=f"transcript-{ctx.channel.name}.txt")
            transcript_embed = discord.Embed(
                title="📜 Ticket Transcript",
                description=f"**Channel:** #{ctx.channel.name}\n**Closed by:** {ctx.author.mention}\n**Messages:** {msg_count}",
                color=config.COLORS["INFO"]
            )
            transcript_embed.timestamp = datetime.utcnow()
            transcript_msg = await transcript_channel.send(embed=transcript_embed, file=file)
            transcript_link = f"[{config.TRANSCRIPT.get('LINK_TEXT', '📜 View Transcript')}]({transcript_msg.jump_url})"
    
    embed = create_embed("Closing Ticket", f"{config.MESSAGES['TICKET_CLOSED']}\n\n{transcript_link}", config.COLORS["ERROR"])
    await ctx.send(embed=embed)
    
    delete_guild_ticket(ctx.guild.id, channel_id)
    
    await asyncio.sleep(5)
    try:
        await ctx.channel.delete()
    except discord.Forbidden:
        await ctx.send("I don't have permission to delete this channel.")

@bot.command(name="fee")
@is_staff()
async def fee(ctx):
    """Service fee panel."""
    embed = discord.Embed(title=config.FEE_PANEL["TITLE"], description=config.FEE_PANEL["DESCRIPTION"], color=config.COLORS["DARK"])
    if config.IMAGES.get("FEE_THUMBNAIL"):
        embed.set_thumbnail(url=config.IMAGES["FEE_THUMBNAIL"])
    await ctx.send(embed=embed, view=FeePanelView())

@bot.command(name="confirm")
@is_staff()
async def confirm(ctx):
    """Trade confirmation panel."""
    channel_id = str(ctx.channel.id)
    if "confirmations" not in bot_data["global"]:
        bot_data["global"]["confirmations"] = {}
    bot_data["global"]["confirmations"][channel_id] = {"users": []}
    save_data(bot_data)
    
    embed = discord.Embed(title=config.CONFIRM_PANEL["TITLE"], description=config.CONFIRM_PANEL["DESCRIPTION"], color=config.COLORS["DARK"])
    await ctx.send(embed=embed, view=ConfirmView())

@bot.command(name="howto")
@is_staff()
async def howto(ctx):
    """How to guide."""
    embed = discord.Embed(title="How To Get Items", description="**Step-by-Step:**\n\n1. Find a Seller\n2. Request a Middleman\n3. Provide Details\n4. Wait for MM\n5. Complete Trade\n\n**Never trade without a middleman!**", color=config.COLORS["INFO"])
    await ctx.send(embed=embed)

@bot.command(name="questions")
@is_staff()
async def questions(ctx):
    """Trade questions."""
    embed = discord.Embed(title="Trade Questions", description="1. What are you trading?\n2. What are you receiving?\n3. Who is the other trader?\n4. Agreed price?\n5. Who goes first?\n6. Special conditions?", color=config.COLORS["INFO"])
    await ctx.send(embed=embed)

@bot.command(name="loghit")
@is_helper()
async def loghit(ctx, hitter: discord.Member, *, hit_details: str):
    """Log a hit with the new format (requires picture in message)."""
    # Check if there's an attachment (picture)
    if not ctx.message.attachments:
        await ctx.send(embed=create_embed("❌ Missing Picture", "A picture must be attached to log a hit!\n\nUsage: `+loghit @hitter <hit details>` with an image attached", config.COLORS["ERROR"]))
        return
    
    # Get the log channel
    log_channel = get_channel_from_config(ctx.guild, "LOG_CHANNEL")
    if not log_channel:
        await ctx.send(embed=create_embed("❌ No Log Channel", "Log channel not configured. Use `+set LOG_CHANNEL #channel`", config.COLORS["ERROR"]))
        return
    
    # Create the hit log embed
    embed = discord.Embed(
        title="🎯 HIT LOGGED",
        color=config.COLORS["WARNING"]
    )
    
    embed.add_field(name="➤ Hit:", value=f"{hitter.mention}", inline=False)
    embed.add_field(name="➤ Was the hit:", value=hit_details, inline=False)
    embed.add_field(name="➤ Split:", value="Pending staff confirmation", inline=False)
    embed.add_field(name="➤ Profit:", value="Pending calculation", inline=False)
    
    embed.set_footer(text="⚠️ Milks are NOT counted as profit!\nCheck #〃・role・perks to view your profit limit")
    embed.timestamp = datetime.utcnow()
    
    # Attach the picture
    if ctx.message.attachments:
        embed.set_image(url=ctx.message.attachments[0].url)
    
    # Send to log channel
    await log_channel.send(embed=embed)
    
    # Confirm to user
    await ctx.send(embed=create_embed("✅ Hit Logged", f"Hit for {hitter.mention} has been logged and sent to {log_channel.mention}", config.COLORS["SUCCESS"]))

# ═══════════════════════════════════════════════════════════════════════════════
# PROFIT COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="search")
@is_helper()
async def search(ctx, user: discord.Member):
    """View profit summary."""
    user_id = str(user.id)
    profit_data = bot_data["global"].get("profits", {}).get(user_id, {"total": 0, "history": []})
    
    history_text = ""
    for entry in profit_data.get("history", [])[-5:]:
        history_text += f"- {entry.get('amount', 0)} - {entry.get('date', 'Unknown')}\n"
    if not history_text:
        history_text = "No history yet."
    
    embed = discord.Embed(title=f"Profit - {user.display_name}", color=config.COLORS["WARNING"])
    embed.add_field(name="Total", value=f"${profit_data.get('total', 0):,.2f}", inline=False)
    embed.add_field(name="History", value=history_text, inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="tprofit")
@is_helper()
async def tprofit(ctx, user: discord.Member, amount: float):
    """Set profit."""
    user_id = str(user.id)
    if "profits" not in bot_data["global"]:
        bot_data["global"]["profits"] = {}
    if user_id not in bot_data["global"]["profits"]:
        bot_data["global"]["profits"][user_id] = {"total": 0, "history": []}
    
    old = bot_data["global"]["profits"][user_id]["total"]
    bot_data["global"]["profits"][user_id]["total"] = amount
    bot_data["global"]["profits"][user_id]["history"].append({"amount": amount, "type": "set", "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "by": ctx.author.id})
    save_data(bot_data)
    
    embed = create_embed("Profit Set", f"{user.mention}\n\nOld: ${old:,.2f}\nNew: ${amount:,.2f}", config.COLORS["SUCCESS"])
    await ctx.send(embed=embed)

@bot.command(name="addprofit")
@is_helper()
async def addprofit(ctx, user: discord.Member, amount: float):
    """Add to profit."""
    user_id = str(user.id)
    if "profits" not in bot_data["global"]:
        bot_data["global"]["profits"] = {}
    if user_id not in bot_data["global"]["profits"]:
        bot_data["global"]["profits"][user_id] = {"total": 0, "history": []}
    
    bot_data["global"]["profits"][user_id]["total"] += amount
    bot_data["global"]["profits"][user_id]["history"].append({"amount": amount, "type": "add", "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "by": ctx.author.id})
    save_data(bot_data)
    
    embed = create_embed("Profit Added", f"Added ${amount:,.2f} to {user.mention}\n\nNew Total: ${bot_data['global']['profits'][user_id]['total']:,.2f}", config.COLORS["SUCCESS"])
    await ctx.send(embed=embed)

@bot.command(name="removeprofit")
@is_helper()
async def removeprofit(ctx, user: discord.Member, amount: float):
    """Remove from profit."""
    user_id = str(user.id)
    if "profits" not in bot_data["global"]:
        bot_data["global"]["profits"] = {}
    if user_id not in bot_data["global"]["profits"]:
        bot_data["global"]["profits"][user_id] = {"total": 0, "history": []}
    
    old_total = bot_data["global"]["profits"][user_id]["total"]
    bot_data["global"]["profits"][user_id]["total"] -= amount
    bot_data["global"]["profits"][user_id]["history"].append({"amount": -amount, "type": "remove", "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "by": ctx.author.id})
    save_data(bot_data)
    
    embed = create_embed("Profit Removed", f"Removed ${amount:,.2f} from {user.mention}\n\nOld Total: ${old_total:,.2f}\nNew Total: ${bot_data['global']['profits'][user_id]['total']:,.2f}", config.COLORS["WARNING"])
    await ctx.send(embed=embed)

@bot.command(name="reset")
@is_helper()
async def reset(ctx, user: discord.Member):
    """Reset profile."""
    user_id = str(user.id)
    if "profits" not in bot_data["global"]:
        bot_data["global"]["profits"] = {}
    bot_data["global"]["profits"][user_id] = {"total": 0, "history": []}
    save_data(bot_data)
    
    embed = create_embed("Profile Reset", f"{user.mention}'s profile has been reset.", config.COLORS["WARNING"])
    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════════════════════════════════════
# TICKET GUEST CONTROLS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="add")
async def add_user(ctx, user_input: str):
    """Add user to ticket."""
    user = await find_user(ctx.guild, user_input)
    if not user:
        await ctx.send(embed=create_embed("Not Found", "User not found.", config.COLORS["ERROR"]))
        return
    try:
        await ctx.channel.set_permissions(user, read_messages=True, send_messages=True)
        await ctx.send(embed=create_embed("User Added", f"{user.mention} added.", config.COLORS["SUCCESS"]))
    except discord.Forbidden:
        await ctx.send(embed=create_embed("Error", "No permission.", config.COLORS["ERROR"]))

@bot.command(name="remove")
async def remove_user(ctx, user: discord.Member):
    """Remove user from ticket."""
    try:
        await ctx.channel.set_permissions(user, read_messages=False, send_messages=False)
        await ctx.send(embed=create_embed("User Removed", f"{user.mention} removed.", config.COLORS["WARNING"]))
    except discord.Forbidden:
        await ctx.send(embed=create_embed("Error", "No permission.", config.COLORS["ERROR"]))

# ═══════════════════════════════════════════════════════════════════════════════
# PROMO COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="promo")
@is_staff()
async def promo(ctx, user: discord.Member, role: discord.Role):
    """Promote user."""
    try:
        await user.add_roles(role)
        await ctx.send(embed=create_embed("Promoted", f"{user.mention} → {role.mention}", config.COLORS["SUCCESS"]))
    except discord.Forbidden:
        await ctx.send(embed=create_embed("Error", "No permission.", config.COLORS["ERROR"]))

@bot.command(name="demo")
@is_staff()
async def demo(ctx, user: discord.Member):
    """Demote user."""
    roles_to_check = ["STAFF_ROLE", "HELPER_ROLE", "VIP_ROLE", "CLIENT_ROLE", "HITTER_ROLE"]
    removed = []
    for role_key in roles_to_check:
        role = get_role(ctx.guild, role_key)
        if role and role in user.roles:
            try:
                await user.remove_roles(role)
                removed.append(role.mention)
            except:
                pass
    
    if removed:
        await ctx.send(embed=create_embed("Demoted", f"{user.mention}\n\nRemoved: {', '.join(removed)}", config.COLORS["ERROR"]))
    else:
        await ctx.send(embed=create_embed("No Changes", f"{user.mention} had no special roles.", config.COLORS["INFO"]))

# ═══════════════════════════════════════════════════════════════════════════════
# AUTO COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="autos")
@is_helper()
async def autos(ctx):
    """View auto status."""
    guild_data = get_guild_data(ctx.guild.id)
    autos_data = guild_data.get("autos", {})
    
    embed = discord.Embed(title="Auto Message Status", color=config.COLORS["INFO"])
    for auto_type in ["vouch", "alert", "welcome"]:
        data = autos_data.get(auto_type, {})
        status = "Running" if data.get("enabled") else "Stopped"
        interval = data.get("interval", 300)
        channel_id = data.get("channel")
        channel_text = f"<#{channel_id}>" if channel_id else "Not set"
        embed.add_field(name=auto_type.title(), value=f"Status: {status}\nInterval: {interval}s\nChannel: {channel_text}", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="vouch")
@is_helper()
async def vouch(ctx, action: str):
    """Vouch messages."""
    guild_data = get_guild_data(ctx.guild.id)
    if action.lower() == "start":
        guild_data["autos"]["vouch"]["enabled"] = True
        guild_data["autos"]["vouch"]["channel"] = ctx.channel.id
        save_data(bot_data)
        await ctx.send(embed=create_embed("Started", f"Vouch in {ctx.channel.mention}", config.COLORS["SUCCESS"]))
    elif action.lower() == "stop":
        guild_data["autos"]["vouch"]["enabled"] = False
        save_data(bot_data)
        await ctx.send(embed=create_embed("Stopped", "Vouch stopped.", config.COLORS["WARNING"]))

@bot.command(name="alert")
@is_helper()
async def alert(ctx, action: str):
    """Alert messages."""
    guild_data = get_guild_data(ctx.guild.id)
    if action.lower() == "start":
        guild_data["autos"]["alert"]["enabled"] = True
        guild_data["autos"]["alert"]["channel"] = ctx.channel.id
        save_data(bot_data)
        await ctx.send(embed=create_embed("Started", f"Alert in {ctx.channel.mention}", config.COLORS["SUCCESS"]))
    elif action.lower() == "stop":
        guild_data["autos"]["alert"]["enabled"] = False
        save_data(bot_data)
        await ctx.send(embed=create_embed("Stopped", "Alert stopped.", config.COLORS["WARNING"]))

@bot.command(name="welcome")
@is_helper()
async def welcome(ctx, action: str):
    """Welcome messages."""
    guild_data = get_guild_data(ctx.guild.id)
    if action.lower() == "start":
        guild_data["autos"]["welcome"]["enabled"] = True
        guild_data["autos"]["welcome"]["channel"] = ctx.channel.id
        save_data(bot_data)
        await ctx.send(embed=create_embed("Started", f"Welcome in {ctx.channel.mention}", config.COLORS["SUCCESS"]))
    elif action.lower() == "stop":
        guild_data["autos"]["welcome"]["enabled"] = False
        save_data(bot_data)
        await ctx.send(embed=create_embed("Stopped", "Welcome stopped.", config.COLORS["WARNING"]))

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG COMMANDS (Per-Server)
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="set")
@commands.has_permissions(administrator=True)
async def set_config(ctx, key: str, *, value: str):
    """Set config for THIS server only."""
    key = key.upper()
    
    if ctx.message.role_mentions:
        value = str(ctx.message.role_mentions[0].id)
    elif ctx.message.channel_mentions:
        value = str(ctx.message.channel_mentions[0].id)
    
    set_guild_config(ctx.guild.id, key, value)
    
    embed = create_embed("Config Updated (This Server)", f"**{key}** = `{value}`", config.COLORS["SUCCESS"])
    await ctx.send(embed=embed)

@bot.command(name="check")
@commands.has_permissions(administrator=True)
async def check(ctx):
    """Validate config."""
    problems = []
    
    for role_key in config.ROLES:
        role = get_role(ctx.guild, role_key)
        role_id = get_guild_config(ctx.guild.id, role_key)
        if role_id and not role:
            problems.append(f"- {role_key}: Not found")
        elif not role_id:
            problems.append(f"- {role_key}: Not set")
    
    for channel_key in config.CHANNELS:
        channel = get_channel_from_config(ctx.guild, channel_key)
        channel_id = get_guild_config(ctx.guild.id, channel_key)
        if channel_id and not channel:
            problems.append(f"- {channel_key}: Not found")
        elif not channel_id:
            problems.append(f"- {channel_key}: Not set")
    
    if problems:
        embed = discord.Embed(title="Config Check", description="\n".join(problems), color=config.COLORS["WARNING"])
    else:
        embed = create_embed("Config Check", "All valid!", config.COLORS["SUCCESS"])
    await ctx.send(embed=embed)

@bot.command(name="listvariables")
@commands.has_permissions(administrator=True)
async def listvariables(ctx):
    """List config keys."""
    embed = discord.Embed(title="Config Keys", color=config.COLORS["INFO"])
    embed.add_field(name="Roles", value="\n".join([f"- `{k}`" for k in config.ROLES.keys()]), inline=True)
    embed.add_field(name="Channels", value="\n".join([f"- `{k}`" for k in config.CHANNELS.keys()]), inline=True)
    embed.set_footer(text="+set <key> <value> to configure THIS server")
    await ctx.send(embed=embed)

@bot.command(name="viewvariables")
@commands.has_permissions(administrator=True)
async def viewvariables(ctx):
    """View current config for this server."""
    embed = discord.Embed(title=f"Config for {ctx.guild.name}", color=config.COLORS["INFO"])
    
    role_values = []
    for key in config.ROLES:
        role = get_role(ctx.guild, key)
        role_values.append(f"- **{key}**: {role.mention if role else 'Not set'}")
    embed.add_field(name="Roles", value="\n".join(role_values), inline=False)
    
    channel_values = []
    for key in config.CHANNELS:
        channel = get_channel_from_config(ctx.guild, key)
        channel_values.append(f"- **{key}**: {channel.mention if channel else 'Not set'}")
    embed.add_field(name="Channels", value="\n".join(channel_values), inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name="viewprefix")
async def viewprefix(ctx):
    """Show prefixes."""
    await ctx.send(embed=create_embed("Prefixes", f"Bot responds to: {', '.join([f'`{p}`' for p in config.PREFIXES])}", config.COLORS["INFO"]))

@bot.command(name="stickymm")
@is_staff()
async def stickymm(ctx):
    """Post sticky MM logs message."""
    embed = discord.Embed(
        title="📋 MM Logs",
        description="This channel logs all middleman transactions and hits.\n\n**Keep this channel organized and professional.**",
        color=config.COLORS["PRIMARY"]
    )
    embed.add_field(
        name="📝 Logging Format",
        value="""**➤ Hit:** with @hitter
**➤ Was the hit:** what you splitted
**➤ Split:** how items were split
**➤ Profit:** the hit/your profit

⚠️ **Disclaimer:** Milks are **NOT** counted as profit!
(check #〃・role・perks to view your profit limit)""",
        inline=False
    )
    embed.set_footer(text="Halo's MM Team!")
    await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping(ctx):
    """Bot latency."""
    latency = round(bot.latency * 1000)
    color = config.COLORS["SUCCESS"] if latency < 100 else config.COLORS["WARNING"] if latency < 200 else config.COLORS["ERROR"]
    await ctx.send(embed=discord.Embed(title="Pong!", description=f"**Latency:** {latency}ms", color=color))

# ═══════════════════════════════════════════════════════════════════════════════
# BLOCKCHAIN COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="wallet")
@is_helper()
async def wallet_command(ctx, network: str = None):
    """Generate encrypted wallets for trades across multiple blockchain networks.
    
    Usage:
        +wallet                 # Generate wallets for all networks (ETH, BTC, SOL, LTC)
        +wallet ETH             # Generate wallet for specific network
    
    Wallets are encrypted and stored in bot_data.json with trade association.
    """
    if not wallet_manager:
        await ctx.send(embed=create_embed("❌ Wallet Manager Unavailable", "Wallet manager not initialized.", config.COLORS["ERROR"]))
        return
    
    # Generate trade ID from channel and timestamp
    trade_id = f"trade_{ctx.channel.id}_{int(datetime.utcnow().timestamp())}"
    
    try:
        networks_to_generate = []
        if network:
            network = network.upper()
            if network not in wallet_manager.NETWORKS:
                await ctx.send(embed=create_embed("❌ Invalid Network", f"Supported networks: ETH, BTC, SOL, LTC", config.COLORS["ERROR"]))
                return
            networks_to_generate = [network]
        else:
            networks_to_generate = list(wallet_manager.NETWORKS.keys())
        
        # Generate wallets
        created_wallets = {}
        for net in networks_to_generate:
            try:
                wallet = wallet_manager.create_wallet(net, trade_id)
                created_wallets[net] = {
                    "address": wallet.get("address"),
                    "created_at": wallet.get("created_at")
                }
            except Exception as e:
                print(f"❌ Failed to create {net} wallet: {e}")
        
        if not created_wallets:
            await ctx.send(embed=create_embed("❌ Wallet Generation Failed", "No wallets were created.", config.COLORS["ERROR"]))
            return
        
        # Create response embed
        embed = discord.Embed(
            title="💰 Wallets Generated",
            description=f"Trade ID: `{trade_id}`\n\nNew wallets created for escrow:",
            color=config.COLORS["SUCCESS"]
        )
        
        for net, wallet_info in created_wallets.items():
            network_name = wallet_manager.NETWORKS[net]["name"]
            embed.add_field(
                name=f"{network_name} ({net})",
                value=f"```{wallet_info['address']}```",
                inline=False
            )
        
        embed.set_footer(text="⚠️ Private keys are encrypted and stored securely.")
        await ctx.send(embed=embed)
        
        # Log to channel
        log_channel = get_channel_from_config(ctx.guild, "LOG_CHANNEL")
        if log_channel:
            log_embed = discord.Embed(
                title="📝 Wallet Generation Log",
                description=f"Trade ID: `{trade_id}`\nGenerated by: {ctx.author.mention}",
                color=config.COLORS["INFO"]
            )
            for net, wallet_info in created_wallets.items():
                network_name = wallet_manager.NETWORKS[net]["name"]
                log_embed.add_field(name=network_name, value=f"`{wallet_info['address']}`", inline=False)
            log_embed.timestamp = datetime.utcnow()
            try:
                await log_channel.send(embed=log_embed)
            except:
                pass
    
    except Exception as e:
        await ctx.send(embed=create_embed("❌ Error", f"Failed to generate wallets: {str(e)}", config.COLORS["ERROR"]))


@bot.command(name="rpc-health")
@is_helper()
async def rpc_health_command(ctx):
    """Check RPC endpoint health status for all configured blockchain networks.
    
    Returns status for: Ethereum, Bitcoin, Solana, Litecoin
    """
    if not rpc_client:
        await ctx.send(embed=create_embed("❌ RPC Client Unavailable", "RPC client not initialized.", config.COLORS["ERROR"]))
        return
    
    try:
        # Check health of all networks
        health_results = await rpc_client.health_check_all()
        
        if not health_results:
            await ctx.send(embed=create_embed("⚠️ No Networks Configured", "No RPC endpoints are configured.", config.COLORS["WARNING"]))
            return
        
        # Create status embed
        embed = discord.Embed(
            title="🏥 RPC Health Status",
            description="Blockchain network endpoint health check",
            color=config.COLORS["INFO"]
        )
        
        all_healthy = True
        for network, is_healthy in health_results.items():
            status_icon = "✅" if is_healthy else "❌"
            status_text = "Healthy" if is_healthy else "Unhealthy"
            embed.add_field(
                name=f"{status_icon} {network.upper()}",
                value=status_text,
                inline=True
            )
            if not is_healthy:
                all_healthy = False
        
        # Set color based on overall health
        if all_healthy:
            embed.color = config.COLORS["SUCCESS"]
        else:
            embed.color = config.COLORS["WARNING"]
        
        embed.timestamp = datetime.utcnow()
        embed.set_footer(text="Health check timeout: 2 seconds per network")
        
        await ctx.send(embed=embed)
    
    except Exception as e:
        await ctx.send(embed=create_embed("❌ Health Check Error", f"Failed to check RPC health: {str(e)}", config.COLORS["ERROR"]))


@bot.command(name="metrics")
@is_helper()
async def metrics_command(ctx):
    """Display blockchain and webhook monitoring dashboard.
    
    Shows:
    - RPC endpoint health status
    - Webhook event statistics
    - Trade processing metrics
    - Network performance data
    """
    try:
        embed = discord.Embed(
            title="📊 Monitoring Dashboard",
            description="Blockchain & Webhook Metrics",
            color=config.COLORS["PRIMARY"]
        )
        
        # RPC Health Section
        if rpc_client:
            health_results = await rpc_client.health_check_all()
            health_text = ""
            for network, is_healthy in health_results.items():
                status = "✅ Online" if is_healthy else "❌ Offline"
                health_text += f"{network.upper()}: {status}\n"
            
            if health_text:
                embed.add_field(name="🔗 RPC Endpoints", value=health_text, inline=False)
        
        # Webhook Events Section
        webhook_events = bot_data["global"].get("webhook_events", {})
        total_events = len(webhook_events)
        processed_events = sum(1 for e in webhook_events.values() if e.get("processed"))
        pending_events = total_events - processed_events
        
        webhook_text = f"Total Events: {total_events}\n"
        webhook_text += f"Processed: {processed_events}\n"
        webhook_text += f"Pending: {pending_events}"
        embed.add_field(name="🔔 Webhook Events", value=webhook_text, inline=True)
        
        # Trade Statistics Section
        trades = bot_data["global"].get("trades", {})
        total_trades = len(trades)
        confirmed_trades = sum(1 for t in trades.values() if t.get("status") == "confirmed")
        failed_trades = sum(1 for t in trades.values() if t.get("status") == "failed")
        pending_trades = sum(1 for t in trades.values() if t.get("status") == "pending")
        
        trade_text = f"Total Trades: {total_trades}\n"
        trade_text += f"✅ Confirmed: {confirmed_trades}\n"
        trade_text += f"⏳ Pending: {pending_trades}\n"
        trade_text += f"❌ Failed: {failed_trades}"
        embed.add_field(name="💱 Trade Status", value=trade_text, inline=True)
        
        # Wallet Statistics Section
        if wallet_manager:
            wallet_data = wallet_manager._load_data()
            total_wallets = len(wallet_data.get("wallets", {}))
            
            # Count wallets by network
            network_counts = {}
            for wallet in wallet_data.get("wallets", {}).values():
                network = wallet.get("network", "unknown")
                network_counts[network] = network_counts.get(network, 0) + 1
            
            wallet_text = f"Total Wallets: {total_wallets}\n"
            for network, count in sorted(network_counts.items()):
                wallet_text += f"{network}: {count}\n"
            
            embed.add_field(name="💰 Wallets", value=wallet_text, inline=True)
        
        embed.timestamp = datetime.utcnow()
        embed.set_footer(text="Dashboard updated in real-time")
        
        await ctx.send(embed=embed)
    
    except Exception as e:
        await ctx.send(embed=create_embed("❌ Dashboard Error", f"Failed to load metrics: {str(e)}", config.COLORS["ERROR"]))


@bot.command(name="help")
async def help_command(ctx, category: str = None):
    """Help menu."""
    prefix = config.PREFIXES[0]
    
    if category is None:
        # Main help menu
        embed = discord.Embed(
            title="📚 MM Bot Help",
            description=f"Use `{prefix}help <category>` for more details.\n\n**Categories:**",
            color=config.COLORS["INFO"]
        )
        
        embed.add_field(
            name="🎫 MM Commands",
            value=f"`{prefix}help mm`\nPanel, ticket, and trade commands",
            inline=True
        )
        embed.add_field(
            name="💰 Profit Commands",
            value=f"`{prefix}help profit`\nProfit tracking commands",
            inline=True
        )
        embed.add_field(
            name="🎟️ Ticket Commands",
            value=f"`{prefix}help ticket`\nTicket guest controls",
            inline=True
        )
        embed.add_field(
            name="🎉 Promo Commands",
            value=f"`{prefix}help promo`\nPromotion/demotion commands",
            inline=True
        )
        embed.add_field(
            name="🤖 Auto Commands",
            value=f"`{prefix}help auto`\nAuto message controls",
            inline=True
        )
        embed.add_field(
            name="⚙️ Config Commands",
            value=f"`{prefix}help config`\nBot configuration",
            inline=True
        )
        
    elif category.lower() == "mm":
        embed = discord.Embed(
            title="🎫 MM Commands (Staff Only)",
            description="Commands for middleman services",
            color=config.COLORS["PRIMARY"]
        )
        commands_list = [
            (f"{prefix}panel", "Post the MM request panel"),
            (f"{prefix}mminfo", "Post MM information"),
            (f"{prefix}mercy", "Post recruit panel with reactions"),
            (f"{prefix}claim", "Claim a ticket"),
            (f"{prefix}unclaim", "Unclaim a ticket"),
            (f"{prefix}transfer @user", "Transfer ticket to another user"),
            (f"{prefix}close", "Close a ticket"),
            (f"{prefix}howto", "How to get items guide"),
            (f"{prefix}fee", "Service fee choice buttons"),
            (f"{prefix}confirm", "Have traders confirm trade"),
            (f"{prefix}questions", "Common trade questions"),
        ]
        for cmd, desc in commands_list:
            embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
            
    elif category.lower() == "profit":
        embed = discord.Embed(
            title="💰 Profit Commands (Helper+)",
            description="Commands for profit tracking",
            color=config.COLORS["WARNING"]
        )
        commands_list = [
            (f"{prefix}search @user", "View profit summary"),
            (f"{prefix}tprofit @user amount", "Set user's profit"),
            (f"{prefix}addprofit @user amount", "Add to user's profit"),
            (f"{prefix}removeprofit @user amount", "Remove from user's profit"),
            (f"{prefix}reset @user", "Reset user's profile"),
        ]
        for cmd, desc in commands_list:
            embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
            
    elif category.lower() == "ticket":
        embed = discord.Embed(
            title="🎟️ Ticket Commands",
            description="Commands for ticket guest controls",
            color=config.COLORS["SUCCESS"]
        )
        commands_list = [
            (f"{prefix}add @user", "Allow a user in the ticket"),
            (f"{prefix}remove @user", "Remove a user from the ticket"),
        ]
        for cmd, desc in commands_list:
            embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
            
    elif category.lower() == "promo":
        embed = discord.Embed(
            title="🎉 Promo Commands (Staff Only)",
            description="Commands for promotions/demotions",
            color=config.COLORS["PRIMARY"]
        )
        commands_list = [
            (f"{prefix}promo @user @role", "Promote user to a role"),
            (f"{prefix}demo @user", "Demote user (remove special roles)"),
        ]
        for cmd, desc in commands_list:
            embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
            
    elif category.lower() == "auto":
        embed = discord.Embed(
            title="🤖 Auto Commands (Helper+)",
            description="Commands for auto messages",
            color=config.COLORS["INFO"]
        )
        commands_list = [
            (f"{prefix}autos", "View all auto message status"),
            (f"{prefix}vouch start/stop", "Control vouch messages"),
            (f"{prefix}alert start/stop", "Control alert messages"),
            (f"{prefix}welcome start/stop", "Control welcome messages"),
        ]
        for cmd, desc in commands_list:
            embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
            
    elif category.lower() == "config":
        embed = discord.Embed(
            title="⚙️ Config Commands (Admin Only)",
            description="Commands for bot configuration",
            color=config.COLORS["ERROR"]
        )
        commands_list = [
            (f"{prefix}set <key> <value>", "Set a config value"),
            (f"{prefix}check", "Validate all config"),
            (f"{prefix}listvariables", "List config keys"),
            (f"{prefix}viewvariables", "View current config"),
            (f"{prefix}viewprefix", "Show current prefix"),
            (f"{prefix}ping", "Check bot latency"),
        ]
        for cmd, desc in commands_list:
            embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
    else:
        embed = create_embed(
            "❌ Unknown Category",
            f"Use `{prefix}help` to see available categories.",
            config.COLORS["ERROR"]
        )
    
    embed.set_footer(text="MM Bot • Middleman Services")
    await ctx.send(embed=embed)
# NEW FEATURES FOR LAW BOT
# Add these classes and commands to main.py before the "RUN BOT" section

# ═══════════════════════════════════════════════════════════════════════════════
# REPORT PANEL COMMAND (NEW)
# ═══════════════════════════════════════════════════════════════════════════════

class ReportPanelView(ui.View):
    """View for Report/Support Panel with buttons"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="Server Issues", emoji="🔨", style=discord.ButtonStyle.blurple, custom_id="report_server_issues")
    async def server_issues_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ReportModal(report_type="Server Issues"))
    
    @ui.button(label="Appeal", emoji="🍃", style=discord.ButtonStyle.green, custom_id="report_appeals")
    async def appeals_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ReportModal(report_type="Appeal"))
    
    @ui.button(label="Report", emoji="❌", style=discord.ButtonStyle.red, custom_id="report_report")
    async def report_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ReportModal(report_type="Report"))


class ReportModal(ui.Modal, title="Create Support Ticket"):
    def __init__(self, report_type: str):
        super().__init__()
        self.report_type = report_type
    
    details = ui.TextInput(label="Describe your issue", placeholder="Provide details...", style=discord.TextStyle.paragraph, max_length=1000)
    evidence = ui.TextInput(label="Evidence (Optional)", placeholder="Screenshots, links, etc.", required=False, style=discord.TextStyle.paragraph)
    
    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        ticket_name = f"report-{interaction.user.name.lower()[:10]}"
        
        try:
            ticket_channel = await guild.create_text_channel(
                name=ticket_name,
                category=guild.get_channel(config.CHANNELS.get("TICKET_CATEGORY"))
            )
            
            embed = discord.Embed(
                title=f"📋 {self.report_type} Ticket",
                description=f"**User:** {interaction.user.mention}\n**Type:** {self.report_type}",
                color=config.REPORT_PANEL["ACCENT_COLOR"]
            )
            embed.add_field(name="Details", value=self.details.value, inline=False)
            if self.evidence.value:
                embed.add_field(name="Evidence", value=self.evidence.value, inline=False)
            
            await ticket_channel.send(embed=embed)
            await interaction.response.send_message(f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error creating ticket: {str(e)}", ephemeral=True)


@bot.command(name="report")
@is_staff()
async def report(ctx):
    """Post the Report/Support panel."""
    embed = discord.Embed(
        title=config.REPORT_PANEL["TITLE"],
        description=config.REPORT_PANEL["DESCRIPTION"],
        color=config.REPORT_PANEL["ACCENT_COLOR"]
    )
    if config.REPORT_PANEL.get("THUMBNAIL"):
        embed.set_thumbnail(url=config.REPORT_PANEL["THUMBNAIL"])
    if config.REPORT_PANEL.get("MAIN_IMAGE"):
        embed.set_image(url=config.REPORT_PANEL["MAIN_IMAGE"])
    embed.set_footer(text=config.REPORT_PANEL["FOOTER"])
    await ctx.send(embed=embed, view=ReportPanelView())


# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM EMBED COMMAND (NEW)
# ═══════════════════════════════════════════════════════════════════════════════

class EmbedModal(ui.Modal, title="Create Custom Embed"):
    title_input = ui.TextInput(label="Embed Title", placeholder="Enter embed title...", max_length=256, required=True)
    description_input = ui.TextInput(label="Embed Description", placeholder="Enter description...", style=discord.TextStyle.paragraph, max_length=4096, required=True)
    footer_input = ui.TextInput(label="Footer (Optional)", placeholder="Enter footer text...", max_length=2048, required=False)
    image_url_input = ui.TextInput(label="Image URL (Optional)", placeholder="https://example.com/image.png", required=False)
    thumbnail_url_input = ui.TextInput(label="Thumbnail URL (Optional)", placeholder="https://example.com/thumb.png", required=False)
    color_input = ui.TextInput(label="Color Hex (Optional, e.g., 9B59B6)", placeholder="Leave blank for default", required=False, max_length=6)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            color = 0x9B59B6
            if self.color_input.value:
                try:
                    color = int(self.color_input.value, 16)
                except ValueError:
                    await interaction.response.send_message("❌ Invalid color format. Using default.", ephemeral=True)
            
            embed = discord.Embed(title=self.title_input.value, description=self.description_input.value, color=color)
            if self.footer_input.value:
                embed.set_footer(text=self.footer_input.value)
            if self.image_url_input.value:
                embed.set_image(url=self.image_url_input.value)
            if self.thumbnail_url_input.value:
                embed.set_thumbnail(url=self.thumbnail_url_input.value)
            
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error creating embed: {str(e)}", ephemeral=True)


@bot.command(name="embed")
@is_staff()
async def embed_command(ctx):
    """Create a custom embed with images."""
    class EmbedButton(ui.View):
        @ui.button(label="Create Embed", emoji="🎨", style=discord.ButtonStyle.blurple, custom_id="embed_create")
        async def embed_button(self, interaction: discord.Interaction, button: ui.Button):
            await interaction.response.send_modal(EmbedModal())
    
    await ctx.send("Click below to create an embed:", view=EmbedButton(), delete_after=300)


# ═══════════════════════════════════════════════════════════════════════════════
# STICKY HIT LOGGING - on_message LISTENER
# ═══════════════════════════════════════════════════════════════════════════════

@bot.event
async def on_message(message):
    """Handle sticky hit logging on new messages"""
    if message.author == bot.user:
        await bot.process_commands(message)
        return
    
    # Send sticky hit logging message if enabled
    if config.STICKY_HIT_LOGGING["ENABLED"]:
        channel_id = config.STICKY_HIT_LOGGING["CHANNEL_ID"]
        if channel_id and message.channel.id == channel_id:
            embed = discord.Embed(
                title=config.STICKY_HIT_LOGGING["TITLE"],
                description=config.STICKY_HIT_LOGGING["DESCRIPTION"],
                color=config.STICKY_HIT_LOGGING["COLOR"]
            )
            
            if config.STICKY_HIT_LOGGING.get("THUMBNAIL"):
                embed.set_thumbnail(url=config.STICKY_HIT_LOGGING["THUMBNAIL"])
            
            if config.STICKY_HIT_LOGGING.get("MAIN_IMAGE"):
                embed.set_image(url=config.STICKY_HIT_LOGGING["MAIN_IMAGE"])
            
            try:
                if config.STICKY_HIT_LOGGING.get("DELETE_AFTER_RESEND"):
                    async for msg in message.channel.history(limit=20):
                        if msg.author == bot.user and msg.embeds:
                            if msg.embeds[0].title == config.STICKY_HIT_LOGGING["TITLE"]:
                                await asyncio.sleep(0.5)
                                await msg.delete()
                                break
                
                await message.channel.send(embed=embed)
            except Exception as e:
                print(f"Error sending sticky message: {e}")
    
    await bot.process_commands(message)
# ═══════════════════════════════════════════════════════════════════════════════
# RUN BOT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("DISCORD_TOKEN not found! Set it with: export DISCORD_TOKEN='your_token'")
        exit(1)
    bot.run(TOKEN)
