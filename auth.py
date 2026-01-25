"""
Authentication and Configuration Management for Meeting Scheduler.
Handles organizer login and secure storage of SMTP credentials.
"""

import streamlit as st
import hashlib
import json
import os
from pathlib import Path
from typing import Optional, Dict
import secrets

# Configuration file path (should be in a secure location)
CONFIG_DIR = Path(__file__).parent / ".config"
CONFIG_FILE = CONFIG_DIR / "organizer_config.json"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"


def ensure_config_dir():
    """Ensure the config directory exists."""
    CONFIG_DIR.mkdir(exist_ok=True)
    # Create .gitignore to prevent accidental commits
    gitignore_path = CONFIG_DIR / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text("*\n")


def hash_password(password: str, salt: str = None) -> tuple:
    """Hash a password with salt."""
    if salt is None:
        salt = secrets.token_hex(32)
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode(),
        salt.encode(),
        100000
    ).hex()
    return hashed, salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    """Verify a password against its hash."""
    new_hash, _ = hash_password(password, salt)
    return new_hash == hashed


def load_credentials() -> Dict:
    """Load organizer credentials from file."""
    ensure_config_dir()
    if CREDENTIALS_FILE.exists():
        try:
            return json.loads(CREDENTIALS_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_credentials(credentials: Dict):
    """Save organizer credentials to file."""
    ensure_config_dir()
    CREDENTIALS_FILE.write_text(json.dumps(credentials, indent=2))
    # Set restrictive permissions on Unix systems
    try:
        os.chmod(CREDENTIALS_FILE, 0o600)
    except (OSError, AttributeError):
        pass  # Windows doesn't support chmod


def load_smtp_config(organizer_email: str) -> Optional[Dict]:
    """Load SMTP configuration for an organizer."""
    credentials = load_credentials()
    organizer = credentials.get("organizers", {}).get(organizer_email.lower())
    if organizer:
        return organizer.get("smtp_config")
    return None


def save_smtp_config(organizer_email: str, smtp_config: Dict):
    """Save SMTP configuration for an organizer."""
    credentials = load_credentials()
    if "organizers" not in credentials:
        credentials["organizers"] = {}
    
    email_lower = organizer_email.lower()
    if email_lower not in credentials["organizers"]:
        credentials["organizers"][email_lower] = {}
    
    credentials["organizers"][email_lower]["smtp_config"] = smtp_config
    save_credentials(credentials)


def register_organizer(email: str, password: str, name: str = "") -> bool:
    """Register a new organizer."""
    credentials = load_credentials()
    if "organizers" not in credentials:
        credentials["organizers"] = {}
    
    email_lower = email.lower()
    if email_lower in credentials["organizers"]:
        return False  # Already exists
    
    hashed, salt = hash_password(password)
    credentials["organizers"][email_lower] = {
        "name": name or email.split("@")[0],
        "password_hash": hashed,
        "salt": salt,
        "smtp_config": None
    }
    save_credentials(credentials)
    return True


def authenticate_organizer(email: str, password: str) -> bool:
    """Authenticate an organizer."""
    credentials = load_credentials()
    organizer = credentials.get("organizers", {}).get(email.lower())
    
    if not organizer:
        return False
    
    return verify_password(
        password,
        organizer.get("password_hash", ""),
        organizer.get("salt", "")
    )


def organizer_exists(email: str) -> bool:
    """Check if an organizer account exists."""
    credentials = load_credentials()
    return email.lower() in credentials.get("organizers", {})


def get_organizer_name(email: str) -> str:
    """Get the display name for an organizer."""
    credentials = load_credentials()
    organizer = credentials.get("organizers", {}).get(email.lower())
    if organizer:
        return organizer.get("name", email.split("@")[0])
    return email.split("@")[0]


def is_authenticated() -> bool:
    """Check if current session is authenticated as organizer."""
    return st.session_state.get("authenticated", False) and st.session_state.get("organizer_email")


def get_current_organizer() -> Optional[str]:
    """Get the currently logged in organizer's email."""
    if is_authenticated():
        return st.session_state.get("organizer_email")
    return None


def logout():
    """Log out the current organizer."""
    st.session_state["authenticated"] = False
    st.session_state["organizer_email"] = None
    st.session_state["organizer_name"] = None


def render_login_page() -> bool:
    """
    Render the login/registration page.
    Returns True if authenticated, False otherwise.
    """
    st.markdown("""
    <style>
        .auth-container {
            max-width: 400px;
            margin: 0 auto;
            padding: 40px;
            background: white;
            border-radius: 15px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }
        .auth-header {
            text-align: center;
            margin-bottom: 30px;
        }
        .auth-header h1 {
            color: #667eea;
            margin: 0;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Check if already authenticated
    if is_authenticated():
        return True
    
    st.markdown("""
    <div class="auth-header">
        <h1>📅 Meeting Scheduler</h1>
        <p>Organizer Portal</p>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
    
    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="organizer@university.edu")
            password = st.text_input("Password", type="password")
            
            if st.form_submit_button("Login", use_container_width=True, type="primary"):
                if email and password:
                    if authenticate_organizer(email, password):
                        st.session_state["authenticated"] = True
                        st.session_state["organizer_email"] = email.lower()
                        st.session_state["organizer_name"] = get_organizer_name(email)
                        st.success("✅ Login successful!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid email or password.")
                else:
                    st.error("Please enter email and password.")
    
    with tab2:
        with st.form("register_form"):
            reg_name = st.text_input("Full Name", placeholder="Dr. John Smith")
            reg_email = st.text_input("Email", placeholder="organizer@university.edu", key="reg_email")
            reg_password = st.text_input("Password", type="password", key="reg_pass")
            reg_password_confirm = st.text_input("Confirm Password", type="password")
            
            if st.form_submit_button("Create Account", use_container_width=True):
                if not all([reg_name, reg_email, reg_password, reg_password_confirm]):
                    st.error("Please fill in all fields.")
                elif reg_password != reg_password_confirm:
                    st.error("Passwords do not match.")
                elif len(reg_password) < 8:
                    st.error("Password must be at least 8 characters.")
                elif organizer_exists(reg_email):
                    st.error("An account with this email already exists.")
                else:
                    if register_organizer(reg_email, reg_password, reg_name):
                        st.success("✅ Account created! You can now log in.")
                    else:
                        st.error("Failed to create account.")
    
    return False


def render_smtp_setup():
    """Render SMTP configuration interface."""
    st.subheader("📧 Email Configuration")
    st.markdown("""
    Configure your SMTP settings to send email invitations. 
    Your credentials are stored locally and never shared.
    """)
    
    organizer_email = get_current_organizer()
    current_config = load_smtp_config(organizer_email) or {}
    
    # Show current status
    if current_config.get("smtp_server"):
        st.success(f"✅ Email configured: {current_config.get('from_email', 'Not set')}")
    else:
        st.warning("⚠️ Email not configured. Invitations will be simulated.")
    
    with st.expander("⚙️ Configure SMTP Settings", expanded=not current_config.get("smtp_server")):
        st.markdown("""
        **Common SMTP Settings:**
        - **Gmail**: smtp.gmail.com, Port 587 (requires App Password)
        - **Outlook**: smtp.office365.com, Port 587
        - **Yahoo**: smtp.mail.yahoo.com, Port 587
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            smtp_server = st.text_input(
                "SMTP Server",
                value=current_config.get("smtp_server", "smtp.gmail.com"),
                key="smtp_server"
            )
            smtp_port = st.number_input(
                "SMTP Port",
                value=current_config.get("smtp_port", 587),
                min_value=1,
                max_value=65535,
                key="smtp_port"
            )
        
        with col2:
            smtp_username = st.text_input(
                "SMTP Username",
                value=current_config.get("smtp_username", ""),
                placeholder="your-email@gmail.com",
                key="smtp_username"
            )
            smtp_password = st.text_input(
                "SMTP Password / App Password",
                type="password",
                value="",
                placeholder="Enter password to update",
                key="smtp_password",
                help="For Gmail, use an App Password (not your regular password)"
            )
        
        from_email = st.text_input(
            "From Email Address",
            value=current_config.get("from_email", organizer_email),
            key="from_email"
        )
        
        from_name = st.text_input(
            "From Name",
            value=current_config.get("from_name", "Meeting Scheduler"),
            key="from_name"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("💾 Save Configuration", use_container_width=True, type="primary"):
                new_config = {
                    "smtp_server": smtp_server,
                    "smtp_port": int(smtp_port),
                    "smtp_username": smtp_username,
                    "smtp_password": smtp_password if smtp_password else current_config.get("smtp_password", ""),
                    "from_email": from_email,
                    "from_name": from_name
                }
                save_smtp_config(organizer_email, new_config)
                st.success("✅ Configuration saved!")
                st.rerun()
        
        with col2:
            if st.button("🧪 Test Email", use_container_width=True):
                test_config = {
                    "smtp_server": smtp_server,
                    "smtp_port": int(smtp_port),
                    "smtp_username": smtp_username,
                    "smtp_password": smtp_password if smtp_password else current_config.get("smtp_password", ""),
                    "from_email": from_email,
                    "from_name": from_name
                }
                
                # Import here to avoid circular imports
                from email_utils import send_test_email
                success, message = send_test_email(organizer_email, test_config)
                
                if success:
                    st.success(f"✅ {message}")
                else:
                    st.error(f"❌ {message}")


def render_logout_button():
    """Render logout button in sidebar."""
    if is_authenticated():
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**Logged in as:** {st.session_state.get('organizer_name', 'Organizer')}")
        st.sidebar.markdown(f"*{get_current_organizer()}*")
        if st.sidebar.button("🚪 Logout", use_container_width=True):
            logout()
            st.rerun()
