# app/routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app import db
from werkzeug.utils import secure_filename
import os

auth_bp = Blueprint('auth', __name__, template_folder='templates/auth')

UPLOAD_PROFILE = os.path.join('app', 'static', 'img', 'profiles')


#route de login
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('drive.home'))

    if request.method == 'POST':
        email = request.form['email'].lower().strip()
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash("Votre compte est en attente de validation par un administrateur.", "warning")
                return redirect(url_for('auth.login'))
                
            login_user(user)
            user.last_login = db.func.now()
            db.session.commit()
            flash(f"Bienvenue, {user.name} !", "success")
            return redirect(url_for('drive.home'))
        else:
            flash("Email ou mot de passe incorrect.", "danger")

    return render_template('auth/login.html')



#route de enregistrement
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('drive.home'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')

        # === VALIDATIONS ===
        if not all([name, email, password, password_confirm]):
            flash("Tous les champs obligatoires doivent être remplis.", "danger")
            return redirect(url_for('auth.register'))

        if password != password_confirm:
            flash("Les deux mots de passe ne correspondent pas.", "danger")
            return redirect(url_for('auth.register'))

        if len(password) < 8:
            flash("Le mot de passe doit contenir au moins 8 caractères.", "danger")
            return redirect(url_for('auth.register'))

        if User.query.filter_by(email=email).first():
            flash("Cet email est déjà utilisé.", "danger")
            return redirect(url_for('auth.register'))

        # === GESTION PHOTO DE PROFIL ===
        filename = 'default.jpg'
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != '':
                if file.content_length > 5 * 1024 * 1024:  # 5 Mo max
                    flash("L'image est trop volumineuse (max 5 Mo).", "danger")
                    return redirect(url_for('auth.register'))
                
                filename = secure_filename(file.filename)
                # Optionnel : ajouter un UUID pour éviter les doublons
                import uuid
                ext = filename.rsplit('.', 1)[1] if '.' in filename else 'jpg'
                filename = f"{uuid.uuid4().hex}.{ext}"
                
                file.save(os.path.join(UPLOAD_PROFILE, filename))

        # === CRÉATION UTILISATEUR ===
        user = User(
            name=name,
            email=email,
            role='user',
            is_active=False,
            profile_picture=filename
        )
        user.set_password(password)  # ← on hash ici
        db.session.add(user)
        db.session.commit()

         # envoi email 
        from app.utils.email import send_new_user_notification_to_superadmin
        send_new_user_notification_to_superadmin(user)

        # notification
        from app.utils.email import create_new_registration_notification
        # Envoyer la notification interne aux super_admins
        create_new_registration_notification(user)

        # Optionnel : email aussi
        # from app.utils.email import send_new_user_notification_to_superadmin
        # send_new_user_notification_to_superadmin(user)

        flash("Votre compte a été créé avec succès ! Il est en attente de validation par un administrateur.", "success")
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


#route de deconnexion
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Déconnexion réussie.", "info")
    return redirect(url_for('auth.login'))