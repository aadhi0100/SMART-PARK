import os
import secrets
import logging
from flask import Blueprint, redirect, url_for, session, flash
from authlib.integrations.flask_client import OAuth

logger = logging.getLogger(__name__)

oauth_bp = Blueprint('oauth', __name__)
oauth = OAuth()

def init_oauth(app):
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=os.environ.get('GOOGLE_CLIENT_ID', ''),
        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET', ''),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )

@oauth_bp.route('/google/login')
def google_login():
    redirect_uri = url_for('oauth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)
@oauth_bp.route('/google/callback')
def google_callback():
    from ..core.database import get_db_connection, add_notification, hash_password
    from ..core.email_utils import send_welcome_email
    from authlib.integrations.base_client.errors import OAuthError

    try:
        token = oauth.google.authorize_access_token()
    except OAuthError as e:
        logger.warning("Google OAuth error: %s", e)
        flash('Google sign-in was cancelled or denied. Please try again.', 'danger')
        return redirect(url_for('auth.login'))

    user_info = token.get('userinfo') or oauth.google.userinfo()

    google_id = user_info.get('sub')
    email = user_info.get('email', '')
    name = user_info.get('name', email.split('@')[0] if email else 'user')
    username = ''.join(c if c.isalnum() or c == '_' else '_' for c in name)[:30]

    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT username, role FROM users WHERE google_id = ?", (google_id,)).fetchone()
        if not user:
            base = username
            suffix = 1
            while conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone():
                username = "{}_{}".format(base, suffix)
                suffix += 1
            rand_pw = hash_password(secrets.token_hex(32))
            conn.execute(
                "INSERT INTO users (username, password_hash, role, email, google_id) VALUES (?, ?, 'user', ?, ?)",
                (username, rand_pw, email, google_id)
            )
            conn.commit()
            add_notification(username, "\U0001f44b Welcome to SmartPark! You signed in with Google.")
            send_welcome_email(email, username)
            role = 'user'
        else:
            username = user['username']
            role = user['role']
    finally:
        conn.close()

    session['username'] = username
    session['role'] = role
    return redirect(url_for('core.dashboard', username=username))
