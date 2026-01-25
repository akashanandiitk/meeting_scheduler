"""
Email utilities for the Meeting Scheduler app.
Supports SMTP email sending with templates.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Dict, Tuple
import os


class EmailConfig:
    """Email configuration - can be set via environment variables or per-organizer config."""
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    FROM_EMAIL = os.getenv("FROM_EMAIL", "")
    FROM_NAME = os.getenv("FROM_NAME", "Meeting Scheduler")


def get_smtp_config(organizer_email: str = None) -> Dict:
    """
    Get SMTP configuration for an organizer.
    Falls back to environment variables if no organizer-specific config exists.
    """
    config = {
        "smtp_server": EmailConfig.SMTP_SERVER,
        "smtp_port": EmailConfig.SMTP_PORT,
        "smtp_username": EmailConfig.SMTP_USERNAME,
        "smtp_password": EmailConfig.SMTP_PASSWORD,
        "from_email": EmailConfig.FROM_EMAIL,
        "from_name": EmailConfig.FROM_NAME
    }
    
    if organizer_email:
        try:
            from auth import load_smtp_config
            organizer_config = load_smtp_config(organizer_email)
            if organizer_config:
                # Merge organizer config (overrides defaults)
                config.update({k: v for k, v in organizer_config.items() if v})
        except ImportError:
            pass  # auth module not available, use defaults
    
    return config


def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    plain_content: Optional[str] = None,
    smtp_config: Optional[Dict] = None
) -> bool:
    """
    Send an email using SMTP.
    Returns True if successful, False otherwise.
    """
    config = smtp_config or get_smtp_config()
    
    if not all([config.get("smtp_username"), config.get("smtp_password"), config.get("from_email")]):
        print(f"[EMAIL SIMULATION] To: {to_email}")
        print(f"[EMAIL SIMULATION] Subject: {subject}")
        print(f"[EMAIL SIMULATION] Content preview: {plain_content[:200] if plain_content else html_content[:200]}...")
        return True  # Simulate success for demo purposes
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{config.get('from_name', 'Meeting Scheduler')} <{config['from_email']}>"
        msg['To'] = to_email
        
        if plain_content:
            msg.attach(MIMEText(plain_content, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))
        
        with smtplib.SMTP(config['smtp_server'], config['smtp_port']) as server:
            server.starttls()
            server.login(config['smtp_username'], config['smtp_password'])
            server.send_message(msg)
        
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def send_test_email(to_email: str, smtp_config: Dict) -> Tuple[bool, str]:
    """
    Send a test email to verify SMTP configuration.
    Returns (success, message) tuple.
    """
    if not all([smtp_config.get("smtp_username"), smtp_config.get("smtp_password"), smtp_config.get("from_email")]):
        return False, "Please fill in all SMTP fields (server, username, password, from email)"
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "🧪 Meeting Scheduler - Test Email"
        msg['From'] = f"{smtp_config.get('from_name', 'Meeting Scheduler')} <{smtp_config['from_email']}>"
        msg['To'] = to_email
        
        html_content = """
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <div style="max-width: 500px; margin: 0 auto; background: #f8f9fa; padding: 30px; border-radius: 10px;">
                <h2 style="color: #667eea; margin-top: 0;">✅ Email Configuration Test</h2>
                <p>Congratulations! Your SMTP settings are working correctly.</p>
                <p>You can now send meeting invitations through the Meeting Scheduler.</p>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                <p style="color: #666; font-size: 12px;">This is a test email from Meeting Scheduler.</p>
            </div>
        </body>
        </html>
        """
        
        plain_content = """
Email Configuration Test

Congratulations! Your SMTP settings are working correctly.
You can now send meeting invitations through the Meeting Scheduler.

This is a test email from Meeting Scheduler.
        """
        
        msg.attach(MIMEText(plain_content, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))
        
        with smtplib.SMTP(smtp_config['smtp_server'], smtp_config['smtp_port']) as server:
            server.starttls()
            server.login(smtp_config['smtp_username'], smtp_config['smtp_password'])
            server.send_message(msg)
        
        return True, f"Test email sent successfully to {to_email}!"
    
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed. Check your username and password. For Gmail, use an App Password."
    except smtplib.SMTPConnectError:
        return False, f"Could not connect to {smtp_config['smtp_server']}:{smtp_config['smtp_port']}"
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def send_invitation_email(
    participant_name: str,
    participant_email: str,
    meeting_title: str,
    meeting_description: str,
    organizer_email: str,
    response_url: str,
    time_slots: List[str]
) -> bool:
    """Send a meeting invitation email to a participant."""
    
    # Get SMTP config for this organizer
    smtp_config = get_smtp_config(organizer_email)
    
    slots_html = "\n".join([f"<li>{slot}</li>" for slot in time_slots])
    slots_text = "\n".join([f"  • {slot}" for slot in time_slots])
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }}
            .btn {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            .btn:hover {{ background: #5a6fd6; }}
            .slots {{ background: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
            .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin: 0;">📅 Meeting Invitation</h1>
            </div>
            <div class="content">
                <p>Hello <strong>{participant_name}</strong>,</p>
                <p>You've been invited to participate in scheduling a meeting:</p>
                
                <h2 style="color: #667eea;">{meeting_title}</h2>
                <p>{meeting_description}</p>
                
                <div class="slots">
                    <h3 style="margin-top: 0;">Proposed Time Slots:</h3>
                    <ul>
                        {slots_html}
                    </ul>
                </div>
                
                <p>Please indicate your availability by clicking the button below:</p>
                
                <center>
                    <a href="{response_url}" class="btn">Respond to Invitation</a>
                </center>
                
                <p style="color: #666; font-size: 14px;">
                    Or copy this link: {response_url}
                </p>
                
                <div class="footer">
                    <p>Organized by: {organizer_email}</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    plain_content = f"""
Meeting Invitation

Hello {participant_name},

You've been invited to participate in scheduling a meeting:

{meeting_title}
{meeting_description}

Proposed Time Slots:
{slots_text}

Please indicate your availability by visiting:
{response_url}

Organized by: {organizer_email}
    """
    
    return send_email(
        to_email=participant_email,
        subject=f"📅 Meeting Invitation: {meeting_title}",
        html_content=html_content,
        plain_content=plain_content,
        smtp_config=smtp_config
    )


def send_response_notification(
    organizer_email: str,
    participant_name: str,
    meeting_title: str,
    meeting_id: str,
    base_url: str
) -> bool:
    """Send notification to organizer when a participant responds."""
    
    # Get SMTP config for the organizer
    smtp_config = get_smtp_config(organizer_email)
    
    dashboard_url = f"{base_url}?page=organizer&meeting_id={meeting_id}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .notification {{ background: #e8f5e9; border-left: 4px solid #4caf50; padding: 20px; border-radius: 5px; }}
            .btn {{ display: inline-block; background: #4caf50; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="notification">
                <h2 style="margin-top: 0; color: #2e7d32;">✅ New Response Received</h2>
                <p><strong>{participant_name}</strong> has responded to your meeting invitation:</p>
                <h3 style="color: #333;">{meeting_title}</h3>
                <a href="{dashboard_url}" class="btn">View Responses</a>
            </div>
        </div>
    </body>
    </html>
    """
    
    plain_content = f"""
New Response Received

{participant_name} has responded to your meeting invitation:
{meeting_title}

View responses at: {dashboard_url}
    """
    
    return send_email(
        to_email=organizer_email,
        subject=f"✅ Response: {participant_name} replied to {meeting_title}",
        html_content=html_content,
        plain_content=plain_content,
        smtp_config=smtp_config
    )


def send_schedule_update(
    participant_name: str,
    participant_email: str,
    meeting_title: str,
    organizer_email: str,
    response_url: str,
    time_slots: List[str],
    is_final: bool = False
) -> bool:
    """Send schedule update or final schedule to participant."""
    
    # Get SMTP config for the organizer
    smtp_config = get_smtp_config(organizer_email)
    
    if is_final:
        subject = f"✅ Final Schedule: {meeting_title}"
        header_text = "Meeting Confirmed"
        header_color = "#4caf50"
        message = "The meeting has been confirmed for the following time:"
    else:
        subject = f"📅 Updated Schedule: {meeting_title}"
        header_text = "Schedule Updated"
        header_color = "#ff9800"
        message = "The proposed time slots have been updated. Please review and indicate your availability:"
    
    slots_html = "\n".join([f"<li><strong>{slot}</strong></li>" for slot in time_slots])
    slots_text = "\n".join([f"  • {slot}" for slot in time_slots])
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: {header_color}; color: white; padding: 30px; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }}
            .btn {{ display: inline-block; background: {header_color}; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            .slots {{ background: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin: 0;">{"✅" if is_final else "📅"} {header_text}</h1>
            </div>
            <div class="content">
                <p>Hello <strong>{participant_name}</strong>,</p>
                <p>{message}</p>
                
                <h2 style="color: {header_color};">{meeting_title}</h2>
                
                <div class="slots">
                    <ul>
                        {slots_html}
                    </ul>
                </div>
                
                {"" if is_final else f'<center><a href="{response_url}" class="btn">Update Your Response</a></center>'}
                
                <p style="color: #666;">Organized by: {organizer_email}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    plain_content = f"""
{header_text}

Hello {participant_name},

{message}

{meeting_title}

{"Confirmed Time:" if is_final else "Updated Time Slots:"}
{slots_text}

{"" if is_final else f"Update your response at: {response_url}"}

Organized by: {organizer_email}
    """
    
    return send_email(
        to_email=participant_email,
        subject=subject,
        html_content=html_content,
        plain_content=plain_content,
        smtp_config=smtp_config
    )
