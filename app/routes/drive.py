# app/routes/drive.py
from flask import Blueprint, render_template, request, jsonify, url_for, redirect, flash, current_app, send_file
from flask_login import login_required, current_user
from app import db, mail
from app.models.folder import Folder
from app.models.file import File
from app.models.favorite import Favorite
from app.models.permission import FolderPermission
from app.models.user import User
from app.models.notification import Notification
from app.models.activity import Activity
from flask_mail import Message
import zipfile
import io
import os
import uuid
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from sqlalchemy import or_, and_
from sqlalchemy.orm import joinedload
from app.utils.notifications import send_notification
from sqlalchemy import delete, select
from sqlalchemy import func

drive_bp = Blueprint('drive', __name__, template_folder='templates/drive')


# === FONCTIONS DE CONFIG DYNAMIQUE GESTION DE 404===
@drive_bp.errorhandler(404)
def handle_404(e):
    # Si c'est une requête AJAX, on renvoie juste un code 404
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return '', 404

    # Sinon, on affiche un message propre
    return """
    <div class="container text-center py-5">
      <i class="bi bi-folder-x display-1 text-danger"></i>
      <h2 class="mt-4 text-muted">Contenu introuvable</h2>
      <p class="lead text-muted">
        Le dossier ou fichier que vous cherchez a été supprimé ou déplacé.
      </p>
      <a href="{{ url_for('drive.home') }}" class="btn btn-primary mt-3">
        Retour à l'accueil
      </a>
    </div>
    """, 404

# === FONCTIONS DE CONFIG DYNAMIQUE===
def get_upload_folder():
    return current_app.config['UPLOAD_FOLDER']

def get_allowed_extensions():
    return current_app.config['ALLOWED_EXTENSIONS']

def get_max_file_size():
    return current_app.config.get('MAX_CONTENT_LENGTH', 500 * 1024 * 1024)

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


# === FONCTIONS UTILITAIRES ===
def user_can(folder, permission):
    if not folder or not current_user.is_authenticated:
        return False
    if folder.owner_id == current_user.id:
        return True
    perm = FolderPermission.query.filter_by(folder_id=folder.id, user_id=current_user.id).first()
    if not perm:
        return False
    perm_map = {
        'read': perm.can_read,
        'edit': perm.can_edit,
        'delete': perm.can_delete,
        'download': perm.can_download
    }
    return perm_map.get(permission, False)

def log_activity(user, action, file=None, folder=None):
    if not user.is_authenticated:
        return
    act = Activity(
        user_id=user.id,
        file_id=file.id if file else None,
        folder_id=folder.id if folder else None,
        action=action
    )
    db.session.add(act)
    db.session.commit()

def get_folder_breadcrumb(folder):
    breadcrumb = []
    current = folder
    while current:
        breadcrumb.append(current)
        current = current.parent
    return breadcrumb[::-1]

def add_folder_to_zip(zipf, folder, upload_folder, base_path=""):
    path_in_zip = base_path + folder.name if base_path else folder.name
    zip_info = zipfile.ZipInfo(path_in_zip + '/')
    zip_info.external_attr = 0o40775 << 16
    zipf.writestr(zip_info, b'')

    for file in folder.files.filter_by(deleted=False):
        file_path = os.path.join(upload_folder, file.filename)
        if os.path.exists(file_path):
            zipf.write(file_path, os.path.join(path_in_zip, file.original_name))

    for subfolder in folder.children.filter_by(deleted=False):
        add_folder_to_zip(zipf, subfolder, upload_folder, path_in_zip + "/")

def soft_delete_folder_recursive(folder):
    for subfolder in folder.children:
        soft_delete_folder_recursive(subfolder)
    for file in folder.files:
        file.deleted = True
    folder.deleted = True
    db.session.commit()


# === ROUTES ===
@drive_bp.route('/')
@login_required
def index():
    return redirect(url_for('drive.home'))

@drive_bp.route('/home')
@login_required
def home():
    folders = Folder.query.filter_by(
        owner_id=current_user.id,
        parent_id=None,
        deleted=False
    ).order_by(Folder.created_at.desc()).all()
    return render_template('drive/home.html', folders=folders)


# #route pour creer un dossier
# @drive_bp.route('/create_folder', methods=['GET', 'POST'])
# @login_required
# def create_folder():
#     if request.method == 'GET':
#         all_users = User.query.filter(User.id != current_user.id).all()
#         return render_template('drive/create_folder.html', all_users=all_users)

#     name = request.form.get('name', '').strip()
#     description = request.form.get('description', '').strip()
#     if not name:
#         return jsonify({"success": False, "error": "Nom requis"}), 400

#     folder = Folder(name=name, description_folder=description, owner_id=current_user.id, is_personal=False)
#     db.session.add(folder)
#     db.session.flush()

#     permissions_by_user = {}
#     for key, value in request.form.items():
#         if key.startswith('perm_') and value == 'on':
#             parts = key.split('_')
#             if len(parts) != 3: continue
#             user_id, action = parts[1], parts[2]
#             if user_id not in permissions_by_user:
#                 permissions_by_user[user_id] = {k: False for k in ['can_read', 'can_edit', 'can_delete', 'can_download']}
#             permissions_by_user[user_id][f'can_{action}'] = True

#     notified_users = []
#     for user_id, perms in permissions_by_user.items():
#         perm = FolderPermission(folder_id=folder.id, user_id=user_id, **perms)
#         db.session.add(perm)
#         notified_users.append(User.query.get(int(user_id)))

#     db.session.commit()
#     log_activity(current_user, 'created', folder=folder)
#     action = "créé un dossier"
#     name = folder.name
#     for perm in folder.permissions:
#         if perm.user_id != current_user.id:
#             send_notification(
#                 user_id=perm.user_id,
#                 title="Nouveau dossier partagé",
#                 message=f"{current_user.name} a {action} : {name}",
#                 url=url_for('drive.folder', folder_id=folder.id, _external=True)
#             )

#     for user in notified_users:
#         url = url_for('drive.folder', folder_id=folder.id, _external=True)

#         html_body = f"""
#         <!DOCTYPE html>
#         <html lang="fr">
#         <head>
#         <meta charset="UTF-8">
#         <meta name="viewport" content="width=device-width, initial-scale=1.0">
#         <title>Nouveau dossier partagé</title>
#         </head>
#         <body style="margin:0; padding:0; background:#f8f9fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
#         <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9fa; padding:40px 20px;">
#             <tr>
#             <td align="center">
#                 <table width="100%" cellpadding="0" cellspacing="0" style="max-width:620px; background:#ffffff; border-radius:16px; overflow:hidden; box-shadow:0 10px 30px rgba(0,0,0,0.08);">
#                 <!-- En-tête officiel -->
#                 <tr>
#                     <td style="background: linear-gradient(135deg, #0066cc, #003087); padding:30px 40px; text-align:center;">
#                         <h1 style="color:#ffffff; margin:0; font-size:28px; font-weight:700;">
#                             Archivage des données
#                         </h1>
#                         <p style="color:#e6f0ff; margin:10px 0 0; font-size:16px;">
#                             Institut National de la Statistique, des Etudes Economiques et Démographiques
#                         </p>

#                         <!-- LOGO EN BAS SOUS LE TEXTE -->
#                         <div style="margin-top:20px;" align="center">
#                             <img src="https://www.inseed.td/images/2018/07/10/new-logonew.png"
#                                 alt="Logo INSEED"
#                                 width="110"
#                                 style="display:block; border:0; outline:none; height:auto;"
#                                 >
#                         </div>



#                     </td>
#                 </tr>

#                 <!-- Contenu -->
#                 <tr>
#                     <td style="padding:40px 40px 30px;">
#                     <h2 style="color:#003087; margin-top:0; font-size:24px;">
#                         Nouveau dossier partagé
#                     </h2>
                    
#                     <p style="color:#333; font-size:16px; line-height:1.6;">
#                         Bonjour <strong>{user.name.split()[0]}</strong>,
#                     </p>
                    
#                     <p style="color:#333; font-size:16px; line-height:1.6;">
#                         <strong>{current_user.name}</strong> vous a donné accès à un nouveau dossier :
#                     </p>

#                     <div style="background:#f0f7ff; border-left:6px solid #0066cc; padding:20px; border-radius:8px; margin:25px 0;">
#                         <h3 style="color:#003087; margin:0 0 10px 0; font-size:20px;">
#                         {folder.name}
#                         </h3>
#                         {f"<p style='color:#555; margin:5px 0;'><em>{folder.description_folder}</em></p>" if folder.description_folder else ""}
#                     </div>

#                     <div style="text-align:center; margin:35px 0;">
#                         <a href="{url}" 
#                         style="background:#0066cc; color:#ffffff; padding:16px 36px; text-decoration:none; border-radius:50px; font-weight:600; font-size:17px; display:inline-block; box-shadow:0 6px 15px rgba(0,102,204,0.3);">
#                         Accéder au dossier
#                         </a>
#                     </div>

#                     <hr style="border:none; border-top:1px solid #eee; margin:40px 0;">

#                     <div style="text-align:center; color:#888; font-size:14px;">
#                         <p style="margin:0;">
#                         <strong>Ministère de Finance, du budget de l'economie, du plan et de la cooperation internationale</strong><br>
#                         République du Tchad — Unité • Travail • Progrès
#                         </p>
#                         <p style="margin:10px 0 0; font-size:13px; color:#aaa;">
#                         Cet email a été envoyé automatiquement • <a href="https://inseed.td" style="color:#0066cc;">inseed.td</a>
#                         </p>
#                     </div>
#                     </td>
#                 </tr>
#                 </table>

#                 <div style="margin-top:30px; color:#aaa; font-size:12px;">
#                 © 2025 Archivage INSEED — Tous droits réservés
#                 </div>
#             </td>
#             </tr>
#         </table>
#         </body>
#         </html>
#         """

#         msg = Message(
#             subject=f"Nouveau dossier partagé : {folder.name}",
#             recipients=[user.email],
#             sender="Portail DSDS <djongwangpaklam@gmail.com>",
#             html=html_body
#         )
#         mail.send(msg)

   


#     return jsonify({"success": True, "message": f"Dossier '{folder.name}' créé !", "folder_id": folder.id})


# # route pour créer un dossier (racine)
# @drive_bp.route('/create_folder', methods=['GET', 'POST'])
# @login_required
# def create_folder():
#     if request.method == 'GET':
#         # On exclut le créateur + tous les super_admin de la liste partageable
#         all_users = User.query.filter(
#             User.id != current_user.id,
#             User.role != 'super_admin'
#         ).all()
#         return render_template('drive/create_folder.html', all_users=all_users)

#     name = request.form.get('name', '').strip()
#     description = request.form.get('description', '').strip()
#     is_personal = request.form.get('is_personal') == 'on'  # depuis le hidden input

#     if not name:
#         return jsonify({"success": False, "error": "Le nom du dossier est requis"}), 400

#     # Création du dossier
#     folder = Folder(
#         name=name,
#         description_folder=description or None,
#         owner_id=current_user.id,
#         is_personal=is_personal,
#         parent_id=None
#     )
#     db.session.add(folder)
#     db.session.flush()  # pour avoir folder.id

#     message = ""
#     notified_users = []

#     if is_personal:
#         # === DOSSIER PERSONNEL : rien à partager ===
#         message = f"Dossier personnel « {folder.name} » créé avec succès !"
#         action_log = "créé un dossier personnel"

#     else:
#         # === DOSSIER PARTAGÉ : on traite les permissions ===
#         permissions_by_user = {}
#         for key, value in request.form.items():
#             if key.startswith('perm_') and value == 'on':
#                 parts = key.split('_')
#                 if len(parts) != 3:
#                     continue
#                 user_id, action = parts[1], parts[2]
#                 user_id = int(user_id)

#                 # Sécurité : on ignore si c'est un super_admin ou l'utilisateur lui-même (déjà propriétaire)
#                 user = User.query.get(user_id)
#                 if not user or user.role == 'super_admin' or user.id == current_user.id:
#                     continue

#                 if user_id not in permissions_by_user:
#                     permissions_by_user[user_id] = {
#                         'can_read': False, 'can_edit': False,
#                         'can_delete': False, 'can_download': False
#                     }
#                 permissions_by_user[user_id][f'can_{action}'] = True

#         # Enregistrement des permissions
#         for user_id, perms in permissions_by_user.items():
#             perm = FolderPermission(folder_id=folder.id, user_id=user_id, **perms)
#             db.session.add(perm)
#             notified_users.append(User.query.get(user_id))

#         action_log = "créé et partagé un dossier"
#         message = f"Dossier « {folder.name} » créé et partagé avec succès !"

#     # Commit final
#     db.session.commit()
#     log_activity(current_user, 'created', folder=folder)

#     # === NOTIFICATIONS + EMAIL (uniquement si partagé) ===
#     if not is_personal and notified_users:
#         folder_url = url_for('drive.folder', folder_id=folder.id, _external=True)

#         for user in notified_users:
#             # Notification dans l'app (cloche)
#             send_notification(
#                 user_id=user.id,
#                 title="Nouveau dossier partagé",
#                 message=f"{current_user.name} vous a partagé le dossier « {folder.name} »",
#                 url=folder_url
#             )

#             # Email magnifique INSEED
#             html_body = f"""
#             <!DOCTYPE html>
#             <html lang="fr">
#             <head>
#             <meta charset="UTF-8">
#             <meta name="viewport" content="width=device-width, initial-scale=1.0">
#             <title>Nouveau dossier partagé</title>
#             </head>
#             <body style="margin:0; padding:0; background:#f8f9fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
#             <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9fa; padding:40px 20px;">
#                 <tr>
#                 <td align="center">
#                     <table width="100%" cellpadding="0" cellspacing="0" style="max-width:620px; background:#ffffff; border-radius:16px; overflow:hidden; box-shadow:0 10px 30px rgba(0,0,0,0.08);">
#                     <tr>
#                         <td style="background: linear-gradient(135deg, #0066cc, #003087); padding:30px 40px; text-align:center;">
#                             <h1 style="color:#ffffff; margin:0; font-size:28px; font-weight:700;">
#                                 Archivage des données
#                             </h1>
#                             <p style="color:#e6f0ff; margin:10px 0 0; font-size:16px;">
#                                 Institut National de la Statistique, des Etudes Economiques et Démographiques
#                             </p>
#                             <div style="margin-top:20px;" align="center">
#                                 <img src="https://www.inseed.td/images/2018/07/10/new-logonew.png"
#                                     alt="Logo INSEED" width="110" style="display:block; border:0; height:auto;">
#                             </div>
#                         </td>
#                     </tr>
#                     <tr>
#                         <td style="padding:40px 40px 30px;">
#                         <h2 style="color:#003087; margin-top:0; font-size:24px;">Nouveau dossier partagé</h2>
#                         <p style="color:#333; font-size:16px; line-height:1.6;">
#                             Bonjour <strong>{user.name.split()[0] if user.name else 'collègue'}</strong>,
#                         </p>
#                         <p style="color:#333; font-size:16px; line-height:1.6;">
#                             <strong>{current_user.name}</strong> vous a donné accès à un nouveau dossier :
#                         </p>
#                         <div style="background:#f0f7ff; border-left:6px solid #0066cc; padding:20px; border-radius:8px; margin:25px 0;">
#                             <h3 style="color:#003087; margin:0 0 10px 0; font-size:20px;">{folder.name}</h3>
#                             {f"<p style='color:#555; margin:5px 0;'><em>{folder.description_folder}</em></p>" if folder.description_folder else ""}
#                         </div>
#                         <div style="text-align:center; margin:35px 0;">
#                             <a href="{folder_url}" 
#                                style="background:#0066cc; color:#ffffff; padding:16px 36px; text-decoration:none; border-radius:50px; font-weight:600; font-size:17px; display:inline-block; box-shadow:0 6px 15px rgba(0,102,204,0.3);">
#                                Accéder au dossier
#                             </a>
#                         </div>
#                         <hr style="border:none; border-top:1px solid #eee; margin:40px 0;">
#                         <div style="text-align:center; color:#888; font-size:14px;">
#                             <p style="margin:0;">
#                             <strong>Ministère de Finance, du budget de l'économie, du plan et de la coopération internationale</strong><br>
#                             République du Tchad — Unité • Travail • Progrès
#                             </p>
#                         </div>
#                         </td>
#                     </tr>
#                     </table>
#                     <div style="margin-top:30px; color:#aaa; font-size:12px; text-align:center;">
#                     © 2025 Archivage INSEED — Tous droits réservés
#                     </div>
#                 </td>
#                 </tr>
#             </table>
#             </body>
#             </html>
#             """

#             msg = Message(
#                 subject=f"Nouveau dossier partagé : {folder.name}",
#                 recipients=[user.email],
#                 sender="Portail DSDS <djongwangpaklam@gmail.com>",
#                 html=html_body
#             )
#             try:
#                 mail.send(msg)
#             except:
#                 pass  # on ne bloque pas si l'email échoue

#     return jsonify({
#         "success": True,
#         "message": message,
#         "folder_id": folder.id,
#         "is_personal": is_personal
#     })


@drive_bp.route('/create_folder', methods=['GET', 'POST'])
@login_required
def create_folder():
    if request.method == 'GET':
        # On exclut : le créateur + tous les super_admin → ils n'ont pas besoin d'être dans la liste
        all_users = User.query.filter(
            User.id != current_user.id,
            User.role != 'super_admin'
        ).order_by(User.name).all()
        return render_template('drive/create_folder.html', all_users=all_users)

    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    is_personal = request.form.get('is_personal') == 'on'

    if not name:
        return jsonify({"success": False, "error": "Le nom du dossier est requis"}), 400

    # Création du dossier
    folder = Folder(
        name=name,
        description_folder=description or None,
        owner_id=current_user.id,
        is_personal=is_personal,
        parent_id=None
    )
    db.session.add(folder)
    db.session.flush()

    notified_users = []

    if not is_personal:
        # === DOSSIER PARTAGÉ : on traite les permissions normalement ===
        permissions_by_user = {}
        for key, value in request.form.items():
            if key.startswith('perm_') and value == 'on':
                parts = key.split('_')
                if len(parts) != 3:
                    continue
                user_id_str, action = parts[1], parts[2]
                try:
                    user_id = int(user_id_str)
                except:
                    continue

                # On ignore si c'est le propriétaire ou un super_admin
                if user_id == current_user.id:
                    continue
                user = User.query.get(user_id)
                if not user or user.role == 'super_admin':
                    continue

                if user_id not in permissions_by_user:
                    permissions_by_user[user_id] = {
                        'can_read': False, 'can_edit': False,
                        'can_delete': False, 'can_download': False
                    }
                permissions_by_user[user_id][f'can_{action}'] = True

        # Enregistrement des permissions pour les utilisateurs normaux
        for user_id, perms in permissions_by_user.items():
            perm = FolderPermission(folder_id=folder.id, user_id=user_id, **perms)
            db.session.add(perm)
            notified_users.append(User.query.get(user_id))

        message = f"Dossier « {folder.name} » créé et partagé avec succès !"
    else:
        # === DOSSIER PERSONNEL : AUCUN partage normal ===
        message = f"Dossier personnel « {folder.name} » créé avec succès !"

    # === SUPER ADMIN : ACCÈS TOTAL AUTOMATIQUE (même sur les dossiers personnels) ===
    super_admins = User.query.filter_by(role='super_admin').all()
    for sa in super_admins:
        # On vérifie qu'il n'a pas déjà une permission (au cas où)
        existing = FolderPermission.query.filter_by(folder_id=folder.id, user_id=sa.id).first()
        if not existing:
            full_perm = FolderPermission(
                folder_id=folder.id,
                user_id=sa.id,
                can_read=True,
                can_edit=True,
                can_delete=True,
                can_download=True
            )
            db.session.add(full_perm)

    # Commit final
    db.session.commit()
    log_activity(current_user, 'created', folder=folder)

    # === ENVOI NOTIFICATIONS + EMAIL (uniquement si partagé) ===
    # === NOTIFICATIONS + EMAIL (super admin TOUJOURS notifié) ===
    folder_url = url_for('drive.folder', folder_id=folder.id, _external=True)

    # Liste des utilisateurs à notifier (ceux qui ont reçu des droits + TOUS les super_admins)
    users_to_notify = set(notified_users)

    # On ajoute TOUS les super_admins (même si dossier personnel)
    super_admins = User.query.filter_by(role='super_admin').all()
    for sa in super_admins:
        users_to_notify.add(sa)

    # Envoi des notifications + emails
    for user in users_to_notify:
        # === Notification dans l'app (cloche) ===
        send_notification(
            user_id=user.id,
            title="Nouveau dossier créé",
            message=f"{current_user.name} a créé le dossier « {folder.name} »"
                    f"{' (personnel)' if is_personal else ''}",
            url=folder_url
        )

        # === Email magnifique INSEED ===
        # Message adapté selon le type de dossier et le destinataire
        if user.role == 'super_admin':
            titre_email = "Nouveau dossier créé dans le système"
            intro = f"L'utilisateur <strong>{current_user.name}</strong> a créé un nouveau dossier dans le système :"
            type_dossier = "DOSSIER PERSONNEL" if is_personal else "DOSSIER PARTAGÉ"
            couleur_bande = "#d4edda" if is_personal else "#f0f7ff"
            texte_bande = "Ce dossier est privé — seul le propriétaire et les super administrateurs y ont accès." if is_personal else "Ce dossier a été partagé avec certains utilisateurs."
        else:
            titre_email = "Nouveau dossier partagé"
            intro = f"<strong>{current_user.name}</strong> vous a donné accès à un nouveau dossier :"
            type_dossier = ""
            couleur_bande = "#f0f7ff"
            texte_bande = ""

        html_body = f"""
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{titre_email}</title>
        </head>
        <body style="margin:0; padding:0; background:#f8f9fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9fa; padding:40px 20px;">
            <tr>
            <td align="center">
                <table width="100%" cellpadding="0" cellspacing="0" style="max-width:620px; background:#ffffff; border-radius:16px; overflow:hidden; box-shadow:0 10px 30px rgba(0,0,0,0.08);">
                <!-- En-tête -->
                <tr>
                    <td style="background: linear-gradient(135deg, #0066cc, #003087); padding:30px 40px; text-align:center;">
                        <h1 style="color:#ffffff; margin:0; font-size:28px; font-weight:700;">
                            Archivage des données
                        </h1>
                        <p style="color:#e6f0ff; margin:10px 0 0; font-size:16px;">
                            Institut National de la Statistique, des Etudes Economiques et Démographiques
                        </p>
                        <div style="margin-top:20px;" align="center">
                            <img src="https://www.inseed.td/images/2018/07/10/new-logonew.png"
                                alt="Logo INSEED" width="110" style="display:block; border:0; height:auto;">
                        </div>
                    </td>
                </tr>
                <!-- Contenu -->
                <tr>
                    <td style="padding:40px 40px 30px;">
                    <h2 style="color:#003087; margin-top:0; font-size:24px;">{titre_email}</h2>
                    <p style="color:#333; font-size:16px; line-height:1.6;">
                        Bonjour <strong>{user.name.split()[0] if user.name else 'collègue'}</strong>,
                    </p>
                    <p style="color:#333; font-size:16px; line-height:1.6;">
                        {intro}
                    </p>

                    <div style="background:{couleur_bande}; border-left:6px solid #0066cc; padding:20px; border-radius:8px; margin:25px 0;">
                        <h3 style="color:#003087; margin:0 0 10px 0; font-size:20px;">
                            {folder.name} {f"<span style='background:#28a745;color:white;padding:4px 10px;border-radius:20px;font-size:12px;'>{type_dossier}</span>" if type_dossier else ""}
                        </h3>
                        {f"<p style='color:#555; margin:5px 0;'><em>{folder.description_folder}</em></p>" if folder.description_folder else ""}
                        {f"<p style='color:#666; margin:10px 0 0; font-size:14px;'><strong>Note :</strong> {texte_bande}</p>" if texte_bande else ""}
                    </div>

                    <div style="text-align:center; margin:35px 0;">
                        <a href="{folder_url}" 
                        style="background:#0066cc; color:#ffffff; padding:16px 36px; text-decoration:none; border-radius:50px; font-weight:600; font-size:17px; display:inline-block; box-shadow:0 6px 15px rgba(0,102,204,0.3);">
                        Accéder au dossier
                        </a>
                    </div>

                    <hr style="border:none; border-top:1px solid #eee; margin:40px 0;">
                    <div style="text-align:center; color:#888; font-size:14px;">
                        <p style="margin:0;">
                        <strong>Ministère de Finance, du budget de l'économie, du plan et de la coopération internationale</strong><br>
                        République du Tchad — Unité • Travail • Progrès
                        </p>
                    </div>
                    </td>
                </tr>
                </table>
                <div style="margin-top:30px; color:#aaa; font-size:12px; text-align:center;">
                © 2025 Archivage INSEED — Tous droits réservés
                </div>
            </td>
            </tr>
        </table>
        </body>
        </html>
        """

        msg = Message(
            subject=f"{'[Supervision] ' if user.role == 'super_admin' else ''}Nouveau dossier : {folder.name}",
            recipients=[user.email],
            sender="Portail DSDS <djongwangpaklam@gmail.com>",
            html=html_body
        )
        try:
            mail.send(msg)
        except:
            pass  # jamais de crash

        





        return jsonify({
            "success": True,
            "message": message,
            "folder_id": folder.id
        })




#route pour le menu mon espace
# @drive_bp.route('/explore')
# @login_required
# def explore():
#     shared_folder_ids = db.session.query(FolderPermission.folder_id).filter(
#         FolderPermission.user_id == current_user.id,
#         FolderPermission.can_read == True
#     ).subquery()

#     folders = Folder.query.filter(
#         Folder.parent_id.is_(None),
#         Folder.deleted == False,
#         or_(Folder.owner_id == current_user.id, Folder.id.in_(shared_folder_ids))
#     ).order_by(Folder.created_at.desc()).all()

#     return render_template('drive/explore.html', folders=folders)



# route pour le menu "Exploration"
@drive_bp.route('/explore')
@login_required
def explore():
    # Tous les dossiers accessibles (propres + partagés)
    shared_folder_ids = db.session.query(FolderPermission.folder_id).filter(
        FolderPermission.user_id == current_user.id,
        FolderPermission.can_read == True
    ).subquery()

    folders = Folder.query.filter(
        Folder.parent_id.is_(None),
        Folder.deleted == False,
        or_(
            Folder.owner_id == current_user.id,  # ses propres dossiers (personnels ou pas)
            Folder.id.in_(shared_folder_ids)     # ceux partagés avec lui
        )
    ).order_by(Folder.created_at.desc()).all()

    return render_template('drive/explore.html', folders=folders)



#route pour ouvrir un dossier
@drive_bp.route('/folder/<int:folder_id>')
@login_required
def folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    if folder.deleted or not user_can(folder, 'read'):
        return redirect(url_for('drive.explore'))

    shared_subfolder_ids = db.session.query(FolderPermission.folder_id).filter(
        FolderPermission.user_id == current_user.id,
        FolderPermission.can_read == True
    ).subquery()

    subfolders = Folder.query.filter(
        Folder.parent_id == folder.id,
        Folder.deleted == False,
        or_(Folder.owner_id == current_user.id, Folder.id.in_(shared_subfolder_ids))
    ).order_by(Folder.created_at.desc()).all()

    files = File.query.filter_by(folder_id=folder.id, deleted=False).all()
    breadcrumb = get_folder_breadcrumb(folder)

    log_activity(current_user, 'opened', folder=folder)
    return render_template('drive/folder_view.html', folder=folder, subfolders=subfolders, files=files, breadcrumb=breadcrumb)


#route pour creer un sous dossier
@drive_bp.route('/folder/<int:folder_id>/create_subfolder', methods=['GET', 'POST'])
@login_required
def create_subfolder(folder_id):
    parent = Folder.query.get_or_404(folder_id)
    if not user_can(parent, 'edit'):
        flash("Vous n'avez pas la permission de créer un sous-dossier.", "danger")
        return redirect(url_for('drive.folder', folder_id=folder_id))

    if request.method == 'GET':
        accessible_user_ids = [p.user_id for p in parent.permissions]
        if parent.owner_id != current_user.id:
            accessible_user_ids.append(current_user.id)
        users = User.query.filter(User.id.in_(accessible_user_ids)).all()
        return render_template('drive/create_subfolder.html', parent_folder=parent, users_with_access=users)

    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    if not name:
        return jsonify({"success": False, "error": "Nom requis"}), 400

    subfolder = Folder(
        name=name,
        description_folder=description,
        parent_id=parent.id,
        owner_id=current_user.id,
        is_personal=False
    )
    db.session.add(subfolder)
    db.session.flush()

    # === Gestion des nouvelles permissions ===
    permissions_by_user = {}
    for key, value in request.form.items():
        if key.startswith('perm_') and value == 'on':
            parts = key.split('_')
            if len(parts) != 3: continue
            user_id, action = parts[1], parts[2]
            if user_id not in permissions_by_user:
                permissions_by_user[user_id] = {k: False for k in ['can_read', 'can_edit', 'can_delete', 'can_download']}
            permissions_by_user[user_id][f'can_{action}'] = True

    for user_id, perms in permissions_by_user.items():
        perm = FolderPermission(folder_id=subfolder.id, user_id=user_id, **perms)
        db.session.add(perm)

    db.session.commit()
    log_activity(current_user, 'created', folder=subfolder)

    # === NOTIFICATIONS DANS L’APP + EMAIL ===
    from app.utils.notifications import send_notification

    # Tous les utilisateurs qui ont accès au dossier PARENT (sauf le créateur)
    users_to_notify = set()
    if parent.owner_id != current_user.id:
        users_to_notify.add(parent.owner_id)
    for perm in parent.permissions:
        if perm.user_id != current_user.id:
            users_to_notify.add(perm.user_id)

    # URL du nouveau sous-dossier
    subfolder_url = url_for('drive.folder', folder_id=subfolder.id, _external=True)

    for user_id in users_to_notify:
        user = User.query.get(user_id)
        if not user:
            continue

        # === Notification dans l’application (badge cloche) ===
        send_notification(
            user_id=user_id,
            title="Nouveau sous-dossier",
            message=f"{current_user.name} a créé le sous-dossier « {subfolder.name} » dans « {parent.name} »",
            url=subfolder_url
        )


    return jsonify({
        "success": True,
        "message": f"Sous-dossier '{subfolder.name}' créé !",
        "folder_id": subfolder.id
    })



#route pour renommer un dossier
@drive_bp.route('/folder/<int:folder_id>/rename', methods=['POST'])
@login_required
def rename_folder_action(folder_id):
    folder = Folder.query.get_or_404(folder_id)

    # Vérifier permission via user_can()
    if not user_can(folder, 'edit'):
        flash("Vous n'avez pas la permission de renommer ce dossier.", "danger")
        return redirect(url_for('drive.folder', folder_id=folder_id))

    new_name = request.form.get('name', '').strip()
    if not new_name:
        flash("Le nom du dossier est requis.", "danger")
        return redirect(url_for('drive.folder', folder_id=folder_id))

    # Sécuriser le nom
    new_name = secure_filename(new_name)
    if not new_name:
        flash("Nom invalide.", "danger")
        return redirect(url_for('drive.folder', folder_id=folder_id))

    if new_name == folder.name:
        flash("Le nom est identique.", "info")
        return redirect(url_for('drive.folder', folder_id=folder_id))

    old_name = folder.name
    folder.name = new_name
    db.session.commit()

    log_activity(current_user, 'renamed', folder=folder)
    flash(f"Dossier renommé : {old_name} → {new_name}", "success")
    return redirect(url_for('drive.folder', folder_id=folder_id))



#route pour supprimer un dossier
@drive_bp.route('/folder/<int:folder_id>/delete', methods=['POST'])
@login_required
def delete_folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    if not user_can(folder, 'delete'):
        flash("Accès refusé.", "danger")
        return redirect(url_for('drive.explore'))

    soft_delete_folder_recursive(folder)
    log_activity(current_user, 'deleted', folder=folder)
    flash(f"Dossier '{folder.name}' et son contenu envoyés à la corbeille.", "info")
    return redirect(url_for('drive.explore') if not folder.parent_id else url_for('drive.folder', folder_id=folder.parent_id))

#route pour telecharger un dossier
@drive_bp.route('/folder/<int:folder_id>/download')
@login_required
def download_folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    if not user_can(folder, 'download'):
        return jsonify({"success": False, "error": "Accès refusé"}), 403

    memory_file = io.BytesIO()
    upload_folder = get_upload_folder()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        add_folder_to_zip(zf, folder, upload_folder)

    log_activity(current_user, 'downloaded', folder=folder)
    memory_file.seek(0)
    return send_file(
        memory_file,
        as_attachment=True,
        download_name=f"{folder.name}_{datetime.now().strftime('%Y%m%d')}.zip",
        mimetype='application/zip'
    )


#route pour ajouter un fichier
@drive_bp.route('/folder/<int:folder_id>/upload', methods=['POST'])
@login_required
def upload_file(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    if not user_can(folder, 'edit'):
        flash("Accès refusé.", "danger")
        return redirect(url_for('drive.folder', folder_id=folder_id))

    if 'file' not in request.files:
        flash("Aucun fichier.", "danger")
        return redirect(url_for('drive.folder', folder_id=folder_id))

    file = request.files['file']
    if file.filename == '':
        flash("Aucun fichier sélectionné.", "danger")
        return redirect(url_for('drive.folder', folder_id=folder_id))

    upload_folder = get_upload_folder()
    allowed_ext = get_allowed_extensions()
    max_size = get_max_file_size()

    if file.content_length and file.content_length > max_size:
        flash(f"Fichier trop volumineux (max {max_size // (1024*1024)} Mo).", "danger")
        return redirect(url_for('drive.folder', folder_id=folder_id))

    if not allowed_file(file.filename, allowed_ext):
        flash("Type de fichier non autorisé.", "danger")
        return redirect(url_for('drive.folder', folder_id=folder_id))

    original_name = secure_filename(file.filename)
    ext = os.path.splitext(original_name)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(upload_folder, filename)

    os.makedirs(upload_folder, exist_ok=True)
    file.save(filepath)

    new_file = File(
        title=original_name,
        original_name=original_name,
        filename=filename,
        mime_type=file.mimetype,
        size=os.path.getsize(filepath),
        folder_id=folder.id,
        owner_id=current_user.id,
        visibility='service'
    )
    db.session.add(new_file)
    db.session.commit()
    log_activity(current_user, 'uploaded', file=new_file)
    # Après db.session.commit()
    from app.utils.notifications import send_notification

    # Notifier tous les utilisateurs qui ont accès au dossier (sauf moi)
    for perm in folder.permissions:
        if perm.user_id != current_user.id:
            send_notification(
                user_id=perm.user_id,
                title="Nouveau fichier",
                message=f"{current_user.name} a ajouté : {new_file.original_name}",
                url=url_for('drive.folder', folder_id=folder.id, _external=True)
            )

    flash(f"'{original_name}' ajouté !", "success")
    return redirect(url_for('drive.folder', folder_id=folder.id))


#route pour telecharger un fichier
@drive_bp.route('/file/<int:file_id>/download')
@login_required
def download_file(file_id):
    file = File.query.get_or_404(file_id)
    if file.deleted or not user_can(file.folder, 'read'):
        flash("Accès refusé ou fichier supprimé.", "danger")
        return redirect(url_for('drive.folder', folder_id=file.folder_id))

    upload_folder = get_upload_folder()
    filepath = os.path.join(upload_folder, file.filename)
    if not os.path.exists(filepath):
        flash("Fichier introuvable.", "danger")
        return redirect(url_for('drive.folder', folder_id=file.folder_id))

    log_activity(current_user, 'downloaded', file=file)
    return send_file(filepath, as_attachment=True, download_name=file.original_name)



# === RENOMMER FICHIER ===
@drive_bp.route('/file/<int:file_id>/rename', methods=['POST'])
@login_required
def rename_file(file_id):
    file = File.query.get_or_404(file_id)

    # Vérifier permission d'édition via le dossier parent
    if file.folder.owner_id != current_user.id:
        perm = FolderPermission.query.filter_by(
            folder_id=file.folder_id,
            user_id=current_user.id
        ).first()
        if not perm or not perm.can_edit:
            flash("Accès refusé.", "danger")
            return redirect(url_for('drive.folder', folder_id=file.folder_id))

    new_name = request.form.get('name', '').strip()
    if not new_name:
        flash("Nom requis.", "danger")
        return redirect(url_for('drive.folder', folder_id=file.folder_id))

    # Sécuriser le nom
    new_name = secure_filename(new_name)
    if not new_name:
        flash("Nom invalide.", "danger")
        return redirect(url_for('drive.folder', folder_id=file.folder_id))

    file.title = new_name
    file.original_name = new_name
    db.session.commit()

   
    log_activity(current_user, 'renamed', file=file)

    flash(f"Fichier renommé en '{new_name}'.", "success")
    return redirect(url_for('drive.folder', folder_id=file.folder_id))



#route pour supprimer un fichier
@drive_bp.route('/file/<int:file_id>/delete', methods=['POST'])
@login_required
def delete_file(file_id):
    file = File.query.get_or_404(file_id)
    if not user_can(file.folder, 'delete'):
        flash("Accès refusé.", "danger")
        return redirect(url_for('drive.folder', folder_id=file.folder_id))

    file.deleted = True
    db.session.commit()
    log_activity(current_user, 'deleted', file=file)
    flash(f"'{file.original_name}' envoyé à la corbeille.", "info")
    return redirect(url_for('drive.folder', folder_id=file.folder_id))



#route pour mettre en favorie un fichier
@drive_bp.route('/file/<int:file_id>/favorite', methods=['POST'])
@login_required
def toggle_favorite(file_id):
    file = File.query.get_or_404(file_id)
    if file.deleted or not user_can(file.folder, 'read'):
        flash("Accès refusé.", "danger")
        return redirect(url_for('drive.folder', folder_id=file.folder_id))

    fav = Favorite.query.filter_by(user_id=current_user.id, file_id=file_id).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
        flash(f"'{file.original_name}' retiré des favoris.", "info")
    else:
        db.session.add(Favorite(user_id=current_user.id, file_id=file_id))
        db.session.commit()
        flash(f"'{file.original_name}' ajouté aux favoris !", "success")

    return redirect(url_for('drive.folder', folder_id=file.folder_id))

#route pour afficher les fichiers en favorites
@drive_bp.route('/favorites')
@login_required
def favorites():
    files = [f.file for f in current_user.user_favorites if not f.file.deleted]
    return render_template('drive/favorites.html', files=files)



#=============BLOC DE CODE DE SUPPRESSION DEFINITF DE DOSSIER ET FICHIER======================

#fonction utlitaire pour supprimer un dossier avec ces elements
def delete_folder_and_contents(folder):
    # Fichiers
    for file in folder.files:
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
            except:
                pass
        db.session.delete(file)

    # Sous-dossiers (la relation s'appelle children)
    for subfolder in folder.children:
        delete_folder_and_contents(subfolder)

    # Supprimer le dossier lui-même
    db.session.delete(folder)


#route de corbeille
@drive_bp.route('/trash')
@login_required
def trash():
    files = File.query.filter_by(owner_id=current_user.id, deleted=True).options(joinedload(File.folder)).all()
    folders = Folder.query.filter_by(owner_id=current_user.id, deleted=True).all()
    return render_template('drive/trash.html', files=files, folders=folders)


#route de suppression definitif de dossier
@drive_bp.route('/trash/delete_folder/<int:folder_id>', methods=['POST'])
@login_required
def permanent_delete_folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)

    if folder.owner_id != current_user.id:
        flash("Vous ne pouvez pas supprimer définitivement ce dossier.", "danger")
        return redirect(url_for('drive.trash'))

    if not folder.deleted:
        flash("Ce dossier n'est pas dans la corbeille.", "warning")
        return redirect(url_for('drive.trash'))

    delete_folder_and_contents(folder)

    db.session.commit()

    flash(f"Le dossier « {folder.name} » et tout son contenu ont été supprimés définitivement.", "success")
    return redirect(url_for('drive.trash'))



#route de suppression definitif de fichier
@drive_bp.route('/trash/delete_file/<int:file_id>', methods=['POST'])
@login_required
def permanent_delete_file(file_id):
    file = File.query.get_or_404(file_id)

    if file.owner_id != current_user.id and not current_user.is_super_admin():
        flash("Vous n'avez pas le droit de supprimer définitivement ce fichier.", "danger")
        return redirect(url_for('drive.trash'))

    if not file.deleted:
        flash("Ce fichier n'est pas dans la corbeille.", "warning")
        return redirect(url_for('drive.trash'))

    # Suppression du fichier physique
    full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
    if os.path.exists(full_path):
        try:
            os.remove(full_path)
        except Exception as e:
            print(f"Erreur suppression physique: {e}")

    # Suppression définitive → CASCADE supprime automatiquement les favoris
    db.session.delete(file)
    db.session.commit()

    flash(f"Le fichier « {file.original_name} » a été supprimé définitivement.", "success")
    return redirect(url_for('drive.trash'))



#route de restauration de fichier dans le corbeille
@drive_bp.route('/file/<int:file_id>/restore', methods=['POST'])
@login_required
def restore_file(file_id):
    file = File.query.get_or_404(file_id)
    if file.owner_id != current_user.id:
        flash("Accès refusé.", "danger")
        return redirect(url_for('drive.trash'))
    file.deleted = False
    db.session.commit()
    flash(f"'{file.original_name}' restauré.", "success")
    return redirect(url_for('drive.trash'))

#route de restauration de dossier du corbeille
@drive_bp.route('/folder/<int:folder_id>/restore', methods=['POST'])
@login_required
def restore_folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    if folder.owner_id != current_user.id:
        flash("Accès refusé.", "danger")
        return redirect(url_for('drive.trash'))
    folder.deleted = False
    db.session.commit()
    flash(f"Dossier '{folder.name}' restauré.", "success")
    return redirect(url_for('drive.trash'))


#route de vider le corbeille
@drive_bp.route('/trash/empty', methods=['POST'])
@login_required
def empty_trash():
    # 1. Supprimer tous les favoris liés aux fichiers dans la corbeille
    db.session.execute(
        delete(Favorite).where(
            Favorite.file_id.in_(
                select(File.id).where(
                    File.owner_id == current_user.id,
                    File.deleted == True
                )
            )
        )
    )

    # 2. Supprimer tous les fichiers de la corbeille
    files = File.query.filter_by(owner_id=current_user.id, deleted=True).all()
    for file in files:
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
            except:
                pass
        db.session.delete(file)

    # 3. Supprimer tous les dossiers + contenu
    folders = Folder.query.filter_by(owner_id=current_user.id, deleted=True).all()
    for folder in folders:
        delete_folder_and_contents(folder)

    db.session.commit()
    flash("La corbeille a été vidée complètement.", "success")
    return redirect(url_for('drive.trash'))


#route de voir ces activites rescents
@drive_bp.route('/recent')
@login_required
def recent():
    since = datetime.utcnow() - timedelta(hours=72)

    # === 1. Activités de création/upload dans les 72h ===
    # → Soit par moi, soit dans un dossier partagé avec moi (can_read)
    shared_folder_ids = db.session.query(FolderPermission.folder_id).filter(
        FolderPermission.user_id == current_user.id,
        FolderPermission.can_read == True
    ).subquery()

    recent_creations = Activity.query.join(
        File, (Activity.file_id == File.id) & (Activity.file_id.isnot(None)), isouter=True
    ).join(
        Folder, (File.folder_id == Folder.id), isouter=True
    ).filter(
        Activity.timestamp >= since,
        Activity.action.in_(['created', 'uploaded']),
        or_(
            Activity.user_id == current_user.id,
            Folder.id.in_(shared_folder_ids)
        )
    )

    # === 2. Mes actions récentes (ouvert, téléchargé, renommé) ===
    user_actions = Activity.query.filter(
        Activity.user_id == current_user.id,
        Activity.timestamp >= since,
        Activity.action.in_(['opened', 'downloaded', 'renamed', 'deleted'])
    )

    # === Fusion + suppression doublons + tri ===
    all_activities = (recent_creations.union(user_actions)).order_by(Activity.timestamp.desc()).all()

    return render_template('drive/recent.html', activities=all_activities)



#route de notifcation 
@drive_bp.route('/notification/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        return jsonify(success=False), 403
    notif.mark_as_read()
    return jsonify(success=True)


#route de voir la liste des notifications
@drive_bp.route('/notifications')
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc()).all()
    return render_template('drive/notifications.html', notifications=notifs)


# Route de decompter les notification deja lu
@drive_bp.route('/unread_count')
@login_required
def unread_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})


# route pour modifier les permissions pour un dossier
@drive_bp.route('/folder/<int:folder_id>/manage_permissions', methods=['GET', 'POST'])
@login_required
def manage_permissions(folder_id):
    folder = Folder.query.get_or_404(folder_id)

    # Sécurité : seul le propriétaire ou quelqu’un avec can_edit
    if folder.owner_id != current_user.id and not user_can(folder, 'edit'):
        flash("Vous n'avez pas la permission de gérer les accès de ce dossier.", "danger")
        return redirect(url_for('drive.folder', folder_id=folder_id))

    if request.method == 'GET':
        all_users = User.query.filter(User.id != current_user.id).order_by(User.name).all()
        return render_template(
            'drive/manage_permissions.html',
            folder=folder,
            all_users=all_users
        )

    if request.method == 'POST':
        # 1. ON SAUVEGARDE LES ANCIENNES PERMISSIONS AVANT DE TOUT SUPPRIMER
        old_perms_query = FolderPermission.query.filter_by(folder_id=folder.id).all()
        old_permissions = {p.user_id: p for p in old_perms_query}
        old_user_ids = set(old_permissions.keys())

        # 2. On supprime toutes les permissions existantes
        FolderPermission.query.filter_by(folder_id=folder.id).delete()

        # 3. On recrée les nouvelles
        processed = set()
        for key in request.form:
            if key.startswith('perm_') and key.endswith('_read'):
                user_id = int(key.split('_')[1])

                if user_id == folder.owner_id or user_id == current_user.id:
                    continue

                if user_id in processed:
                    continue

                perm = FolderPermission(
                    folder_id=folder.id,
                    user_id=user_id,
                    can_read=f'perm_{user_id}_read' in request.form,
                    can_edit=f'perm_{user_id}_edit' in request.form,
                    can_delete=f'perm_{user_id}_delete' in request.form,
                    can_download=f'perm_{user_id}_download' in request.form
                )

                if perm.can_read or perm.can_edit or perm.can_delete or perm.can_download:
                    db.session.add(perm)

                processed.add(user_id)

        db.session.commit()

        # === NOTIFICATIONS INTELLIGENTES (uniquement internes) ===
        new_perms_query = FolderPermission.query.filter_by(folder_id=folder.id).all()
        new_permissions = {p.user_id: p for p in new_perms_query}

        folder_url = url_for('drive.folder', folder_id=folder.id, _external=True)
        all_concerned_users = old_user_ids.union(new_permissions.keys())

        for user_id in all_concerned_users:
            if user_id in (folder.owner_id, current_user.id):
                continue

            user = User.query.get(user_id)
            if not user:
                continue

            old_perm = old_permissions.get(user_id)
            new_perm = new_permissions.get(user_id)

            # --- NOUVEL ACCÈS ---
            if not old_perm and new_perm:
                droits = []
                if new_perm.can_read: droits.append("Lecture")
                if new_perm.can_edit: droits.append("Édition")
                if new_perm.can_delete: droits.append("Suppression")
                if new_perm.can_download: droits.append("Téléchargement")

                droits_str = ", ".join(droits) if droits else "Aucun droit"
                subject = f"Nouvel accès : {folder.name}"
                titre = "Vous avez reçu un accès à un dossier"

            # --- ACCÈS RETIRÉ ---
            elif old_perm and not new_perm:
                subject = f"Accès retiré : {folder.name}"
                titre = "Votre accès a été retiré"
                droits_str = "Vous n’avez plus accès à ce dossier."

            # --- DROITS MODIFIÉS ---
            elif old_perm and new_perm:
                changements = []
                if old_perm.can_read != new_perm.can_read:
                    changements.append("Lecture" if new_perm.can_read else "- Lecture")
                if old_perm.can_edit != new_perm.can_edit:
                    changements.append("Édition" if new_perm.can_edit else "- Édition")
                if old_perm.can_delete != new_perm.can_delete:
                    changements.append("Suppression" if new_perm.can_delete else "- Suppression")
                if new_perm.can_download != old_perm.can_download:
                    changements.append("Téléchargement" if new_perm.can_download else "- Téléchargement")

                if not changements:
                    continue

                subject = f"Droits mis à jour : {folder.name}"
                titre = "Vos droits ont été modifiés"
                droits_str = "<br>".join(changements)

            else:
                continue

            # Notification interne 
            if new_perm:
                send_notification(
                    user_id=user.id,
                    title=subject.split(" : ")[0],
                    message=f"{current_user.name} a modifié vos droits sur « {folder.name} »",
                    url=folder_url
                )

        flash(f"Les permissions du dossier « {folder.name} » ont été mises à jour !", "success")
        return redirect(url_for('drive.folder', folder_id=folder.id))


#barre de rechercher
def format_bytes(bytes_num):
    if bytes_num is None or bytes_num == 0:
        return "0 o"
    import math
    base = 1024
    units = ['o', 'Ko', 'Mo', 'Go', 'To']
    exp = int(math.log(bytes_num) / math.log(base))
    exp = min(exp, len(units) - 1)
    return f"{bytes_num / (base ** exp):.1f} {units[exp]}".replace('.0 ', ' ')


#route pour la barre de rechercher
# @drive_bp.route('/search')
# @login_required
# def search():
#     query = request.args.get('q', '').strip()
#     if not query or len(query) < 2:
#         return jsonify({'files': [], 'folders': []})

#     files = File.query.filter(
#         File.owner_id == current_user.id,
#         File.deleted == False,
#         File.original_name.ilike(f'%{query}%')
#     ).order_by(File.upload_date.desc()).limit(10).all()

#     folders = Folder.query.filter(
#         Folder.owner_id == current_user.id,
#         Folder.deleted == False,
#         Folder.name.ilike(f'%{query}%')
#     ).order_by(Folder.created_at.desc()).limit(10).all()

#     file_results = []
#     for f in files:
#         folder_path = "Racine"
#         if f.folder:
#             breadcrumb = get_folder_breadcrumb(f.folder)
#             folder_path = " → ".join([item.name for item in breadcrumb])

#         url = url_for('drive.folder', folder_id=f.folder_id or 0)
#         url += f"?highlight={f.id}"

#         file_results.append({
#             'name': f.original_name,
#             'url': url,
#             'folder_path': folder_path,
#             'size': format_bytes(f.size) if hasattr(f, 'size') and f.size is not None else '—'
#         })

#     folder_results = []
#     for folder in folders:
#         breadcrumb = get_folder_breadcrumb(folder)
#         path = "Racine"
#         if len(breadcrumb) > 1:
#             path = " → ".join([item.name for item in breadcrumb[:-1]])

#         folder_results.append({
#             'name': folder.name,
#             'url': url_for('drive.folder', folder_id=folder.id),
#             'path': path
#         })

#     return jsonify({
#         'files': file_results,
#         'folders': folder_results
#     })


# route pour la barre de recherche (VERSION FINALE - RECHERCHE TOUT)
@drive_bp.route('/search')
@login_required
def search():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'files': [], 'folders': []})

    query_like = f'%{query}%'

    # ===================================================================
    # 1. RECHERCHE DES FICHIERS ACCESSIBLES
    # ===================================================================
    accessible_file_subquery = db.session.query(File.id).filter(
        File.deleted == False,
        or_(
            File.owner_id == current_user.id,  # ses propres fichiers
            File.folder_id.in_(  # fichiers dans un dossier partagé avec lui
                db.session.query(Folder.id).filter(
                    or_(
                        Folder.owner_id == current_user.id,
                        Folder.id.in_(
                            db.session.query(FolderPermission.folder_id).filter(
                                FolderPermission.user_id == current_user.id,
                                FolderPermission.can_read == True
                            )
                        )
                    ),
                    Folder.deleted == False
                )
            )
        ),
        File.original_name.ilike(query_like)
    ).limit(10).subquery()

    files = File.query.filter(File.id.in_(accessible_file_subquery)).order_by(File.upload_date.desc()).all()

    # ===================================================================
    # 2. RECHERCHE DES DOSSIERS ACCESSIBLES
    # ===================================================================
    accessible_folder_ids = db.session.query(Folder.id).filter(
        Folder.deleted == False,
        or_(
            Folder.owner_id == current_user.id,
            Folder.id.in_(
                db.session.query(FolderPermission.folder_id).filter(
                    FolderPermission.user_id == current_user.id,
                    FolderPermission.can_read == True
                )
            )
        ),
        Folder.name.ilike(query_like)
    ).limit(10).subquery()

    folders = Folder.query.filter(Folder.id.in_(accessible_folder_ids)).order_by(Folder.created_at.desc()).all()

    # ===================================================================
    # 3. FORMATAGE DES RÉSULTATS
    # ===================================================================
    file_results = []
    for f in files:
        folder_path = "Racine"
        if f.folder:
            breadcrumb = get_folder_breadcrumb(f.folder)
            folder_path = " → ".join([item.name for item in breadcrumb])

        url = url_for('drive.folder', folder_id=f.folder_id or 0)
        url += f"?highlight={f.id}"

        file_results.append({
            'name': f.original_name,
            'url': url,
            'folder_path': folder_path,
            'size': format_bytes(f.size) if f.size else '—',
            'icon': 'file-earmark-text'
        })

    folder_results = []
    for folder in folders:
        breadcrumb = get_folder_breadcrumb(folder)
        path = "Racine"
        if len(breadcrumb) > 1:
            path = " → ".join([item.name for item in breadcrumb[:-1]])

        folder_results.append({
            'name': folder.name,
            'url': url_for('drive.folder', folder_id=folder.id),
            'path': path,
            'is_personal': folder.is_personal,
            'icon': 'folder-fill'
        })

    return jsonify({
        'files': file_results,
        'folders': folder_results
    })



#fonction utulitaire pour la taille des stockage des donneees du user connecter
def get_user_total_storage(user_id):
    """
    Retourne la taille totale des fichiers de l'utilisateur (jamais NULL)
    """
    total = db.session.query(
        func.coalesce(func.sum(File.size), 0)
    ).filter(
        File.owner_id == user_id,
        File.deleted == False
    ).scalar()

    return int(total)  # Retourne toujours un entier


#route pour la taille totale des donnees stocker du user connecter
@drive_bp.route('/storage/total')
@login_required
def storage_total():
    total_bytes = get_user_total_storage(current_user.id)
    return jsonify({
        'total_bytes': total_bytes,
        'total_human': format_bytes(total_bytes)
    })


#fonction utlitaire pour le formatage en byte 
def format_bytes(bytes_num):
    if bytes_num == 0:
        return "0 o"
    import math
    units = ['o', 'Ko', 'Mo', 'Go', 'To', 'Po']
    exp = int(math.log(bytes_num, 1024))
    exp = min(exp, len(units) - 1)
    return f"{bytes_num / (1024 ** exp):.2f} {units[exp]}".strip()



@drive_bp.route('/user-stats')
@login_required
def user_stats():
    try:
        # 1. Tous les dossiers créés par l'utilisateur (personnels + partagés par lui)
        total_owned_folders = Folder.query.filter_by(
            owner_id=current_user.id, deleted=False
        ).count()

        # 2. Dossiers personnels (is_personal = True)
        personal_folders = Folder.query.filter_by(
            owner_id=current_user.id, is_personal=True, deleted=False
        ).count()

        # 3. Dossiers que j'ai créés ET que j'ai partagés à au moins une personne
        shared_by_me = db.session.query(Folder.id) \
            .filter(Folder.owner_id == current_user.id, Folder.deleted == False) \
            .join(FolderPermission, Folder.id == FolderPermission.folder_id) \
            .distinct().count()

        # 4. Dossiers partagés AVEC MOI (créés par d'autres)
        shared_with_me = db.session.query(FolderPermission.folder_id) \
            .filter(
                FolderPermission.user_id == current_user.id,
                FolderPermission.can_read == True
            ).distinct().count()

        # 5. Mes fichiers
        total_files = File.query.filter_by(owner_id=current_user.id, deleted=False).count()

        # 6. Favoris
        favorite_files = Favorite.query.filter_by(user_id=current_user.id).count()

        return jsonify({
            'total_owned_folders': total_owned_folders,        # Tous mes dossiers créés
            'personal_folders': personal_folders,              # Mes dossiers personnels
            'shared_by_me': shared_by_me,                      # NOUVEAU : que j'ai partagés
            'shared_with_me': shared_with_me,                  # NOUVEAU : reçus
            'total_files': total_files,
            'favorite_files': favorite_files,
        })

    except Exception as e:
        print("ERREUR user_stats:", e)
        return jsonify({'error': 'Impossible de charger les statistiques'}), 500
