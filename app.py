"""
Meeting Scheduler - Main Application
A Streamlit-based meeting scheduling application with separate organizer and participant interfaces.
"""

import streamlit as st
from pages_organizer import render_organizer_page
from pages_participant import render_participant_page, render_participant_lookup
from auth import (
    is_authenticated, render_login_page, render_logout_button,
    get_current_organizer, render_smtp_setup
)


def main():
    """Main application entry point."""
    
    # Page configuration
    st.set_page_config(
        page_title="Meeting Scheduler",
        page_icon="📅",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
        /* Main theme colors */
        :root {
            --primary-color: #667eea;
            --secondary-color: #764ba2;
            --success-color: #4caf50;
            --warning-color: #ff9800;
            --error-color: #f44336;
        }
        
        /* Header styling */
        .main-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px 30px;
            border-radius: 15px;
            color: white;
            margin-bottom: 30px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .main-header h1 {
            margin: 0;
            font-size: 2rem;
        }
        
        .main-header p {
            margin: 5px 0 0 0;
            opacity: 0.9;
        }
        
        /* Card styling */
        .info-card {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin: 15px 0;
            border-left: 4px solid var(--primary-color);
        }
        
        /* Button styling */
        .stButton > button {
            border-radius: 8px;
            font-weight: 500;
            transition: all 0.3s ease;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        
        /* Sidebar styling */
        .css-1d391kg {
            background: linear-gradient(180deg, #f8f9fa 0%, #ffffff 100%);
        }
        
        /* Tab styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background: transparent;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            padding: 10px 24px;
            background-color: #f0f2f6;
            border-radius: 10px 10px 0 0;
            color: #333;
            font-weight: 500;
        }
        
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        /* Form styling */
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea,
        .stSelectbox > div > div > select {
            border-radius: 8px;
            border: 2px solid #e0e0e0;
            transition: border-color 0.3s;
        }
        
        .stTextInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus {
            border-color: var(--primary-color);
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        /* Expander styling */
        .streamlit-expanderHeader {
            background: #f8f9fa;
            border-radius: 8px;
            font-weight: 500;
        }
        
        /* Metric styling */
        .css-1xarl3l {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 15px;
            border-radius: 10px;
        }
        
        /* DataFrame styling */
        .stDataFrame {
            border-radius: 10px;
            overflow: hidden;
        }
        
        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* Success/Warning/Error boxes */
        .success-box {
            background: #e8f5e9;
            border-left: 4px solid #4caf50;
            padding: 15px 20px;
            border-radius: 0 8px 8px 0;
            margin: 10px 0;
        }
        
        .warning-box {
            background: #fff3e0;
            border-left: 4px solid #ff9800;
            padding: 15px 20px;
            border-radius: 0 8px 8px 0;
            margin: 10px 0;
        }
        
        .error-box {
            background: #ffebee;
            border-left: 4px solid #f44336;
            padding: 15px 20px;
            border-radius: 0 8px 8px 0;
            margin: 10px 0;
        }
        
        /* Responsive adjustments */
        @media (max-width: 768px) {
            .main-header {
                flex-direction: column;
                text-align: center;
            }
            
            .main-header h1 {
                font-size: 1.5rem;
            }
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Check for direct response link
    query_params = st.query_params
    page = query_params.get("page", "home")
    token = query_params.get("token", None)
    
    # If token is present, go directly to participant response (no auth needed)
    if token:
        render_participant_page(token)
        return
    
    # Sidebar navigation
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 20px 0;">
            <h1 style="color: #667eea; margin: 0;">📅</h1>
            <h2 style="color: #333; margin: 5px 0;">Meeting Scheduler</h2>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Navigation - different options based on auth status
        st.markdown("### 🧭 Navigation")
        
        if is_authenticated():
            nav_option = st.radio(
                "Select Interface",
                ["🏠 Home", "👔 Organizer Portal", "⚙️ Email Settings", "👤 Participant Portal"],
                label_visibility="collapsed"
            )
            # Show logout button
            render_logout_button()
        else:
            nav_option = st.radio(
                "Select Interface",
                ["🏠 Home", "🔐 Organizer Login", "👤 Participant Portal"],
                label_visibility="collapsed"
            )
    
    # Main content based on navigation
    if nav_option == "🏠 Home":
        render_home_page()
    elif nav_option == "👔 Organizer Portal":
        # Requires authentication
        if is_authenticated():
            render_organizer_page()
        else:
            st.warning("⚠️ Please log in to access the Organizer Portal.")
            if render_login_page():
                st.rerun()
    elif nav_option == "🔐 Organizer Login":
        if render_login_page():
            st.rerun()
    elif nav_option == "⚙️ Email Settings":
        if is_authenticated():
            render_smtp_setup()
        else:
            st.warning("⚠️ Please log in to access Email Settings.")
    elif nav_option == "👤 Participant Portal":
        render_participant_lookup()


def render_home_page():
    """Render the home/landing page."""

    
    st.markdown("""
    Welcome to the Meeting Scheduler! This application helps you coordinate meetings 
    by allowing organizers to propose time slots and participants to indicate their availability.
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="info-card">
            <h3>👔 For Organizers</h3>
            <ul>
                <li>Create participant groups (e.g., "Math Faculty")</li>
                <li>Select subsets for specific meetings</li>
                <li>Propose multiple time slots</li>
                <li>Send email invitations automatically</li>
                <li>Track responses in real-time</li>
                <li>Identify optimal meeting times</li>
                <li>Finalize and notify participants</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="info-card">
            <h3>👤 For Participants</h3>
            <ul>
                <li>No login required - token-based access</li>
                <li>Simple availability selection</li>
                <li>Suggest alternative times</li>
                <li>Update responses anytime</li>
                <li>Receive email confirmations</li>
                <li>Get notified of final schedule</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    st.markdown("### 🚀 Getting Started")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        **Step 1: Set Up Groups**
        
        Create participant groups like "Math Faculty" or "Department Heads" 
        to easily organize your meeting invitees.
        """)
    
    with col2:
        st.markdown("""
        **Step 2: Create Meeting**
        
        Enter meeting details, select participants (or a subset from a group), 
        and propose multiple time slots.
        """)
    
    with col3:
        st.markdown("""
        **Step 3: Collect & Finalize**
        
        Track responses, identify the best slot with visual analytics, 
        and send the final schedule to all participants.
        """)
    
    st.markdown("---")
    
    st.info("👈 Use the sidebar to navigate to the **Organizer Portal** or **Participant Portal**")
    
    


if __name__ == "__main__":
    main()
