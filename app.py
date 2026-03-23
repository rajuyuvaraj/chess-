# =============================================================================
# app.py — Main Flask Application
# =============================================================================
# All routes are organised into three clearly labelled sections:
#
#   SECTION A: Public Routes    — Homepage, Registration, Bracket
#   SECTION B: Student Routes   — Login, Dashboard (view own next match)
#   SECTION C: Admin Routes     — Dashboard, Players, Matches, Export
#
# Run with:  flask run          (development)
#            python app.py      (quick start)
#
# First-time setup:
#   1. pip install -r requirements.txt
#   2. flask init-db             ← creates the SQLite database
#   3. flask create-admin        ← creates the first admin account
#   4. flask run
# =============================================================================

import csv
import io
import random
from functools import wraps
from datetime import datetime

import click
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, make_response, g, jsonify
)

from config import *          # Import all settings from config.py
from models import db, Player, Match, Admin


# =============================================================================
# APP FACTORY
# =============================================================================

def create_app():
    """
    Creates and configures the Flask application.
    Using a factory function makes the app easier to test and extend later.
    """
    app = Flask(__name__)

    # --- Load settings from config.py ---
    app.config["SECRET_KEY"]        = SECRET_KEY
    
    # Render's Postgres URL starts with postgres://, but SQLAlchemy requires postgresql://
    db_url = DATABASE_URI
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False  # Suppress a warning
    app.config["DEBUG"]             = DEBUG

    # Inject tournament config vars into every template automatically.
    # This means every template can use {{ tournament_name }}, {{ college_name }}, etc.
    @app.context_processor
    def inject_globals():
        return dict(
            tournament_name   = TOURNAMENT_NAME,
            college_name      = COLLEGE_NAME,
            time_control      = TIME_CONTROL,
            tournament_format = TOURNAMENT_FORMAT,
            organizer_name    = ORGANIZER_NAME,
            one_hour_rule     = ONE_HOUR_RULE,
            registration_open = REGISTRATION_OPEN,
        )

    # --- Attach database to app ---
    db.init_app(app)

    # Automatically create tables and a default admin on startup (ideal for Render zero-config deploys)
    with app.app_context():
        db.create_all()
        if not Admin.query.first():
            default_admin = Admin(username="admin")
            default_admin.set_password("admin123")
            db.session.add(default_admin)
            db.session.commit()

    # =========================================================================
    # CLI COMMANDS
    # =========================================================================
    # These are run once from the terminal to set up the app.

    @app.cli.command("init-db")
    def init_db_command():
        """Creates all database tables based on models.py."""
        with app.app_context():
            db.create_all()
        click.echo("✅  Database initialised. Tables created: players, matches, admins.")

    @app.cli.command("create-admin")
    @click.option("--username", prompt="Admin username", help="Admin login username")
    @click.option("--password", prompt=True, hide_input=True,
                  confirmation_prompt=True, help="Admin password")
    def create_admin_command(username, password):
        """Creates a new admin account (run once after init-db)."""
        with app.app_context():
            if Admin.query.filter_by(username=username).first():
                click.echo(f"❌  Admin '{username}' already exists.")
                return
            admin = Admin(username=username)
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()
            click.echo(f"✅  Admin '{username}' created successfully.")

    # =========================================================================
    # AUTH DECORATORS
    # =========================================================================

    def admin_required(f):
        """
        Route decorator: redirects to admin login if not logged in as admin.
        Usage: @admin_required above any admin route function.
        """
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get("admin_logged_in"):
                flash("Please log in to access the admin panel.", "warning")
                return redirect(url_for("admin_login"))
            return f(*args, **kwargs)
        return decorated

    def student_required(f):
        """
        Route decorator: redirects to student login if student is not logged in.
        """
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get("student_roll"):
                flash("Please log in with your Roll Number to view your dashboard.", "info")
                return redirect(url_for("student_login"))
            return f(*args, **kwargs)
        return decorated

    # =========================================================================
    # SECTION A: PUBLIC ROUTES
    # =========================================================================

    @app.route("/")
    def index():
        """
        Homepage — explains the tournament, rules, and time control.
        Also shows a basic stat block (total registrations, approved players).
        """
        total_registered = Player.query.count()
        total_approved   = Player.query.filter_by(is_approved=True).count()
        active_players   = Player.query.filter_by(is_approved=True, is_eliminated=False).count()

        return render_template(
            "index.html",
            total_registered = total_registered,
            total_approved   = total_approved,
            active_players   = active_players,
        )

    # -------------------------------------------------------------------------

    @app.route("/register", methods=["GET", "POST"])
    def register():
        """
        GET  → Shows the registration form.
        POST → Validates input, saves new Player to the database.
        """
        # If registration is closed, show a message instead of the form
        if not REGISTRATION_OPEN:
            flash("Registration is currently closed. The tournament has already started.", "danger")
            return redirect(url_for("index"))

        if request.method == "POST":
            # --- Collect form data ---
            full_name      = request.form.get("full_name",      "").strip()
            roll_number    = request.form.get("roll_number",    "").strip().upper()
            chess_username = request.form.get("chess_username", "").strip()
            whatsapp       = request.form.get("whatsapp",       "").strip()

            # --- Server-side validation ---
            errors = []

            if not full_name:
                errors.append("Full Name is required.")
            if not roll_number:
                errors.append("Roll Number is required.")
            if not chess_username:
                errors.append("Player Username is required.")
            if not whatsapp:
                errors.append("WhatsApp number is required.")
            if len(whatsapp) < 10:
                errors.append("Please enter a valid WhatsApp number.")

            # Check for duplicate roll number
            if Player.query.filter_by(roll_number=roll_number).first():
                errors.append(f"Roll Number '{roll_number}' is already registered.")

            # Check for duplicate Player Username (case-insensitive)
            if Player.query.filter(
                db.func.lower(Player.chess_username) == chess_username.lower()
            ).first():
                errors.append(f"Player username '{chess_username}' is already registered.")

            # Check max players limit
            if MAX_PLAYERS and Player.query.count() >= MAX_PLAYERS:
                errors.append("Sorry, the maximum number of participants has been reached.")

            # If there are errors, re-render the form with error messages
            if errors:
                for e in errors:
                    flash(e, "danger")
                return render_template(
                    "register.html",
                    # Pre-fill the form so the user doesn't retype everything
                    form_data={
                        "full_name":      full_name,
                        "roll_number":    roll_number,
                        "chess_username": chess_username,
                        "whatsapp":       whatsapp,
                    }
                )

            # --- All good — save to database ---
            new_player = Player(
                full_name      = full_name,
                roll_number    = roll_number,
                chess_username = chess_username,
                whatsapp       = whatsapp,
                # is_approved defaults to False — admin must approve first
            )
            db.session.add(new_player)
            db.session.commit()

            flash(
                f"🎉 Registration successful! Welcome, {full_name}. "
                "Your registration is pending admin approval. "
                "You can log in with your Roll Number to check your status.",
                "success"
            )
            return redirect(url_for("student_login"))

        # GET request — just render the empty form
        return render_template("register.html", form_data={})

    # -------------------------------------------------------------------------

    @app.route("/bracket")
    def bracket():
        """Bracket page — embeds the Challonge iframe."""
        return render_template("bracket.html", challonge_url=CHALLONGE_EMBED_URL)

    # -------------------------------------------------------------------------

    @app.route("/fixtures")
    def fixtures():
        """Public page showing all match fixtures grouped by round."""
        max_round = db.session.query(db.func.max(Match.round_number)).scalar() or 0
        rounds_data = []
        for r in range(1, max_round + 1):
            matches = Match.query.filter_by(round_number=r).order_by(Match.id).all()
            all_done = all(m.status in ('completed', 'bye') for m in matches)
            rounds_data.append({'round_number': r, 'matches': matches, 'all_done': all_done})
        active = Player.query.filter_by(is_approved=True, is_eliminated=False).count()
        return render_template('fixtures.html', rounds_data=rounds_data, current_round=max_round, active_players=active)

    # -------------------------------------------------------------------------

    @app.route("/leaderboard")
    def leaderboard():
        """Public leaderboard ranked by points, then fewest losses."""
        players = Player.query.filter_by(is_approved=True).order_by(
            Player.is_eliminated.asc(), Player.points.desc(),
            Player.wins.desc(), Player.losses.asc()
        ).all()
        active = Player.query.filter_by(is_approved=True, is_eliminated=False).count()
        max_round = db.session.query(db.func.max(Match.round_number)).scalar() or 0
        return render_template('leaderboard.html', players=players, active_players=active, current_round=max_round)

    # =========================================================================
    # SECTION B: STUDENT ROUTES
    # =========================================================================

    @app.route("/student/login", methods=["GET", "POST"])
    def student_login():
        """
        Students log in using their Roll Number + Player Username.
        No password needed — this is a lightweight identity check.
        """
        if session.get("student_roll"):
            return redirect(url_for("student_dashboard"))

        if request.method == "POST":
            roll_number    = request.form.get("roll_number",    "").strip().upper()
            chess_username = request.form.get("chess_username", "").strip()

            # Look up the player
            player = Player.query.filter(
                db.func.upper(Player.roll_number) == roll_number,
                db.func.lower(Player.chess_username) == chess_username.lower()
            ).first()

            if player:
                # Store player ID in session so we can look them up later
                session["student_roll"] = player.roll_number
                session["student_id"]   = player.id
                flash(f"Welcome back, {player.full_name}! ♟️", "success")
                return redirect(url_for("student_dashboard"))
            else:
                flash(
                    "No account found with that Roll Number and Player Username. "
                    "Please check your details or register first.",
                    "danger"
                )

        return render_template("student_login.html")

    # -------------------------------------------------------------------------

    @app.route("/student/logout")
    def student_logout():
        """Clears the student session."""
        session.pop("student_roll", None)
        session.pop("student_id",   None)
        flash("You have been logged out.", "info")
        return redirect(url_for("index"))

    # -------------------------------------------------------------------------

    @app.route("/student/dashboard")
    @student_required
    def student_dashboard():
        """
        The student's personal portal. Shows:
          - Registration status (pending / approved)
          - Current/next match details (opponent's username, round)
          - Match history
          - Elimination status
        """
        # Retrieve the logged-in player from DB using session ID
        player = Player.query.get(session["student_id"])

        if not player:
            # Shouldn't happen, but handle gracefully
            session.clear()
            flash("Your session is invalid. Please log in again.", "danger")
            return redirect(url_for("student_login"))

        # Find this player's current active match (pending or in_progress)
        current_match = player.current_match()

        # Resolve opponent from the current match
        opponent = None
        if current_match:
            if current_match.player1_id == player.id and current_match.player2_id:
                opponent = Player.query.get(current_match.player2_id)
            elif current_match.player2_id == player.id:
                opponent = Player.query.get(current_match.player1_id)

        # Full match history for this player
        match_history = player.all_matches()

        return render_template(
            "student_dashboard.html",
            player        = player,
            current_match = current_match,
            opponent      = opponent,
            match_history = match_history,
        )

    # =========================================================================
    # SECTION C: ADMIN ROUTES
    # =========================================================================

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        """Admin login with username + password."""
        if session.get("admin_logged_in"):
            return redirect(url_for("admin_dashboard"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            admin = Admin.query.filter_by(username=username).first()

            if admin and admin.check_password(password):
                session["admin_logged_in"] = True
                session["admin_username"]  = admin.username
                flash(f"Welcome, {admin.username}! Admin panel access granted.", "success")
                return redirect(url_for("admin_dashboard"))
            else:
                flash("Invalid username or password.", "danger")

        return render_template("admin_login.html")

    # -------------------------------------------------------------------------

    @app.route("/admin/logout")
    @admin_required
    def admin_logout():
        """Clears the admin session."""
        session.pop("admin_logged_in", None)
        session.pop("admin_username",  None)
        flash("Logged out of admin panel.", "info")
        return redirect(url_for("admin_login"))

    # -------------------------------------------------------------------------

    @app.route("/admin/dashboard")
    @admin_required
    def admin_dashboard():
        """Admin home — shows overview stats and quick actions."""
        # --- Stats ---
        stats = {
            "total_registered": Player.query.count(),
            "pending_approval": Player.query.filter_by(is_approved=False).count(),
            "approved":         Player.query.filter_by(is_approved=True).count(),
            "eliminated":       Player.query.filter_by(is_eliminated=True).count(),
            "still_active":     Player.query.filter_by(is_approved=True, is_eliminated=False).count(),
            "total_matches":    Match.query.count(),
            "pending_matches":  Match.query.filter_by(status="pending").count(),
            "live_matches":     Match.query.filter_by(status="in_progress").count(),
            "completed_matches":Match.query.filter_by(status="completed").count(),
        }

        # Current round number (highest round that has matches)
        highest_round = db.session.query(db.func.max(Match.round_number)).scalar() or 0

        # Latest 5 completed matches for the activity feed
        recent_results = Match.query.filter_by(status="completed")\
                                    .order_by(Match.completed_at.desc())\
                                    .limit(5).all()

        # Live matches for the "Watch Live" section
        live_matches = Match.query.filter_by(status="in_progress").all()

        # Can we start next round?
        current_round_done = highest_round == 0 or all(
            m.status in ('completed', 'bye')
            for m in Match.query.filter_by(round_number=highest_round).all()
        )
        has_pending = Match.query.filter_by(round_number=highest_round, status='pending').count() > 0

        return render_template(
            "admin_dashboard.html",
            stats            = stats,
            current_round    = highest_round,
            recent_results   = recent_results,
            live_matches     = live_matches,
            current_round_done = current_round_done,
            has_pending      = has_pending,
        )

    # -------------------------------------------------------------------------

    @app.route("/admin/players")
    @admin_required
    def admin_players():
        """Lists all registered players. Admin can approve or delete them."""
        # Separate pending and approved for easier display
        pending_players  = Player.query.filter_by(is_approved=False).order_by(Player.registered_at).all()
        approved_players = Player.query.filter_by(is_approved=True).order_by(Player.registered_at).all()
        return render_template(
            "admin_players.html",
            pending_players  = pending_players,
            approved_players = approved_players,
        )

    # -------------------------------------------------------------------------

    @app.route("/admin/players/<int:player_id>/approve", methods=["POST"])
    @admin_required
    def admin_approve_player(player_id):
        """Approves a player, making them eligible for the bracket."""
        player = Player.query.get_or_404(player_id)
        player.is_approved = True
        db.session.commit()
        flash(f"✅ {player.full_name} ({player.chess_username}) has been approved.", "success")
        return redirect(url_for("admin_players"))

    # -------------------------------------------------------------------------

    @app.route("/admin/players/<int:player_id>/reject", methods=["POST"])
    @admin_required
    def admin_reject_player(player_id):
        """Removes a player from the database entirely."""
        player = Player.query.get_or_404(player_id)
        name = player.full_name
        db.session.delete(player)
        db.session.commit()
        flash(f"🗑️ {name}'s registration has been removed.", "warning")
        return redirect(url_for("admin_players"))

    # -------------------------------------------------------------------------

    @app.route("/admin/players/approve-all", methods=["POST"])
    @admin_required
    def admin_approve_all():
        """Bulk-approves all pending players at once."""
        pending = Player.query.filter_by(is_approved=False).all()
        count = len(pending)
        for p in pending:
            p.is_approved = True
        db.session.commit()
        flash(f"✅ {count} player(s) approved.", "success")
        return redirect(url_for("admin_players"))

    # -------------------------------------------------------------------------

    @app.route("/admin/matches")
    @admin_required
    def admin_matches():
        """
        Match management page.
        Shows matches grouped by round.
        Admin can:
          - Mark a match as in_progress
          - Record a result (player1 wins / player2 wins / player1 forfeit / player2 forfeit)
          - Generate the next round automatically
        """
        # Group matches by round number
        max_round = db.session.query(db.func.max(Match.round_number)).scalar() or 0

        rounds_data = []
        for r in range(1, max_round + 1):
            matches_in_round = Match.query.filter_by(round_number=r)\
                                         .order_by(Match.id).all()
            all_done = all(m.status in ("completed", "bye") for m in matches_in_round)
            rounds_data.append({
                "round_number": r,
                "matches":      matches_in_round,
                "all_done":     all_done,
            })

        # Determine how many players are available to be paired right now
        active_matches = Match.query.filter(Match.status.in_(["pending", "in_progress"])).all()
        busy_player_ids = set()
        for m in active_matches:
            if m.player1_id: busy_player_ids.add(m.player1_id)
            if m.player2_id: busy_player_ids.add(m.player2_id)

        if busy_player_ids:
            available_players_count = Player.query.filter(
                Player.is_approved == True, 
                Player.is_eliminated == False,
                Player.id.notin_(busy_player_ids)
            ).count()
        else:
            available_players_count = Player.query.filter_by(is_approved=True, is_eliminated=False).count()

        can_generate = available_players_count >= 2

        return render_template(
            "admin_matches.html",
            rounds_data       = rounds_data,
            current_round     = max_round,
            active_players    = Player.query.filter_by(is_approved=True, is_eliminated=False).count(),
            available_players = available_players_count,
            can_generate      = can_generate,
        )

    # -------------------------------------------------------------------------

    @app.route("/admin/matches/generate", methods=["POST"])
    @admin_required
    def admin_generate_round():
        """
        Generates matches for available players.
        Allows staggered generation (pairing winners early without waiting for all matches to finish).
        """
        # Find players who are currently in a match
        active_matches = Match.query.filter(Match.status.in_(["pending", "in_progress"])).all()
        busy_player_ids = set()
        for m in active_matches:
            if m.player1_id: busy_player_ids.add(m.player1_id)
            if m.player2_id: busy_player_ids.add(m.player2_id)

        # Get all active (approved, not eliminated) players who are NOT busy
        if busy_player_ids:
            available_players = Player.query.filter(
                Player.is_approved == True, 
                Player.is_eliminated == False,
                Player.id.notin_(busy_player_ids)
            ).all()
        else:
            available_players = Player.query.filter(
                Player.is_approved == True, 
                Player.is_eliminated == False
            ).all()

        if len(available_players) < 2:
            flash("❌ Need at least 2 available players to generate pairings. Wait for more matches to finish.", "warning")
            return redirect(url_for("admin_matches"))

        # Shuffle for random fair pairing
        random.shuffle(available_players)
        
        total_active_overall = Player.query.filter_by(is_approved=True, is_eliminated=False).count()

        new_matches = []
        for i in range(0, len(available_players) - 1, 2):
            p1 = available_players[i]
            p2 = available_players[i + 1]
            
            p1_matches = Match.query.filter((Match.player1_id == p1.id) | (Match.player2_id == p1.id)).count()
            p2_matches = Match.query.filter((Match.player1_id == p2.id) | (Match.player2_id == p2.id)).count()
            next_round_num = max(p1_matches, p2_matches) + 1
            
            label = f"Round {next_round_num}"
            if total_active_overall <= 8 and total_active_overall > 4: label = "Quarter-Finals"
            elif total_active_overall <= 4 and total_active_overall > 2: label = "Semi-Finals"
            elif total_active_overall == 2: label = "Final"

            m = Match(
                round_number = next_round_num,
                round_label  = label,
                player1_id   = p1.id,
                player2_id   = p2.id,
                status       = "pending",
            )
            new_matches.append(m)

        # Handle odd player — give last player a bye ONLY if there are no active matches left
        if len(available_players) % 2 != 0:
            if len(active_matches) == 0:
                bye_player = available_players[-1]
                bp_matches = Match.query.filter((Match.player1_id == bye_player.id) | (Match.player2_id == bye_player.id)).count()
                next_round_num = bp_matches + 1
                
                label = f"Round {next_round_num}"
                if total_active_overall <= 8 and total_active_overall > 4: label = "Quarter-Finals"
                elif total_active_overall <= 4 and total_active_overall > 2: label = "Semi-Finals"
                
                bye_match  = Match(
                    round_number = next_round_num,
                    round_label  = label + " (BYE)",
                    player1_id   = bye_player.id,
                    player2_id   = None,
                    winner_id    = bye_player.id,
                    status       = "bye",
                    notes        = "Bye — auto-advanced.",
                )
                new_matches.append(bye_match)

        for m in new_matches:
            db.session.add(m)

        db.session.commit()
        flash(f"🏆 {len(new_matches)} new match(es) created!", "success")
        return redirect(url_for("admin_matches"))

    # -------------------------------------------------------------------------

    @app.route("/admin/matches/<int:match_id>/start", methods=["POST"])
    @admin_required
    def admin_start_match(match_id):
        """Marks a match as 'in_progress' (live on the site)."""
        match = Match.query.get_or_404(match_id)
        if match.status != "pending":
            flash("Match cannot be started — it's not in pending state.", "warning")
            return redirect(url_for("admin_matches"))
        match.status = "in_progress"
        db.session.commit()
        flash(f"♟️ Match #{match_id} marked as IN PROGRESS.", "info")
        return redirect(url_for("admin_matches"))

    # -------------------------------------------------------------------------

    @app.route("/admin/matches/<int:match_id>/result", methods=["POST"])
    @admin_required
    def admin_set_result(match_id):
        """
        Records the result of a match.

        Form data:
          winner  → "player1" or "player2"
          notes   → optional text (e.g. "Player 2 forfeited")
        """
        match = Match.query.get_or_404(match_id)

        if match.status == "completed":
            flash("This match has already been completed.", "warning")
            return redirect(url_for("admin_matches"))

        winner_choice = request.form.get("winner")  # "player1" or "player2"
        notes         = request.form.get("notes", "").strip()

        if winner_choice == "player1":
            winner_id = match.player1_id
            loser_id  = match.player2_id
        elif winner_choice == "player2":
            winner_id = match.player2_id
            loser_id  = match.player1_id
        else:
            flash("Invalid result. Please select a winner.", "danger")
            return redirect(url_for("admin_matches"))

        # Update match record
        match.winner_id    = winner_id
        match.status       = "completed"
        match.completed_at = datetime.utcnow()
        match.notes        = notes if notes else None

        # Mark the loser as eliminated
        if loser_id:
            loser = Player.query.get(loser_id)
            if loser:
                loser.is_eliminated = True

        db.session.commit()

        winner = Player.query.get(winner_id)
        flash(
            f"✅ Result recorded. {winner.full_name} advances to the next round!",
            "success"
        )
        return redirect(url_for("admin_matches"))

    # -------------------------------------------------------------------------

    @app.route("/admin/export/players")
    @admin_required
    def admin_export_players():
        """
        Exports all player registrations as a downloadable CSV file.
        Useful for sharing data with tournament organisers or printing.
        """
        players = Player.query.order_by(Player.registered_at).all()

        # Build CSV in memory (no need to write a temp file)
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header row
        writer.writerow([
            "ID", "Full Name", "Roll Number", "Player Username",
            "WhatsApp", "Approved", "Eliminated", "Registered At"
        ])

        # Write one row per player
        for p in players:
            writer.writerow([
                p.id,
                p.full_name,
                p.roll_number,
                p.chess_username,
                p.whatsapp,
                "Yes" if p.is_approved   else "No",
                "Yes" if p.is_eliminated else "No",
                p.registered_at.strftime("%Y-%m-%d %H:%M"),
            ])

        # Create HTTP response with CSV content type
        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = (
            "attachment; filename=tournament_players.csv"
        )
        response.headers["Content-Type"] = "text/csv"
        return response

    # =========================================================================
    # SECTION D: CHESS GAME ROUTES
    # =========================================================================

    @app.route("/match/<int:match_id>/play")
    @student_required
    def play_match(match_id):
        """
        Renders the in-browser chess game for a specific match.
        Only the two players in the match may access this page.
        Auto-sets match status to 'in_progress' when first opened.
        """
        match = Match.query.get_or_404(match_id)
        player_id = session.get("student_id")

        # Only allow players IN this match to access it
        if player_id not in [match.player1_id, match.player2_id]:
            flash("You are not a player in this match.", "danger")
            return redirect(url_for("student_dashboard"))

        # Only allow pending or in_progress matches
        if match.status not in ("pending", "in_progress"):
            flash("This match is already completed.", "info")
            return redirect(url_for("student_dashboard"))

        # Auto-set to in_progress when first player opens the game
        if match.status == "pending":
            match.status = "in_progress"
            db.session.commit()

        player_white = Player.query.get(match.player1_id)
        player_black = Player.query.get(match.player2_id) if match.player2_id else None
        my_color = "white" if player_id == match.player1_id else "black"

        return render_template(
            "chess_game.html",
            match=match,
            player_white=player_white.chess_username if player_white else "White",
            player_black=player_black.chess_username if player_black else "Black",
            match_id=match_id,
            my_color=my_color,
        )

    @app.route("/match/<int:match_id>/submit", methods=["POST"])
    @student_required
    def submit_match_result(match_id):
        """
        Accepts JSON result from the chess game page and records the outcome.
        Returns JSON status. Idempotent — returns 'already_done' if called twice.
        """
        match = Match.query.get_or_404(match_id)

        if match.status == "completed":
            return jsonify({"status": "already_done"})

        data = request.get_json()
        winner_side = data.get("winner")    # 'white', 'black', or 'draw'
        method      = data.get("method")    # 'checkmate', 'resignation', 'stalemate'
        moves       = data.get("move_count", 0)

        if winner_side == "draw":
            match.status       = "completed"
            match.completed_at = datetime.utcnow()
            match.notes        = f"Draw by {method} after {moves} moves"
            db.session.commit()
            return jsonify({"status": "ok", "result": "draw"})

        if winner_side == "white":
            winner_id = match.player1_id
            loser_id  = match.player2_id
        else:
            winner_id = match.player2_id
            loser_id  = match.player1_id

        match.winner_id    = winner_id
        match.status       = "completed"
        match.completed_at = datetime.utcnow()
        match.notes        = f"Won by {method} in {moves} moves"

        # Update player stats
        winner = Player.query.get(winner_id)
        if winner:
            winner.wins  += 1
            winner.points += 1

        if loser_id:
            loser = Player.query.get(loser_id)
            if loser:
                loser.is_eliminated = True
                loser.losses += 1

        db.session.commit()
        return jsonify({"status": "ok", "winner": winner_side})

    # -------------------------------------------------------------------------

    @app.route("/match/<int:match_id>/move", methods=["POST"])
    @student_required
    def save_match_move(match_id):
        """Saves board state after each move — enables live spectating."""
        match = Match.query.get_or_404(match_id)
        data = request.get_json()
        match.board_state   = data.get("board_state")
        match.move_history  = data.get("move_history", "[]")
        match.last_move     = data.get("last_move")
        match.current_turn  = data.get("current_turn", "white")
        match.move_count    = data.get("move_count", 0)
        db.session.commit()
        return jsonify({"status": "ok"})

    # -------------------------------------------------------------------------

    @app.route("/match/<int:match_id>/state")
    def get_match_state(match_id):
        """Returns JSON board state for spectator polling."""
        match = Match.query.get_or_404(match_id)
        return jsonify({
            "board_state":  match.board_state,
            "move_history": match.move_history,
            "last_move":    match.last_move,
            "current_turn": match.current_turn,
            "move_count":   match.move_count,
            "status":       match.status,
            "player_white": match.player1.chess_username if match.player1 else "White",
            "player_black": match.player2.chess_username if match.player2 else "Black",
        })

    # =========================================================================
    # SECTION E: ADMIN SPECTATOR & ROUND CONTROL
    # =========================================================================

    @app.route("/admin/watch/<int:match_id>")
    @admin_required
    def admin_watch(match_id):
        """Admin live spectator view — read-only board that polls for updates."""
        match = Match.query.get_or_404(match_id)
        pw = Player.query.get(match.player1_id)
        pb = Player.query.get(match.player2_id) if match.player2_id else None
        return render_template('admin_watch.html', match=match,
            player_white=pw.chess_username if pw else 'White',
            player_black=pb.chess_username if pb else 'Black',
            match_id=match_id)

    @app.route("/admin/round/<int:round_num>/start-all", methods=["POST"])
    @admin_required
    def admin_start_all(round_num):
        """Bulk-flips all pending matches in a round to in_progress."""
        matches = Match.query.filter_by(round_number=round_num, status='pending').all()
        count = 0
        for m in matches:
            m.status = 'in_progress'
            count += 1
        db.session.commit()
        flash(f'♟ {count} match(es) in Round {round_num} started!', 'success')
        return redirect(url_for('admin_dashboard'))

    return app   # End of create_app()


# =============================================================================
# ENTRY POINT
# =============================================================================

# This is only used when you run `python app.py` directly.
# Prefer `flask run` for development (supports auto-reload and debug mode).
app = create_app()

if __name__ == "__main__":
    app.run(debug=DEBUG, host="0.0.0.0", port=5000)
