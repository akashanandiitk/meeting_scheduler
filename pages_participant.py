"""
Participant Module for Meeting Scheduler
Simple interface for participants to respond to meeting invitations.
Token-based authentication - no login required.
"""

import streamlit as st
from datetime import datetime
from database import (
    get_participant_by_token, get_meeting_slots,
    save_response, mark_participant_responded,
    add_suggested_slot, get_participant_responses,
    get_meeting_by_id
)
from email_utils import send_response_notification
import os


def get_base_url():
    """Get the base URL for participant response links."""
    return os.getenv(
        "PARTICIPANT_URL",
        os.getenv("PARTICIPANT_APP_URL", 
                  os.getenv("APP_BASE_URL", "http://localhost:8501"))
    )


def render_participant_page(token: str = None):
    """Render the participant response page."""
    
    st.markdown("""
    <style>
        .meeting-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 30px;
            border-radius: 15px;
            color: white;
            margin-bottom: 30px;
        }
        .slot-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            border: 2px solid #e0e0e0;
            margin: 10px 0;
            transition: all 0.3s;
        }
        .slot-card:hover {
            border-color: #667eea;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
        }
        .availability-btn {
            padding: 10px 20px;
            border-radius: 8px;
            border: none;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.2s;
        }
        .finalized-banner {
            background: linear-gradient(135deg, #4caf50 0%, #45a049 100%);
            padding: 25px;
            border-radius: 15px;
            color: white;
            text-align: center;
            margin: 20px 0;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Get token from URL or session
    if not token:
        query_params = st.query_params
        token = query_params.get("token", None)
    
    if not token:
        st.warning(" No response token found.")
        st.markdown("""
        ### How to respond to a meeting invitation:
        1. Check your email for the meeting invitation
        2. Click the **"Respond to Invitation"** button in the email
        3. Or paste the response link directly in your browser
        """)
        
        # Manual token entry (for testing)
        with st.expander(" Enter Token Manually"):
            manual_token = st.text_input("Response Token", placeholder="Enter your token...")
            if manual_token:
                st.query_params["token"] = manual_token
                st.rerun()
        return
    
    # Validate token and get participant info
    participant_info = get_participant_by_token(token)
    
    if not participant_info:
        st.error(" Invalid or expired response link.")
        st.markdown("Please check your email for the correct invitation link, or contact the meeting organizer.")
        return
    
    # Extract info
    participant_name = participant_info['name']
    participant_email = participant_info['email']
    participant_id = participant_info['id']
    meeting_id = participant_info['meeting_id']
    meeting_title = participant_info['meeting_title']
    meeting_description = participant_info['meeting_description']
    meeting_status = participant_info['meeting_status']
    organizer_email = participant_info['organizer_email']
    finalized_slot = participant_info.get('finalized_slot')
    already_responded = participant_info['responded']
    
    # Header
    st.markdown(f"""
    <div class="meeting-header">
        <h1 style="margin: 0;"> Meeting Invitation</h1>
        <p style="opacity: 0.9; margin-top: 10px;">Hello, {participant_name}!</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Meeting info
    st.markdown(f"## {meeting_title}")
    if meeting_description:
        st.markdown(f"*{meeting_description}*")
    st.markdown(f"**Organized by:** {organizer_email}")
    
    # Check if meeting is finalized
    if meeting_status == 'finalized' and finalized_slot:
        st.markdown(f"""
        <div class="finalized-banner">
            <h2 style="margin: 0;"> Meeting Confirmed!</h2>
            <p style="font-size: 1.3em; margin-top: 15px;">{finalized_slot}</p>
        </div>
        """, unsafe_allow_html=True)
        st.balloons()
        return
    
    if meeting_status == 'cancelled':
        st.error(" This meeting has been cancelled by the organizer.")
        return
    
    # Get time slots
    slots = get_meeting_slots(meeting_id)
    
    if not slots:
        st.warning("No time slots have been proposed yet.")
        return
    
    # Previous responses
    previous_responses = {}
    if already_responded:
        existing = get_participant_responses(meeting_id, participant_id)
        for r in existing:
            previous_responses[r['slot_id']] = r['availability']
        
        st.info(" You have already responded. You can update your response below.")
    
    st.markdown("---")
    st.subheader(" Please indicate your availability for each proposed time:")
    
    # Initialize session state for responses - MEETING SPECIFIC
    session_key = f'slot_responses_{meeting_id}'
    if session_key not in st.session_state:
        st.session_state[session_key] = previous_responses.copy()
    
    # Display slots with radio buttons
    for slot in slots:
        slot_dt = datetime.fromisoformat(slot['slot_datetime'])
        slot_display = slot_dt.strftime('%A, %B %d, %Y at %I:%M %p')
        duration = slot['duration_minutes']
        
        col1, col2 = st.columns([2, 3])
        
        with col1:
            st.markdown(f"###  {slot_display}")
            st.caption(f"Duration: {duration} minutes")
        
        with col2:
            # Get default value
            default_idx = 0
            if slot['id'] in st.session_state[session_key]:
                avail = st.session_state[session_key][slot['id']]
                if avail == 'available':
                    default_idx = 0
                elif avail == 'maybe':
                    default_idx = 1
                else:
                    default_idx = 2
            
            response = st.radio(
                "Your availability",
                options=['available', 'maybe', 'unavailable'],
                index=default_idx,
                format_func=lambda x: {
                    'available': ' Available',
                    'maybe': ' Maybe / If needed',
                    'unavailable': ' Not available'
                }[x],
                key=f"slot_{meeting_id}_{slot['id']}",
                horizontal=True,
                label_visibility="collapsed"
            )
            st.session_state[session_key][slot['id']] = response
        
        st.markdown("---")
    
    # Suggest alternative time
    st.subheader(" Suggest Alternative Time (Optional)")
    
    with st.expander("Add a time that works better for you"):
        col1, col2 = st.columns(2)
        with col1:
            alt_date = st.date_input("Date", key="alt_date")
        with col2:
            alt_time = st.time_input("Time", key="alt_time")
        
        alt_note = st.text_input("Note (optional)", placeholder="e.g., I'm free all afternoon that day")
    
    # Submit button
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if st.button(" Submit Response", use_container_width=True, type="primary"):
            # Save all responses using meeting-specific session key
            session_key = f'slot_responses_{meeting_id}'
            for slot in slots:
                availability = st.session_state[session_key].get(slot['id'], 'unavailable')
                save_response(
                    meeting_id=meeting_id,
                    participant_id=participant_id,
                    slot_id=slot['id'],
                    availability=availability
                )
            
            # Save suggested slot if provided
            if alt_date and alt_time:
                alt_datetime = datetime.combine(alt_date, alt_time)
                add_suggested_slot(
                    meeting_id=meeting_id,
                    participant_id=participant_id,
                    suggested_datetime=alt_datetime.isoformat(),
                    note=alt_note
                )
            
            # Mark as responded
            mark_participant_responded(meeting_id, participant_id)
            
            # Notify organizer
            base_url = get_base_url()
            send_response_notification(
                organizer_email=organizer_email,
                participant_name=participant_name,
                meeting_title=meeting_title,
                meeting_id=meeting_id,
                base_url=base_url
            )
            
            st.success("✅ Your response has been submitted! Thank you.")
            st.balloons()
            
            # Show summary
            st.markdown("### Your Response Summary:")
            for slot in slots:
                slot_dt = datetime.fromisoformat(slot['slot_datetime'])
                slot_display = slot_dt.strftime('%a %m/%d %I:%M%p')
                avail = st.session_state[session_key].get(slot['id'], 'unavailable')
                icon = {'available': '✅', 'maybe': '🟡', 'unavailable': '❌'}[avail]
                st.write(f"{icon} {slot_display}")
            
            st.info("You can revisit this link anytime to update your response.")


def render_participant_lookup():
    """Simple interface for participants to look up their meetings."""
    
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 30px; border-radius: 15px; color: white; margin-bottom: 30px;">
        <h1 style="margin: 0;"> Participant Portal</h1>
        <p style="opacity: 0.9;">Check your pending meeting invitations</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    ### How to respond to meetings:
    
    1. **Check your email** for meeting invitations
    2. **Click the response link** in the email
    3. **Select your availability** for each proposed time slot
    4. **Submit** your response
    
    ---
    
    Don't see an invitation? Contact your meeting organizer or check your spam folder.
    """)


if __name__ == "__main__":
    st.set_page_config(page_title="Meeting Scheduler - Respond", layout="centered")
    render_participant_page()
