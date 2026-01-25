"""
Meeting Scheduler - Organizer App
Protected interface for meeting organizers.
Requires login to access.
"""

import streamlit as st
from pages_organizer import render_organizer_page
from auth import (
    is_authenticated, render_login_page, render_logout_button,
    get_current_organizer, render_smtp_setup
)


def main():
    """Main entry point for organizer app."""
    
    # Page configuration
    st.set_page_config(
        page_title="Meeting Scheduler - Organizer",
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
        
        /* Tab styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            padding: 10px 24px;
            background-color: #f0f2f6;
            border-radius: 10px 10px 0 0;
        }
        
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 20px 0;">
            <h1 style="color: #667eea; margin: 0;">📅</h1>
            <h2 style="color: #333; margin: 5px 0;">Organizer Portal</h2>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        if is_authenticated():
            # Navigation for authenticated users
            nav_option = st.radio(
                "Navigation",
                ["📅 Meetings", "⚙️ Email Settings"],
                label_visibility="collapsed"
            )
            render_logout_button()
        else:
            nav_option = "login"
    
    # Main content
    if not is_authenticated():
        # Show login page
        st.markdown("""
        <div style="text-align: center; margin-bottom: 30px;">
            <h1>📅 Organizer Portal</h1>
            <p>Please log in to continue</p>
        </div>
        """, unsafe_allow_html=True)
        
        if render_login_page():
            st.rerun()
    else:
        # Show appropriate page based on navigation
        if nav_option == "📅 Meetings":
            render_organizer_page()
        elif nav_option == "⚙️ Email Settings":
            st.header("⚙️ Email Settings")
            render_smtp_setup()


if __name__ == "__main__":
    main()
