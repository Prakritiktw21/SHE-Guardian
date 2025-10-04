# helpers.py: utility functions shared by agents
from math import radians, sin, cos, asin, sqrt

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2-lat1)
    dl = radians(lon2-lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dl/2)**2
    return 2*R*asin(sqrt(a))
