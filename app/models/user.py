# app/models/user.py
from flask_login import UserMixin
from app import db
from flask_bcrypt import Bcrypt
from flask import current_app

# On crée bcrypt ici ou dans __init__.py → on le fait proprement dans create_app()
bcrypt = None


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # ← 255 pour le hash
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)

    profile_picture = db.Column(db.String(255), default='default.jpg')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=db.func.now())
    last_login = db.Column(db.DateTime)

    created_users = db.relationship('User', remote_side=[id], backref='creator')

    def set_password(self, password):
        """Hash le mot de passe (utilisé à l'inscription et au changement)"""
        global bcrypt
        if bcrypt is None:
            bcrypt = Bcrypt(current_app)
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """Vérifie le mot de passe – compatible ancien (clair) et nouveau (hashé)"""
        global bcrypt
        if bcrypt is None:
            bcrypt = Bcrypt(current_app)

        # Si le mot de passe fait moins de 50 caractères → c’est du texte clair (ancien système)
        if len(self.password) < 50:
            if self.password == password:
                # Connexion OK → on profite pour HASHER le mot de passe en arrière-plan
                self.set_password(password)
                db.session.commit()
                return True
            return False

        # Sinon → c’est déjà hashé → vérification normale
        return bcrypt.check_password_hash(self.password, password)

    def is_super_admin(self):
        return self.role == 'super_admin'


# app/models/user.py → juste avant la classe User

from sqlalchemy import event
from sqlalchemy.orm import Session

@event.listens_for(User.password, 'set', retval=True)
def hash_password_on_set(target, value, oldvalue, initiator):
    """
    Intercepte TOUTE assignation à user.password
    Si la valeur n'est pas déjà un hash bcrypt (commence par $2b$), on la hashe
    """
    if value is None:
        return value

    # Si c'est déjà un hash bcrypt (commence par $2b$ ou $2a$ ou $2y$)
    if str(value).startswith(('$2a$', '$2b$', '$2y$')):
        return value

    # Sinon → c'est du texte clair → on hash
    global bcrypt
    if bcrypt is None:
        from flask import current_app
        bcrypt = Bcrypt(current_app)
    
    return bcrypt.generate_password_hash(value).decode('utf-8')