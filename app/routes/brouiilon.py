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
from flask_mail import Message
import zipfile, io, os
from datetime import datetime


drive_bp = Blueprint('drive', __name__, template_folder='templates/drive')


@drive_bp.route('/')
@login_required
def index():
    return redirect(url_for('drive.home'))



@drive_bp.route('/home')
@login_required
def home():
    # Dossiers créés par l'utilisateur (racine uniquement + non supprimés)
    folders = Folder.query.filter_by(
        owner_id=current_user.id,
        parent_id=None,
        deleted=False
    ).order_by(Folder.created_at.desc()).all()

    return render_template('drive/home.html', folders=folders)


@drive_bp.route('/create_folder', methods=['GET', 'POST'])
@login_required
def create_folder():
    if request.method == 'GET':
        all_users = User.query.filter(User.id != current_user.id).all()
        return render_template('drive/create_folder.html', all_users=all_users)

    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        return jsonify({"success": False, "error": "Nom requis"}), 400

    # Créer le dossier
    folder = Folder(
        name=name,
        description_folder=description,
        owner_id=current_user.id,
        is_personal=False
    )
    db.session.add(folder)
    db.session.flush()

    # === PERMISSIONS ===
    permissions_by_user = {}
    for key, value in request.form.items():
        if key.startswith('perm_') and value == 'on':
            parts = key.split('_')
            user_id = parts[1]
            action = parts[2]
            if user_id not in permissions_by_user:
                permissions_by_user[user_id] = {
                    'can_read': False, 'can_edit': False,
                    'can_delete': False, 'can_download': False
                }
            permissions_by_user[user_id][f'can_{action}'] = True

    notified_users = []
    for user_id, perms in permissions_by_user.items():
        perm = FolderPermission(folder_id=folder.id, user_id=user_id, **perms)
        db.session.add(perm)
        notified_users.append(User.query.get(int(user_id)))

    db.session.commit()
    log_activity(current_user, 'created', folder=folder)

    # === EMAIL ===
    for user in notified_users:
        msg = Message(
            subject=f"Nouveau dossier partagé : {folder.name}",
            recipients=[user.email],
            body=f"""
            Bonjour {user.name},

            {current_user.name} a créé un nouveau dossier et vous y a donné accès :

            → **{folder.name}**

            Lien direct : {url_for('drive.folder', folder_id=folder.id, _external=True)}

            Cordialement,
            Portail DSDS
            """
        )
        mail.send(msg)

    # RETOUR JSON : succès + message + reset formulaire
    return jsonify({
        "success": True,
        "message": f"Dossier '{folder.name}' créé avec succès !",
        "folder_id": folder.id
    })


@drive_bp.route('/explore')
@login_required
def explore():
    folders = Folder.query.join(
        FolderPermission,
        (Folder.id == FolderPermission.folder_id) &
        (FolderPermission.user_id == current_user.id) &
        (FolderPermission.can_read == True),
        isouter=True
    ).filter(
        Folder.parent_id.is_(None),
        Folder.deleted == False,  # SEULEMENT LES DOSSIERS NON SUPPRIMÉS
        db.or_(
            Folder.owner_id == current_user.id,
            FolderPermission.user_id == current_user.id
        )
    ).order_by(Folder.created_at.desc()).distinct().all()

    return render_template('drive/explore.html', folders=folders)



@drive_bp.route('/folder/<int:folder_id>')
@login_required
def folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)

    # VÉRIFIER QUE LE DOSSIER N'EST PAS SUPPRIMÉ
    if folder.deleted:
        return redirect(url_for('drive.explore'))

    # VÉRIFICATION D'ACCÈS SILENCIEUSE
    if folder.owner_id != current_user.id:
        perm = FolderPermission.query.filter_by(
            folder_id=folder.id,
            user_id=current_user.id
        ).first()
        if not perm or not perm.can_read:
            return redirect(url_for('drive.explore'))

    # SOUS-DOSSIERS : UNIQUEMENT NON SUPPRIMÉS + ACCESSIBLES
    subfolders = Folder.query.join(
        FolderPermission,
        (Folder.id == FolderPermission.folder_id) &
        (FolderPermission.user_id == current_user.id) &
        (FolderPermission.can_read == True),
        isouter=True
    ).filter(
        Folder.parent_id == folder.id,
        Folder.deleted == False,  # EXCLURE LES SUPPRIMÉS
        db.or_(
            Folder.owner_id == current_user.id,
            FolderPermission.user_id == current_user.id
        )
    ).order_by(Folder.created_at.desc()).distinct().all()

    # FICHIERS : UNIQUEMENT NON SUPPRIMÉS
    files = File.query.filter_by(
        folder_id=folder.id,
        deleted=False  # DÉJÀ PRÉSENT, ON GARDE
    ).all()

    
    log_activity(current_user, 'opened', folder=folder)

    return render_template(
        'drive/folder_view.html',
        folder=folder,
        subfolders=subfolders,
        files=files
    )



@drive_bp.route('/folder/<int:folder_id>/create_subfolder', methods=['GET', 'POST'])
@login_required
def create_subfolder(folder_id):
    parent_folder = Folder.query.get_or_404(folder_id)

    # Vérifier si l'utilisateur peut modifier le dossier parent
    if parent_folder.owner_id != current_user.id:
        perm = FolderPermission.query.filter_by(folder_id=parent_folder.id, user_id=current_user.id).first()
        if not perm or not perm.can_edit:
            flash("Vous n'avez pas la permission de créer un sous-dossier ici.", "danger")
            return redirect(url_for('drive.folder', folder_id=folder_id))

    if request.method == 'GET':
        # Récupérer les utilisateurs qui ont accès au dossier parent
        accessible_user_ids = [
            p.user_id for p in parent_folder.permissions
        ]
        if parent_folder.owner_id != current_user.id:
            accessible_user_ids.append(current_user.id)

        users_with_access = User.query.filter(User.id.in_(accessible_user_ids)).all()

        return render_template(
            'drive/create_subfolder.html',
            parent_folder=parent_folder,
            users_with_access=users_with_access
        )

    # === POST : Création du sous-dossier ===
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        return jsonify({"success": False, "error": "Nom requis"}), 400

    subfolder = Folder(
        name=name,
        description_folder=description,
        parent_id=parent_folder.id,
        owner_id=current_user.id,
        is_personal=False
    )
    db.session.add(subfolder)
    db.session.flush()

    # === Permissions : uniquement sur les utilisateurs qui ont accès au parent ===
    permissions_by_user = {}
    for key, value in request.form.items():
        if key.startswith('perm_') and value == 'on':
            parts = key.split('_')
            user_id = parts[1]
            action = parts[2]
            if user_id not in permissions_by_user:
                permissions_by_user[user_id] = {
                    'can_read': False, 'can_edit': False,
                    'can_delete': False, 'can_download': False
                }
            permissions_by_user[user_id][f'can_{action}'] = True

    notified_users = []
    for user_id, perms in permissions_by_user.items():
        perm = FolderPermission(folder_id=subfolder.id, user_id=user_id, **perms)
        db.session.add(perm)
        notified_users.append(User.query.get(int(user_id)))

    db.session.commit()
    log_activity(current_user, 'created', folder=subfolder)

    # === Email de notification ===
    for user in notified_users:
        msg = Message(
            subject=f"Sous-dossier partagé : {subfolder.name}",
            recipients=[user.email],
            body=f"""
            Bonjour {user.name},

            {current_user.name} a créé un **sous-dossier** dans **{parent_folder.name}** :

            → **{subfolder.name}**

            Lien : {url_for('drive.folder', folder_id=subfolder.id, _external=True)}

            Cordialement,
            Portail DSDS
            """
        )
        mail.send(msg)

    return jsonify({
        "success": True,
        "message": f"Sous-dossier '{subfolder.name}' créé !",
        "folder_id": subfolder.id
    })



def get_folder_breadcrumb(folder):
    """Retourne la liste des dossiers parents jusqu'à la racine (ordre : racine → actuel)"""
    breadcrumb = []
    current = folder
    while current:
        breadcrumb.append(current)
        current = current.parent
    return breadcrumb[::-1]  # Inverse : racine → actuel


@drive_bp.route('/folder/<int:folder_id>/rename', methods=['POST'])
@login_required
def rename_folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    if not user_can_edit(folder, current_user):
        return jsonify({"success": False, "error": "Accès refusé"}), 403

    new_name = request.form.get('name', '').strip()
    if not new_name:
        return jsonify({"success": False, "error": "Nom requis"}), 400

    folder.name = new_name
    db.session.commit()

    return redirect(url_for('drive.folder', folder_id=folder.id))

@drive_bp.route('/folder/<int:folder_id>/delete', methods=['POST'])
@login_required
def delete_folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)

    # Vérifier les droits
    if not user_can(folder, 'delete'):
        flash("Accès refusé.", "danger")
        return redirect(url_for('drive.explore'))

    # === SOFT DELETE ===
    folder.deleted = True
    db.session.commit()
    flash(f"Dossier '{folder.name}' envoyé à la corbeille.", "info")

    # === REDIRECTION INTELLIGENTE ===
    if folder.parent_id:
        parent = Folder.query.get(folder.parent_id)
        if parent and not parent.deleted:
            return redirect(url_for('drive.folder', folder_id=parent.id))
    
    # Si parent supprimé ou inexistant → explore
    return redirect(url_for('drive.explore'))

# def delete_folder_recursive(folder):
#     """Supprime récursivement un dossier et tout son contenu"""
#     for subfolder in folder.children:
#         delete_folder_recursive(subfolder)
#     for file in folder.files:
#         if file.filename and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], file.filename)):
#             os.remove(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
#         db.session.delete(file)
#     db.session.delete(folder)


@drive_bp.route('/folder/<int:folder_id>/download')
@login_required
def download_folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    if not user_can_download(folder, current_user):
        return jsonify({"success": False, "error": "Accès refusé"}), 403

    memory_file = io.BytesIO()
    upload_folder = current_app.config['UPLOAD_FOLDER']

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


def add_folder_to_zip(zipf, folder, upload_folder, base_path=""):
    path_in_zip = base_path + folder.name if base_path else folder.name

    # === AJOUTER LE DOSSIER DANS LE ZIP (sans fichier) ===
    zip_info = zipfile.ZipInfo(path_in_zip + '/')
    zip_info.external_attr = 0o40775 << 16  # Permissions dossier (drwxrwxr-x)
    zipf.writestr(zip_info, b'')

    # === AJOUTER LES FICHIERS ===
    for file in folder.files.filter_by(deleted=False):
        file_path = os.path.join(upload_folder, file.filename)
        if os.path.exists(file_path):
            zipf.write(file_path, os.path.join(path_in_zip, file.original_name))

    # === RÉCURSION POUR SOUS-DOSSIERS ===
    for subfolder in folder.children:
        add_folder_to_zip(zipf, subfolder, upload_folder, path_in_zip + "/")


def user_can_edit(folder, user):
    if folder.owner_id == user.id:
        return True
    perm = FolderPermission.query.filter_by(folder_id=folder.id, user_id=user.id).first()
    return perm and perm.can_edit

def user_can_delete(folder, user):
    if folder.owner_id == user.id:
        return True
    perm = FolderPermission.query.filter_by(folder_id=folder.id, user_id=user.id).first()
    return perm and perm.can_delete

def user_can_download(folder, user):
    if folder.owner_id == user.id:
        return True
    perm = FolderPermission.query.filter_by(folder_id=folder.id, user_id=user.id).first()
    return perm and perm.can_download




import os, uuid
from werkzeug.utils import secure_filename
from flask import current_app, flash, request, redirect, url_for
from app.models.file import File

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']




@drive_bp.route('/folder/<int:folder_id>/upload', methods=['POST'])
@login_required
def upload_file(folder_id):
    folder = Folder.query.get_or_404(folder_id)

    # Vérification des droits
    if folder.owner_id != current_user.id:
        perm = FolderPermission.query.filter_by(folder_id=folder.id, user_id=current_user.id).first()
        if not perm or not perm.can_edit:
            flash("Accès refusé.", "danger")
            return redirect(url_for('drive.folder', folder_id=folder.id))

    if 'file' not in request.files:
        flash("Aucun fichier.", "danger")
        return redirect(url_for('drive.folder', folder_id=folder.id))

    file = request.files['file']
    if file.filename == '':
        flash("Aucun fichier sélectionné.", "danger")
        return redirect(url_for('drive.folder', folder_id=folder.id))

    if not allowed_file(file.filename):
        flash("Type non autorisé.", "danger")
        return redirect(url_for('drive.folder', folder_id=folder.id))

    # Nom original et sécurisé
    original_name = secure_filename(file.filename)
    ext = os.path.splitext(original_name)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

    # Sauvegarde
    file.save(filepath)

    # Création en DB
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

    flash(f"'{original_name}' ajouté avec succès !", "success")
    return redirect(url_for('drive.folder', folder_id=folder.id))


# app/routes/drive.py

from flask import send_file, abort
import os

@drive_bp.route('/file/<int:file_id>/download')
@login_required
def download_file(file_id):
    """
    Télécharge un fichier par son ID
    Vérifie :
    - Que le fichier existe
    - Que l'utilisateur a accès au dossier parent
    - Que le fichier n'est pas supprimé
    """
    file = File.query.get_or_404(file_id)

    # Vérifier que l'utilisateur a accès au dossier parent
    if file.folder.owner_id != current_user.id:
        perm = FolderPermission.query.filter_by(
            folder_id=file.folder_id,
            user_id=current_user.id
        ).first()
        if not perm or not perm.can_read:
            flash("Accès refusé.", "danger")
            return redirect(url_for('drive.folder', folder_id=file.folder_id))

    # Vérifier que le fichier n'est pas supprimé
    if file.deleted:
        flash("Fichier supprimé.", "danger")
        return redirect(url_for('drive.folder', folder_id=file.folder_id))

    # Chemin complet
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)

    # Vérifier que le fichier existe sur le disque
    if not os.path.exists(filepath):
        flash("Fichier introuvable sur le serveur.", "danger")
        return redirect(url_for('drive.folder', folder_id=file.folder_id))
    
    log_activity(current_user, 'downloaded', file=file)

    # Téléchargement avec le nom original
    return send_file(
        filepath,
        as_attachment=True,
        download_name=file.original_name  # ← Nom original (ex: Rapport.pdf)
    )



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


# === SUPPRIMER FICHIER (soft delete) ===
@drive_bp.route('/file/<int:file_id>/delete', methods=['POST'])
@login_required
def delete_file(file_id):
    file = File.query.get_or_404(file_id)

    # Vérifier permission de suppression via le dossier parent
    if file.folder.owner_id != current_user.id:
        perm = FolderPermission.query.filter_by(
            folder_id=file.folder_id,
            user_id=current_user.id
        ).first()
        if not perm or not perm.can_delete:
            flash("Accès refusé.", "danger")
            return redirect(url_for('drive.folder', folder_id=file.folder_id))

    # Soft delete
    file.deleted = True
    db.session.commit()

    flash(f"'{file.original_name}' envoyé à la corbeille.", "info")
    return redirect(url_for('drive.folder', folder_id=file.folder_id))



# === AJOUTER / SUPPRIMER FAVORI ===
@drive_bp.route('/file/<int:file_id>/favorite', methods=['POST'])
@login_required
def toggle_favorite(file_id):
    file = File.query.get_or_404(file_id)

    # Vérifier accès au dossier parent
    if file.folder.owner_id != current_user.id:
        perm = FolderPermission.query.filter_by(
            folder_id=file.folder_id,
            user_id=current_user.id
        ).first()
        if not perm or not perm.can_read:
            flash("Accès refusé.", "danger")
            return redirect(url_for('drive.folder', folder_id=file.folder_id))

    # Vérifier si déjà favori
    favorite = Favorite.query.filter_by(
        user_id=current_user.id,
        file_id=file_id
    ).first()

    if favorite:
        # Supprimer
        db.session.delete(favorite)
        db.session.commit()
        flash(f"'{file.original_name}' retiré des favoris.", "info")
    else:
        # Ajouter
        new_fav = Favorite(user_id=current_user.id, file_id=file_id)
        db.session.add(new_fav)
        db.session.commit()
        flash(f"'{file.original_name}' ajouté aux favoris !", "success")

    return redirect(url_for('drive.folder', folder_id=file.folder_id))


@drive_bp.route('/favorites')
@login_required
def favorites():
    # Récupérer tous les favoris de l'utilisateur
    favorites = Favorite.query.filter_by(user_id=current_user.id).all()
    files = [fav.file for fav in favorites if not fav.file.deleted]

    return render_template(
        'drive/favorites.html',
        files=files
    )


# === PAGE CORBEILLE ===
@drive_bp.route('/trash')
@login_required
def trash():
    # Fichiers supprimés par l'utilisateur
    files = File.query.filter_by(
        owner_id=current_user.id,
        deleted=True
    ).options(db.joinedload(File.folder)).all()

    # Dossiers supprimés par l'utilisateur
    folders = Folder.query.filter_by(
        owner_id=current_user.id,
        deleted=True
    ).all()

    return render_template(
        'drive/trash.html',
        files=files,
        folders=folders
    )


# === RESTAURER FICHIER ===
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

# === RESTAURER DOSSIER ===
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


from app import db
from app.models.activity import Activity

def log_activity(user, action, file=None, folder=None):
    """
    Enregistre une activité dans la table activities
    """
    act = Activity(
        user_id=user.id,
        file_id=file.id if file else None,
        folder_id=folder.id if folder else None,
        action=action
    )
    db.session.add(act)
    db.session.commit()



from datetime import timedelta, datetime
from sqlalchemy import or_, and_

from datetime import timedelta, datetime
from sqlalchemy import or_, and_

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



def user_can(folder, permission):
    if not folder or not current_user.is_authenticated:
        return False
    if folder.owner_id == current_user.id:
        return True
    perm = FolderPermission.query.filter_by(
        folder_id=folder.id,
        user_id= current_user.id
    ).first()
    if not perm:
        return False
    perm_map = {
        'read': perm.can_read,
        'edit': perm.can_edit,
        'delete': perm.can_delete,
        'download': perm.can_download
    }
    return perm_map.get(permission, False)
