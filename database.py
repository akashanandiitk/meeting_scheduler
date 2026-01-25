"""
Database models and utilities for the Meeting Scheduler app.
Uses SQLite for persistence.
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
    
    # Participant groups (supersets like "Math Faculty")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS participant_groups (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Individual participants
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Group membership (many-to-many)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            group_id TEXT NOT NULL,
            participant_id TEXT NOT NULL,
            PRIMARY KEY (group_id, participant_id),
            FOREIGN KEY (group_id) REFERENCES participant_groups(id),
            FOREIGN KEY (participant_id) REFERENCES participants(id)
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
            participant_id TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            responded BOOLEAN DEFAULT FALSE,
            responded_at TIMESTAMP,
            PRIMARY KEY (meeting_id, participant_id),
            FOREIGN KEY (meeting_id) REFERENCES meetings(id),
            FOREIGN KEY (participant_id) REFERENCES participants(id)
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
            participant_id TEXT NOT NULL,
            slot_id TEXT NOT NULL,
            availability TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id),
            FOREIGN KEY (participant_id) REFERENCES participants(id),
            FOREIGN KEY (slot_id) REFERENCES time_slots(id)
        )
    """)
    
    # Alternative slots suggested by participants
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suggested_slots (
            id TEXT PRIMARY KEY,
            meeting_id TEXT NOT NULL,
            participant_id TEXT NOT NULL,
            suggested_datetime TEXT NOT NULL,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id),
            FOREIGN KEY (participant_id) REFERENCES participants(id)
        )
    """)
    
    conn.commit()
    conn.close()


# --- Participant Group Functions ---

def create_participant_group(name: str, description: str = "") -> str:
    """Create a new participant group."""
    conn = get_connection()
    cursor = conn.cursor()
    group_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO participant_groups (id, name, description) VALUES (?, ?, ?)",
        (group_id, name, description)
    )
    conn.commit()
    conn.close()
    return group_id


def get_all_groups() -> List[Dict]:
    """Get all participant groups."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM participant_groups ORDER BY name")
    groups = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return groups


def get_group_by_id(group_id: str) -> Optional[Dict]:
    """Get a group by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM participant_groups WHERE id = ?", (group_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_group(group_id: str):
    """Delete a participant group."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM group_members WHERE group_id = ?", (group_id,))
    cursor.execute("DELETE FROM participant_groups WHERE id = ?", (group_id,))
    conn.commit()
    conn.close()


# --- Participant Functions ---

def create_participant(name: str, email: str) -> str:
    """Create a new participant."""
    conn = get_connection()
    cursor = conn.cursor()
    participant_id = str(uuid.uuid4())
    try:
        cursor.execute(
            "INSERT INTO participants (id, name, email) VALUES (?, ?, ?)",
            (participant_id, name, email.lower())
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # Email already exists, get existing ID
        cursor.execute("SELECT id FROM participants WHERE email = ?", (email.lower(),))
        participant_id = cursor.fetchone()['id']
    conn.close()
    return participant_id


def get_participant_by_email(email: str) -> Optional[Dict]:
    """Get participant by email."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM participants WHERE email = ?", (email.lower(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_participants() -> List[Dict]:
    """Get all participants."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM participants ORDER BY name")
    participants = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return participants


def add_participant_to_group(participant_id: str, group_id: str):
    """Add a participant to a group."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO group_members (group_id, participant_id) VALUES (?, ?)",
            (group_id, participant_id)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Already a member
    conn.close()


def remove_participant_from_group(participant_id: str, group_id: str):
    """Remove a participant from a group."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM group_members WHERE group_id = ? AND participant_id = ?",
        (group_id, participant_id)
    )
    conn.commit()
    conn.close()


def get_group_members(group_id: str) -> List[Dict]:
    """Get all members of a group."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.* FROM participants p
        JOIN group_members gm ON p.id = gm.participant_id
        WHERE gm.group_id = ?
        ORDER BY p.name
    """, (group_id,))
    members = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return members


def get_participant_groups(participant_id: str) -> List[Dict]:
    """Get all groups a participant belongs to."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT pg.* FROM participant_groups pg
        JOIN group_members gm ON pg.id = gm.group_id
        WHERE gm.participant_id = ?
        ORDER BY pg.name
    """, (participant_id,))
    groups = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return groups


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
    """Get a meeting by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_meetings_by_organizer(organizer_email: str) -> List[Dict]:
    """Get all meetings for an organizer."""
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

def generate_token(meeting_id: str, participant_id: str) -> str:
    """Generate a unique token for a participant to respond to a meeting."""
    data = f"{meeting_id}:{participant_id}:{uuid.uuid4()}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


def add_meeting_participant(meeting_id: str, participant_id: str) -> str:
    """Add a participant to a meeting and generate their unique token."""
    conn = get_connection()
    cursor = conn.cursor()
    token = generate_token(meeting_id, participant_id)
    try:
        cursor.execute(
            "INSERT INTO meeting_participants (meeting_id, participant_id, token) VALUES (?, ?, ?)",
            (meeting_id, participant_id, token)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # Already added, get existing token
        cursor.execute(
            "SELECT token FROM meeting_participants WHERE meeting_id = ? AND participant_id = ?",
            (meeting_id, participant_id)
        )
        token = cursor.fetchone()['token']
    conn.close()
    return token


def get_meeting_participants(meeting_id: str) -> List[Dict]:
    """Get all participants for a meeting with their response status."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, mp.token, mp.responded, mp.responded_at
        FROM participants p
        JOIN meeting_participants mp ON p.id = mp.participant_id
        WHERE mp.meeting_id = ?
        ORDER BY p.name
    """, (meeting_id,))
    participants = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return participants


def get_participant_by_token(token: str) -> Optional[Dict]:
    """Get participant and meeting info by token."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, mp.meeting_id, mp.responded, m.title as meeting_title, 
               m.description as meeting_description, m.status as meeting_status,
               m.organizer_email, m.finalized_slot
        FROM participants p
        JOIN meeting_participants mp ON p.id = mp.participant_id
        JOIN meetings m ON mp.meeting_id = m.id
        WHERE mp.token = ?
    """, (token,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def mark_participant_responded(meeting_id: str, participant_id: str):
    """Mark a participant as having responded."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE meeting_participants 
        SET responded = TRUE, responded_at = CURRENT_TIMESTAMP
        WHERE meeting_id = ? AND participant_id = ?
    """, (meeting_id, participant_id))
    conn.commit()
    conn.close()


# --- Response Functions ---

def save_response(meeting_id: str, participant_id: str, slot_id: str, availability: str) -> str:
    """Save or update a participant's response for a time slot."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if response exists
    cursor.execute("""
        SELECT id FROM responses 
        WHERE meeting_id = ? AND participant_id = ? AND slot_id = ?
    """, (meeting_id, participant_id, slot_id))
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute("""
            UPDATE responses SET availability = ?, created_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (availability, existing['id']))
        response_id = existing['id']
    else:
        response_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO responses (id, meeting_id, participant_id, slot_id, availability)
            VALUES (?, ?, ?, ?, ?)
        """, (response_id, meeting_id, participant_id, slot_id, availability))
    
    conn.commit()
    conn.close()
    return response_id


def get_responses_for_meeting(meeting_id: str) -> List[Dict]:
    """Get all responses for a meeting."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*, p.name as participant_name, p.email as participant_email,
               ts.slot_datetime, ts.duration_minutes
        FROM responses r
        JOIN participants p ON r.participant_id = p.id
        JOIN time_slots ts ON r.slot_id = ts.id
        WHERE r.meeting_id = ?
        ORDER BY ts.slot_datetime, p.name
    """, (meeting_id,))
    responses = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return responses


def get_participant_responses(meeting_id: str, participant_id: str) -> List[Dict]:
    """Get a participant's responses for a meeting."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*, ts.slot_datetime, ts.duration_minutes
        FROM responses r
        JOIN time_slots ts ON r.slot_id = ts.id
        WHERE r.meeting_id = ? AND r.participant_id = ?
        ORDER BY ts.slot_datetime
    """, (meeting_id, participant_id))
    responses = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return responses


# --- Suggested Slots Functions ---

def add_suggested_slot(meeting_id: str, participant_id: str, suggested_datetime: str, note: str = "") -> str:
    """Add a suggested alternative slot from a participant."""
    conn = get_connection()
    cursor = conn.cursor()
    slot_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO suggested_slots (id, meeting_id, participant_id, suggested_datetime, note)
        VALUES (?, ?, ?, ?, ?)
    """, (slot_id, meeting_id, participant_id, suggested_datetime, note))
    conn.commit()
    conn.close()
    return slot_id


def get_suggested_slots(meeting_id: str) -> List[Dict]:
    """Get all suggested slots for a meeting."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ss.*, p.name as participant_name, p.email as participant_email
        FROM suggested_slots ss
        JOIN participants p ON ss.participant_id = p.id
        WHERE ss.meeting_id = ?
        ORDER BY ss.suggested_datetime
    """, (meeting_id,))
    slots = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return slots


# Initialize database on import
init_db()
