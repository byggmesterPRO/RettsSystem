import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import logging
import datetime
import os
import io
import asyncio

# Set up logging
logger = logging.getLogger("CourtBot.Judge")

class Judge(commands.Cog):
    """Commands for judges to manage cases"""
    
    def __init__(self, bot):
        self.bot = bot
    
    def get_db_connection(self):
        """Get database connection"""
        conn = sqlite3.connect('data/courtbot.db')
        conn.row_factory = sqlite3.Row
        return conn
    
    async def is_judge(self, user_id):
        """Check if user is a judge"""
        conn = self.get_db_connection()
        c = conn.cursor()
        
        c.execute('''
        SELECT * FROM judges WHERE user_id = ?
        ''', (user_id,))
        
        judge = c.fetchone()
        conn.close()
        
        return judge is not None
    
    @app_commands.command(name="ta-sak", description="Tar den nåværende saken og flytter den til ditt kvarter")
    async def claim_case(self, interaction: discord.Interaction):
        """Claims the current case and moves it to the judge's quarters"""
        await interaction.response.defer(ephemeral=False)
        
        # Check if user is a judge
        is_judge = await self.is_judge(interaction.user.id)
        if not is_judge:
            await interaction.followup.send("Du har ikke tillatelse til å ta saker.", ephemeral=True)
            return
        
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
        
        # Check if case is already assigned
        if case['assigned_judge_id'] is not None:
            judge = interaction.guild.get_member(case['assigned_judge_id'])
            if judge:
                await interaction.followup.send(f"Denne saken er allerede tildelt {judge.display_name}.", ephemeral=True)
            else:
                await interaction.followup.send("Denne saken er allerede tildelt en dommer.", ephemeral=True)
            conn.close()
            return
        
        # Get judge's category
        c.execute('''
        SELECT * FROM judges WHERE user_id = ?
        ''', (interaction.user.id,))
        
        judge = c.fetchone()
        
        if not judge:
            await interaction.followup.send("Feil: Kunne ikke finne ditt dommer-kvarter.", ephemeral=True)
            conn.close()
            return
        
        judge_category = interaction.guild.get_channel(judge['category_id'])
        
        if not judge_category:
            await interaction.followup.send("Feil: Ditt dommer-kvarter eksisterer ikke lenger.", ephemeral=True)
            conn.close()
            return
        
        # Update case in database
        c.execute('''
        UPDATE cases 
        SET assigned_judge_id = ?, status = 'Under behandling'
        WHERE channel_id = ?
        ''', (interaction.user.id, interaction.channel.id))
        
        conn.commit()
        
        # Move channel to judge's category
        await interaction.channel.edit(category=judge_category)
        
        # Update channel permissions
        await interaction.channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        
        # Send claim message
        embed = discord.Embed(
            title="Sak tildelt",
            description=f"Denne saken har blitt tatt av dommer {interaction.user.mention}.",
            color=discord.Color.orange()
        )
        embed.add_field(name="Status", value="🟠 Under behandling", inline=True)
        embed.add_field(name="Tildelt", value=discord.utils.format_dt(datetime.datetime.now()), inline=True)
        
        await interaction.followup.send(embed=embed)
        
        # Notify case creator
        creator = interaction.guild.get_member(case['creator_id'])
        if creator:
            try:
                await creator.send(f"Din sak har blitt tatt av dommer {interaction.user.display_name}.")
            except discord.Forbidden:
                logger.warning(f"Could not send DM to case creator {creator.name}")
        
        logger.info(f"Case {case['id']} claimed by judge {interaction.user}")
        conn.close()
    
    @app_commands.command(name="send-sak", description="Sender den nåværende saken til en annen kategori")
    @app_commands.describe(
        kategori="Kategorien saken skal sendes til"
    )
    async def send_case(self, interaction: discord.Interaction, kategori: str):
        """Sends the current case to a different category"""
        await interaction.response.defer(ephemeral=True)
        
        # Check if user is a judge
        is_judge = await self.is_judge(interaction.user.id)
        if not is_judge:
            await interaction.followup.send("Du har ikke tillatelse til å flytte saker.", ephemeral=True)
            return
        
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
        
        # Find target category
        c.execute('''
        SELECT * FROM categories WHERE name LIKE ?
        ''', (f"%{kategori}%",))
        
        categories = c.fetchall()
        
        if not categories:
            await interaction.followup.send(f"Fant ingen kategori med navn '{kategori}'.", ephemeral=True)
            conn.close()
            return
        
        if len(categories) > 1:
            # Multiple matches, list them
            category_list = "\n".join([f"{cat['name']}" for cat in categories])
            await interaction.followup.send(
                f"Fant flere kategorier som matcher. Vær mer spesifikk:\n{category_list}", 
                ephemeral=True
            )
            conn.close()
            return
        
        target_category = interaction.guild.get_channel(categories[0]['category_id'])
        
        if not target_category:
            await interaction.followup.send("Feil: Kategorien eksisterer ikke lenger.", ephemeral=True)
            conn.close()
            return
        
        # Move channel to target category
        await interaction.channel.edit(category=target_category)
        
        # Update role permissions if needed
        role_id = categories[0]['role_id']
        if role_id and role_id != 0:
            role = interaction.guild.get_role(role_id)
            if role:
                await interaction.channel.set_permissions(role, read_messages=True, send_messages=True)
        
        # Send move message
        await interaction.channel.send(
            f"Denne saken har blitt flyttet til kategorien '{target_category.name}' av {interaction.user.mention}."
        )
        
        await interaction.followup.send(f"Saken er flyttet til '{target_category.name}'.")
        logger.info(f"Case {case['id']} moved to category {target_category.name} by {interaction.user}")
        
        conn.close()
    
    @app_commands.command(name="send-dm", description="Sender en DM til en bruker gjennom boten")
    @app_commands.describe(
        bruker="Brukeren som skal motta DM",
        tekst="Meldingen som skal sendes"
    )
    async def send_dm(self, interaction: discord.Interaction, bruker: discord.Member, tekst: str):
        """
        Allows judges to send DMs to users through the bot
        
        Args:
            bruker: The user to send the DM to
            tekst: The message to send
        """
        await interaction.response.defer(ephemeral=True)
        
        # Check if user is a judge
        is_judge = await self.is_judge(interaction.user.id)
        if not is_judge:
            await interaction.followup.send("Du har ikke tillatelse til å sende DMs gjennom boten.", ephemeral=True)
            return
        
        try:
            # Create embed for the DM
            embed = discord.Embed(
                title="Melding fra Domstolen",
                description=tekst,
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Sendt av dommer {interaction.user.display_name}")
            embed.timestamp = datetime.datetime.now()
            
            # Send DM to user
            await bruker.send(embed=embed)
            
            # Confirm to judge
            await interaction.followup.send(f"Melding sendt til {bruker.display_name}.", ephemeral=True)
            
            # Log the action
            logger.info(f"DM sent to {bruker.display_name} by judge {interaction.user.display_name}")
            
        except discord.Forbidden:
            await interaction.followup.send(
                f"Kunne ikke sende melding til {bruker.display_name}. Brukeren har kanskje blokkert DMs fra serveren.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"En feil oppstod: {e}", ephemeral=True)
            logger.error(f"Error sending DM: {e}")
    
    @app_commands.command(name="legg-til-notat", description="Legger til et notat i saken")
    @app_commands.describe(
        tekst="Notatteksten som skal legges til"
    )
    async def add_note(self, interaction: discord.Interaction, tekst: str):
        """Adds a note to the case file"""
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
        
        # Create note embed
        embed = discord.Embed(
            title="Dommer-notat",
            description=tekst,
            color=discord.Color.dark_blue()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Tidspunkt", value=discord.utils.format_dt(datetime.datetime.now()), inline=True)
        
        await interaction.followup.send(embed=embed)
        
        logger.info(f"Note added to case {case['id']} by {interaction.user}")
        conn.close()
    
    @app_commands.command(name="vis-saker", description="Viser alle saker tildelt en dommer")
    @app_commands.describe(
        bruker="Dommeren som sakene skal vises for (valgfritt)"
    )
    async def show_cases(self, interaction: discord.Interaction, bruker: discord.Member = None):
        """Shows all cases assigned to the judge"""
        await interaction.response.defer(ephemeral=True)
        
        target_user = bruker if bruker else interaction.user
        
        # Check if user is a judge if checking own cases
        if target_user.id == interaction.user.id:
            is_judge = await self.is_judge(interaction.user.id)
            if not is_judge:
                await interaction.followup.send("Du er ikke en dommer.", ephemeral=True)
                return
        
        # Get cases from database
        conn = self.get_db_connection()
        c = conn.cursor()
        
        c.execute('''
        SELECT * FROM cases WHERE assigned_judge_id = ? ORDER BY id DESC
        ''', (target_user.id,))
        
        cases = c.fetchall()
        
        if not cases:
            await interaction.followup.send(
                f"{'Du har' if target_user.id == interaction.user.id else f'{target_user.display_name} har'} ingen tildelte saker."
            )
            conn.close()
            return
        
        # Create embed with cases
        embed = discord.Embed(
            title=f"Saker tildelt {target_user.display_name}",
            color=discord.Color.blue()
        )
        
        for case in cases:
            channel = interaction.guild.get_channel(case['channel_id'])
            status_emoji = "🟢" if case['status'] == "Åpen" else "🟠" if case['status'] == "Under behandling" else "🔴" if case['status'] == "Lukket" else "🟣"
            
            value = f"**Status:** {status_emoji} {case['status']}\n"
            value += f"**Opprettet:** {case['created_at']}\n"
            
            if channel:
                value += f"**Kanal:** {channel.mention}"
            else:
                value += "**Kanal:** Ikke tilgjengelig"
            
            embed.add_field(
                name=f"Sak #{case['id']} - {case['title']}",
                value=value,
                inline=False
            )
        
        await interaction.followup.send(embed=embed)
        conn.close()
    
    @app_commands.command(name="vis-åpne-saker", description="Viser alle åpne saker i systemet")
    async def show_open_cases(self, interaction: discord.Interaction):
        """Shows all open cases in the system"""
        await interaction.response.defer(ephemeral=True)
        
        # Get cases from database
        conn = self.get_db_connection()
        c = conn.cursor()
        
        c.execute('''
        SELECT * FROM cases WHERE status = 'Åpen' ORDER BY id DESC
        ''')
        
        cases = c.fetchall()
        
        if not cases:
            await interaction.followup.send("Det er ingen åpne saker.")
            conn.close()
            return
        
        # Create embed with cases
        embed = discord.Embed(
            title="Åpne saker",
            color=discord.Color.green()
        )
        
        for case in cases:
            channel = interaction.guild.get_channel(case['channel_id'])
            creator = interaction.guild.get_member(case['creator_id'])
            
            value = f"**Opprettet av:** {creator.mention if creator else 'Ukjent'}\n"
            value += f"**Opprettet:** {case['created_at']}\n"
            
            if channel:
                value += f"**Kanal:** {channel.mention}"
            else:
                value += "**Kanal:** Ikke tilgjengelig"
            
            embed.add_field(
                name=f"Sak #{case['id']} - {case['title']}",
                value=value,
                inline=False
            )
        
        await interaction.followup.send(embed=embed)
        conn.close()
    
    @app_commands.command(name="arkiver-legacy", description="Arkiverer en eksisterende kanal uten å registrere den som en ny sak")
    @app_commands.describe(
        tittel="Tittel for den arkiverte saken",
        beskrivelse="Beskrivelse av den arkiverte saken"
    )
    @app_commands.default_permissions(administrator=True)
    async def archive_legacy(self, interaction: discord.Interaction, tittel: str, beskrivelse: str):
        """
        Archives an existing channel without registering it as a new case.
        This is a temporary command for migrating from a previous ticket system.
        
        Args:
            tittel: Title for the archived case
            beskrivelse: Description of the archived case
        """
        await interaction.response.defer(ephemeral=True)
        
        # Check if user is a judge
        if not await self.is_judge(interaction.user.id):
            await interaction.followup.send("Du må være dommer for å bruke denne kommandoen.", ephemeral=True)
            return
        
        await interaction.followup.send("Starter arkivering av kanalen...", ephemeral=True)
        
        # Fetch messages from channel (limited to 500 most recent)
        raw_messages = []
        async for message in interaction.channel.history(limit=500, oldest_first=True):
            # Get user's role color
            role_color = "#000000"  # Default black
            if not message.author.bot and hasattr(message.author, "color") and message.author.color != discord.Color.default():
                # Convert the Discord color to hex
                role_color = f"#{message.author.color.value:06x}"
                
            raw_messages.append({
                'author_id': message.author.id,
                'author': message.author.display_name,
                'author_avatar': str(message.author.display_avatar.url),
                'content': message.content,
                'timestamp': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'timestamp_obj': message.created_at,
                'attachments': [attachment.url for attachment in message.attachments],
                'embeds': [{'title': embed.title, 'description': embed.description} for embed in message.embeds],
                'role_color': role_color
            })
            
        # Group consecutive messages from the same author
        messages = []
        current_group = None
        
        for msg in raw_messages:
            # If this is the first message or a new author or more than 5 minutes since last message
            if (current_group is None or 
                current_group['author_id'] != msg['author_id'] or
                (msg['timestamp_obj'] - current_group['last_timestamp']).total_seconds() > 300):
                
                # Start a new message group
                current_group = {
                    'author_id': msg['author_id'],
                    'author': msg['author'],
                    'author_avatar': msg['author_avatar'],
                    'role_color': msg['role_color'],
                    'last_timestamp': msg['timestamp_obj'],
                    'first_timestamp': msg['timestamp'],
                    'messages': []
                }
                messages.append(current_group)
            else:
                # Update the last timestamp
                current_group['last_timestamp'] = msg['timestamp_obj']
            
            # Add this message content to the current group
            current_group['messages'].append({
                'content': msg['content'],
                'timestamp': msg['timestamp'],
                'attachments': msg['attachments'],
                'embeds': msg['embeds']
            })
        
        # Generate HTML
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Legacy Arkiv: {tittel}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f2f2f2; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
                .message-group {{ padding: 10px; border-bottom: 1px solid #eee; display: flex; }}
                .message-group:nth-child(odd) {{ background-color: #f9f9f9; }}
                .avatar {{ width: 40px; height: 40px; border-radius: 50%; margin-right: 10px; }}
                .message-content {{ flex: 1; }}
                .author {{ font-weight: bold; }}
                .timestamp {{ color: #777; font-size: 12px; margin-left: 10px; }}
                .message-item {{ margin-bottom: 8px; }}
                .attachment {{ background-color: #f0f0f0; padding: 5px; margin-top: 5px; border-radius: 3px; }}
                .embed {{ border-left: 4px solid #7289da; padding: 8px; margin-top: 5px; background-color: #f6f6f6; }}
                .embed-title {{ font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Legacy Arkiv: {tittel}</h1>
                <p><strong>Beskrivelse:</strong> {beskrivelse}</p>
                <p><strong>Kanal:</strong> {interaction.channel.name}</p>
                <p><strong>Arkivert av:</strong> {interaction.user.display_name}</p>
                <p><strong>Arkivert:</strong> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <h2>Meldinger</h2>
            <div class="messages">
        """
        
        for message_group in messages:
            html += f"""
            <div class="message-group">
                <img class="avatar" src="{message_group['author_avatar']}" alt="{message_group['author']}">
                <div class="message-content">
                    <span class="author" style="color: {message_group['role_color']};">{message_group['author']}</span>
                    <span class="timestamp">{message_group['first_timestamp']}</span>
            """
            
            for msg in message_group['messages']:
                html += f"""
                    <div class="message-item">
                        <p>{msg['content'] if msg['content'] else ''}</p>
                """
                
                if msg['attachments']:
                    for attachment in msg['attachments']:
                        html += f"""
                        <div class="attachment">
                            <a href="{attachment}" target="_blank">{attachment}</a>
                        </div>
                        """
                
                if msg['embeds']:
                    for embed in msg['embeds']:
                        if embed['title'] or embed['description']:
                            html += f"""
                            <div class="embed">
                                {f'<div class="embed-title">{embed["title"]}</div>' if embed['title'] else ''}
                                {f'<div class="embed-description">{embed["description"]}</div>' if embed['description'] else ''}
                            </div>
                            """
                
                html += """
                    </div>
                """
            
            html += """
                </div>
            </div>
            """
        
        html += """
            </div>
        </body>
        </html>
        """
        
        # Create file with HTML content
        file_name = f"legacy-arkiv-{timestamp}.html"
        with open(file_name, "w", encoding="utf-8") as file:
            file.write(html)
        
        # Send file to archive log channel
        archive_category = None
        for category in interaction.guild.categories:
            if category.name == "Arkiv":
                archive_category = category
                break
        
        if not archive_category:
            await interaction.followup.send("Feil: Arkiv-kategori finnes ikke.", ephemeral=True)
            return
        
        archive_log = None
        for channel in archive_category.channels:
            if channel.name == "arkiv-logg":
                archive_log = channel
                break
        
        if not archive_log:
            await interaction.followup.send("Feil: Arkiv-logg kanal finnes ikke.", ephemeral=True)
            return
        
        await archive_log.send(
            f"**Legacy Arkiv:** {tittel}\n**Beskrivelse:** {beskrivelse}\n**Arkivert av:** {interaction.user.mention}\n**Dato:** {discord.utils.format_dt(datetime.datetime.now())}",
            file=discord.File(file_name, filename=file_name)
        )
        
        # Delete local file after sending
        try:
            os.remove(file_name)
        except Exception as e:
            logger.error(f"Error removing temporary file: {e}")
        
        # Confirm to user
        await interaction.followup.send("Kanalen er arkivert. Sletter kanalen om 5 sekunder...", ephemeral=True)
        
        # Wait 5 seconds before deleting
        await asyncio.sleep(5)
        
        # Delete the channel
        try:
            await interaction.channel.delete(reason=f"Legacy arkivering av {tittel}")
            logger.info(f"Legacy channel '{interaction.channel.name}' archived and deleted by {interaction.user}")
        except Exception as e:
            await interaction.user.send(f"Kunne ikke slette kanalen automatisk: {e}")
            logger.error(f"Error deleting channel after legacy archive: {e}")
    
    @app_commands.command(name="send-dm", description="Sender en direktemelding til en bruker via boten")
    @app_commands.describe(
        bruker="Brukeren som skal motta meldingen",
        tekst="Teksten som skal sendes"
    )
    async def send_dm(self, interaction: discord.Interaction, bruker: discord.Member, tekst: str):
        """Allows judges to send DMs to people through the bot"""
        await interaction.response.defer(ephemeral=True)
        
        # Check if user is a judge
        is_judge = await self.is_judge(interaction.user.id)
        if not is_judge:
            await interaction.followup.send("Du har ikke tillatelse til å sende meldinger som dommer.", ephemeral=True)
            return
        
        # Try to send DM
        try:
            embed = discord.Embed(
                title=f"Melding fra dommer {interaction.user.display_name}",
                description=tekst,
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Sendt fra {interaction.guild.name}")
            
            await bruker.send(embed=embed)
            
            await interaction.followup.send(f"Melding sendt til {bruker.display_name}.")
            logger.info(f"DM sent to {bruker.name} by judge {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send(
                f"Kunne ikke sende melding til {bruker.display_name}. Brukeren har sannsynligvis blokkert DMs fra serveren.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Judge(bot))
