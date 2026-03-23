# ♛ College Chess Championship Platform

An end-to-end, fully automated chess tournament management and playing platform. Built with Python, Flask, and vanilla JS, this platform allows students to register, get paired, and play live chess matches **directly on the site**, while admins spectate and manage the bracket.

---

## ✨ Key Features
- **Built-in Live Games:** Players play their matches directly on the platform with real-time board synchronization, piece-movement rules, castling, en passant, and automatic legal move validation.
- **Auto-Matchmaking:** The system automatically pairs available winners into the next round asynchronousy. Admins no longer have to wait for an entire round to finish!
- **Spectator Mode:** Admins can watch any live game in real-time using the **Live Spectate** feature.
- **Auto-Result Tracking:** Checkmates, stalemates, and resignations are automatically detected. The server instantly eliminates the loser and advances the winner.
- **Zero-Config Deployment:** Easily deploy to Render's Free tier with a single click using the included `render.yaml` Blueprint. The PostgreSQL database is automatically provisioned and built.

---

## 🚀 Easy Deployment (Render)

This application is fully automated to deploy on Render (100% Free plan, no credit card required).

1. Upload or fork this repository to your GitHub account.
2. Go to your [Render Dashboard](https://dashboard.render.com).
3. Click **New +** -> **Blueprint**.
4. Connect the repository you just uploaded.
5. Render will automatically provision a Free PostgreSQL database, install requirements, and deploy the Web Service.
6. The database tables and default admin account are **automatically created** on the first boot!

---

## 👑 Managing the Tournament

Here is the quick guide to running your tournament:

1. **Admin Login:** Go to `/admin/login`. 
   - **Default Username:** `admin` 
   - **Default Password:** `admin123` 
   - *(Note: Please change your password on the admin dashboard if you deploy this publicly!)*
2. **Registration:** Share your home page URL with students. Once they register, review and approve them in the **Admin → Players** tab.
3. **Generate Matches:** Go to **Admin → Matches** and click **Generate Matches**. Start the live matches! You can pair any available players as soon as they finish their previous round.
4. **Spectate:** Click the **"Live"** button on any in-progress match to watch the students play in real-time.

---

## 💻 Local Development

If you'd like to run or test the platform locally on your own PC:

1. Open your terminal in the project folder.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the Flask server:
   ```bash
   python app.py
   ```
4. Open your browser and go to: `http://127.0.0.1:5000`

---

## ⚙️ Customization

You can quickly edit `config.py` to change the main tournament rules, college name, and formatting before deploying or starting matches.

| Name | File | 
|---|---|
| Tournament Name & Format | `config.py` |
| Close Registrations | `config.py` → `REGISTRATION_OPEN = False` |
| Color Scheme / Aesthetics | `static/css/style.css` (See CSS Variables at the top) |
