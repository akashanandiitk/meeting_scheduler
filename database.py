"""
Database models and utilities for the Meeting Scheduler app.
Uses SQLite for persistence.

Schema Design:
- Each organizer has their own private contact list
- Contacts can be organized into groups (owned by organizer)
- Groups can optionally be shared with other organizers
- Full CRUD operations for contacts and groups
"""

import sqlite3
import json
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

DB_PATH = Path(__file__).parent / "meetings.db"


def get_connection():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Contacts (private to each organizer)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id TEXT PRIMARY KEY,
            owner_email TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(owner_email, email)
        )
    """)
    
    # Contact groups (owned by organizer)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contact_groups (
            id TEXT PRIMARY KEY,
            owner_email TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            is_shared BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Group membership (many-to-many)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            group_id TEXT NOT NULL,
            contact_id TEXT NOT NULL,
            PRIMARY KEY (group_id, contact_id),
            FOREIGN KEY (group_id) REFERENCES contact_groups(id),
            FOREIGN KEY (contact_id) REFERENCES contacts(id)
        )
    """)
    
    # Shared groups (which organizers have access to shared groups)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shared_groups (
            group_id TEXT NOT NULL,
            shared_with_email TEXT NOT NULL,
            shared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (group_id, shared_with_email),
            FOREIGN KEY (group_id) REFERENCES contact_groups(id)
        )
    """)
    
    # Meetings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meetings (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            organizer_email TEXT NOT NULL,
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finalized_slot TEXT
        )
    """)
    
    # Meeting participants (subset for specific meeting)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meeting_participants (
            meeting_id TEXT NOT NULL,
            contact_id TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            responded BOOLEAN DEFAULT FALSE,
            responded_at TIMESTAMP,
            PRIMARY KEY (meeting_id, contact_id),
            FOREIGN KEY (meeting_id) REFERENCES meetings(id),
            FOREIGN KEY (contact_id) REFERENCES contacts(id)
        )
    """)
    
    # Proposed time slots
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS time_slots (
            id TEXT PRIMARY KEY,
            meeting_id TEXT NOT NULL,
            slot_datetime TEXT NOT NULL,
            duration_minutes INTEGER DEFAULT 60,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id)
        )
    """)
    
    # Participant responses
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS responses (
            id TEXT PRIMARY KEY,
            meeting_id TEXT NOT NULL,
            contact_id TEXT NOT NULL,
            slot_id TEXT NOT NULL,
            availability TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id),
            FOREIGN KEY (contact_id) REFERENCES contacts(id),
            FOREIGN KEY (slot_id) REFERENCES time_slots(id)
        )
    """)
    
    # Alternative slots suggested by participants
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suggested_slots (
            id TEXT PRIMARY KEY,
            meeting_id TEXT NOT NULL,
            contact_id TEXT NOT NULL,
            suggested_datetime TEXT NOT NULL,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id),
            FOREIGN KEY (contact_id) REFERENCES contacts(id)
        )
    """)
    
    conn.commit()
    conn.close()


# Initialize database on module load
init_db()


# --- Contact Functions ---

def create_contact(owner_email: str, name: str, email: str) -> str:
    """Create a new contact for an organizer."""
    conn = get_connection()
    cursor = conn.cursor()
    contact_id = str(uuid.uuid4())
    try:
        cursor.execute(
            "INSERT INTO contacts (id, owner_email, name, email) VALUES (?, ?, ?, ?)",
            (contact_id, owner_email.lower(), name, email.lower())
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # Contact already exists for this organizer, get existing ID
        cursor.execute(
            "SELECT id FROM contacts WHERE owner_email = ? AND email = ?",
            (owner_email.lower(), email.lower())
        )
        row = cursor.fetchone()
        contact_id = row['id'] if row else None
    conn.close()
    return contact_id


def get_contact_by_id(contact_id: str) -> Optional[Dict]:
    """Get contact by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_contacts_by_owner(owner_email: str) -> List[Dict]:
    """Get all contacts for an organizer."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM contacts WHERE owner_email = ? ORDER BY name",
        (owner_email.lower(),)
    )
    contacts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return contacts


def update_contact(contact_id: str, name: str, email: str) -> bool:
    """Update a contact's details."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE contacts SET name = ?, email = ? WHERE id = ?",
            (name, email.lower(), contact_id)
        )
        conn.commit()
        success = cursor.rowcount > 0
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success


def delete_contact(contact_id: str) -> bool:
    """Delete a contact and remove from all groups."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Remove from groups first
    cursor.execute("DELETE FROM group_members WHERE contact_id = ?", (contact_id,))
    
    # Delete the contact
    cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


def contact_in_use(contact_id: str) -> List[Dict]:
    """Check if contact is used in any meetings. Returns list of meetings."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.id, m.title, m.status 
        FROM meetings m
        JOIN meeting_participants mp ON m.id = mp.meeting_id
        WHERE mp.contact_id = ?
    """, (contact_id,))
    meetings = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return meetings


# --- Contact Group Functions ---

def create_contact_group(owner_email: str, name: str, description: str = "") -> str:
    """Create a new contact group."""
    conn = get_connection()
    cursor = conn.cursor()
    group_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO contact_groups (id, owner_email, name, description) VALUES (?, ?, ?, ?)",
        (group_id, owner_email.lower(), name, description)
    )
    conn.commit()
    conn.close()
    return group_id


def get_groups_by_owner(owner_email: str, include_shared: bool = True) -> List[Dict]:
    """Get all groups owned by or shared with an organizer."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get owned groups
    cursor.execute(
        "SELECT *, 'owned' as access_type FROM contact_groups WHERE owner_email = ? ORDER BY name",
        (owner_email.lower(),)
    )
    groups = [dict(row) for row in cursor.fetchall()]
    
    if include_shared:
        # Get groups shared with this organizer
        cursor.execute("""
            SELECT cg.*, 'shared' as access_type, cg.owner_email as shared_by
            FROM contact_groups cg
            JOIN shared_groups sg ON cg.id = sg.group_id
            WHERE sg.shared_with_email = ? AND cg.is_shared = 1
            ORDER BY cg.name
        """, (owner_email.lower(),))
        shared = [dict(row) for row in cursor.fetchall()]
        groups.extend(shared)
    
    conn.close()
    return groups


def get_group_by_id(group_id: str) -> Optional[Dict]:
    """Get group by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contact_groups WHERE id = ?", (group_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_group(group_id: str, name: str, description: str) -> bool:
    """Update a group's details."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE contact_groups SET name = ?, description = ? WHERE id = ?",
        (name, description, group_id)
    )
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


def delete_group(group_id: str) -> bool:
    """Delete a group and its memberships."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Remove memberships
    cursor.execute("DELETE FROM group_members WHERE group_id = ?", (group_id,))
    
    # Remove sharing
    cursor.execute("DELETE FROM shared_groups WHERE group_id = ?", (group_id,))
    
    # Delete group
    cursor.execute("DELETE FROM contact_groups WHERE id = ?", (group_id,))
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


# --- Group Membership Functions ---

def add_contact_to_group(contact_id: str, group_id: str) -> bool:
    """Add a contact to a group."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO group_members (group_id, contact_id) VALUES (?, ?)",
            (group_id, contact_id)
        )
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False  # Already a member
    conn.close()
    return success


def remove_contact_from_group(contact_id: str, group_id: str) -> bool:
    """Remove a contact from a group."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM group_members WHERE group_id = ? AND contact_id = ?",
        (group_id, contact_id)
    )
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


def get_group_members(group_id: str) -> List[Dict]:
    """Get all contacts in a group."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.* FROM contacts c
        JOIN group_members gm ON c.id = gm.contact_id
        WHERE gm.group_id = ?
        ORDER BY c.name
    """, (group_id,))
    members = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return members


def get_contact_groups(contact_id: str) -> List[Dict]:
    """Get all groups a contact belongs to."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT cg.* FROM contact_groups cg
        JOIN group_members gm ON cg.id = gm.group_id
        WHERE gm.contact_id = ?
        ORDER BY cg.name
    """, (contact_id,))
    groups = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return groups


# --- Group Sharing Functions ---

def set_group_shared(group_id: str, is_shared: bool) -> bool:
    """Set whether a group is shared."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE contact_groups SET is_shared = ? WHERE id = ?",
        (1 if is_shared else 0, group_id)
    )
    
    # If unsharing, remove all shares
    if not is_shared:
        cursor.execute("DELETE FROM shared_groups WHERE group_id = ?", (group_id,))
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


def share_group_with(group_id: str, shared_with_email: str) -> bool:
    """Share a group with another organizer."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # First ensure group is marked as shared
    cursor.execute(
        "UPDATE contact_groups SET is_shared = 1 WHERE id = ?",
        (group_id,)
    )
    
    try:
        cursor.execute(
            "INSERT INTO shared_groups (group_id, shared_with_email) VALUES (?, ?)",
            (group_id, shared_with_email.lower())
        )
        success = True
    except sqlite3.IntegrityError:
        success = False  # Already shared
    
    conn.commit()
    conn.close()
    return success


def unshare_group_with(group_id: str, shared_with_email: str) -> bool:
    """Remove sharing of a group with an organizer."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM shared_groups WHERE group_id = ? AND shared_with_email = ?",
        (group_id, shared_with_email.lower())
    )
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


def get_group_shares(group_id: str) -> List[str]:
    """Get list of emails the group is shared with."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT shared_with_email FROM shared_groups WHERE group_id = ?",
        (group_id,)
    )
    shares = [row['shared_with_email'] for row in cursor.fetchall()]
    conn.close()
    return shares


# --- Meeting Functions ---

def create_meeting(title: str, description: str, organizer_email: str) -> str:
    """Create a new meeting."""
    conn = get_connection()
    cursor = conn.cursor()
    meeting_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO meetings (id, title, description, organizer_email) VALUES (?, ?, ?, ?)",
        (meeting_id, title, description, organizer_email.lower())
    )
    conn.commit()
    conn.close()
    return meeting_id


def get_meeting_by_id(meeting_id: str) -> Optional[Dict]:
    """Get meeting by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_meetings_by_organizer(organizer_email: str) -> List[Dict]:
    """Get all meetings by an organizer."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM meetings WHERE organizer_email = ? ORDER BY created_at DESC",
        (organizer_email.lower(),)
    )
    meetings = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return meetings


def update_meeting_status(meeting_id: str, status: str, finalized_slot: str = None):
    """Update meeting status."""
    conn = get_connection()
    cursor = conn.cursor()
    if finalized_slot:
        cursor.execute(
            "UPDATE meetings SET status = ?, finalized_slot = ? WHERE id = ?",
            (status, finalized_slot, meeting_id)
        )
    else:
        cursor.execute(
            "UPDATE meetings SET status = ? WHERE id = ?",
            (status, meeting_id)
        )
    conn.commit()
    conn.close()


def delete_meeting(meeting_id: str):
    """Delete a meeting and all related data."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM responses WHERE meeting_id = ?", (meeting_id,))
    cursor.execute("DELETE FROM suggested_slots WHERE meeting_id = ?", (meeting_id,))
    cursor.execute("DELETE FROM time_slots WHERE meeting_id = ?", (meeting_id,))
    cursor.execute("DELETE FROM meeting_participants WHERE meeting_id = ?", (meeting_id,))
    cursor.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
    conn.commit()
    conn.close()


# --- Time Slot Functions ---

def add_time_slot(meeting_id: str, slot_datetime: str, duration_minutes: int = 60) -> str:
    """Add a time slot to a meeting."""
    conn = get_connection()
    cursor = conn.cursor()
    slot_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO time_slots (id, meeting_id, slot_datetime, duration_minutes) VALUES (?, ?, ?, ?)",
        (slot_id, meeting_id, slot_datetime, duration_minutes)
    )
    conn.commit()
    conn.close()
    return slot_id


def get_meeting_slots(meeting_id: str) -> List[Dict]:
    """Get all time slots for a meeting."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM time_slots WHERE meeting_id = ? ORDER BY slot_datetime",
        (meeting_id,)
    )
    slots = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return slots


def delete_time_slot(slot_id: str):
    """Delete a time slot."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM responses WHERE slot_id = ?", (slot_id,))
    cursor.execute("DELETE FROM time_slots WHERE id = ?", (slot_id,))
    conn.commit()
    conn.close()


# --- Meeting Participant Functions ---

def add_meeting_participant(meeting_id: str, contact_id: str) -> str:
    """Add a participant to a meeting."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Generate unique token
    token_data = f"{meeting_id}:{contact_id}:{datetime.now().isoformat()}"
    token = hashlib.sha256(token_data.encode()).hexdigest()[:32]
    
    try:
        cursor.execute(
            "INSERT INTO meeting_participants (meeting_id, contact_id, token) VALUES (?, ?, ?)",
            (meeting_id, contact_id, token)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # Already added, get existing token
        cursor.execute(
            "SELECT token FROM meeting_participants WHERE meeting_id = ? AND contact_id = ?",
            (meeting_id, contact_id)
        )
        token = cursor.fetchone()['token']
    conn.close()
    return token


def get_meeting_participants(meeting_id: str) -> List[Dict]:
    """Get all participants for a meeting with their response status."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, mp.token, mp.responded, mp.responded_at
        FROM contacts c
        JOIN meeting_participants mp ON c.id = mp.contact_id
        WHERE mp.meeting_id = ?
        ORDER BY c.name
    """, (meeting_id,))
    participants = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return participants


def get_participant_by_token(token: str) -> Optional[Dict]:
    """Get participant and meeting info by token."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, mp.meeting_id, mp.responded, m.title as meeting_title, 
               m.description as meeting_description, m.status as meeting_status,
               m.organizer_email, m.finalized_slot
        FROM contacts c
        JOIN meeting_participants mp ON c.id = mp.contact_id
        JOIN meetings m ON mp.meeting_id = m.id
        WHERE mp.token = ?
    """, (token,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def mark_participant_responded(meeting_id: str, contact_id: str):
    """Mark a participant as having responded."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE meeting_participants SET responded = 1, responded_at = ? WHERE meeting_id = ? AND contact_id = ?",
        (datetime.now().isoformat(), meeting_id, contact_id)
    )
    conn.commit()
    conn.close()


# --- Response Functions ---

def save_response(meeting_id: str, contact_id: str, slot_id: str, availability: str):
    """Save or update a participant's response for a slot."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if response exists
    cursor.execute(
        "SELECT id FROM responses WHERE meeting_id = ? AND contact_id = ? AND slot_id = ?",
        (meeting_id, contact_id, slot_id)
    )
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute(
            "UPDATE responses SET availability = ?, created_at = ? WHERE id = ?",
            (availability, datetime.now().isoformat(), existing['id'])
        )
    else:
        response_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO responses (id, meeting_id, contact_id, slot_id, availability) VALUES (?, ?, ?, ?, ?)",
            (response_id, meeting_id, contact_id, slot_id, availability)
        )
    
    conn.commit()
    conn.close()


def get_responses_for_meeting(meeting_id: str) -> List[Dict]:
    """Get all responses for a meeting."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*, c.name as participant_name, c.email as participant_email
        FROM responses r
        JOIN contacts c ON r.contact_id = c.id
        WHERE r.meeting_id = ?
    """, (meeting_id,))
    responses = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return responses


def get_participant_responses(meeting_id: str, contact_id: str) -> List[Dict]:
    """Get a specific participant's responses for a meeting."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM responses WHERE meeting_id = ? AND contact_id = ?",
        (meeting_id, contact_id)
    )
    responses = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return responses


# --- Suggested Slot Functions ---

def add_suggested_slot(meeting_id: str, contact_id: str, suggested_datetime: str, note: str = None) -> str:
    """Add an alternative slot suggestion."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Remove any previous suggestion from this participant
    cursor.execute(
        "DELETE FROM suggested_slots WHERE meeting_id = ? AND contact_id = ?",
        (meeting_id, contact_id)
    )
    
    slot_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO suggested_slots (id, meeting_id, contact_id, suggested_datetime, note) VALUES (?, ?, ?, ?, ?)",
        (slot_id, meeting_id, contact_id, suggested_datetime, note)
    )
    conn.commit()
    conn.close()
    return slot_id


def get_suggested_slots(meeting_id: str) -> List[Dict]:
    """Get all suggested alternative slots for a meeting."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ss.*, c.name as participant_name, c.email as participant_email
        FROM suggested_slots ss
        JOIN contacts c ON ss.contact_id = c.id
        WHERE ss.meeting_id = ?
        ORDER BY ss.suggested_datetime
    """, (meeting_id,))
    suggestions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return suggestions
