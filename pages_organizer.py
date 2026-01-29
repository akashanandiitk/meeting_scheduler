"""
Organizer Module for Meeting Scheduler
Handles contact management, group management, meeting creation, and response tracking.
"""

import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from database import (
    # Contact functions
    create_contact, get_contacts_by_owner, get_contact_by_id,
    update_contact, delete_contact, contact_in_use,
    # Group functions  
    create_contact_group, get_groups_by_owner, get_group_by_id,
    update_group, delete_group,
    # Group membership
    add_contact_to_group, remove_contact_from_group, get_group_members,
    # Group sharing
    set_group_shared, share_group_with, unshare_group_with, get_group_shares,
    # Meeting functions
    create_meeting, get_meeting_by_id, get_meetings_by_organizer,
    update_meeting_status, delete_meeting,
    # Time slot functions
    add_time_slot, get_meeting_slots, delete_time_slot,
    # Participant functions
    add_meeting_participant, get_meeting_participants,
    get_responses_for_meeting, get_suggested_slots
)
from email_utils import (
    send_invitation_email, send_schedule_update
)
from auth import get_current_organizer, is_authenticated


def get_base_url():
    """Get the base URL for participant response links.
    
    Set PARTICIPANT_URL environment variable to your website URL, e.g.:
    https://home.iitk.ac.in/~akasha/meeting-scheduler.html
    
    This way, response links will direct to your webpage which then
    loads the Streamlit app in an iframe with the token.
    """
    import os
    # Priority: PARTICIPANT_URL > PARTICIPANT_APP_URL > APP_BASE_URL > default
    return os.getenv(
        "PARTICIPANT_URL",
        os.getenv("PARTICIPANT_APP_URL", 
                  os.getenv("APP_BASE_URL", "http://localhost:8501"))
    )


def render_organizer_page():
    """Main organizer page with tabs for different functions."""
    
    # Check authentication
    if not is_authenticated():
        st.warning(" Please log in to access the Organizer Portal.")
        return
    
    # Get the authenticated organizer's email
    organizer_email = get_current_organizer()
    st.session_state.organizer_email = organizer_email
    
    st.markdown("""
    <style>
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 10px 20px;
            background-color: #f0f2f6;
            border-radius: 8px 8px 0 0;
        }
        .stTabs [aria-selected="true"] {
            background-color: #667eea;
            color: white;
        }
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 10px;
            color: white;
            text-align: center;
        }
        .success-box {
            background: #e8f5e9;
            border-left: 4px solid #4caf50;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
        }
        .warning-box {
            background: #fff3e0;
            border-left: 4px solid #ff9800;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "My Contacts", 
        "Contact Groups", 
        "Create Meeting", 
        "View Responses"
    ])
    
    with tab1:
        render_contacts_management()
    
    with tab2:
        render_group_management()
    
    with tab3:
        render_meeting_creation()
    
    with tab4:
        render_response_view()


def render_contacts_management():
    """Render the contacts management interface."""
    st.header("My Contacts")
    st.markdown("Manage your private contact list. These contacts are only visible to you.")
    
    organizer_email = st.session_state.organizer_email
    
    # Get existing contacts
    contacts = get_contacts_by_owner(organizer_email)
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Add New Contact")
        
        new_name = st.text_input("Name", key="new_contact_name", placeholder="John Doe")
        new_email = st.text_input("Email", key="new_contact_email", placeholder="john@example.com")
        
        if st.button("Add Contact", use_container_width=True, type="primary"):
            if new_name and new_email:
                contact_id = create_contact(organizer_email, new_name, new_email)
                if contact_id:
                    st.success(f"Contact '{new_name}' added!")
                    st.rerun()
                else:
                    st.error("Failed to add contact.")
            else:
                st.error("Please enter both name and email.")
    
    with col2:
        st.subheader(f"Your Contacts ({len(contacts)})")
        
        if not contacts:
            st.info("No contacts yet. Add your first contact using the form on the left.")
        else:
            # Search/filter
            search = st.text_input("Search contacts", key="contact_search", placeholder="Search by name or email...")
            
            filtered_contacts = contacts
            if search:
                search_lower = search.lower()
                filtered_contacts = [
                    c for c in contacts 
                    if search_lower in c['name'].lower() or search_lower in c['email'].lower()
                ]
            
            # Display contacts
            for contact in filtered_contacts:
                with st.expander(f"{contact['name']} ({contact['email']})"):
                    # Edit form
                    edit_col1, edit_col2 = st.columns(2)
                    with edit_col1:
                        edit_name = st.text_input(
                            "Name", 
                            value=contact['name'], 
                            key=f"edit_name_{contact['id']}"
                        )
                    with edit_col2:
                        edit_email = st.text_input(
                            "Email", 
                            value=contact['email'], 
                            key=f"edit_email_{contact['id']}"
                        )
                    
                    btn_col1, btn_col2, btn_col3 = st.columns(3)
                    
                    with btn_col1:
                        if st.button("Save Changes", key=f"save_{contact['id']}", use_container_width=True):
                            if update_contact(contact['id'], edit_name, edit_email):
                                st.success("Contact updated!")
                                st.rerun()
                            else:
                                st.error("Failed to update. Email may already exist.")
                    
                    with btn_col2:
                        # Check if contact is in use
                        meetings_using = contact_in_use(contact['id'])
                        if meetings_using:
                            st.warning(f"Used in {len(meetings_using)} meeting(s)")
                    
                    with btn_col3:
                        if st.button("Delete", key=f"del_{contact['id']}", type="secondary", use_container_width=True):
                            if contact_in_use(contact['id']):
                                st.error("Cannot delete: contact is used in meetings.")
                            else:
                                if delete_contact(contact['id']):
                                    st.success("Contact deleted!")
                                    st.rerun()


def render_group_management():
    """Render the group management interface."""
    st.header("Contact Groups")
    st.markdown("Organize your contacts into groups for easy meeting scheduling. You can optionally share groups with other organizers.")
    
    organizer_email = st.session_state.organizer_email
    contacts = get_contacts_by_owner(organizer_email)
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Create New Group")
        
        group_name = st.text_input("Group Name", placeholder="e.g., Math Faculty", key="new_group_name")
        group_desc = st.text_area("Description", placeholder="Optional description...", key="new_group_desc")
        
        if st.button("Create Group", use_container_width=True, type="primary"):
            if group_name:
                create_contact_group(organizer_email, group_name, group_desc)
                st.success(f"Created group: {group_name}")
                st.rerun()
            else:
                st.error("Please enter a group name.")
    
    with col2:
        st.subheader("Your Groups")
        groups = get_groups_by_owner(organizer_email)
        
        if not groups:
            st.info("No groups created yet. Create your first group!")
        else:
            for group in groups:
                is_shared_group = group.get('access_type') == 'shared'
                group_label = f"{group['name']}"
                if is_shared_group:
                    group_label += f" (shared by {group.get('shared_by', 'unknown')})"
                elif group.get('is_shared'):
                    group_label += " [Shared]"
                
                with st.expander(group_label, expanded=False):
                    if is_shared_group:
                        st.info("This group was shared with you. You can use it but cannot edit it.")
                    
                    st.markdown(f"*{group['description'] or 'No description'}*")
                    
                    members = get_group_members(group['id'])
                    st.markdown(f"**Members:** {len(members)}")
                    
                    if members:
                        member_df = pd.DataFrame(members)[['name', 'email']]
                        st.dataframe(member_df, use_container_width=True, hide_index=True)
                    
                    # Only allow editing if user owns the group
                    if not is_shared_group:
                        st.markdown("---")
                        
                        # Edit group details
                        edit_col1, edit_col2 = st.columns(2)
                        with edit_col1:
                            edit_name = st.text_input(
                                "Group Name",
                                value=group['name'],
                                key=f"edit_grp_name_{group['id']}"
                            )
                        with edit_col2:
                            edit_desc = st.text_input(
                                "Description",
                                value=group['description'] or "",
                                key=f"edit_grp_desc_{group['id']}"
                            )
                        
                        if st.button("Save Group Details", key=f"save_grp_{group['id']}"):
                            update_group(group['id'], edit_name, edit_desc)
                            st.success("Group updated!")
                            st.rerun()
                        
                        st.markdown("---")
                        
                        # Add member to group
                        member_ids = {m['id'] for m in members}
                        available = [c for c in contacts if c['id'] not in member_ids]
                        
                        if available:
                            add_col1, add_col2 = st.columns([3, 1])
                            with add_col1:
                                selected = st.selectbox(
                                    "Add contact to group",
                                    options=available,
                                    format_func=lambda x: f"{x['name']} ({x['email']})",
                                    key=f"add_member_{group['id']}"
                                )
                            with add_col2:
                                if st.button("Add", key=f"btn_add_{group['id']}"):
                                    add_contact_to_group(selected['id'], group['id'])
                                    st.rerun()
                        elif not contacts:
                            st.warning("Add contacts first in the 'My Contacts' tab.")
                        
                        # Remove member
                        if members:
                            rem_col1, rem_col2 = st.columns([3, 1])
                            with rem_col1:
                                to_remove = st.selectbox(
                                    "Remove from group",
                                    options=members,
                                    format_func=lambda x: f"{x['name']} ({x['email']})",
                                    key=f"remove_member_{group['id']}"
                                )
                            with rem_col2:
                                if st.button("Remove", key=f"btn_remove_{group['id']}"):
                                    remove_contact_from_group(to_remove['id'], group['id'])
                                    st.rerun()
                        
                        st.markdown("---")
                        
                        # Sharing options
                        st.markdown("**Sharing**")
                        current_shares = get_group_shares(group['id'])
                        
                        is_shared = group.get('is_shared', False)
                        share_toggle = st.checkbox(
                            "Allow sharing this group",
                            value=is_shared,
                            key=f"share_toggle_{group['id']}"
                        )
                        
                        if share_toggle != is_shared:
                            set_group_shared(group['id'], share_toggle)
                            st.rerun()
                        
                        if share_toggle:
                            share_col1, share_col2 = st.columns([3, 1])
                            with share_col1:
                                share_email = st.text_input(
                                    "Share with (email)",
                                    placeholder="colleague@example.com",
                                    key=f"share_email_{group['id']}"
                                )
                            with share_col2:
                                if st.button("Share", key=f"btn_share_{group['id']}"):
                                    if share_email:
                                        share_group_with(group['id'], share_email)
                                        st.success(f"Shared with {share_email}")
                                        st.rerun()
                            
                            if current_shares:
                                st.markdown("**Currently shared with:**")
                                for shared_email in current_shares:
                                    sh_col1, sh_col2 = st.columns([3, 1])
                                    with sh_col1:
                                        st.write(f"- {shared_email}")
                                    with sh_col2:
                                        if st.button("Revoke", key=f"unshare_{group['id']}_{shared_email}"):
                                            unshare_group_with(group['id'], shared_email)
                                            st.rerun()
                        
                        st.markdown("---")
                        
                        # Delete group
                        if st.button("Delete Group", key=f"delete_{group['id']}", type="secondary"):
                            delete_group(group['id'])
                            st.success("Group deleted!")
                            st.rerun()


def render_meeting_creation():
    """Render the meeting creation interface."""
    st.header("Create New Meeting")
    
    organizer_email = st.session_state.organizer_email
    
    # Check for existing draft meetings
    existing_meetings = get_meetings_by_organizer(st.session_state.organizer_email)
    draft_meetings = [m for m in existing_meetings if m['status'] == 'draft']
    
    if draft_meetings:
        st.info(f"You have {len(draft_meetings)} draft meeting(s). Continue editing below or create a new one.")
    
    # Meeting Details Section (outside form for immediate updates)
    st.subheader("Meeting Details")
    
    col1, col2 = st.columns(2)
    with col1:
        title = st.text_input("Meeting Title", placeholder="e.g., DFAC Committee Meeting", key="meeting_title")
    with col2:
        pass
    
    description = st.text_area(
        "Description",
        placeholder="Describe the purpose and agenda of the meeting...",
        height=100,
        key="meeting_description"
    )
    
    st.markdown("---")
    st.subheader("Select Participants")
    
    # Get contacts and groups for this organizer
    contacts = get_contacts_by_owner(organizer_email)
    groups = get_groups_by_owner(organizer_email)
    
    # Source selection
    source = st.radio(
        "Add participants from:",
        ["Contact Group", "Individual Contacts"],
        horizontal=True,
        key="participant_source"
    )
    
    selected_participants = []
    
    if source == "Contact Group":
        if groups:
            selected_group = st.selectbox(
                "Select Group",
                options=groups,
                format_func=lambda x: f"{x['name']} ({len(get_group_members(x['id']))} members)" + (" [Shared]" if x.get('access_type') == 'shared' else ""),
                key="selected_group"
            )
            if selected_group:
                members = get_group_members(selected_group['id'])
                st.write(f"**Members in {selected_group['name']}:**")
                
                # Allow selecting subset
                if members:
                    selected_ids = st.multiselect(
                        "Select members (leave empty for all)",
                        options=[m['id'] for m in members],
                        format_func=lambda x: next(m['name'] for m in members if m['id'] == x),
                        default=[m['id'] for m in members],
                        key="selected_group_members"
                    )
                    selected_participants = [m for m in members if m['id'] in selected_ids]
                else:
                    st.warning("This group has no members. Add contacts to it first.")
        else:
            st.warning("No groups available. Create a group in the 'Contact Groups' tab first.")
    else:
        if contacts:
            selected_ids = st.multiselect(
                "Select Contacts",
                options=[c['id'] for c in contacts],
                format_func=lambda x: next(f"{c['name']} ({c['email']})" for c in contacts if c['id'] == x),
                key="selected_individual_contacts"
            )
            selected_participants = [c for c in contacts if c['id'] in selected_ids]
        else:
            st.warning("No contacts available. Add contacts in the 'My Contacts' tab first.")
    
    if selected_participants:
        st.success(f"{len(selected_participants)} participant(s) selected")
    
    # Time slots section
    st.markdown("---")
    st.subheader("Propose Time Slots")
    
    # Number input for immediate updates
    num_slots = st.number_input("Number of time slots", min_value=1, max_value=10, value=3, key="num_slots_input")
    
    slots = []
    cols = st.columns(2)
    for i in range(int(num_slots)):
        with cols[i % 2]:
            st.markdown(f"**Slot {i+1}**")
            date = st.date_input(
                "Date",
                value=datetime.now().date() + timedelta(days=7+i),
                key=f"slot_date_{i}"
            )
            time = st.time_input(
                "Time",
                value=datetime.strptime("10:00", "%H:%M").time(),
                key=f"slot_time_{i}"
            )
            duration = st.selectbox(
                "Duration",
                options=[30, 45, 60, 90, 120],
                index=2,
                format_func=lambda x: f"{x} minutes",
                key=f"slot_duration_{i}"
            )
            slots.append({
                'datetime': datetime.combine(date, time),
                'duration': duration
            })
    
    st.markdown("---")
    
    # Check for success message from previous action
    if st.session_state.get('meeting_created_success'):
        msg = st.session_state.pop('meeting_created_success')
        st.success(msg['message'])
        with st.expander("Email Status", expanded=True):
            for name, success in msg['email_results']:
                if success:
                    st.write(f"✅ {name}")
                else:
                    st.write(f"❌ {name} - Failed to send")
        # Clear the success message and show option to create another
        if st.button("Create Another Meeting"):
            del st.session_state['meeting_created_success']
            st.rerun()
        return  # Don't show the form again until user clicks "Create Another"
    
    # Submit button
    if st.button("Create & Send Invitations", use_container_width=True, type="primary"):
        if not title:
            st.error("Please enter a meeting title.")
        elif not selected_participants:
            st.error("Please select at least one participant.")
        elif not slots:
            st.error("Please add at least one time slot.")
        else:
            # Show a spinner while sending
            with st.spinner("Creating meeting and sending invitations..."):
                # Create meeting
                meeting_id = create_meeting(
                    title=title,
                    description=description,
                    organizer_email=st.session_state.organizer_email
                )
                
                # Add time slots
                for slot in slots:
                    add_time_slot(
                        meeting_id=meeting_id,
                        slot_datetime=slot['datetime'].isoformat(),
                        duration_minutes=slot['duration']
                    )
                
                # Add participants and send emails
                base_url = get_base_url()
                slot_strings = [
                    f"{s['datetime'].strftime('%A, %B %d, %Y at %I:%M %p')} ({s['duration']} min)"
                    for s in slots
                ]
                
                email_results = []
                for participant in selected_participants:
                    token = add_meeting_participant(meeting_id, participant['id'])
                    response_url = f"{base_url}?token={token}"
                    
                    success = send_invitation_email(
                        participant_name=participant['name'],
                        participant_email=participant['email'],
                        meeting_title=title,
                        meeting_description=description,
                        organizer_email=st.session_state.organizer_email,
                        response_url=response_url,
                        time_slots=slot_strings
                    )
                    email_results.append((participant['name'], success))
                
                # Update status
                update_meeting_status(meeting_id, 'sent')
            
            # Store success message in session state to show after rerun
            st.session_state['meeting_created_success'] = {
                'message': f" Meeting '{title}' created! Invitations sent to {len(selected_participants)} participant(s).",
                'email_results': email_results
            }
            
            st.rerun()


def render_response_view():
    """Render the response viewing interface."""
    st.header(" Meeting Responses")
    
    # Try to use streamlit-autorefresh if available
    try:
        from streamlit_autorefresh import st_autorefresh
        
        col_refresh1, col_refresh2, col_refresh3 = st.columns([2, 1, 1])
        with col_refresh1:
            st.caption(" Data refreshes automatically when auto-refresh is enabled")
        with col_refresh2:
            if st.button(" Refresh Now", use_container_width=True):
                st.rerun()
        with col_refresh3:
            auto_refresh = st.checkbox("Auto-refresh", value=False, help="Refresh every 30 seconds")
        
        if auto_refresh:
            # Auto-refresh every 30 seconds (30000 ms)
            st_autorefresh(interval=30000, limit=None, key="response_autorefresh")
            st.info(" Auto-refresh enabled (every 30 seconds)")
    
    except ImportError:
        # Fallback if streamlit-autorefresh is not installed
        col_refresh1, col_refresh2 = st.columns([3, 1])
        with col_refresh1:
            st.caption(" Click 'Refresh' to see the latest responses")
        with col_refresh2:
            if st.button(" Refresh Data", use_container_width=True):
                st.rerun()
    
    meetings = get_meetings_by_organizer(st.session_state.organizer_email)
    
    if not meetings:
        st.info("No meetings created yet. Go to 'Create Meeting' to get started!")
        return
    
    # Meeting selector
    active_meetings = [m for m in meetings if m['status'] != 'cancelled']
    
    if not active_meetings:
        st.info("No active meetings. All meetings have been cancelled.")
        return
    
    selected_meeting = st.selectbox(
        "Select Meeting",
        options=active_meetings,
        format_func=lambda x: f"{x['title']} ({x['status']}) - {x['created_at'][:10]}"
    )
    
    if not selected_meeting:
        return
    
    meeting_id = selected_meeting['id']
    
    # Meeting overview
    col1, col2, col3, col4 = st.columns(4)
    
    participants = get_meeting_participants(meeting_id)
    responses = get_responses_for_meeting(meeting_id)
    slots = get_meeting_slots(meeting_id)
    suggested = get_suggested_slots(meeting_id)
    
    responded_count = sum(1 for p in participants if p['responded'])
    
    with col1:
        st.metric("Total Invited", len(participants))
    with col2:
        st.metric("Responded", responded_count)
    with col3:
        st.metric("Pending", len(participants) - responded_count)
    with col4:
        st.metric("Time Slots", len(slots))
    
    st.markdown("---")
    
    # Response matrix
    st.subheader("Availability Matrix")
    
    # Initialize slot_scores to avoid UnboundLocalError
    slot_scores = []
    
    if responses and slots:
        # Build response matrix
        matrix_data = {}
        for slot in slots:
            slot_dt = datetime.fromisoformat(slot['slot_datetime'])
            slot_str = slot_dt.strftime('%a %m/%d %I:%M%p')
            matrix_data[slot_str] = {}
            
            for participant in participants:
                # Find response for this slot
                resp = next(
                    (r for r in responses 
                     if r['slot_id'] == slot['id'] and r['contact_id'] == participant['id']),
                    None
                )
                if resp:
                    avail = resp['availability']
                    if avail == 'available':
                        matrix_data[slot_str][participant['name']] = '✅'
                    elif avail == 'maybe':
                        matrix_data[slot_str][participant['name']] = '🟡'
                    else:
                        matrix_data[slot_str][participant['name']] = '❌'
                elif not participant['responded']:
                    matrix_data[slot_str][participant['name']] = '⏳'
                else:
                    matrix_data[slot_str][participant['name']] = '➖'
        
        df = pd.DataFrame(matrix_data).T
        
        # Calculate best slots
        st.markdown("**Legend:** ✅ Available | 🟡 Maybe | ❌ Unavailable | ⏳ Pending | ➖ No response")
        
        # Display matrix
        st.dataframe(df, use_container_width=True)
        
        # Best slot analysis
        st.subheader("Best Slots")
        
        slot_scores = []
        for slot in slots:
            slot_dt = datetime.fromisoformat(slot['slot_datetime'])
            slot_str = slot_dt.strftime('%a %m/%d %I:%M%p')
            
            available_count = sum(
                1 for r in responses 
                if r['slot_id'] == slot['id'] and r['availability'] == 'available'
            )
            maybe_count = sum(
                1 for r in responses 
                if r['slot_id'] == slot['id'] and r['availability'] == 'maybe'
            )
            
            slot_scores.append({
                'slot_id': slot['id'],
                'slot': slot_str,
                'available': available_count,
                'maybe': maybe_count,
                'score': available_count + (maybe_count * 0.5)
            })
        
        slot_scores.sort(key=lambda x: x['score'], reverse=True)
        
        for i, slot in enumerate(slot_scores[:3]):
            if slot['available'] > 0:
                if i == 0:
                    st.success(f" **{slot['slot']}**: {slot['available']} available, {slot['maybe']} maybe")
                elif i == 1:
                    st.info(f" **{slot['slot']}**: {slot['available']} available, {slot['maybe']} maybe")
                else:
                    st.info(f" **{slot['slot']}**: {slot['available']} available, {slot['maybe']} maybe")
    else:
        st.info("No responses received yet.")
    
    # Suggested alternative slots - only show if there are actual suggestions
    if suggested and len(suggested) > 0:
        st.markdown("---")
        st.subheader("Suggested Alternative Slots")
        
        for s in suggested:
            suggested_dt = s['suggested_datetime']
            # Format the datetime if it's in ISO format
            try:
                from datetime import datetime as dt
                parsed_dt = dt.fromisoformat(suggested_dt)
                suggested_dt = parsed_dt.strftime('%A, %B %d, %Y at %I:%M %p')
            except:
                pass
            note_text = f" - {s['note']}" if s['note'] else ""
            st.write(f"**{s['participant_name']}** suggested: {suggested_dt}{note_text}")
    
    # Participant status
    st.markdown("---")
    st.subheader(" Participant Status")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("** Responded:**")
        for p in participants:
            if p['responded']:
                st.write(f"- {p['name']} ({p['email']}) - {p['responded_at'][:16] if p['responded_at'] else ''}")
    
    with col2:
        st.markdown("** Pending:**")
        for p in participants:
            if not p['responded']:
                st.write(f"- {p['name']} ({p['email']})")
    
    # Actions
    st.markdown("---")
    st.subheader(" Actions")
    
    # Send Reminder
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button(" Send Reminder to Pending", use_container_width=True):
            pending = [p for p in participants if not p['responded']]
            if pending:
                base_url = get_base_url()
                slot_strings = [
                    datetime.fromisoformat(s['slot_datetime']).strftime('%A, %B %d at %I:%M %p')
                    for s in slots
                ]
                
                for p in pending:
                    response_url = f"{base_url}?token={p['token']}"
                    send_invitation_email(
                        participant_name=p['name'],
                        participant_email=p['email'],
                        meeting_title=selected_meeting['title'],
                        meeting_description=selected_meeting['description'] or "",
                        organizer_email=st.session_state.organizer_email,
                        response_url=response_url,
                        time_slots=slot_strings
                    )
                st.success(f" Reminder sent to {len(pending)} participant(s)")
            else:
                st.info("All participants have already responded!")
    
    with col2:
        if st.button(" Cancel Meeting", use_container_width=True, type="secondary"):
            update_meeting_status(meeting_id, 'cancelled')
            st.warning("Meeting cancelled.")
            st.rerun()
    
    # Finalize Meeting Section
    st.markdown("---")
    st.subheader(" Finalize Meeting")
    
    if not slot_scores:
        st.info("No responses yet. Wait for participants to respond before finalizing.")
    else:
        # Sort slots by score (available + 0.5*maybe)
        slot_scores_sorted = sorted(slot_scores, key=lambda x: x['score'], reverse=True)
        
        # Check if any slot has full availability
        total_participants = len(participants)
        best_score = slot_scores_sorted[0]['score'] if slot_scores_sorted else 0
        
        # Display slot options with detailed info
        st.markdown("**Select a time slot to finalize:**")
        
        # Create a more detailed view of each slot
        slot_options = []
        for slot in slot_scores_sorted:
            available = slot['available']
            maybe = slot['maybe']
            unavailable = total_participants - available - maybe
            
            # Calculate participation rate
            if total_participants > 0:
                participation_rate = (available + maybe) / total_participants * 100
            else:
                participation_rate = 0
            
            # Determine status indicator
            if available == total_participants:
                status = "🟢 ALL AVAILABLE"
            elif available + maybe == total_participants:
                status = "🟡 All can attend (some tentative)"
            elif available > 0:
                status = f"🟠 {available}/{total_participants} confirmed"
            else:
                status = f"🔴 No confirmations"
            
            slot_options.append({
                'slot_id': slot['slot_id'],
                'display': f"{slot['slot']} - {status} | ✅{available} 🟡{maybe} ❌{unavailable}",
                'slot_str': slot['slot'],
                'available': available,
                'maybe': maybe,
                'unavailable': unavailable,
                'participation_rate': participation_rate
            })
        
        # Slot selector - use meeting-specific key and find index for current selection
        selector_key = f"finalize_slot_{meeting_id}"
        
        # Get previously selected slot_id from session state
        prev_selected_id = st.session_state.get(f"{selector_key}_id")
        
        # Find the index of previously selected slot, default to 0
        default_index = 0
        if prev_selected_id:
            for i, opt in enumerate(slot_options):
                if opt['slot_id'] == prev_selected_id:
                    default_index = i
                    break
        
        selected_slot_option = st.selectbox(
            "Choose time slot",
            options=slot_options,
            index=default_index,
            format_func=lambda x: x['display'],
            key=selector_key
        )
        
        # Store the selected slot_id in session state
        if selected_slot_option:
            st.session_state[f"{selector_key}_id"] = selected_slot_option['slot_id']
        
        if selected_slot_option:
            # Show who is available for selected slot
            selected_slot_id = selected_slot_option['slot_id']
            
            col_a, col_b, col_c = st.columns(3)
            
            # Get responses for selected slot
            available_names = []
            maybe_names = []
            unavailable_names = []
            no_response_names = []
            
            for p in participants:
                resp = next(
                    (r for r in responses if r['slot_id'] == selected_slot_id and r['contact_id'] == p['id']),
                    None
                )
                if resp:
                    if resp['availability'] == 'available':
                        available_names.append(p['name'])
                    elif resp['availability'] == 'maybe':
                        maybe_names.append(p['name'])
                    else:
                        unavailable_names.append(p['name'])
                else:
                    if p['responded']:
                        unavailable_names.append(p['name'])
                    else:
                        no_response_names.append(p['name'])
            
            with col_a:
                st.markdown("**✅ Available:**")
                for name in available_names:
                    st.write(f"- {name}")
                if not available_names:
                    st.caption("None")
            
            with col_b:
                st.markdown("**🟡 Maybe:**")
                for name in maybe_names:
                    st.write(f"- {name}")
                if not maybe_names:
                    st.caption("None")
            
            with col_c:
                st.markdown("**❌ Unavailable:**")
                for name in unavailable_names:
                    st.write(f"- {name}")
                for name in no_response_names:
                    st.write(f"- {name} (no response)")
                if not unavailable_names and not no_response_names:
                    st.caption("None")
            
            # Warning if not everyone is available
            if selected_slot_option['unavailable'] > 0 or no_response_names:
                st.warning(f"⚠️ {selected_slot_option['unavailable'] + len(no_response_names)} participant(s) may not be able to attend this slot.")
            
            # Finalize button
            st.markdown("---")
            
            col_final1, col_final2 = st.columns([2, 1])
            
            with col_final1:
                confirm = st.checkbox(
                    f"I confirm I want to finalize the meeting for **{selected_slot_option['slot_str']}**",
                    key=f"confirm_finalize_{meeting_id}"
                )
            
            with col_final2:
                finalize_disabled = not confirm
                if st.button("Finalize This Slot", use_container_width=True, type="primary", disabled=finalize_disabled):
                    # Get the full slot datetime
                    selected_slot_obj = next(s for s in slots if s['id'] == selected_slot_id)
                    slot_dt = datetime.fromisoformat(selected_slot_obj['slot_datetime'])
                    final_slot_str = slot_dt.strftime('%A, %B %d, %Y at %I:%M %p')
                    
                    update_meeting_status(meeting_id, 'finalized', final_slot_str)
                    
                    # Notify all participants
                    base_url = get_base_url()
                    with st.spinner("Sending confirmations to all participants..."):
                        for p in participants:
                            response_url = f"{base_url}?token={p['token']}"
                            send_schedule_update(
                                participant_name=p['name'],
                                participant_email=p['email'],
                                meeting_title=selected_meeting['title'],
                                organizer_email=st.session_state.organizer_email,
                                response_url=response_url,
                                time_slots=[final_slot_str],
                                is_final=True
                            )
                    
                    st.success(f" Meeting finalized for: {final_slot_str}")
                    st.balloons()
                    st.rerun()


if __name__ == "__main__":
    st.set_page_config(page_title="Meeting Scheduler - Organizer", layout="wide")
    render_organizer_page()
