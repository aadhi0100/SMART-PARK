import logging
from flask import Blueprint, request, render_template, redirect, url_for, session, jsonify
from ..core.database import get_db_connection_legacy as get_db_connection, add_notification, hash_password, verify_password
from ..core.email_utils import send_welcome_email
from ..core.security import (
    sanitize_input, validate_username, validate_email, 
    log_security_event, rate_limit_key
)

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Sanitize inputs
        username = sanitize_input(request.form.get('username', ''), 50).lower()
        password = request.form.get('password', '')

        # Validate inputs
        if not username or not password:
            log_security_event('LOGIN_ATTEMPT', {'username': username, 'error': 'missing_credentials'}, 'WARNING')
            return render_template('auth/login.html', message="Username and password required")

        # Rate limiting check (basic implementation)
        if len(password) > 128:  # Prevent extremely long passwords
            log_security_event('LOGIN_ATTEMPT', {'username': username, 'error': 'password_too_long'}, 'WARNING')
            return render_template('auth/login.html', message="Invalid credentials")

        conn = get_db_connection()
        try:
            user = conn.execute(
                "SELECT username, password_hash, role FROM users WHERE username = ?", (username,)
            ).fetchone()
        except Exception as e:
            logger.error(f"Database error during login: {e}")
            return render_template('auth/login.html', message="System error. Please try again.")
        finally:
            conn.close()

        if user and verify_password(password, user['password_hash']):
            session['username'] = user['username']
            session['role'] = user['role']
            session.permanent = True  # Make session permanent
            
            log_security_event('LOGIN_SUCCESS', {'username': username}, 'INFO')
            return redirect(url_for('core.dashboard', username=username))
        else:
            log_security_event('LOGIN_FAILED', {'username': username}, 'WARNING')
            return render_template('auth/login.html', message="Invalid username or password")

    return render_template('auth/login.html')
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Sanitize inputs
        username = sanitize_input(request.form.get('username', ''), 50)
        password = request.form.get('password', '')
        email = sanitize_input(request.form.get('email', ''), 254)

        # Validate username
        is_valid_username, username_error = validate_username(username)
        if not is_valid_username:
            log_security_event('REGISTRATION_ATTEMPT', {'username': username, 'error': username_error}, 'WARNING')
            return render_template('auth/register.html', message=username_error)

        # Validate password
        if not password or len(password) < 8:
            return render_template('auth/register.html', message="Password must be at least 8 characters")
        
        if len(password) > 128:
            return render_template('auth/register.html', message="Password is too long")

        # Validate email
        if not validate_email(email):
            return render_template('auth/register.html', message="Please enter a valid email address")

        # Normalize username
        username = username.lower()

        conn = get_db_connection()
        try:
            # Check for existing username
            if conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone():
                log_security_event('REGISTRATION_ATTEMPT', {'username': username, 'error': 'username_exists'}, 'INFO')
                return render_template('auth/register.html', message="Username already exists")
            if conn.execute("SELECT id FROM users WHERE email = ? AND email != ''", (email,)).fetchone():
                log_security_event('REGISTRATION_ATTEMPT', {'email': email, 'error': 'email_exists'}, 'INFO')
                return render_template('auth/register.html', message="Email already registered")

            # Create user with secure password hash
            conn.execute(
                "INSERT INTO users (username, password_hash, role, email) VALUES (?, ?, ?, ?)",
                (username, hash_password(password), 'user', email)
            )
            conn.commit()
            
            log_security_event('REGISTRATION_SUCCESS', {'username': username, 'email': email}, 'INFO')
            
        except Exception as e:
            logger.error(f"Database error during registration: {e}")
            return render_template('auth/register.html', message="Registration failed. Please try again.")
        finally:
            conn.close()

        # Send welcome notification and email
        try:
            add_notification(username, "🎉 Welcome to SmartPark! Your account is ready.")
            send_welcome_email(email, username)
        except Exception as e:
            logger.warning(f"Failed to send welcome email to {email}: {e}")

        return render_template('auth/register.html', 
                             message="Registration successful! You can now login.", 
                             success=True)

    return render_template('auth/register.html')

@auth_bp.route('/change_password/<username>', methods=['POST'])
def change_password(username):
    # Sanitize username
    username = sanitize_input(username, 50).lower()
    
    if session.get('username') != username:
        log_security_event('UNAUTHORIZED_PASSWORD_CHANGE', {'username': username, 'session_user': session.get('username')}, 'WARNING')
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Invalid request'}), 400

    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    
    # Validate new password
    if len(new_password) < 8:
        return jsonify({'success': False, 'message': 'New password must be at least 8 characters'})
    
    if len(new_password) > 128:
        return jsonify({'success': False, 'message': 'New password is too long'})
    
    # Check password complexity
    if not any(c.isupper() for c in new_password) or not any(c.islower() for c in new_password) or not any(c.isdigit() for c in new_password):
        return jsonify({'success': False, 'message': 'Password must contain uppercase, lowercase, and numeric characters'})

    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()

        if not user or not verify_password(current_password, user['password_hash']):
            log_security_event('PASSWORD_CHANGE_FAILED', {'username': username, 'error': 'invalid_current_password'}, 'WARNING')
            return jsonify({'success': False, 'message': 'Current password is incorrect'})

        # Update password with new secure hash
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (hash_password(new_password), username)
        )
        conn.commit()
        
        log_security_event('PASSWORD_CHANGE_SUCCESS', {'username': username}, 'INFO')
        
    except Exception as e:
        logger.error(f"Database error during password change: {e}")
        return jsonify({'success': False, 'message': 'System error. Please try again.'})
    finally:
        conn.close()

    return jsonify({'success': True, 'message': 'Password changed successfully'})


@auth_bp.route('/logout')
def logout():
    username = session.get('username')
    if username:
        log_security_event('LOGOUT', {'username': username}, 'INFO')
    
    session.clear()
    return redirect(url_for('auth.login'))
