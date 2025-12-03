# app/models/favorite.py
from app import db
from datetime import datetime

class Favorite(db.Model):
    __tablename__ = 'favorites'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # LIGNE MAGIQUE QUI RÉSOUT TOUT
    file_id = db.Column(
        db.Integer,
        db.ForeignKey('files.id', ondelete='CASCADE'),  # ← Suppression en cascade côté base
        nullable=False
    )
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='user_favorites', passive_deletes=True)
    # backref 'file' est déjà défini dans File.file_favorites