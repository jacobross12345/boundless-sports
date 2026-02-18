from flask import Flask, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

# MLB
def search_mlb_player(name):
    url = "https://statsapi.mlb.com/api/v1/people/search"
    params = {"names": name, "sportId": 1}
    r = requests.get(url, params=params, timeout=10)
    people = r.json().get("people", [])
    if not people:
        return None
    player = people[0]
    pid = player["id"]

    stats_url = f"https://statsapi.mlb.com/api/v1/people/{pid}/stats"
    stats_params = {"stats": "career", "group": "hitting", "sportId": 1}
    sr = requests.get(stats_url, params=stats_params, timeout=10)
    stats_data = sr.json().get("stats", [])
    splits = stats_data[0].get("splits", []) if stats_data else []
    hitting = splits[0].get("stat", {}) if splits else {}

    stats_params["group"] = "pitching"
    sr2 = requests.get(stats_url, params=stats_params, timeout=10)
    stats_data2 = sr2.json().get("stats", [])
    splits2 = stats_data2[0].get("splits", []) if stats_data2 else []
    pitching = splits2[0].get("stat", {}) if splits2 else {}

    return {
        "name": player.get("fullName"),
        "sport": "MLB",
        "position": player.get("primaryPosition", {}).get("abbreviation", "N/A"),
        "stats": {
            "hitting": {
                "AVG": hitting.get("avg", "N/A"),
                "OPS": hitting.get("ops", "N/A"),
                "HR": hitting.get("homeRuns", "N/A"),
                "RBI": hitting.get("rbi", "N/A"),
                "AB": hitting.get("atBats", "N/A"),
            },
            "pitching": {
                "ERA": pitching.get("era", "N/A"),
                "WHIP": pitching.get("whip", "N/A"),
                "SO": pitching.get("strikeOuts", "N/A"),
                "W": pitching.get("wins", "N/A"),
            } if pitching else {}
        }
    }

# NBA
def search_nba_player(name):
    from nba_api.stats.static import players
    from nba_api.stats.endpoints import playercareerstats

    matches = players.find_players_by_full_name(name)
    if not matches:
        return None
    player = matches[0]
    pid = player["id"]

    career = playercareerstats.PlayerCareerStats(player_id=pid, timeout=10)
    df = career.get_data_frames()[0]
    if df.empty:
        return None

    totals = df[df["SEASON_ID"] == "Career"]
    if totals.empty:
        seasons = df[df["SEASON_ID"] != "Career"]
        sums = seasons.sum(numeric_only=True)
        sums["FG_PCT"] = seasons["FG_PCT"].mean()
        sums["FG3_PCT"] = seasons["FG3_PCT"].mean()
        totals = sums.to_frame().T

    row = totals.iloc[0]
    gp = row.get("GP", 1) or 1

    return {
        "name": player["full_name"],
        "sport": "NBA",
        "position": "N/A",
        "stats": {
            "PPG": round(row.get("PTS", 0) / gp, 1),
            "RPG": round(row.get("REB", 0) / gp, 1),
            "APG": round(row.get("AST", 0) / gp, 1),
            "FG%": round(row.get("FG_PCT", 0) * 100, 1),
            "3P%": round(row.get("FG3_PCT", 0) * 100, 1),
            "GP": int(gp),
        }
    }

# NFL
def search_nfl_player(name):
    search_url = "https://site.web.api.espn.com/apis/search/v2"
    params = {"query": name, "limit": 5, "type": "player"}
    r = requests.get(search_url, params=params, timeout=10)
    data = r.json()

    try:
        contents = data["results"][0]["contents"]
    except (KeyError, IndexError):
        return None

    if not contents:
        return None

    player = contents[0]
    uid = player.get("uid", "")
    pid = uid.split("~a:")[-1] if "~a:" in uid else None
    if not pid:
        return None

    detail_url = f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/athletes/{pid}"
    dr = requests.get(detail_url, timeout=10)
    d = dr.json()

    position = d.get("position", {}).get("abbreviation", "N/A")

    stats_url = f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/athletes/{pid}/statistics"
    sr = requests.get(stats_url, timeout=10)
    categories = sr.json().get("splits", {}).get("categories", [])

    stat_map = {}
    for cat in categories:
        for s in cat.get("stats", []):
            stat_map[s.get("shortDisplayName", s.get("name", ""))] = s.get("displayValue", "N/A")

    passing = {k: stat_map[k] for k in ["YDS", "Touchdowns", "INT", "RTG", "CMP%", "ATT"] if k in stat_map}
    rushing = {k: stat_map[k] for k in ["CAR", "Rushing Touchdowns", "YDS"] if k in stat_map}

    return {
        "name": player.get("displayName", name),
        "sport": "NFL",
        "position": position,
        "stats": passing or rushing or stat_map or {"note": "Stats unavailable"}
    }


# Press Command+S, go to Terminal, press Control+C, then run:
# python3 app.py
#
# Then test in your browser:
# http://127.0.0.1:5000/player/nfl/patrick%20mahomes
#
# Note: Save the file and restart the server with `python3 app.py`.
# Example request:
# http://127.0.0.1:5000/player/nfl/mahomes

# ROUTES
@app.route("/player/<sport>/<n>")
def get_player(sport, n):
    sport = sport.lower()
    try:
        if sport == "mlb":
            data = search_mlb_player(n)
        elif sport == "nba":
            data = search_nba_player(n)
        elif sport == "nfl":
            data = search_nfl_player(n)
        else:
            return jsonify({"error": "Sport must be mlb, nba, or nfl"}), 400

        if not data:
            return jsonify({"error": f"Player '{n}' not found"}), 404
        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health():
    return jsonify({"status": "ok", "message": "Rosetta Sports API is running"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)