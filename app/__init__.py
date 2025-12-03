# app/__init__.py
from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from config import Config
import os
from flask_bcrypt import Bcrypt

# === CRÉER LES OBJETS ===
db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()


login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # === AJOUT DE BCRYPT ===
    bcrypt = Bcrypt(app)  # ← Ligne magique
    app.bcrypt = bcrypt   # On l'attache à l'app pour accès global si besoin

    # === CRÉER LE DOSSIER UPLOADS À LA RACINE ===
    upload_folder = app.config['UPLOAD_FOLDER']
    print(f"Chemin d'upload configuré : {upload_folder}")

    if not os.path.exists(upload_folder):
        print(f"Création du dossier : {upload_folder}")
        os.makedirs(upload_folder, exist_ok=True)
    else:
        print(f"Dossier déjà existant : {upload_folder}")

    # === IMPORTER User ===
    from app.models.user import User

    # === INIT DB, LOGIN MANAGER ET MAIL ===
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    # === USER LOADER ===
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # === FILTRE filesizeformat ===
    @app.template_filter('filesizeformat')
    def filesizeformat(value):
        if not value:
            return "0 o"
        for unit in ['o', 'Ko', 'Mo', 'Go']:
            if value < 1024:
                return f"{value:.1f} {unit}".replace('.0', '')
            value /= 1024
        return f"{value:.1f} To"

    # === EXPOSER LA FONCTION BREADCRUMB DANS LES TEMPLATES ===
    from app.routes.drive import get_folder_breadcrumb
    app.jinja_env.globals['get_folder_breadcrumb'] = get_folder_breadcrumb

    # === ROUTE D’ACCUEIL ===
    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    # === INJECTER user_can DANS JINJA ===
    @app.context_processor
    def inject_user_can():
        from app.routes.drive import user_can
        return dict(user_can=user_can)

    # === INJECTER NOTIFICATIONS DANS TOUTES LES PAGES (CLOCHE) ===
    @app.context_processor
    def inject_notifications():
        from app.models.notification import Notification
        from flask_login import current_user
        if current_user.is_authenticated:
            unread_count = Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False
            ).count()
            notifications = Notification.query.filter_by(
                user_id=current_user.id
            ).order_by(Notification.created_at.desc()).limit(5).all()
        else:
            unread_count = 0
            notifications = []
        return dict(unread_count=unread_count, notifications=notifications)
    
    # === FILTRE endswith (pour tester l'extension) ===
    @app.template_filter('endswith')
    def endswith_filter(value, suffix):
        return str(value).lower().endswith(suffix.lower()) if value else False
    

    # === BLUEPRINTS ===
    from .routes.auth import auth_bp
    from .routes.dashboard import dashboard_bp
    from .routes.admin import admin_bp
    from .routes.drive import drive_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(drive_bp, url_prefix='/drive')

    return app


