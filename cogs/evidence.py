import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import logging
import datetime
from typing import Optional, List
import os
import tempfile
import re

# Set up logging
logger = logging.getLogger("CourtBot.Evidence")

class Evidence(commands.Cog):
    """Commands for evidence management"""
    
    def __init__(self, bot):
        self.bot = bot
    
    def get_db_connection(self):
        """Get database connection"""
        conn = sqlite3.connect('data/courtbot.db')
        conn.row_factory = sqlite3.Row
        return conn
    
    @app_commands.command(name="legg-til-bevis", description="Legger til bevis i saken")
    @app_commands.describe(
        beskrivelse="Kort beskrivelse eller navn på beviset",
        dokument_link="Link til dokumentet eller beviset"
    )
    async def add_evidence(self, interaction: discord.Interaction, beskrivelse: str, dokument_link: str):
        """Adds evidence to the case with description and link"""
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
        
        # Get next sub-ID for this case
        c.execute('''
        SELECT COUNT(*) as count FROM evidence WHERE case_id = ?
        ''', (case['id'],))
        
        count = c.fetchone()['count']
        sub_id = count + 1
        
        # Create full evidence ID (case.sub_id format)
        evidence_id = f"{case['id']}.{sub_id}"
        
        # Add evidence to database
        c.execute('''
        INSERT INTO evidence (case_id, submitter_id, description, link)
        VALUES (?, ?, ?, ?)
        ''', (case['id'], interaction.user.id, beskrivelse, dokument_link))
        
        conn.commit()
        
        # Create evidence embed
        embed = discord.Embed(
            title=f"Bevis #{evidence_id}",
            description=beskrivelse,
            color=discord.Color.green()
        )
        embed.add_field(name="Link", value=dokument_link, inline=False)
        embed.add_field(name="Lagt til av", value=interaction.user.mention, inline=True)
        embed.add_field(name="Tidspunkt", value=discord.utils.format_dt(datetime.datetime.now()), inline=True)
        
        await interaction.followup.send(embed=embed)
        
        logger.info(f"Evidence #{evidence_id} added to case {case['id']} by {interaction.user}")
        conn.close()
    
    @app_commands.command(name="fjern-bevis", description="Fjerner bevis fra saken")
    @app_commands.describe(
        bevis_id="ID-en til beviset som skal fjernes (f.eks. 1.2)"
    )
    async def remove_evidence(self, interaction: discord.Interaction, bevis_id: str):
        """Removes evidence from the case"""
        await interaction.response.defer(ephemeral=True)
        
        # Parse evidence ID
        match = re.match(r"(\d+)\.(\d+)", bevis_id)
        if not match:
            await interaction.followup.send("Ugyldig bevis-ID. Formatet skal være 'sak.sub' (f.eks. 1.2).", ephemeral=True)
            return
        
        case_id = int(match.group(1))
        sub_id = int(match.group(2))
        
        # Check if channel is a ticket for the specified case
        conn = self.get_db_connection()
        c = conn.cursor()
        
        c.execute('''
        SELECT * FROM cases WHERE channel_id = ? AND id = ?
        ''', (interaction.channel.id, case_id))
        
        case = c.fetchone()
        
        if not case:
            await interaction.followup.send("Dette er ikke riktig sak-kanal for dette beviset.", ephemeral=True)
            conn.close()
            return
        
        # Get all evidence for this case
        c.execute('''
        SELECT * FROM evidence WHERE case_id = ? ORDER BY id
        ''', (case_id,))
        
        all_evidence = c.fetchall()
        
        if len(all_evidence) < sub_id or sub_id <= 0:
            await interaction.followup.send(f"Fant ikke bevis med ID {bevis_id}.", ephemeral=True)
            conn.close()
            return
        
        # Get the specific evidence (arrayindex = sub_id - 1)
        evidence = all_evidence[sub_id - 1]
        
        # Delete evidence from database
        c.execute('''
        DELETE FROM evidence WHERE id = ?
        ''', (evidence['id'],))
        
        conn.commit()
        
        # Send confirmation
        await interaction.followup.send(f"Bevis #{bevis_id} ({evidence['description']}) har blitt fjernet.")
        
        logger.info(f"Evidence #{bevis_id} removed from case {case_id} by {interaction.user}")
        conn.close()
    
    @app_commands.command(name="vis-bevis", description="Viser alle bevis i den nåværende saken")
    async def show_evidence(self, interaction: discord.Interaction):
        """Shows all evidence in the current case"""
        await interaction.response.defer(ephemeral=True)
        
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
        
        # Get all evidence for this case
        c.execute('''
        SELECT * FROM evidence WHERE case_id = ? ORDER BY id
        ''', (case['id'],))
        
        evidence_list = c.fetchall()
        
        if not evidence_list:
            await interaction.followup.send("Det er ingen registrerte bevis i denne saken.", ephemeral=True)
            conn.close()
            return
        
        # Create embed with evidence
        embed = discord.Embed(
            title=f"Bevis for sak #{case['id']}",
            description=f"Totalt {len(evidence_list)} bevis registrert",
            color=discord.Color.blue()
        )
        
        for i, evidence in enumerate(evidence_list, 1):
            submitter = interaction.guild.get_member(evidence['submitter_id'])
            submitter_name = submitter.display_name if submitter else "Ukjent"
            
            embed.add_field(
                name=f"Bevis #{case['id']}.{i} - {evidence['description']}",
                value=f"**Link:** {evidence['link']}\n**Lagt til av:** {submitter_name}\n**Dato:** {evidence['submitted_at']}",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        conn.close()
    
    @app_commands.command(name="hent-bevis", description="Henter en liste over bevis for en spesifikk sak")
    @app_commands.describe(
        sak_id="ID-en til saken"
    )
    async def get_evidence(self, interaction: discord.Interaction, sak_id: int):
        """Retrieves a list of evidence for the specified case ID"""
        await interaction.response.defer(ephemeral=True)
        
        # Get case from database
        conn = self.get_db_connection()
        c = conn.cursor()
        
        c.execute('''
        SELECT * FROM cases WHERE id = ?
        ''', (sak_id,))
        
        case = c.fetchone()
        
        if not case:
            await interaction.followup.send(f"Fant ikke sak med ID {sak_id}.", ephemeral=True)
            conn.close()
            return
        
        # Get all evidence for this case
        c.execute('''
        SELECT * FROM evidence WHERE case_id = ? ORDER BY id
        ''', (sak_id,))
        
        evidence_list = c.fetchall()
        
        if not evidence_list:
            await interaction.followup.send(f"Det er ingen registrerte bevis i sak #{sak_id}.", ephemeral=True)
            conn.close()
            return
        
        # Create embed with evidence
        embed = discord.Embed(
            title=f"Bevis for sak #{sak_id} - {case['title']}",
            description=f"Totalt {len(evidence_list)} bevis registrert",
            color=discord.Color.blue()
        )
        
        for i, evidence in enumerate(evidence_list, 1):
            submitter = interaction.guild.get_member(evidence['submitter_id'])
            submitter_name = submitter.display_name if submitter else "Ukjent"
            
            embed.add_field(
                name=f"Bevis #{sak_id}.{i} - {evidence['description']}",
                value=f"**Link:** {evidence['link']}\n**Lagt til av:** {submitter_name}\n**Dato:** {evidence['submitted_at']}",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        conn.close()
    
    @app_commands.command(name="eksporter-sak", description="Eksporterer den nåværende saken som HTML")
    async def export_case(self, interaction: discord.Interaction):
        """Exports the current case as an HTML document in the ticket"""
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
        
        # Generate HTML content
        html_content = await self.generate_case_html(interaction.channel, case)
        
        if not html_content:
            await interaction.followup.send("Feil: Kunne ikke generere HTML for saken.", ephemeral=True)
            conn.close()
            return
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as tmp:
            tmp.write(html_content.encode('utf-8'))
            tmp.flush()
            temp_file_path = tmp.name
            
        # Create proper filename for the user
        display_filename = f"sak_{case['id']}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            
        # Create Discord file object
        file = discord.File(temp_file_path, filename=display_filename)
        
        # Send file to channel
        await interaction.followup.send(
            f"Her er eksporten av sak #{case['id']} - {case['title']}:",
            file=file
        )
        
        # Remove temporary file
        os.remove(temp_file_path)
        
        logger.info(f"Case {case['id']} exported by {interaction.user}")
        conn.close()
    
    async def generate_case_html(self, channel, case):
        """
        Generates HTML content for a case
        
        Args:
            channel: The Discord channel object
            case: The case database row
            
        Returns:
            str: HTML content or None if error
        """
        try:
            # Get database connection
            conn = self.get_db_connection()
            c = conn.cursor()
            
            # Get all evidence for this case
            c.execute('''
            SELECT * FROM evidence WHERE case_id = ? ORDER BY id
            ''', (case['id'],))
            
            evidence_list = c.fetchall()
            
            # Fetch messages from channel (limited to 100 most recent)
            raw_messages = []
            async for message in channel.history(limit=100, oldest_first=True):
                # Skip bot messages that are just system notifications
                if message.author.bot and len(message.embeds) > 0:
                    # Only include if it's not a system notification
                    if not any(keyword in message.embeds[0].title.lower() if message.embeds[0].title else "" 
                              for keyword in ["tildelt", "lukket", "arkivert", "bevis"]):
                        continue
                
                # Process message content for HTML
                content = message.content
                # Escape HTML characters
                content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                # Convert Discord markdown to HTML
                content = content.replace("**", "<strong>").replace("**", "</strong>")
                content = content.replace("*", "<em>").replace("*", "</em>")
                content = content.replace("~~", "<del>").replace("~~", "</del>")
                content = content.replace("__", "<u>").replace("__", "</u>")
                # Convert newlines to <br>
                content = content.replace("\n", "<br>")
                
                # Process embeds
                embeds_content = ""
                for embed in message.embeds:
                    embeds_content += f'<div class="embed">'
                    if embed.title:
                        embeds_content += f'<div class="embed-title">{embed.title}</div>'
                    if embed.description:
                        embeds_content += f'<div class="embed-description">{embed.description}</div>'
                    for field in embed.fields:
                        embeds_content += f'<div class="embed-field"><div class="embed-field-name">{field.name}</div><div class="embed-field-value">{field.value}</div></div>'
                    embeds_content += '</div>'
                
                # Get user's role color
                role_color = "#000000"  # Default black
                if not message.author.bot and hasattr(message.author, "color") and message.author.color != discord.Color.default():
                    # Convert the Discord color to hex
                    role_color = f"#{message.author.color.value:06x}"
                
                raw_messages.append({
                    'author_id': message.author.id,
                    'author': message.author.display_name,
                    'author_avatar': message.author.display_avatar.url,
                    'content': content,
                    'embeds': embeds_content,
                    'timestamp': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'timestamp_obj': message.created_at,
                    'attachments': [attachment.url for attachment in message.attachments],
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
                    'embeds': msg['embeds'],
                    'timestamp': msg['timestamp'],
                    'attachments': msg['attachments']
                })
            
            # Get assigned judge if any
            judge_name = "Ingen"
            if case['assigned_judge_id']:
                c.execute('''
                SELECT * FROM judges WHERE user_id = ?
                ''', (case['assigned_judge_id'],))
                judge = c.fetchone()
                if judge:
                    guild = channel.guild
                    judge_member = guild.get_member(case['assigned_judge_id'])
                    if judge_member:
                        judge_name = judge_member.display_name
            
            # Generate HTML
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Sak #{case['id']} - {case['title']}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f9f9f9; color: #333; }}
                    .header {{ background-color: #f2f2f2; padding: 20px; border-radius: 5px; margin-bottom: 20px; border: 1px solid #ddd; }}
                    .evidence {{ background-color: #e6f7ff; padding: 15px; border-radius: 5px; margin-bottom: 15px; border: 1px solid #b8e2f2; }}
                    .messages {{ border: 1px solid #ddd; border-radius: 5px; overflow: hidden; }}
                    .message-group {{ padding: 15px; border-bottom: 1px solid #eee; display: flex; }}
                    .message-group:nth-child(odd) {{ background-color: #f9f9f9; }}
                    .message-group:nth-child(even) {{ background-color: #fff; }}
                    .message-avatar {{ width: 40px; height: 40px; border-radius: 50%; margin-right: 15px; }}
                    .message-content {{ flex: 1; }}
                    .message-header {{ display: flex; justify-content: space-between; margin-bottom: 5px; }}
                    .message-author {{ font-weight: bold; }}
                    .message-timestamp {{ color: #777; font-size: 12px; }}
                    .message-text {{ margin-bottom: 10px; }}
                    .message-item {{ margin-bottom: 8px; }}
                    .attachment {{ background-color: #f0f0f0; padding: 8px; margin-top: 5px; border-radius: 3px; display: inline-block; }}
                    .embed {{ background-color: #f0f0f0; padding: 10px; margin-top: 10px; border-radius: 5px; border-left: 4px solid #7289da; }}
                    .embed-title {{ font-weight: bold; margin-bottom: 5px; }}
                    .embed-description {{ margin-bottom: 10px; }}
                    .embed-field {{ margin-top: 5px; }}
                    .embed-field-name {{ font-weight: bold; }}
                    h1, h2 {{ color: #2c3e50; }}
                    a {{ color: #3498db; text-decoration: none; }}
                    a:hover {{ text-decoration: underline; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>Sak #{case['id']} - {case['title']}</h1>
                    <p><strong>Beskrivelse:</strong> {case['description']}</p>
                    <p><strong>Status:</strong> {case['status']}</p>
                    <p><strong>Opprettet:</strong> {case['created_at']}</p>
                    <p><strong>Tildelt dommer:</strong> {judge_name}</p>
                </div>
                
                <h2>Bevis</h2>
            """
            
            if evidence_list:
                for i, evidence in enumerate(evidence_list, 1):
                    html += f"""
                    <div class="evidence">
                        <h3>Bevis #{case['id']}.{i} - {evidence['description']}</h3>
                        <p><strong>Link:</strong> <a href="{evidence['link']}" target="_blank">{evidence['link']}</a></p>
                        <p><strong>Lagt til:</strong> {evidence['submitted_at']}</p>
                    </div>
                    """
            else:
                html += "<p>Ingen bevis registrert for denne saken.</p>"
            
            html += """
                <h2>Meldinger</h2>
                <div class="messages">
            """
            
            for message_group in messages:
                html += f"""
                <div class="message-group">
                    <img class="message-avatar" src="{message_group['author_avatar']}" alt="{message_group['author']}">
                    <div class="message-content">
                        <div class="message-header">
                            <span class="message-author" style="color: {message_group['role_color']};">{message_group['author']}</span>
                            <span class="message-timestamp">{message_group['first_timestamp']}</span>
                        </div>
                """
                
                for msg in message_group['messages']:
                    html += f"""
                        <div class="message-item">
                            <div class="message-text">{msg['content']}</div>
                            {msg['embeds']}
                    """
                    
                    if msg['attachments']:
                        for attachment in msg['attachments']:
                            html += f"""
                            <div class="attachment">
                                <a href="{attachment}" target="_blank">{attachment}</a>
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
                <div style="margin-top: 20px; text-align: center; color: #777; font-size: 12px;">
                    Generert av Oslo Tingrett
                </div>
            </body>
            </html>
            """
            
            conn.close()
            return html
            
        except Exception as e:
            logger.error(f"Error generating HTML for case {case['id']}: {e}")
            return None

async def setup(bot):
    await bot.add_cog(Evidence(bot))
