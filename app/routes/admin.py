# app/routes/admin.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from werkzeug.utils import secure_filename
import os

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
        user.set_password(password)  # À corriger plus tard avec hash
        db.session.add(user)
        db.session.commit()

        flash(f"Utilisateur {name} créé avec succès !", "success")
        return redirect(url_for('drive.home'))

    return render_template('admin/create_user.html')

# app/routes/admin.py  (à ajouter après la route create_user)

@admin_bp.route('/users')
@login_required
def list_users():
    if not current_user.is_super_admin():
        flash("Accès refusé.", "danger")
        return redirect(url_for('drive.home'))
    
    users = User.query.all()
    return render_template('admin/users_list.html', users=users)


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if not current_user.is_super_admin():
        flash("Accès refusé.", "danger")
        return redirect(url_for('drive.home'))

    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        user.name = request.form['name']
        user.email = request.form['email']
        user.role = request.form['role']

        # Gestion de la photo
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join(UPLOAD_PROFILE, filename))
                user.profile_picture = filename

        db.session.commit()
        flash(f"Utilisateur {user.name} modifié avec succès !", "success")
        return redirect(url_for('admin.list_users'))

    return render_template('admin/edit_user.html', user=user)


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_super_admin():
        return jsonify(success=False, message="Accès refusé"), 403

    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify(success=False, message="Vous ne pouvez pas vous supprimer vous-même !"), 400

    # Optionnel : supprimer la photo physique
    if user.profile_picture and user.profile_picture != 'default.jpg':
        try:
            os.remove(os.path.join(UPLOAD_PROFILE, user.profile_picture))
        except:
            pass

    db.session.delete(user)
    db.session.commit()
    return jsonify(success=True)



