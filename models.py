# =============================================================================
# models.py — Database Schema (SQLAlchemy ORM)
# =============================================================================
# Defines three tables:
#   1. Player  — every registered student
#   2. Match   — each knockout match between two players
#   3. Admin   — administrator accounts (username + hashed password)
#
# SQLAlchemy lets us work with these tables as Python objects instead of
# writing raw SQL. Flask-SQLAlchemy integrates it tightly with Flask.
# =============================================================================

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# db is the SQLAlchemy instance. We create it here and initialise it
# inside create_app() in app.py using db.init_app(app).
db = SQLAlchemy()


# =============================================================================
# TABLE 1: Player
# =============================================================================

class Player(db.Model):
    """
    Represents one registered student/player.

    Lifecycle:
        Registration → is_approved=False (pending admin review)
        Admin approves → is_approved=True (eligible for bracket)
        Loses a match  → is_eliminated=True (out of tournament)
    """
    __tablename__ = "players"

    # --- Primary Key ---
    id = db.Column(db.Integer, primary_key=True)

    # --- Registration Fields ---
    full_name      = db.Column(db.String(100), nullable=False)
    roll_number    = db.Column(db.String(50),  unique=True, nullable=False)
    chess_username = db.Column(db.String(50),  unique=True, nullable=False)
    whatsapp       = db.Column(db.String(20),  nullable=False)

    # --- Timestamps ---
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- Tournament State ---
    is_approved   = db.Column(db.Boolean, default=False)   # Admin must approve
    is_eliminated = db.Column(db.Boolean, default=False)   # Set True after a loss

    # --- Leaderboard Stats ---
    wins      = db.Column(db.Integer, default=0)   # Total match wins
    losses    = db.Column(db.Integer, default=0)   # Total match losses
    points    = db.Column(db.Integer, default=0)   # 1 per win, used for ranking
    bye_count = db.Column(db.Integer, default=0)   # Number of byes received

    # --- Relationships ---
    # A Player can appear as player1 or player2 in many matches.
    # back_populates is set on Match so we can do player.matches_as_p1, etc.
    matches_as_p1 = db.relationship(
        "Match", foreign_keys="Match.player1_id",
        backref="player1", lazy="dynamic"
    )
    matches_as_p2 = db.relationship(
        "Match", foreign_keys="Match.player2_id",
        backref="player2", lazy="dynamic"
    )
    matches_won = db.relationship(
        "Match", foreign_keys="Match.winner_id",
        backref="winner", lazy="dynamic"
    )

    def __repr__(self):
        return f"<Player {self.roll_number} — {self.chess_username}>"

    # Helper: return all matches this player is involved in
    def all_matches(self):
        return Match.query.filter(
            (Match.player1_id == self.id) | (Match.player2_id == self.id)
        ).order_by(Match.round_number).all()

    # Helper: return the latest pending or in-progress match for this player
    def current_match(self):
        return Match.query.filter(
            ((Match.player1_id == self.id) | (Match.player2_id == self.id)),
            Match.status.in_(["pending", "in_progress"])
        ).order_by(Match.round_number.desc()).first()


# =============================================================================
# TABLE 2: Match
# =============================================================================

class Match(db.Model):
    """
    Represents one knockout match between two players in a specific round.

    Status flow:  pending → in_progress → completed
                                        → bye  (when player2_id is NULL)

    A NULL player2_id means the player gets a "bye" and auto-advances.
    """
    __tablename__ = "matches"

    # --- Primary Key ---
    id = db.Column(db.Integer, primary_key=True)

    # --- Round Info ---
    round_number = db.Column(db.Integer, nullable=False)   # 1 = Round 1, 2 = QF, etc.
    round_label  = db.Column(db.String(50), nullable=True) # e.g. "Quarter-Final"

    # --- Players ---
    # player2_id is nullable — NULL means this is a bye for player1
    player1_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False)
    player2_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=True)

    # --- Result ---
    # winner_id points to the Player who won. NULL while match is pending/in_progress.
    winner_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=True)

    # --- Status ---
    # "pending"     → match created, not yet started
    # "in_progress" → match is live on the site right now
    # "completed"   → result has been recorded
    # "bye"         → player1 advances automatically (no opponent)
    status = db.Column(db.String(20), default="pending", nullable=False)

    # --- Timestamps ---
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    # --- Live Game State (for spectator view) ---
    board_state   = db.Column(db.Text, nullable=True)       # JSON string of 8x8 board
    move_history  = db.Column(db.Text, default='[]')         # JSON array of move notations
    last_move     = db.Column(db.String(20), nullable=True)  # Last move in algebraic notation
    current_turn  = db.Column(db.String(10), default='white') # 'white' or 'black'
    move_count    = db.Column(db.Integer, default=0)          # Total moves played

    # --- Optional notes (e.g. "Player 2 forfeited — did not join in time") ---
    notes = db.Column(db.String(300), nullable=True)

    def __repr__(self):
        return f"<Match Round {self.round_number}: P{self.player1_id} vs P{self.player2_id}>"

    @property
    def is_bye(self):
        """True if this match has no opponent (auto-advance)."""
        return self.player2_id is None


# =============================================================================
# TABLE 3: Admin
# =============================================================================

class Admin(db.Model):
    """
    Stores admin accounts. Passwords are NEVER stored in plain text —
    only a secure bcrypt/pbkdf2 hash via Werkzeug's generate_password_hash.
    """
    __tablename__ = "admins"

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    # --- Password Helpers ---

    def set_password(self, plain_text_password: str):
        """Hashes and stores the password. Call this when creating/changing passwords."""
        self.password_hash = generate_password_hash(plain_text_password)

    def check_password(self, plain_text_password: str) -> bool:
        """Returns True if the given password matches the stored hash."""
        return check_password_hash(self.password_hash, plain_text_password)

    def __repr__(self):
        return f"<Admin {self.username}>"
