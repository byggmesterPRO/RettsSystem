import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
import sqlite3
import os
import datetime
import logging
import json
import asyncio
from config import TOKEN, GUILD_ID

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("courtbot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CourtBot")

# Initialize bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize database connection
def get_db_connection():
    # Create database directory if it doesn't exist
    os.makedirs('data', exist_ok=True)
    conn = sqlite3.connect('data/courtbot.db')
    conn.row_factory = sqlite3.Row
    return conn

# Create the database tables if they don't exist
def init_db():
    logger.info("Initializing database...")
    conn = get_db_connection()
    c = conn.cursor()
    
    # Cases table
    c.execute('''
    CREATE TABLE IF NOT EXISTS cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id INTEGER UNIQUE,
        category_id INTEGER,
        creator_id INTEGER,
        assigned_judge_id INTEGER NULL,
        title TEXT,
        description TEXT,
        status TEXT DEFAULT 'Åpen',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        closed_at TIMESTAMP NULL,
        closing_reason TEXT NULL,
        archive_url TEXT NULL
    )
    ''')
    
    # Judges table
    c.execute('''
    CREATE TABLE IF NOT EXISTS judges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        category_id INTEGER UNIQUE,
        category_name TEXT
    )
    ''')
    
    # Categories table
    c.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER UNIQUE,
        name TEXT,
        role_id INTEGER
    )
    ''')
    
    # Evidence table
    c.execute('''
    CREATE TABLE IF NOT EXISTS evidence (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER,
        submitter_id INTEGER,
        description TEXT,
        link TEXT,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (case_id) REFERENCES cases (id)
    )
    ''')
    
    # Scheduled notifications table
    c.execute('''
    CREATE TABLE IF NOT EXISTS scheduled_notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_user_id INTEGER,
        message TEXT,
        scheduled_time TIMESTAMP,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        sent BOOLEAN DEFAULT 0
    )
    ''')
    
    # Role permissions table
    c.execute('''
    CREATE TABLE IF NOT EXISTS role_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        function TEXT,
        role_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(guild_id, function)
    )
    ''')
    
    # Ticket buttons table
    c.execute('''
    CREATE TABLE IF NOT EXISTS ticket_buttons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        title TEXT,
        description TEXT,
        emoji TEXT,
        button_text TEXT,
        role_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories (category_id)
    )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")

# On bot ready event
@bot.event
async def on_ready():
    logger.info(f'Bot is ready! Logged in as {bot.user} (ID: {bot.user.id})')
    init_db()
    check_scheduled_notifications.start()
    
    # Sync commands globally
    try:
        synced = await bot.tree.sync()
        logger.info(f'Synced {len(synced)} command(s) globally')
    except Exception as e:
        logger.error(f'Failed to sync commands: {e}')

# Task to check for scheduled notifications
@tasks.loop(minutes=1)
async def check_scheduled_notifications():
    try:
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get all notifications that need to be sent
        c.execute('''
        SELECT * FROM scheduled_notifications 
        WHERE scheduled_time <= ? AND sent = 0
        ''', (current_time,))
        
        notifications = c.fetchall()
        
        for notification in notifications:
            user = bot.get_user(notification['target_user_id'])
            if user:
                try:
                    await user.send(notification['message'])
                    # Mark as sent
                    c.execute('''
                    UPDATE scheduled_notifications 
                    SET sent = 1 
                    WHERE id = ?
                    ''', (notification['id'],))
                    conn.commit()
                    logger.info(f"Sent scheduled notification #{notification['id']} to {user.name}")
                except Exception as e:
                    logger.error(f"Failed to send notification to {user.name}: {e}")
            else:
                logger.error(f"Could not find user with ID {notification['target_user_id']}")
        
        conn.close()
    except Exception as e:
        logger.error(f"Error in scheduled notifications task: {e}")

@check_scheduled_notifications.before_loop
async def before_check_notifications():
    await bot.wait_until_ready()

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    logger.error(f'Command error: {error}')
    await ctx.send(f'En feil oppsto: {error}')

# Load cogs
async def load_extensions():
    """Load all extensions (cogs)"""
    await bot.load_extension("cogs.setup")
    await bot.load_extension("cogs.tickets")
    await bot.load_extension("cogs.judge")
    await bot.load_extension("cogs.evidence")
    await bot.load_extension("cogs.notifications")
    await bot.load_extension("cogs.information")

# Run the bot
async def main():
    await load_extensions()
    await bot.start(TOKEN)

if __name__ == '__main__':
    asyncio.run(main())
