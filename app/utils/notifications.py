# app/utils/notifications.py
from app import db
from app.models.notification import Notification
from flask_login import current_user

def send_notification(user_id, title, message, url):
    """
    Envoie une notification à un utilisateur.
    """
    if not current_user.is_authenticated:
        return

    notif = Notification(
        user_id=user_id,
        title=title,
        message=message,
        url=url
    )
    db.session.add(notif)
    db.session.commit()