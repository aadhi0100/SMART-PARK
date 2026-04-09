# URL Routes Mapping - Smart Parking System

## Current Blueprint Structure

### Core Routes (core_bp - no prefix)
- `/` → `core.index` → Redirects to auth.login
- `/dashboard/<username>` → `core.dashboard` → Main dashboard
- `/profile/<username>` → `core.profile` → User profile
- `/logout` → `core.logout` → Logout redirect

### Auth Routes (auth_bp - /auth prefix)
- `/auth/login` → `auth.login` → Login page
- `/auth/register` → `auth.register` → Registration page

### Booking Routes (booking_bp - /booking prefix)
- `/booking/book/<username>` → `booking.book` → Book parking slot
- `/booking/bookings/<username>` → `booking.view_bookings` → View user bookings
- `/booking/ticket/<username>/<int:booking_id>` → `booking.ticket` → Booking confirmation ticket
- `/booking/download_ticket/<username>/<int:booking_id>` → `booking.download_ticket` → Download PDF ticket
- `/booking/slots/<username>` → `booking.slot_management` → Slot management page
- `/booking/release_slot/<username>` → `booking.release_slot` → Release slot (POST)

### Admin Routes (admin_bp - /admin prefix)
- `/admin/cctv/<username>` → `admin.admin_cctv` → CCTV monitoring
- `/admin/users/<username>` → `admin.admin_users` → User management
- `/admin/reports/<username>` → `admin.admin_reports` → System reports
- `/admin/change_role/<username>` → `admin.admin_change_role` → Change user role (POST)

### Map Routes (map_bp - /map prefix)
- `/map/<username>` → `map.parking_map` → Interactive parking map

## Template URL References

### All templates should use these blueprint references:

#### Navigation (in all templates):
```html
<a href="{{ url_for('core.dashboard', username=username) }}">Dashboard</a>
<a href="{{ url_for('core.profile', username=username) }}">Profile</a>
<a href="{{ url_for('core.logout') }}">Logout</a>
```

#### Authentication:
```html
<a href="{{ url_for('auth.login') }}">Login</a>
<a href="{{ url_for('auth.register') }}">Register</a>
```

#### Booking:
```html
<a href="{{ url_for('booking.book', username=username) }}">Book Parking</a>
<a href="{{ url_for('booking.view_bookings', username=username) }}">My Bookings</a>
<a href="{{ url_for('booking.slot_management', username=username) }}">Manage Slots</a>
<a href="{{ url_for('booking.ticket', username=username, booking_id=booking_id) }}">View Ticket</a>
<a href="{{ url_for('booking.download_ticket', username=username, booking_id=booking_id) }}">Download PDF</a>
```

#### Admin:
```html
<a href="{{ url_for('admin.admin_cctv', username=username) }}">CCTV</a>
<a href="{{ url_for('admin.admin_users', username=username) }}">Manage Users</a>
<a href="{{ url_for('admin.admin_reports', username=username) }}">Reports</a>
```

#### Map:
```html
<a href="{{ url_for('map.parking_map', username=username) }}">View Map</a>
```

## AJAX Endpoints

### JavaScript fetch URLs:
```javascript
// Slot release
fetch(`/booking/release_slot/${username}`, { method: 'POST' })

// Role change (admin)
fetch(`/admin/change_role/${username}`, { method: 'POST' })
```

## Issues to Fix

### 1. Remove old app.py
The old `app.py` file should be removed as it conflicts with the new modular structure.

### 2. Template Path Updates
All templates moved to `app/templates/` with feature-based organization:
- `app/templates/auth/` - login.html, register.html
- `app/templates/booking/` - booking.html, ticket.html, view_bookings.html, slot_management.html
- `app/templates/admin/` - admin_*.html files
- `app/templates/map/` - map.html
- `app/templates/` - dashboard.html, profile.html

### 3. Static Files
Static files remain at `static/css/style.css` (Flask auto-detects)

## Verification Checklist

- [ ] Remove old app.py file
- [ ] All templates use correct blueprint URL references
- [ ] All AJAX calls use correct endpoints
- [ ] Flask app factory properly registers all blueprints
- [ ] Templates are in correct directories under app/templates/