# app/models/user.py
from flask_login import UserMixin
from app import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)  # ← on garde en clair pour l'instant
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # user | admin | super_admin

    # === AJOUT PHOTO DE PROFIL ===
    profile_picture = db.Column(db.String(255), default='default.jpg')

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=db.func.now())
    last_login = db.Column(db.DateTime)

    # Relation
    created_users = db.relationship('User', remote_side=[id], backref='creator')

    # === MÉTHODES QU'ON GARDE COMME ÇA ===
    def set_password(self, password):
        self.password = password

    def check_password(self, password):
        return self.password == password

    # === NOUVELLE MÉTHODE ===
    def is_super_admin(self):
        return self.role == 'super_admin'