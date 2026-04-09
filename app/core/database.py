import hashlib
import logging
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
import threading

logger = logging.getLogger(__name__)

# Thread-local storage for database connections
_thread_locals = threading.local()

VEHICLE_RATES = {'Car': 50, 'Bike': 20, 'Truck': 80, 'SUV': 60, 'Van': 70}

# Peak hours: 8-10am, 5-8pm -> 1.5x multiplier
PEAK_HOURS = list(range(8, 10)) + list(range(17, 20))
PEAK_MULTIPLIER = 1.5

# Loyalty tiers: (min_points, tier_name, discount_pct)
LOYALTY_TIERS = [
    (0,   'Bronze',   0),
    (100, 'Silver',   5),
    (300, 'Gold',    10),
    (600, 'Platinum', 15),
    (1000, 'Diamond', 20),
]

def _get_db_path() -> str:
    return os.path.normpath(
        os.environ.get(
            'DB_PATH',
            os.path.join(os.path.dirname(__file__), '..', '..', 'database', 'parking.db')
        )
    )


@contextmanager
def get_db_connection():
    """Context manager for database connections with proper error handling"""
    conn = None
    try:
        conn = sqlite3.connect(_get_db_path(), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA journal_mode = WAL')
        yield conn
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()


def get_db_connection_legacy():
    """Legacy function for backward compatibility"""
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str) -> str:
    """Hash password with salt for better security"""
    import secrets
    salt = secrets.token_hex(16)
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex() + ':' + salt


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    try:
        if ':' in hashed:
            # New format with salt
            hash_part, salt = hashed.split(':', 1)
            return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex() == hash_part
        else:
            # Legacy format (backward compatibility)
            return hashlib.sha256(password.encode()).hexdigest() == hashed
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def sanitize_username(username: str) -> str:
    """Sanitize username with better validation"""
    if not username or len(username) < 3:
        raise ValueError("Username must be at least 3 characters long")
    
    # Allow alphanumeric, underscore, hyphen, and dot
    sanitized = re.sub(r'[^\w\-\.]', '', username)[:50]
    
    if len(sanitized) < 3:
        raise ValueError("Username contains invalid characters")
    
    return sanitized.lower()


def sanitize_plate(plate: str) -> str:
    """Enhanced plate number sanitization"""
    if not plate:
        return ''
    
    # Remove spaces and special characters, keep only alphanumeric
    sanitized = re.sub(r'[^A-Z0-9]', '', plate.upper())[:20]
    
    # Basic Indian license plate validation
    if sanitized and len(sanitized) < 4:
        logger.warning(f"Potentially invalid plate number: {sanitized}")
    
    return sanitized


def validate_email(email: str) -> bool:
    """Validate email format"""
    if not email:
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email)) and len(email) <= 254


def get_peak_multiplier() -> float:
    hour = datetime.now().hour
    return PEAK_MULTIPLIER if hour in PEAK_HOURS else 1.0


def get_loyalty_tier(points: int) -> dict:
    tier = LOYALTY_TIERS[0]
    for min_pts, name, disc in LOYALTY_TIERS:
        if points >= min_pts:
            tier = (min_pts, name, disc)
    return {'name': tier[1], 'discount': tier[2], 'points': points}


def init_db() -> None:
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY,
                  username TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL,
                  role TEXT DEFAULT 'user',
                  email TEXT DEFAULT '',
                  phone TEXT DEFAULT '',
                  google_id TEXT DEFAULT NULL,
                  favourite_slot TEXT DEFAULT '',
                  loyalty_points INTEGER DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    c.execute('''CREATE TABLE IF NOT EXISTS bookings
                 (id INTEGER PRIMARY KEY, username TEXT, slot TEXT, vehicle TEXT,
                  duration_hours INTEGER DEFAULT 1,
                  amount_paid REAL DEFAULT 0,
                  status TEXT DEFAULT 'active',
                  vehicle_plate TEXT DEFAULT '',
                  peak_booking INTEGER DEFAULT 0,
                  loyalty_discount REAL DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    c.execute('''CREATE TABLE IF NOT EXISTS notifications
                 (id INTEGER PRIMARY KEY,
                  username TEXT NOT NULL,
                  message TEXT NOT NULL,
                  is_read INTEGER DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    c.execute('''CREATE TABLE IF NOT EXISTS waitlist
                 (id INTEGER PRIMARY KEY,
                  username TEXT NOT NULL,
                  slot TEXT NOT NULL,
                  vehicle TEXT NOT NULL,
                  duration_hours INTEGER DEFAULT 1,
                  vehicle_plate TEXT DEFAULT '',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    c.execute('''CREATE TABLE IF NOT EXISTS reviews
                 (id INTEGER PRIMARY KEY,
                  username TEXT NOT NULL,
                  slot TEXT NOT NULL,
                  rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                  comment TEXT DEFAULT '',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    _BOOKING_COLS = [
        ('duration_hours', 'INTEGER DEFAULT 1'),
        ('amount_paid', 'REAL DEFAULT 0'),
        ('status', "TEXT DEFAULT 'active'"),
        ('vehicle_plate', "TEXT DEFAULT ''"),
        ('peak_booking', 'INTEGER DEFAULT 0'),
        ('loyalty_discount', 'REAL DEFAULT 0'),
        ('start_time', 'TEXT DEFAULT NULL'),
        ('payment_method', "TEXT DEFAULT 'Cash'"),
    ]
    _USER_COLS = [
        ('email', "TEXT DEFAULT ''"),
        ('phone', "TEXT DEFAULT ''"),
        ('google_id', 'TEXT DEFAULT NULL'),
        ('favourite_slot', "TEXT DEFAULT ''"),
        ('loyalty_points', 'INTEGER DEFAULT 0'),
    ]
    for col, defval in _BOOKING_COLS:
        try:
            c.execute("ALTER TABLE bookings ADD COLUMN {} {}".format(col, defval))
        except sqlite3.OperationalError:
            pass
    for col, defval in _USER_COLS:
        try:
            c.execute("ALTER TABLE users ADD COLUMN {} {}".format(col, defval))
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()
    create_default_admin()


def create_default_admin() -> None:
    conn = get_db_connection_legacy()
    try:
        if not conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone():
            conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ('admin', hash_password('admin123'), 'admin')
            )
            conn.commit()
            logger.info("Default admin created (username: admin)")
    except Exception as e:
        logger.error(f"Error creating default admin: {e}")
    finally:
        conn.close()


def add_notification(username: str, message: str) -> None:
    """Add notification with input validation"""
    if not username or not message:
        logger.warning("Invalid notification parameters")
        return
    
    # Sanitize inputs
    username = username.strip()[:50]
    message = message.strip()[:500]
    
    conn = get_db_connection_legacy()
    try:
        conn.execute(
            "INSERT INTO notifications (username, message) VALUES (?, ?)",
            (username, message)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to add notification: {e}")
    finally:
        conn.close()


def expire_old_bookings() -> int:
    """Expire old bookings with better error handling"""
    conn = get_db_connection_legacy()
    expired_count = 0
    
    try:
        rows = conn.execute(
            "SELECT id, username, slot, duration_hours, created_at FROM bookings WHERE status = 'active'"
        ).fetchall()
        
        expired = []
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        for r in rows:
            try:
                created = datetime.strptime(str(r['created_at'])[:19], '%Y-%m-%d %H:%M:%S')
                duration_hours = max(1, r['duration_hours'] or 1)  # Ensure minimum 1 hour
                
                if now >= created + timedelta(hours=duration_hours):
                    expired.append((r['id'], r['username'], r['slot']))
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse created_at for booking id={r['id']}: {e}")

        for bid, uname, slot in expired:
            try:
                # Update booking status
                conn.execute("UPDATE bookings SET status = 'completed' WHERE id = ?", (bid,))
                
                # Add notification
                conn.execute(
                    "INSERT INTO notifications (username, message) VALUES (?, ?)",
                    (uname, f"⏰ Booking #{bid} for slot {slot} has expired and been auto-completed.")
                )
                
                # Check waitlist
                waiter = conn.execute(
                    "SELECT id, username, vehicle, duration_hours, vehicle_plate "
                    "FROM waitlist WHERE slot = ? ORDER BY created_at LIMIT 1",
                    (slot,)
                ).fetchone()
                
                if waiter:
                    # Remove from waitlist
                    conn.execute("DELETE FROM waitlist WHERE id = ?", (waiter['id'],))
                    
                    # Calculate amount
                    vehicle_rate = VEHICLE_RATES.get(waiter['vehicle'], 50)
                    duration = max(1, waiter['duration_hours'] or 1)
                    amount = vehicle_rate * duration
                    
                    # Create new booking
                    conn.execute(
                        "INSERT INTO bookings (username, slot, vehicle, duration_hours, amount_paid, status, vehicle_plate) "
                        "VALUES (?, ?, ?, ?, ?, 'active', ?)",
                        (waiter['username'], slot, waiter['vehicle'], duration, amount, waiter['vehicle_plate'] or '')
                    )
                    
                    # Notify waitlist user
                    conn.execute(
                        "INSERT INTO notifications (username, message) VALUES (?, ?)",
                        (waiter['username'], f"🎉 Slot {slot} is now available! Your waitlist booking has been confirmed.")
                    )
                
                expired_count += 1
                
            except Exception as e:
                logger.error(f"Error processing expired booking {bid}: {e}")
                continue
        
        conn.commit()
        
        if expired_count > 0:
            logger.info(f"Expired {expired_count} booking(s)")
            
    except Exception as e:
        logger.error(f"Error in expire_old_bookings: {e}")
        conn.rollback()
    finally:
        conn.close()
    
    return expired_count
