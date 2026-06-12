import os
import resend

resend.api_key = os.getenv("RESEND_API_KEY", "")

FROM_EMAIL = "LFG Tool <noreply@yourdomain.com>"  # update with your verified domain

def send_request_notification(target_email: str, requester_rank: str, requester_role: str, requester_wr: float, requester_notes: str):
    """Email sent to listing owner when someone requests to play with them."""
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": target_email,
            "subject": "🎮 Someone wants to play with you!",
            "html": f"""
            <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
                <h2 style="color: #C89B3C;">League LFG — New Request</h2>
                <p>Someone is looking for a teammate and wants to play with you!</p>
                <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                    <tr><td style="padding: 8px; color: #888;">Rank</td><td style="padding: 8px; font-weight: bold;">{requester_rank}</td></tr>
                    <tr style="background: #f9f9f9;"><td style="padding: 8px; color: #888;">Role</td><td style="padding: 8px;">{requester_role}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">Win Rate</td><td style="padding: 8px;">{requester_wr:.1f}%</td></tr>
                    <tr style="background: #f9f9f9;"><td style="padding: 8px; color: #888;">Notes</td><td style="padding: 8px;">{requester_notes or "None"}</td></tr>
                </table>
                <p>Run <code>python lfg.py requests</code> to approve or deny.</p>
                <p style="color: #888; font-size: 12px;">Your Riot ID will only be shared if you approve.</p>
            </div>
            """
        })
        return True
    except Exception as e:
        print(f"Email send failed: {e}")
        return False

def send_approval_email(requester_email: str, target_riot_id: str, target_rank: str, target_role: str):
    """Email sent to requester when their request is approved."""
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": requester_email,
            "subject": "✅ Your LFG request was approved!",
            "html": f"""
            <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
                <h2 style="color: #27AE60;">Request Approved!</h2>
                <p>Your teammate is ready to play. Here's their info:</p>
                <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                    <tr><td style="padding: 8px; color: #888;">Riot ID</td><td style="padding: 8px; font-weight: bold; font-size: 18px;">{target_riot_id}</td></tr>
                    <tr style="background: #f9f9f9;"><td style="padding: 8px; color: #888;">Rank</td><td style="padding: 8px;">{target_rank}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">Role</td><td style="padding: 8px;">{target_role}</td></tr>
                </table>
                <p>Add them on League and get in a game! Good luck 🎮</p>
            </div>
            """
        })
        return True
    except Exception as e:
        print(f"Email send failed: {e}")
        return False

def send_denial_email(requester_email: str):
    """Email sent to requester when their request is denied."""
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": requester_email,
            "subject": "❌ Your LFG request was declined",
            "html": """
            <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
                <h2 style="color: #E74C3C;">Request Declined</h2>
                <p>Your request was declined. No worries — keep browsing to find another teammate!</p>
                <p>Run <code>python lfg.py browse</code> to see more players.</p>
            </div>
            """
        })
        return True
    except Exception as e:
        print(f"Email send failed: {e}")
        return False

def send_approval_confirmation_to_owner(owner_email: str, requester_riot_id: str, requester_rank: str, requester_role: str):
    """Email sent to listing owner confirming they approved (gives them requester's ID too)."""
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": owner_email,
            "subject": "✅ Match confirmed — here's their Riot ID",
            "html": f"""
            <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
                <h2 style="color: #27AE60;">You approved a request!</h2>
                <p>Here's your teammate's info. Add them to get the game started:</p>
                <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                    <tr><td style="padding: 8px; color: #888;">Riot ID</td><td style="padding: 8px; font-weight: bold; font-size: 18px;">{requester_riot_id}</td></tr>
                    <tr style="background: #f9f9f9;"><td style="padding: 8px; color: #888;">Rank</td><td style="padding: 8px;">{requester_rank}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">Role</td><td style="padding: 8px;">{requester_role}</td></tr>
                </table>
                <p>Your listing has been marked as fulfilled. Good luck! 🎮</p>
            </div>
            """
        })
        return True
    except Exception as e:
        print(f"Email send failed: {e}")
        return False
