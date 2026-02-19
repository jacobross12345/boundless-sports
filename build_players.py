import json
import time
from nba_api.stats.static import players as nba_players
from nba_api.stats.endpoints import playercareerstats

def build_nba():
    all_players = nba_players.get_active_players()
    result = {}
    for p in all_players:
        try:
            career = playercareerstats.PlayerCareerStats(player_id=p["id"], timeout=10)
            df = career.get_data_frames()[0]
            if df.empty:
                continue
            seasons = df[df["SEASON_ID"] != "Career"]
            if seasons.empty:
                continue
            sums = seasons.sum(numeric_only=True)
            gp = sums.get("GP", 1) or 1
            result[p["full_name"].lower()] = {
                "name": p["full_name"],
                "sport": "NBA",
                "position": "N/A",
                "stats": {
                    "PPG": round(sums.get("PTS", 0) / gp, 1),
                    "RPG": round(sums.get("REB", 0) / gp, 1),
                    "APG": round(sums.get("AST", 0) / gp, 1),
                    "FG%": round(seasons["FG_PCT"].mean() * 100, 1),
                    "3P%": round(seasons["FG3_PCT"].mean() * 100, 1),
                    "GP": int(gp),
                }
            }
            print(f"✓ {p['full_name']}")
            time.sleep(0.6)
        except Exception as e:
            print(f"✗ {p['full_name']}: {e}")
    return result

print("Building NBA players...")
data = build_nba()
with open("players_cache.json", "w") as f:
    json.dump(data, f)
print(f"\nDone! {len(data)} players saved to players_cache.json")