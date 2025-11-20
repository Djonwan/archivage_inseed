# app/models/file.py
from app import db
from datetime import datetime

class File(db.Model):
    __tablename__ = 'files'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(100))
    size = db.Column(db.Integer)
    visibility = db.Column(db.String(20), default='service')
    folder_id = db.Column(db.Integer, db.ForeignKey('folders.id'))
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # AJOUTÉ
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    deleted = db.Column(db.Boolean, default=False)

    # Relations
    owner = db.relationship('User', backref='uploaded_files')