"""
Meeting Scheduler - Participant App
A simple, standalone interface for participants to respond to meeting invitations.
No login required - uses token-based authentication from email links.
"""

import streamlit as st
from pages_participant import render_participant_page


def main():
    """Main entry point for participant app."""
    
    # Page configuration
    st.set_page_config(
        page_title="Meeting Scheduler - Respond",
        page_icon="📅",
        layout="centered",
        initial_sidebar_state="collapsed"
    )
    
    # Minimal CSS for participant interface
    st.markdown("""
    <style>
        /* Hide sidebar completely for participants */
        [data-testid="stSidebar"] {
            display: none;
        }
        
        /* Clean, simple styling */
        .stApp {
            max-width: 800px;
            margin: 0 auto;
        }
        
        /* Button styling */
        .stButton > button {
            border-radius: 8px;
            font-weight: 500;
        }
        
        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)
    
    # Get token from URL
    query_params = st.query_params
    token = query_params.get("token", None)
    
    # Render the participant response page
    render_participant_page(token)


if __name__ == "__main__":
    main()
