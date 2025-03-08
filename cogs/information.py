import discord
from discord import app_commands
from discord.ext import commands
import datetime
import logging
import sqlite3
import os
import config

logger = logging.getLogger('discord')

class Information(commands.Cog):
    """Commands for viewing case information and statistics"""
    
    def __init__(self, bot):
        self.bot = bot
    
    def get_db_connection(self):
        """Get a connection to the SQLite database"""
        conn = sqlite3.connect('court.db')
        conn.row_factory = sqlite3.Row
        return conn
    
    @app_commands.command(name="sak-info", description="Viser informasjon om en spesifikk sak")
    @app_commands.describe(
        sak_id="ID-nummeret til saken du vil se informasjon om"
    )
    async def case_info(self, interaction: discord.Interaction, sak_id: int):
        """
        Shows detailed information about a specific case
        
        Args:
            sak_id: The ID of the case to show information for
        """
        await interaction.response.defer(ephemeral=True)
        
        # Get case from database
        conn = self.get_db_connection()
        c = conn.cursor()
        
        c.execute('''
        SELECT * FROM cases WHERE id = ?
        ''', (sak_id,))
        
        case = c.fetchone()
        
        if not case:
            await interaction.followup.send(f"Fant ingen sak med ID #{sak_id}.", ephemeral=True)
            conn.close()
            return
        
        # Get evidence count
        c.execute('''
        SELECT COUNT(*) as count FROM evidence WHERE case_id = ?
        ''', (sak_id,))
        
        evidence_count = c.fetchone()['count']
        
        # Get judge information if assigned
        judge_name = "Ingen"
        if case['assigned_judge_id']:
            judge_member = interaction.guild.get_member(case['assigned_judge_id'])
            if judge_member:
                judge_name = judge_member.display_name
        
        # Get creator information
        creator_name = "Ukjent"
        creator_member = interaction.guild.get_member(case['creator_id'])
        if creator_member:
            creator_name = creator_member.display_name
        
        # Create embed
        embed = discord.Embed(
            title=f"Sak #{case['id']} - {case['title']}",
            description=case['description'],
            color=config.COLORS.get(case['status'], discord.Color.default())
        )
        
        # Add fields
        embed.add_field(name="Status", value=case['status'], inline=True)
        embed.add_field(name="Opprettet av", value=creator_name, inline=True)
        embed.add_field(name="Tildelt dommer", value=judge_name, inline=True)
        embed.add_field(name="Opprettet", value=discord.utils.format_dt(datetime.datetime.fromisoformat(case['created_at'])) if case['created_at'] else "Ukjent", inline=True)
        
        if case['closed_at']:
            embed.add_field(name="Lukket", value=discord.utils.format_dt(datetime.datetime.fromisoformat(case['closed_at'])), inline=True)
            
        if case['closing_reason']:
            embed.add_field(name="Begrunnelse for lukking", value=case['closing_reason'], inline=False)
            
        embed.add_field(name="Antall bevis", value=str(evidence_count), inline=True)
        
        # Add link to channel if it exists
        if case['channel_id']:
            channel = interaction.guild.get_channel(case['channel_id'])
            if channel:
                embed.add_field(name="Kanal", value=channel.mention, inline=True)
        
        # Add link to archive if it exists
        if case['archive_url']:
            embed.add_field(name="Arkiv", value=f"[Klikk her for å se arkivert sak]({case['archive_url']})", inline=False)
        
        # Send embed
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"Case info for case {sak_id} viewed by {interaction.user}")
        conn.close()
    
    @app_commands.command(name="søk-arkiv", description="Søker i arkiverte saker")
    @app_commands.describe(
        søkeord="Søkeord for å finne saker (tittel eller beskrivelse)"
    )
    async def search_archive(self, interaction: discord.Interaction, søkeord: str):
        """
        Searches for cases in the archive based on title or description
        
        Args:
            søkeord: Search term to find cases by title or description
        """
        await interaction.response.defer(ephemeral=True)
        
        # Search database for cases matching the search term
        conn = self.get_db_connection()
        c = conn.cursor()
        
        # Use LIKE for case-insensitive search in both title and description
        c.execute('''
        SELECT * FROM cases 
        WHERE (title LIKE ? OR description LIKE ?) 
        AND (status = 'Lukket' OR status = 'Arkivert')
        ORDER BY id DESC
        LIMIT 10
        ''', (f'%{søkeord}%', f'%{søkeord}%'))
        
        cases = c.fetchall()
        
        if not cases:
            await interaction.followup.send(f"Fant ingen arkiverte saker som matcher søkeordet '{søkeord}'.", ephemeral=True)
            conn.close()
            return
        
        # Create embed with search results
        embed = discord.Embed(
            title=f"Søkeresultater for '{søkeord}'",
            description=f"Fant {len(cases)} saker som matcher søkeordet.",
            color=discord.Color.blue()
        )
        
        # Add each case to the embed
        for case in cases:
            # Format the case information
            case_info = f"**Status:** {case['status']}\n"
            case_info += f"**Opprettet:** {case['created_at']}\n"
            
            if case['archive_url']:
                case_info += f"[Se arkivert sak]({case['archive_url']})\n"
            
            embed.add_field(
                name=f"Sak #{case['id']} - {case['title']}",
                value=case_info,
                inline=False
            )
        
        # Add footer with instruction
        embed.set_footer(text="Bruk /sak-info <sak-id> for å se mer detaljer om en spesifikk sak.")
        
        # Send embed
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"Archive search for '{søkeord}' by {interaction.user}")
        conn.close()
    
    @app_commands.command(name="statistikk", description="Viser statistikk for saker og dommere")
    async def statistics(self, interaction: discord.Interaction):
        """Shows statistics for cases and judges"""
        await interaction.response.defer(ephemeral=True)
        
        # Get statistics from database
        conn = self.get_db_connection()
        c = conn.cursor()
        
        # Get case statistics
        c.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'Åpen' THEN 1 ELSE 0 END) as open,
            SUM(CASE WHEN status = 'Tildelt' THEN 1 ELSE 0 END) as assigned,
            SUM(CASE WHEN status = 'Lukket' THEN 1 ELSE 0 END) as closed,
            SUM(CASE WHEN status = 'Arkivert' THEN 1 ELSE 0 END) as archived
        FROM cases
        ''')
        
        case_stats = c.fetchone()
        
        # Get judge statistics
        c.execute('''
        SELECT 
            j.user_id,
            COUNT(c.id) as total_cases,
            SUM(CASE WHEN c.status = 'Lukket' THEN 1 ELSE 0 END) as closed_cases
        FROM judges j
        LEFT JOIN cases c ON j.user_id = c.assigned_judge_id
        GROUP BY j.user_id
        ''')
        
        judge_stats = c.fetchall()
        
        # Create embed for statistics
        embed = discord.Embed(
            title="Domstol Statistikk",
            description="Statistikk for saker og dommere",
            color=discord.Color.gold()
        )
        
        # Add case statistics
        embed.add_field(
            name="Sak Statistikk",
            value=f"**Totalt antall saker:** {case_stats['total']}\n"
                  f"**Åpne saker:** {case_stats['open']}\n"
                  f"**Tildelte saker:** {case_stats['assigned']}\n"
                  f"**Lukkede saker:** {case_stats['closed']}\n"
                  f"**Arkiverte saker:** {case_stats['archived']}",
            inline=False
        )
        
        # Add judge statistics
        judge_info = ""
        for judge in judge_stats:
            if judge['user_id']:  # Skip if user_id is NULL
                judge_member = interaction.guild.get_member(judge['user_id'])
                if judge_member:
                    judge_info += f"**{judge_member.display_name}:** {judge['closed_cases']} avsluttede av {judge['total_cases']} totalt\n"
        
        if judge_info:
            embed.add_field(
                name="Dommer Statistikk",
                value=judge_info,
                inline=False
            )
        else:
            embed.add_field(
                name="Dommer Statistikk",
                value="Ingen dommer-statistikk tilgjengelig.",
                inline=False
            )
        
        # Add timestamp
        embed.set_footer(text=f"Generert: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Send embed
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"Statistics viewed by {interaction.user}")
        conn.close()
    
    @app_commands.command(name="hjelp", description="Viser hjelp for kommandoer")
    async def help_command(self, interaction: discord.Interaction):
        """Shows help information for commands"""
        await interaction.response.defer(ephemeral=True)
        
        # Create embed for help
        embed = discord.Embed(
            title="CourtBot Hjelp",
            description="Her er en oversikt over tilgjengelige kommandoer:",
            color=discord.Color.blue()
        )
        
        # Setup commands
        embed.add_field(
            name="Oppsett",
            value="**/opprett-kategori** - Oppretter en ny kategori for saker\n"
                  "**/fjern-kategori** - Fjerner en kategori\n"
                  "**/legg-til-dommer** - Legger til en dommer\n"
                  "**/fjern-dommer** - Fjerner en dommer",
            inline=False
        )
        
        # Ticket commands
        embed.add_field(
            name="Saker",
            value="**/opprett-sak** - Oppretter en ny sak\n"
                  "**/avslutt-sak** - Avslutter en sak med begrunnelse\n"
                  "**/arkiver-sak** - Arkiverer en sak uten å lukke den",
            inline=False
        )
        
        # Judge commands
        embed.add_field(
            name="Dommer",
            value="**/ta-sak** - Tildeler en sak til deg selv som dommer\n"
                  "**/send-dm** - Sender en DM til en bruker som dommer\n"
                  "**/mine-saker** - Viser saker tildelt til deg",
            inline=False
        )
        
        # Evidence commands
        embed.add_field(
            name="Bevis",
            value="**/legg-til-bevis** - Legger til bevis i en sak\n"
                  "**/fjern-bevis** - Fjerner bevis fra en sak\n"
                  "**/vis-bevis** - Viser alle bevis i en sak\n"
                  "**/eksporter-sak** - Eksporterer en sak som HTML",
            inline=False
        )
        
        # Notification commands
        embed.add_field(
            name="Varsler",
            value="**/varsle-klient** - Planlegger en DM til en bruker\n"
                  "**/avbryt-varsel** - Avbryter et planlagt varsel\n"
                  "**/vis-varsler** - Viser alle planlagte varsler",
            inline=False
        )
        
        # Information commands
        embed.add_field(
            name="Informasjon",
            value="**/sak-info** - Viser informasjon om en spesifikk sak\n"
                  "**/søk-arkiv** - Søker i arkiverte saker\n"
                  "**/statistikk** - Viser statistikk for saker og dommere\n"
                  "**/hjelp** - Viser denne hjelpeteksten",
            inline=False
        )
        
        # Send embed
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"Help viewed by {interaction.user}")

async def setup(bot):
    await bot.add_cog(Information(bot))
