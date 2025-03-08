# CourtBot - Discord Court System

CourtBot is a Discord bot designed to create and manage a virtual court system for Discord servers. It provides a structured way to handle cases, evidence, and court proceedings within your Discord community.

## Features

- **Case Management**: Create, track, and archive court cases
- **Evidence Collection**: Submit and organize evidence for each case
- **Role-Based Permissions**: Control access to commands based on Discord roles
- **Judge System**: Assign judges to cases and manage case proceedings
- **HTML Exports**: Generate HTML exports of cases with all messages and evidence
- **Notification System**: Keep users informed about case updates
- **Archive System**: Maintain a searchable archive of past cases

## Setup Guide

### Prerequisites

- Python 3.8 or higher
- Discord Bot Token
- Discord Server with admin permissions

### Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/courtbot.git
   cd courtbot
   ```

2. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the root directory with your Discord bot token:
   ```
   DISCORD_TOKEN=your_discord_bot_token_here
   ```

4. Run the bot:
   ```
   python main.py
   ```

### Initial Server Setup

1. Invite the bot to your server with appropriate permissions (Administrator is recommended)
2. Run the `/oppsett` command to set up the necessary categories and channels
3. Use the `/sett-rolle` command to assign permissions to different Discord roles

## Command Reference

### Admin Commands

- `/oppsett` - Sets up the necessary categories and channels for the court system
- `/sett-rolle` - Assigns a Discord role to a specific bot function
- `/vis-roller` - Displays all current role assignments

### Judge Commands

- `/tildel` - Claims a case and assigns it to yourself as a judge
- `/send-sak` - Moves a case to a different category
- `/send-dm` - Sends a direct message to a user through the bot
- `/legg-til-notat` - Adds a note to the case file
- `/vis-saker` - Shows all cases assigned to a judge
- `/vis-åpne-saker` - Shows all open cases in the system
- `/arkiver-legacy` - Archives an existing channel as a legacy case

### Case Management Commands

- `/opprett-sak` - Creates a new case
- `/lukk-sak` - Closes and archives a case
- `/endre-status` - Changes the status of a case

### Evidence Commands

- `/legg-til-bevis` - Adds evidence to a case
- `/fjern-bevis` - Removes evidence from a case
- `/vis-bevis` - Shows all evidence for a case
- `/eksporter-html` - Exports a case to HTML format

### Notification Commands

- `/varsle` - Sends a notification to a user about a case
- `/varsle-alle` - Sends a notification to all participants in a case

## Role Permissions

The bot uses a role-based permission system with the following function categories:

- `judge` - For judge-specific commands
- `admin` - For administrative commands
- `case_management` - For case-related commands
- `evidence_management` - For evidence-related commands
- `notification_management` - For notification-related commands
- `archive_access` - For archive access

## Database Structure

The bot uses SQLite to store all data. The database includes tables for:

- Cases
- Evidence
- Judges
- Categories
- Role permissions
- Notifications

## HTML Exports

The bot can generate HTML exports of cases that include:

- Case information (title, description, status, etc.)
- All evidence submitted for the case
- All messages in the case channel with user avatars and role colors
- Messages are grouped by user and displayed in a format similar to Discord

## Troubleshooting

- **Permission Errors**: Ensure the bot has the necessary permissions in your Discord server
- **Database Errors**: Check that the SQLite database file exists and is not corrupted
- **Command Not Working**: Verify that the user has the appropriate role permission for the command

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- Discord.py library
- All contributors to the project
