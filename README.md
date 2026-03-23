# ♟ College Chess Tournament — Setup Guide

## Folder Structure
```
chess_tournament/
├── app.py                          # All Flask routes (public, student, admin)
├── models.py                       # Database models: Player, Match, Admin
├── config.py                       # ← EDIT THIS for your tournament settings
├── requirements.txt                # Python dependencies
│
├── static/
│   └── css/
│       └── style.css               # Chess-themed dark UI styles
│
└── templates/
    ├── base.html                   # Master layout (navbar, footer, flash msgs)
    ├── index.html                  # Homepage with rules & stats
    ├── register.html               # Student registration form
    ├── bracket.html                # Challonge bracket embed
    ├── student_login.html          # Player login (Roll No + Chess.com username)
    ├── student_dashboard.html      # Player's personal match portal
    ├── admin_login.html            # Admin login
    ├── admin_dashboard.html        # Overview stats + quick actions
    ├── admin_players.html          # Approve / reject registrations
    └── admin_matches.html          # Generate rounds + set results
```

---

## One-Time Setup (Run These Once)

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. Customise the tournament (IMPORTANT — do this before anything else)
Edit `config.py` and fill in your details:
- `TOURNAMENT_NAME`   — e.g. "CSE Department Chess Championship"
- `COLLEGE_NAME`      — your college name
- `CHALLONGE_EMBED_URL` — paste your Challonge iframe src URL here
- `ORGANIZER_WHATSAPP` — your WhatsApp number for the group

### 3. Create the database
```bash
flask init-db
```
This creates `tournament.db` (the SQLite file) with all three tables.

### 4. Create the first admin account
```bash
flask create-admin
```
You'll be prompted for a username and password. Store them safely!

### 5. Start the development server
```bash
flask run
```
Open `http://127.0.0.1:5000` in your browser.

---

## Running the Tournament — Step by Step

### Phase 1: Registration
1. Share the site URL with students. They register at `/register`.
2. Go to **Admin → Players** and approve valid registrations.
3. Use **Approve All** to bulk-approve if you trust all entries.

### Phase 2: Start the Bracket
1. Create your bracket on [challonge.com](https://challonge.com) and add your players.
2. Paste the embed URL into `config.py` → `CHALLONGE_EMBED_URL`.
3. Set `REGISTRATION_OPEN = False` in `config.py` to close registrations.

### Phase 3: Run Rounds
In **Admin → Matches**:
1. Click **"Generate Round 1"** — this randomly pairs all approved players.
2. Announce pairings to players via the WhatsApp group.
3. When a match starts on Chess.com, click **"Mark as LIVE"**.
4. After the game, click **"[Winner Name] Wins"** to record the result.
   - The loser is automatically marked as eliminated.
5. Once ALL matches in a round are done, click **"Generate Round 2"**.
6. Repeat until 1 player remains.

### Phase 4: Student Experience
Students go to **Player Login** and enter their Roll Number + Chess.com Username.
Their dashboard shows:
- ✅ Approval status
- ♟ Current match with opponent's Chess.com username
- 🔗 Direct link to opponent's Chess.com profile
- 📋 Full match history

---

## Exporting Data
Go to **Admin → Dashboard → Export Players** or hit `/admin/export/players`.
Downloads a CSV with all player info — useful for sharing with faculty.

---

## Environment Variables (Production)
For deployment, set these instead of editing `config.py`:
```bash
export SECRET_KEY="your-long-random-secret-key-here"
```
Generate a secure key: `python -c "import secrets; print(secrets.token_hex(32))"`

---

## Common Customisations

| What to change | Where |
|---|---|
| Tournament name, time control, rules | `config.py` |
| Challonge bracket URL | `config.py` → `CHALLONGE_EMBED_URL` |
| Close registrations | `config.py` → `REGISTRATION_OPEN = False` |
| Change admin password | Re-run `flask create-admin` |
| Max player count | `config.py` → `MAX_PLAYERS` |
| Colour scheme / fonts | `static/css/style.css` → CSS variables at top |
