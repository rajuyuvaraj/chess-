# =============================================================================
# config.py — Tournament Configuration
# =============================================================================
# Edit this file to customize your tournament settings.
# All editable settings are grouped here so you never have to dig into app.py.
# =============================================================================

import os

# -----------------------------------------------------------------------------
# FLASK CORE SETTINGS
# -----------------------------------------------------------------------------

# SECRET_KEY: Used to sign session cookies. Change this to a long random string
# before deploying. You can generate one with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production-to-a-random-secret")

# Path to the database. Uses Render's DATABASE_URL if available, otherwise local SQLite.
DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///tournament.db")

# Set to False in production (hides detailed error pages from users)
DEBUG = True

# -----------------------------------------------------------------------------
# TOURNAMENT DETAILS — Edit these for your event
# -----------------------------------------------------------------------------

TOURNAMENT_NAME     = "College Chess Championship 2025"
COLLEGE_NAME        = "Your College Name"
TIME_CONTROL        = "10+0 Rapid (10 minutes, no increment)"
TOURNAMENT_FORMAT   = "Single-Elimination Knockout"
ORGANIZER_NAME      = "Chess Club"
ORGANIZER_WHATSAPP  = "+91-XXXXXXXXXX"   # WhatsApp number for the group

# Challonge bracket embed URL
# After creating your bracket on challonge.com, go to:
#   Your Bracket → Share → Embed → copy the src URL
# It looks like: https://challonge.com/tournaments/<your_id>/module
CHALLONGE_EMBED_URL = "https://challonge.com/tournaments/YOUR_TOURNAMENT_ID/module"

# -----------------------------------------------------------------------------
# ONE-HOUR JOIN RULE — Displayed prominently on the homepage
# -----------------------------------------------------------------------------

ONE_HOUR_RULE = (
    "Once the bracket is published and your match is announced, "
    "you MUST join your match on this site within "
    "<strong>60 minutes</strong>. Failure to do so will result in a "
    "walkover loss for the round."
)

# -----------------------------------------------------------------------------
# REGISTRATION SETTINGS
# -----------------------------------------------------------------------------

# Set to False to stop accepting new registrations (e.g., once tournament starts)
REGISTRATION_OPEN = True

# Maximum number of players. Set to None for unlimited.
MAX_PLAYERS = 64
