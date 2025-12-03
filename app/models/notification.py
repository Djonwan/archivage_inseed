# app/models/notification.py
from app import db
from datetime import datetime

class Notification(db.Model):
    __tablename__ = 'notifications'
   
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref='notifications', passive_deletes=True)

    def mark_as_read(self):
        self.is_read = True
        db.session.commit()