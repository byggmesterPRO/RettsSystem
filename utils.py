import discord
import sqlite3
from typing import Optional, List, Union

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect('data/courtbot.db')
    conn.row_factory = sqlite3.Row
    return conn

async def has_role_permission(user: discord.Member, function: str) -> bool:
    """
    Check if a user has the required role permission for a specific function
    
    Args:
        user: The user to check permissions for
        function: The function to check permission for
        
    Returns:
        bool: True if the user has permission, False otherwise
    """
    # Server owner always has permission
    if user.guild.owner_id == user.id:
        return True
    
    # Administrator permission always has permission
    if user.guild_permissions.administrator:
        return True
    
    # Get the role ID for the function from the database
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
    SELECT role_id FROM role_permissions 
    WHERE function = ? AND guild_id = ?
    ''', (function, user.guild.id))
    
    result = c.fetchone()
    conn.close()
    
    if not result:
        # If no role is set for this function, default to requiring administrator
        return user.guild_permissions.administrator
    
    # Check if the user has the required role
    role_id = result['role_id']
    role = user.guild.get_role(role_id)
    
    if not role:
        # If the role doesn't exist anymore, default to requiring administrator
        return user.guild_permissions.administrator
    
    return role in user.roles

def check_role_permission(function: str):
    """
    Decorator to check if a user has the required role permission for a command
    
    Args:
        function: The function to check permission for
        
    Returns:
        function: The decorated function
    """
    async def predicate(interaction: discord.Interaction) -> bool:
        return await has_role_permission(interaction.user, function)
    
    return discord.app_commands.check(predicate)
