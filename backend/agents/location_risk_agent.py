# backend/agents/location_risk_agent.py
import time, requests
from datetime import datetime

# Tunable thresholds
VOICE_THR = 0.60     # if voice_prob >= this, count as distress
STAT_THR  = 180      # seconds stationary to consider "stuck"
POI_THR   = 3        # <= this many POIs in radius -> considered isolated
POI_RADIUS_M = 200   # check POIs in this radius (meters)

# Overpass query helper (returns count of nearby amenity nodes)
def poi_density(lat, lon, radius_m=POI_RADIUS_M, timeout=5):
    q = f"""
    [out:json][timeout:{timeout}];
    node(around:{radius_m},{lat},{lon})[amenity];
    out count;
    """
    url = "https://overpass-api.de/api/interpreter"
    try:
        r = requests.post(url, data=q, timeout=timeout)
        j = r.json()
        # Overpass returns {'elements': [{'type':'count','tags':{'total':'N'}}]} for out count
        # fallback to len(elements) if count not provided
        if isinstance(j, dict) and j.get("elements"):
            # try tags total
            el0 = j["elements"][0]
            if "tags" in el0 and "total" in el0["tags"]:
                try:
                    return int(el0["tags"]["total"])
                except:
                    pass
            # fallback
            return len(j.get("elements", []))
        return 0
    except Exception:
        return 0  # conservative fallback

def is_night(ts=None, tz_offset_hours=5.5):
    if ts is None:
        ts = int(time.time())
    # approximate local hour using tz offset; good for demo (India +5.5)
    utc_hour = datetime.utcfromtimestamp(ts).hour
    local_hour = (utc_hour + int(tz_offset_hours)) % 24
    # night = before 6am or after 8pm
    return (local_hour < 6) or (local_hour >= 20)

def evaluate(user, lat, lon, stationary_seconds=0, ts=None, voice_prob=None):
    """
    Returns a dict: { action: "NONE"|"NOTIFY"|"AUTO_SOS", reason: str, evidence: str }
    Logic:
      - If voice_prob >= VOICE_THR -> AUTO_SOS immediately (evidence includes voice_prob)
      - Else if stationary_seconds >= STAT_THR AND is_night AND poi_density <= POI_THR -> AUTO_SOS
      - Else if any weak signal present -> NOTIFY
      - Else NONE
    """
    reasons = []
    # voice check
    if voice_prob is not None:
        reasons.append(f"voice_prob={voice_prob:.2f}")
        if voice_prob >= VOICE_THR:
            return {"action": "AUTO_SOS", "reason": "voice_distress", "evidence": ";".join(reasons)}

    # stationary + night + isolation check
    if stationary_seconds >= STAT_THR:
        reasons.append(f"stationary={stationary_seconds}s")
        night = is_night(ts)
        reasons.append(f"night={night}")
        pd = poi_density(lat, lon)
        reasons.append(f"poi_count={pd}")
        if night and pd <= POI_THR:
            return {"action": "AUTO_SOS", "reason": "stationary_night_low_poi", "evidence": ";".join(reasons)}
        # if stationary but not full conditions -> notify
        return {"action": "NOTIFY", "reason": "stationary", "evidence": ";".join(reasons)}

    # if there is a voice_prob but below threshold: notify
    if voice_prob is not None and voice_prob > 0.2:
        return {"action": "NOTIFY", "reason": "possible_voice", "evidence": ";".join(reasons)}

    return {"action": "NONE", "reason": "ok", "evidence": ""}
