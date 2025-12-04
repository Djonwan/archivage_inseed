# app/routes/admin.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify,current_app
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from werkzeug.utils import secure_filename
import os
from app.models.folder import Folder
from app.models.file import File
from app.models.favorite import Favorite
from app.models.permission import FolderPermission
from app.models.user import User
from app.models.notification import Notification
from app.models.activity import Activity

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

UPLOAD_PROFILE = os.path.join('app', 'static', 'img', 'profiles')

@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
def create_user():
    if not current_user.is_super_admin():
        flash("Accès refusé.", "danger")
        return redirect(url_for('drive.home'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')

        if not all([name, email, password, role]):
            flash("Tous les champs sont obligatoires.", "danger")
            return redirect(url_for('admin.create_user'))

        if User.query.filter_by(email=email).first():
            flash("Cet email existe déjà.", "danger")
            return redirect(url_for('admin.create_user'))

        # Gestion de la photo
        filename = 'default.jpg'
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join(UPLOAD_PROFILE, filename))

        user = User(
            name=name,
            email=email,
            role=role,
            profile_picture=filename,
            created_by=current_user.id
        )
        user.set_password(password) 
        db.session.add(user)
        db.session.commit()

        flash(f"Utilisateur {name} créé avec succès !", "success")
        return redirect(url_for('drive.home'))

    return render_template('admin/create_user.html')



@admin_bp.route('/users')
@login_required
def list_users():
    if not current_user.is_super_admin():
        flash("Accès refusé.", "danger")
        return redirect(url_for('drive.home'))
    
    users = User.query.all()
    return render_template('admin/users_list.html', users=users)




# @admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
# @login_required
# def edit_user(user_id):
#     if not current_user.is_super_admin():
#         flash("Accès refusé.", "danger")
#         return redirect(url_for('drive.home'))

#     user = User.query.get_or_404(user_id)

#     if request.method == 'POST':
#         user.name = request.form['name']
#         user.email = request.form['email']
#         user.role = request.form['role']

#         # Gestion de la photo
#         if 'profile_picture' in request.files:
#             file = request.files['profile_picture']
#             if file and file.filename != '':
#                 filename = secure_filename(file.filename)
#                 file.save(os.path.join(UPLOAD_PROFILE, filename))
#                 user.profile_picture = filename

#         db.session.commit()
#         flash(f"Utilisateur {user.name} modifié avec succès !", "success")
#         return redirect(url_for('admin.list_users'))

#     return render_template('admin/edit_user.html', user=user)

# app/routes/admin.py → dans edit_user()

@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if not current_user.is_super_admin():
        flash("Accès refusé.", "danger")
        return redirect(url_for('drive.home'))

    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        user.name = request.form['name'].strip()
        user.email = request.form['email'].lower().strip()
        user.role = request.form['role']

        # === CHANGEMENT DE MOT DE PASSE (optionnel) ===
        new_password = request.form.get('new_password')
        password_confirm = request.form.get('password_confirm')

        if new_password or password_confirm:
            if new_password != password_confirm:
                flash("Les deux mots de passe ne correspondent pas.", "danger")
                return render_template('admin/edit_user.html', user=user)

            if len(new_password) < 8:
                flash("Le mot de passe doit faire au moins 8 caractères.", "danger")
                return render_template('admin/edit_user.html', user=user)

            user.set_password(new_password)  # ← HACHÉ AUTOMATIQUEMENT
            flash("Mot de passe mis à jour avec succès.", "success")

        # === PHOTO DE PROFIL ===
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != '':
                # Supprimer l'ancienne photo si ce n'est pas default.jpg
                if user.profile_picture and user.profile_picture != 'default.jpg':
                    try:
                        os.remove(os.path.join(UPLOAD_PROFILE, user.profile_picture))
                    except:
                        pass

                filename = secure_filename(file.filename)
                import uuid
                ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
                filename = f"{uuid.uuid4().hex}.{ext}"
                file.save(os.path.join(UPLOAD_PROFILE, filename))
                user.profile_picture = filename

        db.session.commit()
        flash(f"Utilisateur {user.name} modifié avec succès !", "success")
        return redirect(url_for('admin.list_users'))

    return render_template('admin/edit_user.html', user=user)




# @admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
# @login_required
# def delete_user(user_id):
#     if not current_user.is_super_admin():
#         return jsonify(success=False, message="Accès refusé"), 403

#     user = User.query.get_or_404(user_id)

#     if user.id == current_user.id:
#         return jsonify(success=False, message="Impossible de vous supprimer vous-même"), 400

#     if user.is_super_admin() and User.query.filter_by(role='super_admin', is_active=True).count() <= 1:
#         return jsonify(success=False, message="Impossible de supprimer le dernier super admin"), 400

#     # === LA LIGNE QUI TUE TOUTES LES ERREURS À JAMAIS ===
#     db.session.execute(db.text("DELETE FROM folder_permissions WHERE user_id = :uid"), {"uid": user.id})
#     db.session.execute(db.text("DELETE FROM favorites WHERE user_id = :uid"), {"uid": user.id})
#     db.session.execute(db.text("DELETE FROM notifications WHERE user_id = :uid"), {"uid": user.id})
#     db.session.execute(db.text("DELETE FROM activities WHERE user_id = :uid"), {"uid": user.id})
#     db.session.execute(db.text("DELETE FROM folders WHERE owner_id = :uid"), {"uid": user.id})

#     # Photo de profil
#     if user.profile_picture and user.profile_picture != 'default.jpg':
#         path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles', user.profile_picture)
#         if os.path.exists(path):
#             os.remove(path)

#     # Maintenant on supprime l'utilisateur → plus rien ne bloque
#     db.session.delete(user)
#     db.session.commit()

#     return jsonify(success=True, message=f"Utilisateur {user.name} supprimé avec succès")


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_super_admin():
        return jsonify(success=False, message="Accès refusé"), 403

    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        return jsonify(success=False, message="Impossible de vous supprimer vous-même"), 400

    if user.is_super_admin() and User.query.filter_by(role='super_admin', is_active=True).count() <= 1:
        return jsonify(success=False, message="Impossible de supprimer le dernier super admin"), 400

    # Récupère le super admin qui va tout récupérer
    new_owner = User.query.filter(
        User.role == 'super_admin',
        User.is_active == True,
        User.id != user.id
    ).first()

    if not new_owner:
        return jsonify(success=False, message="Aucun super admin disponible"), 400

    # 1. Transfert des dossiers (propriété)
    db.session.query(Folder).filter(Folder.owner_id == user.id).update(
        {"owner_id": new_owner.id},
        synchronize_session=False
    )

    # 2. Transfert des fichiers uploadés par cet utilisateur
    db.session.query(File).filter(File.owner_id == user.id).update(
        {"owner_id": new_owner.id},
        synchronize_session=False
    )

    # 3. Nettoyage des données personnelles
    FolderPermission.query.filter_by(user_id=user.id).delete()
    Favorite.query.filter_by(user_id=user.id).delete()
    Notification.query.filter_by(user_id=user.id).delete()
    Activity.query.filter_by(user_id=user.id).delete()

    # 4. Photo de profil
    if user.profile_picture and user.profile_picture != 'default.jpg':
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles', user.profile_picture)
        if os.path.exists(path):
            try:
                os.remove(path)
            except:
                pass

    # 5. Suppression finale
    db.session.delete(user)
    db.session.commit()

    return jsonify(
        success=True,
        message=f"Utilisateur {user.name} supprimé avec succès.<br>"
                f"Tous ses dossiers et fichiers appartiennent désormais à <strong>{new_owner.name}</strong>."
    )




@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
def toggle_user_active(user_id):
    if not current_user.is_super_admin():
        return jsonify(success=False, message="Accès refusé"), 403

    user = User.query.get_or_404(user_id)

    # Optionnel : empêcher de désactiver le dernier super_admin
    if user.is_super_admin() and user.is_active:
        active_super_admins = User.query.filter_by(role='super_admin', is_active=True).count()
        if active_super_admins <= 1:
            return jsonify(success=False, message="Impossible de désactiver le dernier super admin !"), 400

    user.is_active = not user.is_active
    db.session.commit()

    action = "activé" if user.is_active else "désactivé"
    return jsonify(
        success=True,
        message=f"Compte de {user.name} {action} avec succès",
        is_active=user.is_active
    )




# la route d un petit stat 
@admin_bp.route('/user-stats')
@login_required
def user_stats():
    # 1. Dossiers créés par l'utilisateur (peu importe le parent)
    total_owned_folders = Folder.query.filter(
        Folder.owner_id == current_user.id,
        Folder.deleted == False
    ).count()

    # 2. Dossiers personnels (is_personal = True)
    personal_folders = Folder.query.filter(
        Folder.owner_id == current_user.id,
        Folder.is_personal == True,
        Folder.deleted == False
    ).count()

    # 3. Dossiers auxquels il a accès via permission (en plus des siens)
    accessible_via_permission = db.session.query(FolderPermission.folder_id).filter(
        FolderPermission.user_id == current_user.id,
        FolderPermission.can_read == True
    ).distinct().count()

    # 4. Fichiers appartenant à l'utilisateur
    total_user_files = File.query.filter(
        File.owner_id == current_user.id,
        File.deleted == False
    ).count()

    # 5. Fichiers en favoris
    favorite_files_count = Favorite.query.filter(
        Favorite.user_id == current_user.id
    ).count()

    stats = {
        'total_owned_folders': total_owned_folders,
        'personal_folders': personal_folders,
        'accessible_shared_folders': accessible_via_permission,
        'total_files': total_user_files,
        'favorite_files': favorite_files_count,
    }

    return jsonify(stats)



































