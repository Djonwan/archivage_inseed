# app/models/activity.py
from app import db
from datetime import datetime

class Activity(db.Model):
    __tablename__ = 'activities'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'))
    folder_id = db.Column(db.Integer, db.ForeignKey('folders.id'))
    action = db.Column(db.String(50), nullable=False)  # created, uploaded, renamed, opened, downloaded
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User')
    file = db.relationship('File')
    folder = db.relationship('Folder')