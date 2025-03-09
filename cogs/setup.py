import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import logging
from typing import Optional

# Set up logging
logger = logging.getLogger("CourtBot.Setup")

class Setup(commands.Cog):
    """Commands for setting up the CourtBot"""
    
    def __init__(self, bot):
        self.bot = bot
        
    def get_db_connection(self):
        """Get database connection"""
        conn = sqlite3.connect('data/courtbot.db')
        conn.row_factory = sqlite3.Row
        return conn
    
    @app_commands.command(name="oppsett", description="Setter opp CourtBot på serveren")
    @app_commands.default_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction):
        """Initial setup for the bot in a server"""
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        conn = self.get_db_connection()
        c = conn.cursor()
        
        # Check if we already have categories in the database for this guild
        c.execute('''
        SELECT category_id, name FROM categories
        ''')
        existing_categories = c.fetchall()
        existing_category_names = {cat['name']: cat['category_id'] for cat in existing_categories}
        
        # Initialize variables for categories
        archive_category = None
        tickets_category = None
        
        # First, try to find existing categories by name
        for category in guild.categories:
            if category.name == "Arkiv" and "Arkiv" not in existing_category_names:
                archive_category = category
                logger.info(f"Found existing 'Arkiv' category: {category.id}")
                
                # Add to database since it's not there yet
                c.execute('''
                INSERT INTO categories (category_id, name, role_id)
                VALUES (?, ?, ?)
                ''', (category.id, "Arkiv", 0))
                logger.info(f"Added existing 'Arkiv' category to database: {category.id}")
                
            elif category.name == "Saker" and "Saker" not in existing_category_names:
                tickets_category = category
                logger.info(f"Found existing 'Saker' category: {category.id}")
                
                # Add to database since it's not there yet
                c.execute('''
                INSERT INTO categories (category_id, name, role_id)
                VALUES (?, ?, ?)
                ''', (category.id, "Saker", 0))
                logger.info(f"Added existing 'Saker' category to database: {category.id}")
        
        # If we found existing categories in the database, verify they still exist on Discord
        for cat_name, cat_id in existing_category_names.items():
            channel = guild.get_channel(cat_id)
            if not channel:
                logger.warning(f"Category {cat_name} with ID {cat_id} exists in database but not on Discord")
                
                # Find if there's a category with this name but different ID
                for category in guild.categories:
                    if category.name == cat_name:
                        logger.info(f"Found category {cat_name} with new ID {category.id}, updating database")
                        
                        # Update the database with the new ID
                        c.execute('''
                        UPDATE categories SET category_id = ? WHERE name = ?
                        ''', (category.id, cat_name))
                        
                        if cat_name == "Arkiv":
                            archive_category = category
                        elif cat_name == "Saker":
                            tickets_category = category
                        break
        
        # Create archive category if it doesn't exist
        if not archive_category and "Arkiv" not in existing_category_names:
            try:
                archive_category = await guild.create_category("Arkiv")
                await archive_category.set_permissions(guild.default_role, read_messages=False, send_messages=False)
                logger.info(f"Created new 'Arkiv' category: {archive_category.id}")
                
                # Store archive category in database
                c.execute('''
                INSERT INTO categories (category_id, name, role_id)
                VALUES (?, ?, ?)
                ''', (archive_category.id, "Arkiv", 0))
            except discord.Forbidden:
                await interaction.followup.send("Feil: Boten har ikke tillatelse til å opprette kategorier. Gi boten 'Administrer kanaler' tillatelse.", ephemeral=True)
            except Exception as e:
                logger.error(f"Error creating archive category: {e}")
                await interaction.followup.send(f"Feil ved oppretting av arkivkategori: {e}", ephemeral=True)
        elif "Arkiv" in existing_category_names:
            # Try to get the existing category from the database
            category_id = existing_category_names["Arkiv"]
            archive_category = guild.get_channel(category_id)
            
            if not archive_category:
                # If the category doesn't exist anymore, create a new one
                try:
                    archive_category = await guild.create_category("Arkiv")
                    await archive_category.set_permissions(guild.default_role, read_messages=False, send_messages=False)
                    logger.info(f"Recreated 'Arkiv' category: {archive_category.id}")
                    
                    # Update the database with the new category ID
                    c.execute('''
                    UPDATE categories SET category_id = ? WHERE name = 'Arkiv'
                    ''', (archive_category.id,))
                except discord.Forbidden:
                    await interaction.followup.send("Feil: Boten har ikke tillatelse til å opprette kategorier. Gi boten 'Administrer kanaler' tillatelse.", ephemeral=True)
                except Exception as e:
                    logger.error(f"Error recreating archive category: {e}")
                    await interaction.followup.send(f"Feil ved gjenoppretting av arkivkategori: {e}", ephemeral=True)
            else:
                logger.info(f"Using existing 'Arkiv' category from database: {archive_category.id}")
        
        # Check if archive channel exists, create if not
        archive_channel = None
        if archive_category:
            for channel in archive_category.channels:
                if channel.name == "arkiv-logg":
                    archive_channel = channel
                    break
            
            if not archive_channel:
                try:
                    archive_channel = await archive_category.create_text_channel("arkiv-logg")
                    logger.info(f"Created 'arkiv-logg' channel: {archive_channel.id}")
                except discord.Forbidden:
                    await interaction.followup.send("Feil: Boten har ikke tillatelse til å opprette kanaler. Gi boten 'Administrer kanaler' tillatelse.", ephemeral=True)
                except Exception as e:
                    logger.error(f"Error creating archive log channel: {e}")
                    await interaction.followup.send(f"Feil ved oppretting av arkiv-logg kanal: {e}", ephemeral=True)
        
        # Create tickets category if it doesn't exist
        if not tickets_category and "Saker" not in existing_category_names:
            try:
                tickets_category = await guild.create_category("Saker")
                logger.info(f"Created new 'Saker' category: {tickets_category.id}")
                
                # Store tickets category in database
                c.execute('''
                INSERT INTO categories (category_id, name, role_id)
                VALUES (?, ?, ?)
                ''', (tickets_category.id, "Saker", 0))
            except discord.Forbidden:
                await interaction.followup.send("Feil: Boten har ikke tillatelse til å opprette kategorier. Gi boten 'Administrer kanaler' tillatelse.", ephemeral=True)
            except Exception as e:
                logger.error(f"Error creating tickets category: {e}")
                await interaction.followup.send(f"Feil ved oppretting av sakskategori: {e}", ephemeral=True)
        elif "Saker" in existing_category_names:
            # Try to get the existing category from the database
            category_id = existing_category_names["Saker"]
            tickets_category = guild.get_channel(category_id)
            
            if not tickets_category:
                # If the category doesn't exist anymore, create a new one
                try:
                    tickets_category = await guild.create_category("Saker")
                    logger.info(f"Recreated 'Saker' category: {tickets_category.id}")
                    
                    # Update the database with the new category ID
                    c.execute('''
                    UPDATE categories SET category_id = ? WHERE name = 'Saker'
                    ''', (tickets_category.id,))
                except discord.Forbidden:
                    await interaction.followup.send("Feil: Boten har ikke tillatelse til å opprette kategorier. Gi boten 'Administrer kanaler' tillatelse.", ephemeral=True)
                except Exception as e:
                    logger.error(f"Error recreating tickets category: {e}")
                    await interaction.followup.send(f"Feil ved gjenoppretting av sakskategori: {e}", ephemeral=True)
            else:
                logger.info(f"Using existing 'Saker' category from database: {tickets_category.id}")
        
        # Log the current state of the database after setup
        c.execute('''
        SELECT * FROM categories
        ''')
        categories_after_setup = c.fetchall()
        for cat in categories_after_setup:
            logger.info(f"Category in database after setup: {cat['name']} (ID: {cat['category_id']})")
        
        conn.commit()
        conn.close()
        
        # Prepare response message
        response_parts = []
        if archive_category:
            if archive_channel:
                response_parts.append("Arkiv kategori og arkiv-logg kanal er konfigurert.")
            else:
                response_parts.append("Arkiv kategori er konfigurert, men kunne ikke opprette arkiv-logg kanal.")
        else:
            response_parts.append("Kunne ikke konfigurere Arkiv kategori.")
            
        if tickets_category:
            response_parts.append("Saker kategori er konfigurert.")
        else:
            response_parts.append("Kunne ikke konfigurere Saker kategori.")
        
        await interaction.followup.send(f"CourtBot oppsett fullført!\n\n{' '.join(response_parts)}", ephemeral=True)
        logger.info(f"Setup completed for guild {guild.name} (ID: {guild.id})")
    
    @app_commands.command(name="sett-dommer", description="Setter opp en dommers kvarter")
    @app_commands.describe(
        bruker="Dommeren som skal ha kvarteret",
        kategori_navn="Navnet på kategorien som skal opprettes"
    )
    @app_commands.default_permissions(administrator=True)
    async def set_judge(self, interaction: discord.Interaction, bruker: discord.Member, kategori_navn: str):
        """Sets up a judge's quarters with the specified category name"""
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        
        # Create judge role if it doesn't exist
        judge_role = discord.utils.get(guild.roles, name="Dommer")
        if not judge_role:
            try:
                judge_role = await guild.create_role(name="Dommer", color=discord.Color.from_rgb(50, 100, 150))
                logger.info(f"Created 'Dommer' role in guild {guild.name}")
            except discord.Forbidden:
                await interaction.followup.send("Feil: Boten har ikke tillatelse til å opprette roller. Gi boten 'Administrer roller' tillatelse.", ephemeral=True)
                return
            except Exception as e:
                logger.error(f"Error creating judge role: {e}")
                await interaction.followup.send(f"Feil ved oppretting av dommerrolle: {e}", ephemeral=True)
                return
            
        # Assign judge role to user
        try:
            await bruker.add_roles(judge_role)
            logger.info(f"Added 'Dommer' role to {bruker.display_name}")
        except discord.Forbidden:
            await interaction.followup.send(
                "Feil: Boten har ikke tillatelse til å legge til roller for brukere. "
                "Dette kan skje hvis:\n"
                "1. Boten mangler 'Administrer roller' tillatelse\n"
                "2. Brukerens høyeste rolle er høyere enn botens høyeste rolle\n\n"
                "Fortsetter oppsett uten å legge til dommerrolle.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error adding judge role to user: {e}")
            await interaction.followup.send(f"Advarsel: Kunne ikke legge til dommerrolle for brukeren: {e}. Fortsetter oppsett.", ephemeral=True)
        
        # Create judge category
        try:
            judge_category = await guild.create_category(kategori_navn)
            logger.info(f"Created judge category '{kategori_navn}'")
            
            # Set permissions for the category
            try:
                await judge_category.set_permissions(guild.default_role, read_messages=False, send_messages=False)
                await judge_category.set_permissions(bruker, read_messages=True, send_messages=True)
                await judge_category.set_permissions(judge_role, read_messages=True, send_messages=True)
                logger.info(f"Set permissions for judge category '{kategori_navn}'")
            except discord.Forbidden:
                await interaction.followup.send(
                    "Advarsel: Boten har ikke tillatelse til å sette rettigheter for kategorien. "
                    "Gi boten 'Administrer kanaler' og 'Administrer roller' tillatelser.",
                    ephemeral=True
                )
            except Exception as e:
                logger.error(f"Error setting category permissions: {e}")
                await interaction.followup.send(f"Advarsel: Kunne ikke sette rettigheter for kategorien: {e}", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("Feil: Boten har ikke tillatelse til å opprette kategorier. Gi boten 'Administrer kanaler' tillatelse.", ephemeral=True)
            return
        except Exception as e:
            logger.error(f"Error creating judge category: {e}")
            await interaction.followup.send(f"Feil ved oppretting av dommerkategori: {e}", ephemeral=True)
            return
        
        # Store judge in database
        try:
            conn = self.get_db_connection()
            c = conn.cursor()
            
            # Check if judge already exists
            c.execute('''
            SELECT * FROM judges WHERE user_id = ?
            ''', (bruker.id,))
            
            existing_judge = c.fetchone()
            
            if existing_judge:
                # Update existing judge
                c.execute('''
                UPDATE judges 
                SET category_id = ?, category_name = ?
                WHERE user_id = ?
                ''', (judge_category.id, kategori_navn, bruker.id))
                logger.info(f"Updated judge {bruker.display_name} with new category")
            else:
                # Insert new judge
                c.execute('''
                INSERT INTO judges (user_id, category_id, category_name)
                VALUES (?, ?, ?)
                ''', (bruker.id, judge_category.id, kategori_navn))
                logger.info(f"Added new judge {bruker.display_name} to database")
            
            # Add category to categories table
            c.execute('''
            INSERT INTO categories (category_id, name, role_id)
            VALUES (?, ?, ?)
            ''', (judge_category.id, kategori_navn, judge_role.id))
            
            conn.commit()
            conn.close()
            
            await interaction.followup.send(f"Dommer {bruker.mention} har fått tildelt kvarter '{kategori_navn}'.", ephemeral=True)
        except Exception as e:
            logger.error(f"Database error in set_judge: {e}")
            await interaction.followup.send(f"Feil ved lagring av dommerdata i databasen: {e}", ephemeral=True)
    
    @app_commands.command(name="fjern-dommer", description="Fjerner en dommers kvarter")
    @app_commands.describe(
        bruker="Dommeren som skal fjernes"
    )
    @app_commands.default_permissions(administrator=True)
    async def remove_judge(self, interaction: discord.Interaction, bruker: discord.Member):
        """Removes a judge's quarters"""
        await interaction.response.defer(ephemeral=True)
        
        # Get judge info from database
        conn = self.get_db_connection()
        c = conn.cursor()
        
        c.execute('''
        SELECT * FROM judges WHERE user_id = ?
        ''', (bruker.id,))
        
        judge = c.fetchone()
        
        if not judge:
            await interaction.followup.send(f"{bruker.display_name} er ikke registrert som dommer.", ephemeral=True)
            conn.close()
            return
            
        # Get category
        category = interaction.guild.get_channel(judge['category_id'])
        
        # Delete category and all channels
        if category:
            try:
                for channel in category.channels:
                    try:
                        await channel.delete()
                        logger.info(f"Deleted channel {channel.name} from judge category")
                    except discord.Forbidden:
                        await interaction.followup.send(f"Advarsel: Kunne ikke slette kanalen {channel.name}. Mangler tillatelser.", ephemeral=True)
                    except Exception as e:
                        logger.error(f"Error deleting channel {channel.name}: {e}")
                        await interaction.followup.send(f"Advarsel: Feil ved sletting av kanal {channel.name}: {e}", ephemeral=True)
                
                try:
                    await category.delete()
                    logger.info(f"Deleted judge category {category.name}")
                except discord.Forbidden:
                    await interaction.followup.send(f"Advarsel: Kunne ikke slette kategorien {category.name}. Mangler tillatelser.", ephemeral=True)
                except Exception as e:
                    logger.error(f"Error deleting category {category.name}: {e}")
                    await interaction.followup.send(f"Advarsel: Feil ved sletting av kategori {category.name}: {e}", ephemeral=True)
            except Exception as e:
                logger.error(f"Error processing category deletion: {e}")
                await interaction.followup.send(f"Advarsel: Feil ved prosessering av kategorisletting: {e}", ephemeral=True)
        else:
            logger.warning(f"Judge category with ID {judge['category_id']} not found")
            await interaction.followup.send(f"Advarsel: Fant ikke dommerkategorien med ID {judge['category_id']}.", ephemeral=True)
        
        # Remove judge role
        judge_role = discord.utils.get(interaction.guild.roles, name="Dommer")
        if judge_role and judge_role in bruker.roles:
            try:
                await bruker.remove_roles(judge_role)
                logger.info(f"Removed 'Dommer' role from {bruker.display_name}")
            except discord.Forbidden:
                await interaction.followup.send(
                    "Advarsel: Boten har ikke tillatelse til å fjerne roller fra brukere. "
                    "Dette kan skje hvis:\n"
                    "1. Boten mangler 'Administrer roller' tillatelse\n"
                    "2. Brukerens høyeste rolle er høyere enn botens høyeste rolle",
                    ephemeral=True
                )
            except Exception as e:
                logger.error(f"Error removing judge role from user: {e}")
                await interaction.followup.send(f"Advarsel: Kunne ikke fjerne dommerrolle fra brukeren: {e}", ephemeral=True)
        
        # Remove from database
        try:
            # Remove from judges table
            c.execute('''
            DELETE FROM judges WHERE user_id = ?
            ''', (bruker.id,))
            
            # Remove from categories table
            c.execute('''
            DELETE FROM categories WHERE category_id = ?
            ''', (judge['category_id'],))
            
            conn.commit()
            conn.close()
            
            await interaction.followup.send(f"Dommer {bruker.mention} har blitt fjernet.", ephemeral=True)
            logger.info(f"Judge {bruker.name} (ID: {bruker.id}) removed")
        except Exception as e:
            logger.error(f"Database error in remove_judge: {e}")
            await interaction.followup.send(f"Feil ved sletting av dommerdata fra databasen: {e}", ephemeral=True)
    
    @app_commands.command(name="lag-kategori", description="Oppretter en ny sak-kategori")
    @app_commands.describe(
        navn="Navnet på den nye kategorien"
    )
    @app_commands.default_permissions(administrator=True)
    async def create_category(self, interaction: discord.Interaction, navn: str):
        """Creates a new ticket category"""
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        
        # Create category
        category = await guild.create_category(navn)
        
        # Store in database
        conn = self.get_db_connection()
        c = conn.cursor()
        
        c.execute('''
        INSERT INTO categories (category_id, name, role_id)
        VALUES (?, ?, ?)
        ''', (category.id, navn, 0))
        
        conn.commit()
        conn.close()
        
        await interaction.followup.send(f"Kategori '{navn}' er opprettet!")
        logger.info(f"Category '{navn}' created in guild {guild.name}")
    
    @app_commands.command(name="registrer-kategori", description="Registrerer en kategori med rolletilgang")
    @app_commands.describe(
        navn="Navnet på kategorien",
        rolle="Rollen som skal ha tilgang til kategorien"
    )
    @app_commands.default_permissions(administrator=True)
    async def register_category(self, interaction: discord.Interaction, navn: str, rolle: discord.Role):
        """Registers a new category seperate from judge quarter categories"""
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        
        # Create category
        category = await guild.create_category(navn)
        await category.set_permissions(guild.default_role, read_messages=False, send_messages=False)
        await category.set_permissions(rolle, read_messages=True, send_messages=True)
        
        # Store in database
        conn = self.get_db_connection()
        c = conn.cursor()
        
        c.execute('''
        INSERT INTO categories (category_id, name, role_id)
        VALUES (?, ?, ?)
        ''', (category.id, navn, rolle.id))
        
        conn.commit()
        conn.close()
        
        await interaction.followup.send(f"Kategori '{navn}' er registrert med tilgang for rollen {rolle.name}!")
        logger.info(f"Category '{navn}' registered with role {rolle.name} in guild {guild.name}")

    @app_commands.command(name="sett-rolle", description="Setter rolletillatelser for ulike bot-funksjoner")
    @app_commands.describe(
        rolle_funksjon="Funksjonen som rollen skal ha tilgang til",
        rolle="Rollen som skal ha tilgangen"
    )
    @app_commands.choices(rolle_funksjon=[
        app_commands.Choice(name="Dommer", value="judge"),
        app_commands.Choice(name="Administrator", value="admin"),
        app_commands.Choice(name="Sak-håndtering", value="case_management"),
        app_commands.Choice(name="Bevis-håndtering", value="evidence_management"),
        app_commands.Choice(name="Varsel-håndtering", value="notification_management"),
        app_commands.Choice(name="Arkiv-tilgang", value="archive_access")
    ])
    @app_commands.default_permissions(administrator=True)
    async def set_role_permission(self, interaction: discord.Interaction, rolle_funksjon: str, rolle: discord.Role):
        """
        Sets role permissions for different bot functions
        
        Args:
            rolle_funksjon: The function the role should have access to
            rolle: The role that should have the access
        """
        await interaction.response.defer(ephemeral=True)
        
        # Store in database
        conn = self.get_db_connection()
        c = conn.cursor()
        
        # Check if permission already exists
        c.execute('''
        SELECT * FROM role_permissions WHERE function = ? AND guild_id = ?
        ''', (rolle_funksjon, interaction.guild.id))
        
        existing_permission = c.fetchone()
        
        if existing_permission:
            # Update existing permission
            c.execute('''
            UPDATE role_permissions
            SET role_id = ?
            WHERE function = ? AND guild_id = ?
            ''', (rolle.id, rolle_funksjon, interaction.guild.id))
            
            action = "oppdatert"
        else:
            # Create new permission
            c.execute('''
            INSERT INTO role_permissions (guild_id, function, role_id)
            VALUES (?, ?, ?)
            ''', (interaction.guild.id, rolle_funksjon, rolle.id))
            
            action = "lagt til"
        
        conn.commit()
        conn.close()
        
        # Get function name in Norwegian
        function_names = {
            "judge": "Dommer",
            "admin": "Administrator",
            "case_management": "Sak-håndtering",
            "evidence_management": "Bevis-håndtering",
            "notification_management": "Varsel-håndtering",
            "archive_access": "Arkiv-tilgang"
        }
        
        function_name = function_names.get(rolle_funksjon, rolle_funksjon)
        
        await interaction.followup.send(f"Rolle '{rolle.name}' er {action} for funksjonen '{function_name}'!")
        logger.info(f"Role permission for '{rolle_funksjon}' {action} to '{rolle.name}' in guild {interaction.guild.name}")
    
    @app_commands.command(name="vis-roller", description="Viser alle rolletillatelser for bot-funksjoner")
    @app_commands.default_permissions(administrator=True)
    async def show_role_permissions(self, interaction: discord.Interaction):
        """Shows all role permissions for bot functions"""
        await interaction.response.defer(ephemeral=True)
        
        # Get permissions from database
        conn = self.get_db_connection()
        c = conn.cursor()
        
        c.execute('''
        SELECT * FROM role_permissions WHERE guild_id = ?
        ''', (interaction.guild.id,))
        
        permissions = c.fetchall()
        conn.close()
        
        if not permissions:
            await interaction.followup.send("Ingen rolletillatelser er satt opp ennå.")
            return
        
        # Create embed
        embed = discord.Embed(
            title="Rolletillatelser",
            description="Oversikt over rolletillatelser for bot-funksjoner",
            color=discord.Color.blue()
        )
        
        # Get function names in Norwegian
        function_names = {
            "judge": "Dommer",
            "admin": "Administrator",
            "case_management": "Sak-håndtering",
            "evidence_management": "Bevis-håndtering",
            "notification_management": "Varsel-håndtering",
            "archive_access": "Arkiv-tilgang"
        }
        
        # Add each permission to the embed
        for permission in permissions:
            function_name = function_names.get(permission['function'], permission['function'])
            role = interaction.guild.get_role(permission['role_id'])
            role_name = role.name if role else "Ukjent rolle (slettet)"
            
            embed.add_field(
                name=function_name,
                value=role_name,
                inline=True
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"Role permissions viewed by {interaction.user} in guild {interaction.guild.name}")
    
    @app_commands.command(name="synk-kommandoer", description="Synkroniserer alle kommandoer med Discord")
    @app_commands.default_permissions(administrator=True)
    async def sync_commands(self, interaction: discord.Interaction):
        """
        Syncs all commands with Discord to ensure they show up in the slash command menu
        
        This is useful when new commands have been added but aren't showing up
        """
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Sync commands for the current guild
            synced = await self.bot.tree.sync(guild=discord.Object(id=interaction.guild.id))
            
            # Log the sync
            logger.info(f"Commands synced for guild {interaction.guild.name} (ID: {interaction.guild.id})")
            logger.info(f"Synced {len(synced)} commands")
            
            # Inform the user
            await interaction.followup.send(f"Synkroniserte {len(synced)} kommandoer med Discord. Alle kommandoer burde nå være tilgjengelige.", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error syncing commands: {e}")
            await interaction.followup.send(f"En feil oppstod under synkronisering: {e}", ephemeral=True)
    
    @app_commands.command(name="sett-arkiv-kategori", description="Setter en eksisterende kategori som arkiv-kategori")
    @app_commands.describe(
        kategori="Kategorien som skal settes som arkiv-kategori"
    )
    @app_commands.default_permissions(administrator=True)
    async def set_archive_category(self, interaction: discord.Interaction, kategori: discord.CategoryChannel):
        """
        Sets an existing category as the archive category
        
        This command allows you to designate an existing category as the archive category,
        which is used for storing closed and archived tickets.
        
        Args:
            kategori: The category to set as the archive category
        """
        await interaction.response.defer(ephemeral=True)
        
        # Get connection to database
        conn = self.get_db_connection()
        c = conn.cursor()
        
        # Check if "Arkiv" category already exists in database
        c.execute('''
        SELECT * FROM categories WHERE name = 'Arkiv'
        ''')
        
        existing_archive = c.fetchone()
        
        if existing_archive:
            # Update existing archive category
            c.execute('''
            UPDATE categories
            SET category_id = ?
            WHERE name = 'Arkiv'
            ''', (kategori.id,))
            
            logger.info(f"Updated archive category to {kategori.name} (ID: {kategori.id})")
            action = "oppdatert"
        else:
            # Insert new archive category
            c.execute('''
            INSERT INTO categories (category_id, name, role_id)
            VALUES (?, ?, ?)
            ''', (kategori.id, "Arkiv", 0))
            
            logger.info(f"Set new archive category: {kategori.name} (ID: {kategori.id})")
            action = "satt"
        
        conn.commit()
        
        # Set appropriate permissions for the archive category
        try:
            await kategori.set_permissions(interaction.guild.default_role, read_messages=False, send_messages=False)
            logger.info(f"Set permissions for archive category {kategori.name}")
        except discord.Forbidden:
            await interaction.followup.send(
                "Advarsel: Boten har ikke tillatelse til å sette rettigheter for kategorien. "
                "Gi boten 'Administrer kanaler' tillatelse.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error setting category permissions: {e}")
            await interaction.followup.send(f"Advarsel: Kunne ikke sette rettigheter for kategorien: {e}", ephemeral=True)
        
        # Check if archive-log channel exists in this category
        archive_log_exists = False
        for channel in kategori.text_channels:
            if channel.name == "arkiv-logg":
                archive_log_exists = True
                break
        
        # Provide feedback to user
        if archive_log_exists:
            await interaction.followup.send(
                f"Arkiv-kategori er {action} til '{kategori.name}'. "
                f"Arkiv-logg kanal finnes allerede i denne kategorien.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"Arkiv-kategori er {action} til '{kategori.name}'. "
                f"Merk: Ingen 'arkiv-logg' kanal ble funnet i denne kategorien. "
                f"Du kan opprette den med kommandoen `/sett-arkiv-logg`.",
                ephemeral=True
            )
        
        conn.close()
    
    @app_commands.command(name="sett-arkiv-logg", description="Setter en eksisterende kanal som arkiv-logg")
    @app_commands.describe(
        kanal="Kanalen som skal settes som arkiv-logg"
    )
    @app_commands.default_permissions(administrator=True)
    async def set_archive_log(self, interaction: discord.Interaction, kanal: discord.TextChannel):
        """
        Sets an existing channel as the archive log channel
        
        This command allows you to designate an existing text channel as the archive log channel,
        which is used for storing case exports when cases are closed.
        
        Args:
            kanal: The text channel to set as the archive log channel
        """
        await interaction.response.defer(ephemeral=True)
        
        # Check if the channel name is "arkiv-logg"
        if kanal.name != "arkiv-logg":
            # Rename the channel
            try:
                await kanal.edit(name="arkiv-logg")
                logger.info(f"Renamed channel {kanal.id} to 'arkiv-logg'")
            except discord.Forbidden:
                await interaction.followup.send(
                    "Advarsel: Boten har ikke tillatelse til å endre navn på kanalen. "
                    "Gi boten 'Administrer kanaler' tillatelse. "
                    "Fortsetter uten å endre navn.",
                    ephemeral=True
                )
            except Exception as e:
                logger.error(f"Error renaming channel: {e}")
                await interaction.followup.send(
                    f"Advarsel: Kunne ikke endre navn på kanalen: {e}. "
                    f"Fortsetter uten å endre navn.",
                    ephemeral=True
                )
        
        # Get the parent category
        category = kanal.category
        
        # Get connection to database
        conn = self.get_db_connection()
        c = conn.cursor()
        
        # Check if the parent category is registered as "Arkiv"
        if category:
            c.execute('''
            SELECT * FROM categories WHERE category_id = ? AND name = 'Arkiv'
            ''', (category.id,))
            
            archive_category = c.fetchone()
            
            if not archive_category:
                # Register the parent category as "Arkiv"
                c.execute('''
                SELECT * FROM categories WHERE name = 'Arkiv'
                ''')
                
                existing_archive = c.fetchone()
                
                if existing_archive:
                    # Update existing archive category
                    c.execute('''
                    UPDATE categories
                    SET category_id = ?
                    WHERE name = 'Arkiv'
                    ''', (category.id,))
                    
                    logger.info(f"Updated archive category to match the parent of archive-log: {category.name} (ID: {category.id})")
                else:
                    # Insert new archive category
                    c.execute('''
                    INSERT INTO categories (category_id, name, role_id)
                    VALUES (?, ?, ?)
                    ''', (category.id, "Arkiv", 0))
                    
                    logger.info(f"Set new archive category to match the parent of archive-log: {category.name} (ID: {category.id})")
                
                conn.commit()
                
                await interaction.followup.send(
                    f"Arkiv-logg kanal er satt til '{kanal.name}'. "
                    f"Foreldrekategorien '{category.name}' er nå registrert som arkiv-kategori.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"Arkiv-logg kanal er satt til '{kanal.name}'. "
                    f"Foreldrekategorien '{category.name}' er allerede registrert som arkiv-kategori.",
                    ephemeral=True
                )
        else:
            await interaction.followup.send(
                f"Arkiv-logg kanal er satt til '{kanal.name}'. "
                f"Merk: Kanalen er ikke i en kategori. Det anbefales å flytte den til arkiv-kategorien.",
                ephemeral=True
            )
        
        conn.close()
    
    @app_commands.command(name="sett-saker-kategori", description="Setter en eksisterende kategori som saker-kategori")
    @app_commands.describe(
        kategori="Kategorien som skal settes som saker-kategori"
    )
    @app_commands.default_permissions(administrator=True)
    async def set_cases_category(self, interaction: discord.Interaction, kategori: discord.CategoryChannel):
        """
        Sets an existing category as the cases category
        
        This command allows you to designate an existing category as the cases category,
        which is used for storing open tickets.
        
        Args:
            kategori: The category to set as the cases category
        """
        await interaction.response.defer(ephemeral=True)
        
        # Get connection to database
        conn = self.get_db_connection()
        c = conn.cursor()
        
        # Check if "Saker" category already exists in database
        c.execute('''
        SELECT * FROM categories WHERE name = 'Saker'
        ''')
        
        existing_cases = c.fetchone()
        
        if existing_cases:
            # Update existing cases category
            c.execute('''
            UPDATE categories
            SET category_id = ?
            WHERE name = 'Saker'
            ''', (kategori.id,))
            
            logger.info(f"Updated cases category to {kategori.name} (ID: {kategori.id})")
            action = "oppdatert"
        else:
            # Insert new cases category
            c.execute('''
            INSERT INTO categories (category_id, name, role_id)
            VALUES (?, ?, ?)
            ''', (kategori.id, "Saker", 0))
            
            logger.info(f"Set new cases category: {kategori.name} (ID: {kategori.id})")
            action = "satt"
        
        conn.commit()
        conn.close()
        
        await interaction.followup.send(
            f"Saker-kategori er {action} til '{kategori.name}'.",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(Setup(bot))
