"""
Authentication module for Teli.

Handles Google Sign-In using OAuth 2.0.  Here's the flow:
1. User clicks "Sign in with Google"
2. We redirect them to Google's login page
3. Google asks the user to allow Teli access to their name/email/picture
4. Google redirects back to our /auth/callback URL with a special code
5. We exchange that code for the user's info (name, email, picture)
6. We create or find the user in our database
7. Flask-Login keeps them logged in via a session cookie

Libraries used:
- authlib: Handles the OAuth 2.0 protocol (talking to Google)
- flask-login: Manages user sessions (who's logged in)
"""

from flask import Blueprint, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user
from authlib.integrations.flask_client import OAuth
from database import get_or_create_user, get_user
from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET

# A Blueprint is like a mini Flask app — it groups related routes together.
# This keeps authentication code separate from the main app code.
auth_bp = Blueprint("auth", __name__)

# OAuth client — handles the Google sign-in protocol
oauth = OAuth()

# Flask-Login manager — tracks who's logged in
login_manager = LoginManager()


class User(UserMixin):
    """
    Represents a logged-in user.

    Flask-Login needs a User class with certain properties:
    - id: unique identifier (we use the database ID)
    - is_authenticated: True if the user is logged in
    - is_active: True if the account is active

    UserMixin provides sensible defaults for all of these.
    """
    def __init__(self, user_data):
        # user_data is a dict from the database (id, google_id, email, name, picture)
        self.id = user_data["id"]
        self.google_id = user_data["google_id"]
        self.email = user_data["email"]
        self.name = user_data["name"]
        self.picture = user_data["picture"]


@login_manager.user_loader
def load_user(user_id):
    """
    Flask-Login calls this on every request to figure out who's logged in.

    It looks up the user ID stored in the session cookie and returns
    a User object (or None if the user doesn't exist).
    """
    user_data = get_user(int(user_id))
    if user_data:
        return User(user_data)
    return None


def init_auth(app):
    """
    Set up authentication on the Flask app.

    Called once from app.py when the app starts.  This:
    1. Configures Flask-Login (where to redirect if not logged in)
    2. Registers Google as an OAuth provider
    3. Registers the auth routes blueprint
    """
    # Tell Flask-Login which page to show when someone isn't logged in
    login_manager.login_view = "auth.login"
    # Customize the "please log in" message
    login_manager.login_message = "Please sign in to access your watchlist."
    login_manager.login_message_category = "info"

    # Initialize Flask-Login and OAuth with our app
    login_manager.init_app(app)
    oauth.init_app(app)

    # Register Google as an OAuth provider
    # server_metadata_url tells authlib where to find Google's OAuth endpoints
    # (authorization URL, token URL, etc.) — so we don't have to list them manually
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={
            # "openid" = basic auth, "email" = email address, "profile" = name & picture
            "scope": "openid email profile"
        },
    )

    # Add the auth routes to the app
    app.register_blueprint(auth_bp)


# -----------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------

@auth_bp.route("/login")
def login():
    """Show the login page (unless already logged in)."""
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    from flask import render_template
    return render_template("login.html")


@auth_bp.route("/login/google")
def login_google():
    """
    Start the Google sign-in process.

    This redirects the user to Google's login page.  After they sign in,
    Google will redirect them back to our /auth/callback URL.
    """
    # Build the URL that Google should redirect back to after login
    redirect_uri = url_for("auth.callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/auth/callback")
def callback():
    """
    Handle the redirect back from Google after the user signs in.

    Google sends us a special authorization code.  We exchange it for
    the user's profile info, then log them in.
    """
    try:
        # Exchange the authorization code for an access token
        token = oauth.google.authorize_access_token()

        # Get the user's profile info from the token
        # (Google includes it in the ID token as part of OpenID Connect)
        user_info = token.get("userinfo")

        if not user_info:
            flash("Could not get your Google profile. Please try again.", "error")
            return redirect(url_for("auth.login"))

        # Find or create this user in our database
        user_data = get_or_create_user(
            google_id=user_info["sub"],        # "sub" is Google's unique user ID
            email=user_info["email"],
            name=user_info.get("name", ""),
            picture=user_info.get("picture", ""),
        )

        # Log the user in (creates a session cookie)
        user = User(user_data)
        login_user(user)

        flash(f"Welcome, {user.name}!", "success")
        return redirect(url_for("index"))

    except Exception as e:
        # If anything goes wrong (network error, invalid code, etc.),
        # show an error and redirect back to the login page
        flash("Sign-in failed. Please try again.", "error")
        return redirect(url_for("auth.login"))


@auth_bp.route("/login/demo")
def demo_login():
    """
    Skip Google sign-in for local testing.

    Creates a "Demo User" account and logs you in immediately.
    Only works when the app is running in debug mode (locally).
    """
    from flask import current_app
    if not current_app.debug:
        # Don't allow this in production — everyone must use Google sign-in
        flash("Demo login is only available in development mode.", "error")
        return redirect(url_for("auth.login"))

    # Create or find the demo user
    user_data = get_or_create_user(
        google_id="demo-user-local",
        email="demo@localhost",
        name="Demo User",
        picture="",
    )

    user = User(user_data)
    login_user(user)

    flash("Signed in as Demo User.", "success")
    return redirect(url_for("index"))


@auth_bp.route("/logout")
def logout():
    """Log the user out and redirect to the login page."""
    logout_user()
    flash("You've been signed out.", "info")
    return redirect(url_for("auth.login"))
