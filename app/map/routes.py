from flask import Blueprint, render_template, session, redirect, url_for
from ..core.database import get_db_connection_legacy as get_db_connection
from ..core.routes import LOCATIONS, LOCATION_PREFIXES, TOTAL_SLOTS_PER_LOC

map_bp = Blueprint('map', __name__)

LOCATION_COORDS = {
    'Chennai Central':  (13.0827, 80.2707),
    'Marina Beach':     (13.0524, 80.2824),
    'T Nagar':          (13.0418, 80.2341),
    'Velachery':        (12.9756, 80.2207),
    'Adyar':            (13.0067, 80.2206),
    'Tambaram':         (12.9249, 80.1000),
    'Chromepet':        (12.9516, 80.1462),
    'Guindy':           (13.0100, 80.2100),

    'Porur':            (13.0358, 80.1567),
    'Ambattur':         (13.1143, 80.1548),
    'Anna Nagar':       (13.0850, 80.2101),
    'Kodambakkam':      (13.0524, 80.2200),
    'Perambur':         (13.1167, 80.2333),
    'Sholinganallur':   (12.9010, 80.2279),
    'Mylapore':         (13.0368, 80.2676),
    'Nungambakkam':     (13.0569, 80.2425),
    'Egmore':           (13.0732, 80.2609),
    'Royapuram':        (13.1167, 80.2833),
    'Tondiarpet':       (13.1200, 80.2900),
    'Manali':           (13.1667, 80.2500),
}

@map_bp.route('/<username>')
def parking_map(username):
    if session.get('username') != username:
        return redirect(url_for('auth.login'))
    conn = get_db_connection()
    try:
        booked_slots = [
            row[0] for row in conn.execute(
                "SELECT slot FROM bookings WHERE status = 'active'"
            ).fetchall()
        ]
    finally:
        conn.close()

    parking_areas = []
    for loc in LOCATIONS:
        prefix = LOCATION_PREFIXES[loc]
        lat, lng = LOCATION_COORDS[loc]
        booked_here = len([s for s in booked_slots if s.startswith(loc)])
        parking_areas.append({
            'name': loc,
            'lat': lat, 'lng': lng,
            'slots': [f'{loc} {prefix}{i}' for i in range(1, TOTAL_SLOTS_PER_LOC + 1)],
            'available': TOTAL_SLOTS_PER_LOC - booked_here,
            'total': TOTAL_SLOTS_PER_LOC,
        })

    return render_template('map/map.html', username=username,
                           parking_areas=parking_areas, booked_slots=booked_slots)
