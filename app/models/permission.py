# app/models/permission.py
from app import db


class FolderPermission(db.Model):
    __tablename__ = 'folder_permissions'
    id = db.Column(db.Integer, primary_key=True)
    folder_id = db.Column(db.Integer, db.ForeignKey('folders.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),  # ← CASCADE ici
        nullable=False
    )
    can_read = db.Column(db.Boolean, default=True)
    can_edit = db.Column(db.Boolean, default=False)
    can_delete = db.Column(db.Boolean, default=False)
    can_download = db.Column(db.Boolean, default=True)

    __table_args__ = (db.UniqueConstraint('folder_id', 'user_id', name='uq_folder_user'),)

    folder = db.relationship('Folder', backref=db.backref('permissions', cascade='all, delete-orphan'))
    user = db.relationship('User', backref='folder_permissions', passive_deletes=True)  # ← pas de cascade ici = OK