# personal_agent.py: monitors GPS points and detects anomalies
def detect_anomaly(recent_points, stop_threshold_sec=180, radius_m=15):
    """
    recent_points: list of dicts [{'ts':int,'lat':float,'lon':float}, ...] sorted asc by ts
    returns (flag:bool, reason:str)
    """
    if len(recent_points) < 2:
        return False, None
    # naive: if last ~10 points within radius and time span > threshold -> stopped_long
    from . import notifier_agent  # optional use
    from ..utils.helpers import haversine
    pts = recent_points[-10:]
    lat0, lon0 = pts[-1]['lat'], pts[-1]['lon']
    span = pts[-1]['ts'] - pts[0]['ts']
    within = all(haversine(lat0, lon0, p['lat'], p['lon']) < radius_m for p in pts)
    if within and span > stop_threshold_sec:
        return True, "stopped_long"
    return False, None
