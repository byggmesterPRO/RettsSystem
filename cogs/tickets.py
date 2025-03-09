import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import logging
from typing import Optional
import datetime
import os
import tempfile
import asyncio

# Set up logging
logger = logging.getLogger("CourtBot.Tickets")

class DeleteTicketView(discord.ui.View):
    """View for the delete ticket button"""
    
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        
    @discord.ui.button(
        label="Slett kanal", 
        style=discord.ButtonStyle.danger, 
        emoji="🗑️",
        custom_id="delete_ticket_button"
    )
    async def delete_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Called when someone clicks the delete button"""
        # Check if user has manage channels permission or is a judge
        is_judge = False
        
        # Check if user has the judge role
        judge_role = discord.utils.get(interaction.guild.roles, name="Dommer")
        if judge_role and judge_role in interaction.user.roles:
            is_judge = True
            
        # Also check database for judge status
        conn = sqlite3.connect('data/courtbot.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute('''
        SELECT * FROM judges WHERE user_id = ?
        ''', (interaction.user.id,))
        
        db_judge = c.fetchone()
        conn.close()
        
        if db_judge:
            is_judge = True
        
        # Allow if user has manage_channels permission or is a judge
        if not (interaction.user.guild_permissions.manage_channels or is_judge):
            await interaction.response.send_message("Du har ikke tillatelse til å slette denne kanalen. Du må være dommer eller ha tillatelse til å administrere kanaler.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Send confirmation message
            await interaction.followup.send("Kanalen vil bli slettet om 5 sekunder...", ephemeral=True)
            
            # Send channel message
            await interaction.channel.send("Denne kanalen vil bli slettet om 5 sekunder...")
            
            # Wait 5 seconds
            await asyncio.sleep(5)
            
            # Delete channel
            await interaction.channel.delete()
            logger.info(f"Channel {interaction.channel.name} deleted by {interaction.user}")
        except Exception as e:
            await interaction.followup.send(f"Feil under sletting av kanal: {e}", ephemeral=True)
            logger.error(f"Error deleting channel {interaction.channel.name}: {e}")

class TicketView(discord.ui.View):
    """View for ticket creation buttons"""
    
    def __init__(self, bot, category_id, title, description, emoji, button_text, role_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.category_id = category_id
        self.title = title
        self.description = description
        self.emoji = emoji
        self.role_id = role_id
        
        # Add button with custom emoji and text
        button = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label=button_text, 
            emoji=emoji,
            custom_id=f"ticket_button_{category_id}"
        )
        self.add_item(button)

class Tickets(commands.Cog):
    """Commands for ticket management"""
    
    def __init__(self, bot):
        self.bot = bot
        # Register persistent views when the cog is loaded
        self.bot.add_view(DeleteTicketView(bot))
        
        # Load existing ticket buttons from database
        self.load_ticket_views()
        
    def load_ticket_views(self):
        """Load existing ticket buttons from database"""
        try:
            conn = self.get_db_connection()
            c = conn.cursor()
            
            # Check if categories table exists
            c.execute('''
            SELECT name FROM sqlite_master WHERE type='table' AND name='categories'
            ''')
            
            if not c.fetchone():
                logger.warning("Categories table doesn't exist yet. Skipping ticket view loading.")
                conn.close()
                return
            
            # Get all categories
            c.execute('''
            SELECT * FROM categories
            ''')
            
            categories = c.fetchall()
            
            # Load ticket views for each category
            for category in categories:
                # Check if ticket_buttons table exists
                c.execute('''
                SELECT name FROM sqlite_master WHERE type='table' AND name='ticket_buttons'
                ''')
                
                if not c.fetchone():
                    logger.warning("Ticket_buttons table doesn't exist yet. Skipping ticket view loading.")
                    break
                
                # Get ticket buttons for this category
                c.execute('''
                SELECT * FROM ticket_buttons WHERE category_id = ?
                ''', (category['category_id'],))
                
                buttons = c.fetchall()
                
                # Register views for each button
                for button in buttons:
                    # Check if the category still exists on the server
                    category_channel = self.bot.get_channel(button['category_id'])
                    if not category_channel:
                        logger.warning(f"Category {button['category_id']} not found. Skipping button.")
                        continue
                    
                    # Create and register the view
                    view = TicketView(
                        self.bot,
                        button['category_id'],
                        button['title'],
                        button['description'],
                        button['emoji'],
                        button['button_text'],
                        button['role_id']
                    )
                    self.bot.add_view(view)
                    logger.info(f"Registered ticket view for {button['title']} in category {category['name']}")
            
            conn.close()
        except Exception as e:
            logger.error(f"Error loading ticket views: {e}")
            # Continue bot operation even if ticket views couldn't be loaded
        
    def get_db_connection(self):
        """Get database connection"""
        conn = sqlite3.connect('data/courtbot.db')
        conn.row_factory = sqlite3.Row
        return conn
        
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Handle button interactions"""
        if not interaction.data or not interaction.data.get('custom_id'):
            return
            
        custom_id = interaction.data['custom_id']
        
        # Check if this is a ticket button
        if custom_id.startswith('ticket_button_'):
            await self.handle_ticket_button(interaction, custom_id)
    
    async def handle_ticket_button(self, interaction: discord.Interaction, custom_id: str):
        """Handle ticket button interactions"""
        # Extract category ID from custom_id
        category_id = int(custom_id.replace('ticket_button_', ''))
        
        # Get connection to database
        conn = self.get_db_connection()
        c = conn.cursor()
        
        # Get next case ID
        c.execute("SELECT MAX(id) as max_id FROM cases")
        result = c.fetchone()
        next_id = 1 if result['max_id'] is None else result['max_id'] + 1
        
        # Get category
        category = interaction.guild.get_channel(category_id)
        if not category:
            await interaction.response.send_message("Feil: Kategorien eksisterer ikke lenger.", ephemeral=True)
            conn.close()
            return
        
        # Get category info from database
        c.execute('''
        SELECT * FROM categories WHERE category_id = ?
        ''', (category_id,))
        
        category_info = c.fetchone()
        if not category_info:
            await interaction.response.send_message("Feil: Kategorien er ikke registrert i databasen.", ephemeral=True)
            conn.close()
            return
            
        # Create ticket channel with proper naming format using user's display name
        channel_name = f"{interaction.user.display_name.lower().replace(' ', '-')}-{next_id}"
        
        # Set permissions for channel
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Add role permission if specified
        if category_info['role_id'] and category_info['role_id'] != 0:
            role = interaction.guild.get_role(category_info['role_id'])
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        # Create channel
        try:
            await interaction.response.defer(ephemeral=True)
            
            channel = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites
            )
            
            # Create welcome message
            embed = discord.Embed(
                title=f"Ny sak i {category.name}",
                description="Velkommen til din nye sak. En dommer vil se på saken din så snart som mulig.",
                color=discord.Color.blue()
            )
            embed.add_field(name="Sak ID", value=str(next_id), inline=True)
            embed.add_field(name="Opprettet av", value=interaction.user.mention, inline=True)
            embed.add_field(name="Status", value="🟢 Åpen", inline=True)
            embed.add_field(name="Opprettet", value=discord.utils.format_dt(datetime.datetime.now()), inline=True)
            embed.set_footer(text=f"Sak #{next_id}")
            
            # Send welcome message
            await channel.send(
                f"{interaction.user.mention} har opprettet en ny sak.",
                embed=embed
            )
            
            # Store case in database
            c.execute('''
            INSERT INTO cases (channel_id, category_id, creator_id, title, description)
            VALUES (?, ?, ?, ?, ?)
            ''', (channel.id, category.id, interaction.user.id, f"Ny sak i {category.name}", f"Opprettet av {interaction.user.display_name}"))
            
            conn.commit()
            
            # Send confirmation to user
            await interaction.followup.send(f"Din sak har blitt opprettet i {channel.mention}!", ephemeral=True)
            logger.info(f"Ticket created by {interaction.user} in category {category.name}")
            
        except Exception as e:
            await interaction.followup.send(f"Feil under oppretting av sak: {e}", ephemeral=True)
            logger.error(f"Error creating ticket: {e}")
            
        finally:
            conn.close()

    @app_commands.command(name="ticket", description="Oppretter en ticket-knapp i kanalen")
    @app_commands.describe(
        category="Kategorien der tickets skal opprettes",
        title="Tittel på ticket-knappen",
        description="Beskrivelse som vises i ticket-kanalen",
        button_emoji="Emoji som vises på knappen",
        button_text="Tekst som vises på knappen",
        role="Rolle som skal ha tilgang til alle tickets (valgfritt)"
    )
    async def create_ticket(
        self, 
        interaction: discord.Interaction, 
        category: discord.CategoryChannel,
        title: str, 
        description: str, 
        button_emoji: str, 
        button_text: str,
        role: Optional[discord.Role] = None
    ):
        """Creates a ticket button in the channel it was typed in"""
        await interaction.response.defer(ephemeral=True)
        
        # Get connection to database
        conn = self.get_db_connection()
        c = conn.cursor()
        
        # Store category in database if not exists
        c.execute('''
        SELECT * FROM categories WHERE category_id = ?
        ''', (category.id,))
        
        existing = c.fetchone()
        role_id = role.id if role else 0
        
        if existing:
            # Update existing category
            c.execute('''
            UPDATE categories
            SET name = ?, role_id = ?
            WHERE category_id = ?
            ''', (title, role_id, category.id))
        else:
            # Insert new category
            c.execute('''
            INSERT INTO categories (category_id, name, role_id)
            VALUES (?, ?, ?)
            ''', (category.id, title, role_id))
        
        # Store button information in a separate table or variable
        # Since we can't store it in the categories table
        
        conn.commit()
        conn.close()
        
        # Create embed for ticket panel
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blue()
        )
        
        # Create view with button
        view = discord.ui.View(timeout=None)
        button = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label=button_text, 
            emoji=button_emoji,
            custom_id=f"ticket_button_{category.id}"
        )
        view.add_item(button)
        
        # Register the view with the bot for persistence
        self.bot.add_view(view)
        
        # Send panel
        await interaction.channel.send(embed=embed, view=view)
        
        # Send confirmation
        await interaction.followup.send("Ticket-panel opprettet!", ephemeral=True)
        logger.info(f"Ticket panel created by {interaction.user} in {interaction.channel.name}")
    
    @app_commands.command(name="lukk-sak", description="Lukker den nåværende saken")
    @app_commands.default_permissions(administrator=True)
    async def close_case(self, interaction: discord.Interaction):
        """Closes the current ticket and archives it"""
        await interaction.response.defer(ephemeral=True)
        
        # Check if channel is a ticket
        conn = self.get_db_connection()
        c = conn.cursor()
        
        c.execute('''
        SELECT * FROM cases WHERE channel_id = ?
        ''', (interaction.channel.id,))
        
        case = c.fetchone()
        
        if not case:
            await interaction.followup.send("Dette er ikke en sak-kanal.")
            conn.close()
            return
        
        # Get archive category
        c.execute('''
        SELECT * FROM categories WHERE name = 'Arkiv'
        ''')
        
        archive = c.fetchone()
        
        if not archive:
            await interaction.followup.send("Feil: Arkiv-kategori finnes ikke.")
            conn.close()
            return
        
        archive_category = interaction.guild.get_channel(archive['category_id'])
        
        if not archive_category:
            await interaction.followup.send("Feil: Arkiv-kategori finnes ikke lenger.")
            conn.close()
            return
        
        # Update case status
        c.execute('''
        UPDATE cases
        SET status = 'Lukket', closed_at = ?
        WHERE channel_id = ?
        ''', (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), interaction.channel.id))
        
        conn.commit()
        
        # Archive channel (move to archive category)
        await interaction.channel.edit(category=archive_category)
        
        # Sync permissions with the archive category
        await interaction.channel.edit(sync_permissions=True)
        
        # Disable sending messages for everyone
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        
        # Send closure message
        embed = discord.Embed(
            title="Sak lukket",
            description=f"Denne saken har blitt lukket av {interaction.user.mention}.",
            color=discord.Color.red()
        )
        embed.add_field(name="Lukket", value=discord.utils.format_dt(datetime.datetime.now()), inline=True)
        
        await interaction.channel.send(embed=embed)
        
        await interaction.followup.send("Saken er nå lukket og arkivert.")
        logger.info(f"Case {case['id']} closed by {interaction.user}")
        
        conn.close()
    
    @app_commands.command(name="arkiver-sak", description="Arkiverer den nåværende saken uten å lukke den")
    @app_commands.default_permissions(administrator=True)
    async def archive_case(self, interaction: discord.Interaction):
        """Archives the current ticket without closing it"""
        await interaction.response.defer(ephemeral=True)
        
        # Check if channel is a ticket
        conn = self.get_db_connection()
        c = conn.cursor()
        
        c.execute('''
        SELECT * FROM cases WHERE channel_id = ?
        ''', (interaction.channel.id,))
        
        case = c.fetchone()
        
        if not case:
            await interaction.followup.send("Dette er ikke en sak-kanal.")
            conn.close()
            return
        
        # Get archive category
        c.execute('''
        SELECT * FROM categories WHERE name = 'Arkiv'
        ''')
        
        archive = c.fetchone()
        
        if not archive:
            await interaction.followup.send("Feil: Arkiv-kategori finnes ikke.")
            conn.close()
            return
        
        archive_category = interaction.guild.get_channel(archive['category_id'])
        
        if not archive_category:
            await interaction.followup.send("Feil: Arkiv-kategori finnes ikke lenger.")
            conn.close()
            return
        
        # Archive channel (move to archive category)
        await interaction.channel.edit(category=archive_category)
        
        # Sync permissions with the archive category
        await interaction.channel.edit(sync_permissions=True)
        
        # Send archive message
        embed = discord.Embed(
            title="Sak arkivert",
            description=f"Denne saken har blitt arkivert av {interaction.user.mention}.",
            color=discord.Color.gold()
        )
        embed.add_field(name="Arkivert", value=discord.utils.format_dt(datetime.datetime.now()), inline=True)
        
        await interaction.channel.send(embed=embed)
        
        await interaction.followup.send("Saken er nå arkivert.")
        logger.info(f"Case {case['id']} archived by {interaction.user}")
        
        conn.close()

    @app_commands.command(name="avslutt-sak", description="Avslutter saken med begrunnelse og arkiverer den")
    @app_commands.describe(
        grunnlag="Begrunnelse for avslutning av saken"
    )
    async def close_case_with_reason(self, interaction: discord.Interaction, grunnlag: str):
        """
        Closes the case with specified reason, notifies the opener via DM, 
        exports to HTML, uploads to audit log, then closes the ticket
        """
        await interaction.response.defer(ephemeral=False)
        
        # Check if channel is a ticket
        conn = self.get_db_connection()
        c = conn.cursor()
        
        c.execute('''
        SELECT * FROM cases WHERE channel_id = ?
        ''', (interaction.channel.id,))
        
        case = c.fetchone()
        
        if not case:
            await interaction.followup.send("Dette er ikke en sak-kanal.", ephemeral=True)
            conn.close()
            return
        
        # Check if user is a judge or admin
        judge_role = discord.utils.get(interaction.guild.roles, name="Dommer")
        admin_role = discord.utils.get(interaction.guild.roles, name="Administrator")
        
        if not (judge_role in interaction.user.roles or admin_role in interaction.user.roles):
            await interaction.followup.send("Du har ikke tillatelse til å avslutte saker.", ephemeral=True)
            conn.close()
            return
        
        # Get archive category
        c.execute('''
        SELECT * FROM categories WHERE name = 'Arkiv'
        ''')
        
        archive = c.fetchone()
        
        if not archive:
            await interaction.followup.send("Feil: Arkiv-kategori finnes ikke.", ephemeral=True)
            conn.close()
            return
        
        archive_category = interaction.guild.get_channel(archive['category_id'])
        
        if not archive_category:
            await interaction.followup.send("Feil: Arkiv-kategori finnes ikke lenger.", ephemeral=True)
            conn.close()
            return
        
        # Get archive channel
        archive_channel = None
        for channel in archive_category.text_channels:
            if channel.name == "arkiv-logg":
                archive_channel = channel
                break
        
        if not archive_channel:
            await interaction.followup.send("Feil: Arkiv-logg kanal finnes ikke.", ephemeral=True)
            conn.close()
            return
        
        # Step 1: Export to HTML
        # We'll use the export_case function from the Evidence cog
        evidence_cog = self.bot.get_cog("Evidence")
        if not evidence_cog:
            await interaction.followup.send("Feil: Kunne ikke finne Evidence-cog for eksport.", ephemeral=True)
            conn.close()
            return
        
        # Create a temporary message to show progress
        progress_msg = await interaction.followup.send("Avslutter sak...\n- Eksporterer til HTML...")
        
        # Call the export_case method to generate HTML
        try:
            html_content = await evidence_cog.generate_case_html(interaction.channel, case)
            if not html_content:
                await progress_msg.edit(content="Feil: Kunne ikke generere HTML for saken.")
                conn.close()
                return
            
            await progress_msg.edit(content="Avslutter sak...\n- Eksporterer til HTML... ✅\n- Lagrer i arkiv...")
        except Exception as e:
            await progress_msg.edit(content=f"Feil under HTML-generering: {e}")
            logger.error(f"Error generating HTML for case {case['id']}: {e}")
            conn.close()
            return
        
        # Step 2: Save and upload to audit log
        try:
            # Create file name for display
            display_filename = f"sak_{case['id']}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(html_content)
                temp_file_path = temp_file.name
            
            # Create Discord file object
            file = discord.File(temp_file_path, filename=display_filename)
            
            # Send to archive channel
            archive_message = await archive_channel.send(
                f"**Sak #{case['id']} - {case['title']}** avsluttet av {interaction.user.mention}\n"
                f"**Begrunnelse:** {grunnlag}",
                file=file
            )
            
            # Clean up temporary file
            os.unlink(temp_file_path)
            
            # Get the URL of the uploaded file
            archive_url = None
            for attachment in archive_message.attachments:
                if attachment.filename == display_filename:
                    archive_url = attachment.url
                    break
            
            if not archive_url:
                await progress_msg.edit(content="Feil: Kunne ikke finne URL for arkivert fil.")
                conn.close()
                return
            
            await progress_msg.edit(content="Avslutter sak...\n- Eksporterer til HTML... ✅\n- Lagrer i arkiv... ✅\n- Sender varsel til klient...")
        except Exception as e:
            await progress_msg.edit(content=f"Feil under arkivering: {e}")
            logger.error(f"Error archiving case {case['id']}: {e}")
            conn.close()
            return
        
        # Step 3: Notify case creator
        try:
            creator = interaction.guild.get_member(case['creator_id'])
            if creator:
                embed = discord.Embed(
                    title=f"Din sak har blitt avsluttet",
                    description=f"Sak #{case['id']} - {case['title']} har blitt avsluttet av {interaction.user.display_name}.",
                    color=discord.Color.red()
                )
                embed.add_field(name="Begrunnelse", value=grunnlag, inline=False)
                embed.add_field(name="Arkiv", value=f"[Klikk her for å se arkivert sak]({archive_url})", inline=False)
                
                try:
                    await creator.send(embed=embed)
                except discord.Forbidden:
                    logger.warning(f"Could not send DM to case creator {creator.name}")
            
            await progress_msg.edit(content="Avslutter sak...\n- Eksporterer til HTML... ✅\n- Lagrer i arkiv... ✅\n- Sender varsel til klient... ✅\n- Oppdaterer database...")
        except Exception as e:
            await progress_msg.edit(content=f"Feil under varsling av klient: {e}")
            logger.error(f"Error notifying creator for case {case['id']}: {e}")
            # Continue anyway, this is not critical
        
        # Step 4: Update case in database
        try:
            c.execute('''
            UPDATE cases
            SET status = 'Lukket', closed_at = ?, closing_reason = ?, archive_url = ?
            WHERE channel_id = ?
            ''', (
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                grunnlag, 
                archive_url, 
                interaction.channel.id
            ))
            
            conn.commit()
            await progress_msg.edit(content="Avslutter sak...\n- Eksporterer til HTML... ✅\n- Lagrer i arkiv... ✅\n- Sender varsel til klient... ✅\n- Oppdaterer database... ✅\n- Lukker kanal...")
        except Exception as e:
            await progress_msg.edit(content=f"Feil under oppdatering av database: {e}")
            logger.error(f"Error updating database for case {case['id']}: {e}")
            conn.close()
            return
        
        # Step 5: Close the ticket (move to archive and disable sending)
        try:
            # Move to archive category
            await interaction.channel.edit(category=archive_category)
            
            # Sync permissions with the archive category
            await interaction.channel.edit(sync_permissions=True)
            
            # Disable sending messages for everyone
            await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
            
            # Send closure message
            embed = discord.Embed(
                title="Sak avsluttet",
                description=f"Denne saken har blitt avsluttet av {interaction.user.mention}.",
                color=discord.Color.red()
            )
            embed.add_field(name="Begrunnelse", value=grunnlag, inline=False)
            embed.add_field(name="Lukket", value=discord.utils.format_dt(datetime.datetime.now()), inline=True)
            embed.add_field(name="Arkiv", value=f"[Klikk her for å se arkivert sak]({archive_url})", inline=False)
            
            # Create delete view
            delete_view = DeleteTicketView(self.bot)
            
            await interaction.channel.send(embed=embed, view=delete_view)
            
            await progress_msg.edit(content=f"Sak #{case['id']} er nå avsluttet og arkivert.")
            logger.info(f"Case {case['id']} closed with reason '{grunnlag}' by {interaction.user}")
        except Exception as e:
            await progress_msg.edit(content=f"Feil under lukking av kanal: {e}")
            logger.error(f"Error closing channel for case {case['id']}: {e}")
        
        conn.close()

async def setup(bot):
    await bot.add_cog(Tickets(bot))
