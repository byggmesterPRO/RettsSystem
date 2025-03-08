import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import logging
import datetime
from typing import Optional

# Set up logging
logger = logging.getLogger("CourtBot.Notifications")

class Notifications(commands.Cog):
    """Commands for notification management"""
    
    def __init__(self, bot):
        self.bot = bot
    
    def get_db_connection(self):
        """Get database connection"""
        conn = sqlite3.connect('data/courtbot.db')
        conn.row_factory = sqlite3.Row
        return conn
    
    @app_commands.command(name="varsle-klient", description="Planlegger en DM til en bruker på et bestemt tidspunkt")
    @app_commands.describe(
        bruker="Brukeren som skal motta varselet",
        dato="Dato for varselet (YYYY-MM-DD)",
        tid="Tid for varselet (HH:MM)",
        melding="Meldingen som skal sendes"
    )
    async def schedule_notification(self, interaction: discord.Interaction, bruker: discord.Member, dato: str, tid: str, melding: str):
        """Schedules a DM to be sent to a user"""
        await interaction.response.defer(ephemeral=True)
        
        # Validate date and time format
        try:
            # Parse date and time
            scheduled_time = datetime.datetime.strptime(f"{dato} {tid}", "%Y-%m-%d %H:%M")
            
            # Check if the time is in the past
            if scheduled_time < datetime.datetime.now():
                await interaction.followup.send("Kan ikke planlegge varsel i fortiden.", ephemeral=True)
                return
                
        except ValueError:
            await interaction.followup.send("Ugyldig dato eller tidsformat. Bruk YYYY-MM-DD for dato og HH:MM for tid.", ephemeral=True)
            return
        
        # Store notification in database
        conn = self.get_db_connection()
        c = conn.cursor()
        
        c.execute('''
        INSERT INTO scheduled_notifications (target_user_id, message, scheduled_time, created_by)
        VALUES (?, ?, ?, ?)
        ''', (bruker.id, melding, scheduled_time.strftime('%Y-%m-%d %H:%M:%S'), interaction.user.id))
        
        notification_id = c.lastrowid
        
        conn.commit()
        conn.close()
        
        # Send confirmation
        await interaction.followup.send(
            f"Varsel #{notification_id} planlagt for {bruker.display_name} den {dato} kl. {tid}.\n"
            f"Melding: {melding}"
        )
        
        logger.info(f"Notification #{notification_id} scheduled for {bruker.name} by {interaction.user}")
    
    @app_commands.command(name="avbryt-varsel", description="Avbryter et planlagt varsel")
    @app_commands.describe(
        varsel_id="ID-en til varselet som skal avbrytes"
    )
    async def cancel_notification(self, interaction: discord.Interaction, varsel_id: int):
        """Cancels a scheduled notification"""
        await interaction.response.defer(ephemeral=True)
        
        # Get notification from database
        conn = self.get_db_connection()
        c = conn.cursor()
        
        c.execute('''
        SELECT * FROM scheduled_notifications WHERE id = ?
        ''', (varsel_id,))
        
        notification = c.fetchone()
        
        if not notification:
            await interaction.followup.send(f"Fant ikke varsel med ID {varsel_id}.", ephemeral=True)
            conn.close()
            return
        
        # Check if notification has already been sent
        if notification['sent']:
            await interaction.followup.send(f"Varsel #{varsel_id} har allerede blitt sendt og kan ikke avbrytes.", ephemeral=True)
            conn.close()
            return
        
        # Delete notification
        c.execute('''
        DELETE FROM scheduled_notifications WHERE id = ?
        ''', (varsel_id,))
        
        conn.commit()
        conn.close()
        
        # Send confirmation
        await interaction.followup.send(f"Varsel #{varsel_id} har blitt avbrutt.")
        
        logger.info(f"Notification #{varsel_id} cancelled by {interaction.user}")
    
    @app_commands.command(name="vis-varsler", description="Viser alle planlagte varsler")
    async def show_notifications(self, interaction: discord.Interaction):
        """Shows all scheduled notifications"""
        await interaction.response.defer(ephemeral=True)
        
        # Get notifications from database
        conn = self.get_db_connection()
        c = conn.cursor()
        
        c.execute('''
        SELECT * FROM scheduled_notifications WHERE sent = 0 ORDER BY scheduled_time
        ''')
        
        notifications = c.fetchall()
        
        if not notifications:
            await interaction.followup.send("Det er ingen planlagte varsler.", ephemeral=True)
            conn.close()
            return
        
        # Create embed with notifications
        embed = discord.Embed(
            title="Planlagte varsler",
            description=f"Totalt {len(notifications)} varsler",
            color=discord.Color.blue()
        )
        
        for notification in notifications:
            target_user = interaction.guild.get_member(notification['target_user_id'])
            creator = interaction.guild.get_member(notification['created_by'])
            
            target_name = target_user.display_name if target_user else f"Bruker (ID: {notification['target_user_id']})"
            creator_name = creator.display_name if creator else "Ukjent"
            
            scheduled_time = datetime.datetime.strptime(notification['scheduled_time'], '%Y-%m-%d %H:%M:%S')
            
            embed.add_field(
                name=f"Varsel #{notification['id']}",
                value=(
                    f"**Til:** {target_name}\n"
                    f"**Tidspunkt:** {discord.utils.format_dt(scheduled_time)}\n"
                    f"**Opprettet av:** {creator_name}\n"
                    f"**Melding:** {notification['message']}"
                ),
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        conn.close()

async def setup(bot):
    await bot.add_cog(Notifications(bot))
