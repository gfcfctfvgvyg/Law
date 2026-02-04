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
