# Court Bot Configuration File
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Bot Token (loaded from .env file)
TOKEN = os.getenv("TOKEN")

# Guild ID (replace with your actual guild ID)
GUILD_ID = 123456789012345678 

# Owner ID (replace with your actual Discord user ID)
OWNER_ID = 123456789012345678  

# Bot Colors
COLORS = {
    "primary": 0x3498db,  # Blue
    "success": 0x2ecc71,  # Green
    "warning": 0xf39c12,  # Orange
    "error": 0xe74c3c,    # Red
    "info": 0x7289da      # Discord Blurple
}

# Status Messages
STATUS_MESSAGES = {
    "åpen": "🟢 Åpen",
    "under_behandling": "🟠 Under behandling",
    "lukket": "🔴 Lukket",
    "anket": "🟣 Anket"
}

# Default category names
DEFAULT_CATEGORIES = {
    "tickets": "Saker",
    "archive": "Arkiv"
}

# Message templates
MESSAGES = {
    "case_closed": "Din sak har blitt avsluttet av {judge}.\n\nGrunnlag: {reason}\n\nSaken er nå arkivert og kan ikke gjenåpnes.",
    "notification": "Dette er en påminnelse om din sak: {case_title}\n\nMelding: {message}",
    "evidence_added": "Ny bevis har blitt lagt til saken:\n\nID: {evidence_id}\nBeskrivelse: {description}\nLink: {link}",
    "case_claimed": "Saken har blitt tatt av dommer {judge_name}."
}
