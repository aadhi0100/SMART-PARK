# 🚀 SmartPark - Advanced Parking Management System

## ⚡ NEW: Advanced Features Added!

### 📧 Professional Email System
- **Beautiful Invoice Emails**: Professional, responsive email templates with QR codes
- **Automatic Notifications**: Booking confirmations, reminders, and monthly summaries  
- **Easy Email Management**: Built-in email testing and management interface
- **Multiple Email Types**: Welcome, confirmation, invoice, reminder, and promotional emails

### 🔒 Enhanced Security
- **Secure Password Hashing**: PBKDF2 with salt for maximum security
- **Input Validation**: Comprehensive sanitization and validation
- **SQL Injection Protection**: Parameterized queries throughout
- **Thread-Safe Database**: Proper connection management

### 🎯 Advanced Booking Features
- **Smart Pricing**: Peak hour pricing and 5-tier loyalty system (Bronze to Diamond)
- **Enhanced Vehicle Support**: Car, Bike, Truck, SUV, Van
- **Professional Invoices**: Detailed invoices with QR codes
- **Waitlist System**: Automatic slot assignment

---

## 🚀 Quick Start (Enhanced Version)

### 1. Easy Setup
```bash
# Run the enhanced startup script
start_enhanced.bat
```

### 2. Configure Email (Recommended)
1. Edit `.env` file with your email settings (see EMAIL_SETUP_GUIDE.md)
2. Go to: `http://localhost:5003/booking/email_manager/admin`
3. Click "Send Test Email" to verify setup

### 3. Access the System
- **Main System**: `http://localhost:5003`
- **Admin Panel**: `http://localhost:5003/admin/dashboard/admin`
- **Email Manager**: `http://localhost:5003/booking/email_manager/admin`

## 📚 Documentation

- **[Advanced Features Guide](ADVANCED_FEATURES.md)** - Complete feature overview
- **[Email Setup Guide](EMAIL_SETUP_GUIDE.md)** - Email configuration help
- **[URL Routes Mapping](URL_ROUTES_MAPPING.md)** - All available routes

---

## ✨ Features

### 🔐 Authentication & User Management
- User registration and secure login
- **Google OAuth 2.0** sign-in (via Authlib)
- Role-based access control (User/Admin)
- Profile management with email and phone
- Admin user role management

### 🅿️ Parking Management
- **50 Individual Slots** across 5 Chennai locations
- Real-time availability tracking
- Interactive booking system with availability display
- Slot release functionality for users and admins

### 🗺️ Interactive Map
- Live parking area visualization using Leaflet maps
- Color-coded slot availability (Green: Available, Red: Booked)
- Real Chennai GPS coordinates
- Click-to-book functionality

### 🎫 Ticket System
- PDF ticket generation with QR codes
- HTML fallback for ticket downloads
- Booking history and management
- **Dynamic pricing**: Car ₹50/hr, Bike ₹20/hr, Truck ₹80/hr
- Vehicle plate number tracking

### 👨💼 Admin Features
- **User Management**: Promote/demote user roles
- **System Reports**: Booking analytics and statistics
- **CCTV Monitoring**: Live feed simulation
- **Slot Management**: Release any booked slot

### 📧 Email Notifications
- Welcome email on new account creation (including Google sign-in)
- Booking invoice email with full booking details and amount paid
- Configurable via SMTP environment variables (Gmail supported)

### 🔔 In-App Notifications
- Per-user notification system stored in the database
- Triggered on account creation and key booking events

## 🏗️ Architecture

### Modular Flask Structure
```
app/
├── auth/          # Authentication (login, register)
├── booking/       # Booking management & slot operations
├── admin/         # Admin functionality & user management
├── map/           # Interactive parking map
├── core/          # Database, utilities, dashboard
└── templates/     # Feature-organized templates
```

### Technology Stack
- **Backend**: Flask with Blueprint architecture
- **Database**: SQLite with automatic initialization and migrations
- **Frontend**: HTML5, CSS3, JavaScript
- **Maps**: Leaflet.js with OpenStreetMap
- **PDF Generation**: ReportLab
- **OAuth**: Authlib (Google OAuth 2.0)
- **Email**: smtplib with Gmail SMTP
- **Config**: python-dotenv for environment variables

## 🚀 Quick Start

### Prerequisites
- Python 3.7+
- pip package manager

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd parking_system_final
   ```

2. **Install dependencies** (auto-installed on first run)
   ```bash
   pip install flask reportlab authlib requests python-dotenv
   ```

3. **Run the application**
   ```bash
   python run.py
   ```

4. **Configure environment** (optional — create a `.env` file)
   ```env
   GOOGLE_CLIENT_ID=<your-google-client-id>
   GOOGLE_CLIENT_SECRET=<your-google-client-secret>
   SMTP_USER=<your-gmail-address>
   SMTP_PASS=<your-gmail-app-password>
   SECRET_KEY=<your-secret-key>
   ```

5. **Access the system**
   - URL: http://127.0.0.1:5003
   - Admin: `admin` / `admin123`
   - Or register a new account / sign in with Google

## 🎯 Usage Guide

### For Users
1. **Register/Login** (or **Sign in with Google**) to access the system
2. **View Dashboard** with real-time slot availability and notifications
3. **Book Slots** from 50 available parking spaces with vehicle type and duration
4. **View Map** to see parking locations in Chennai
5. **Manage Bookings** and release slots when needed
6. **Download Tickets** as PDF with QR codes
7. **Receive emails** for welcome and booking invoices

### For Admins
1. **User Management**: Change user roles (User ↔ Admin)
2. **System Reports**: View booking analytics and statistics
3. **CCTV Monitoring**: Access security camera feeds
4. **Slot Management**: Release any user's booking
5. **Full System Control**: Manage all aspects of the parking system

## 🗺️ Parking Locations

| Location | Slots | Coordinates |
|----------|-------|-------------|
| Chennai Central | A1-A10 | 13.0827, 80.2707 |
| Marina Beach | B1-B10 | 13.0524, 80.2824 |
| T Nagar | C1-C10 | 13.0418, 80.2341 |
| Velachery | D1-D10 | 12.9756, 80.2207 |
| Adyar | E1-E10 | 13.0067, 80.2206 |

## 🔧 Configuration

### Environment Variables (`.env`)
| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Flask session secret key | Recommended |
| `GOOGLE_CLIENT_ID` | Google OAuth app client ID | For Google login |
| `GOOGLE_CLIENT_SECRET` | Google OAuth app client secret | For Google login |
| `SMTP_USER` | Gmail address for sending emails | For email features |
| `SMTP_PASS` | Gmail App Password | For email features |
| `SMTP_HOST` | SMTP server (default: `smtp.gmail.com`) | Optional |
| `SMTP_PORT` | SMTP port (default: `587`) | Optional |

### Database
- **Type**: SQLite (auto-created)
- **Location**: `database/parking.db`
- **Auto-initialization**: Creates tables, runs migrations, and creates admin user on first run

### Pricing
| Vehicle | Rate |
|---------|------|
| Car | ₹50/hour |
| Bike | ₹20/hour |
| Truck | ₹80/hour |

### Default Credentials
- **Admin Username**: `admin`
- **Admin Password**: `admin123`
- **Auto-created** on first application start

## 📁 Project Structure

```
parking_system_final/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── auth/                    # Authentication module
│   │   ├── routes.py           # Login, register routes
│   ├── booking/                 # Booking management
│   │   ├── routes.py           # Booking, tickets, slot management
│   │   └── utils.py            # PDF generation utilities
│   ├── admin/                   # Admin functionality
│   │   └── routes.py           # User management, reports, CCTV
│   ├── map/                     # Map visualization
│   │   └── routes.py           # Interactive parking map
│   ├── core/                    # Core functionality
│   │   ├── database.py         # Database operations
│   │   ├── utils.py            # Utility functions
│   │   └── routes.py           # Dashboard, profile
│   └── templates/               # Organized templates
│       ├── auth/               # Authentication pages
│       ├── booking/            # Booking pages
│       ├── admin/              # Admin pages
│       ├── map/                # Map page
│       ├── dashboard.html      # Main dashboard
│       └── profile.html        # User profile
├── static/
│   └── css/
│       └── style.css           # Application styles
├── database/                    # SQLite database (auto-created)
├── run.py                      # Application entry point
├── .env                        # Environment variables (not committed)
├── .gitignore                  # Git ignore rules
└── README.md                   # This file
```

## 🛠️ Development

### Adding New Features
1. Create new module in `app/` directory
2. Add routes using Flask Blueprints
3. Create templates in `app/templates/module_name/`
4. Register blueprint in `app/__init__.py`

### Database Operations
- **Connection**: Use `get_db_connection()` from `app.core.database`
- **Initialization**: Automatic on first run via `init_db()`
- **Location**: `database/parking.db`

## 🔒 Security Features

- **Password Hashing**: SHA-256 encryption
- **Google OAuth 2.0**: Secure third-party authentication via Authlib
- **Role-based Access**: Admin/User permissions
- **Session Management**: Secure user sessions
- **Input Validation**: Form data sanitization
- **Environment Secrets**: Credentials stored in `.env`, excluded from version control

## 🚀 Deployment

### Production Considerations
1. **Environment Variables**: Set `FLASK_ENV=production`
2. **Secret Key**: Use secure random secret key
3. **Database**: Consider PostgreSQL for production
4. **HTTPS**: Enable SSL/TLS encryption
5. **Reverse Proxy**: Use Nginx or Apache

### Docker Deployment
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5003
CMD ["python", "run.py"]
```

> **Note**: Pass environment variables via `--env-file .env` or Docker secrets in production.

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/new-feature`)
3. Commit changes (`git commit -am 'Add new feature'`)
4. Push to branch (`git push origin feature/new-feature`)
5. Create Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue in the repository
- Check existing documentation
- Review the modular code structure

---

**Built with ❤️ using Flask and modern web technologies**