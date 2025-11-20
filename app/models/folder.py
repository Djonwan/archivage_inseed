# app/models/folder.py
from app import db
from datetime import datetime

# app/models/folder.py
class Folder(db.Model):
    __tablename__ = 'folders'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)  # ← C'EST TOUT
    description_folder = db.Column(db.Text)
    parent_id = db.Column(db.Integer, db.ForeignKey('folders.id'))
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_personal = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Ajoute cette colonne
    deleted = db.Column(db.Boolean, default=False)

    # Relations
    children = db.relationship('Folder', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    files = db.relationship('File', backref='folder', lazy='dynamic', cascade='all, delete-orphan')
    owner = db.relationship('User', backref='folders')