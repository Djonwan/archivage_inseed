# app/utils/email.py
from flask_mail import Message
from app import mail
from flask import url_for, current_app

def send_new_user_notification_to_superadmin(new_user):
    # Récupérer tous les super_admins actifs
    from app.models.user import User
    super_admins = User.query.filter_by(role='super_admin', is_active=True).all()
    
    if not super_admins:
        return  # Pas de super admin → rien à faire

    # Lien direct vers la liste des utilisateurs
    admin_list_url = url_for('admin.list_users', _external=True)

    html_body = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Nouvelle demande d'inscription</title>
    </head>
    <body style="margin:0; padding:0; background:#f8f9fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9fa; padding:40px 20px;">
        <tr>
        <td align="center">
            <table width="100%" cellpadding="0" cellspacing="0" style="max-width:620px; background:#ffffff; border-radius:16px; overflow:hidden; box-shadow:0 10px 30px rgba(0,0,0,0.08);">
                <!-- En-tête officiel -->
                
                <!-- En-tête officiel – Logo à gauche + texte à droite -->
                <tr>
                    <td style="background: linear-gradient(135deg, #d43939, #a83232); padding:30px 40px;">
                        <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
                            <tr>
                                <td align="left" valign="middle" style="color:#ffffff;">
                                    <!-- TITRE + TEXTE EN HAUT -->
                                    <h1 style="margin:0; font-size:28px; font-weight:700; line-height:1.2;">
                                        Nouvelle inscription en attente
                                    </h1>
                                    <p style="margin:8px 0 20px; font-size:16px; color:#ffe6e6; line-height:1.4;">
                                        Institut National de la Statistique,<br>
                                        des Études Économiques et Démographiques - INSEED
                                    </p>

                                    <!-- LOGO EN BAS SOUS LE TEXTE -->
                                    <div style="margin-top:20px;" align="center">
                                        <img src="https://www.inseed.td/images/2018/07/10/new-logonew.png"
                                            alt="Logo INSEED"
                                            width="110"
                                            style="display:block; border:0; outline:none; height:auto;"
                                        >
                                    </div>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>

                
                
                



                <!-- Contenu -->
                <tr>
                    <td style="padding:40px 40px 30px;">
                    <h2 style="color:#a83232; margin-top:0; font-size:24px;">
                        Un nouvel utilisateur demande l'accès au système
                    </h2>
                    
                    <p style="color:#333; font-size:16px; line-height:1.6;">
                        Bonjour <strong>Administrateur</strong>,
                    </p>
                    
                    <p style="color:#333; font-size:16px; line-height:1.6;">
                        Une nouvelle personne vient de créer un compte et attend votre validation :
                    </p>

                    <div style="background:#fff0f0; border-left:6px solid #d43939; padding:20px; border-radius:8px; margin:25px 0;">
                        <p style="margin:5px 0; color:#333;">
                            <strong>Nom :</strong> {new_user.name}
                        </p>
                        <p style="margin:5px 0; color:#333;">
                            <strong>Email :</strong> {new_user.email}
                        </p>
                        <p style="margin:5px 0; color:#555;">
                            <em>Inscrit le {new_user.created_at.strftime('%d/%m/%Y à %H:%M')}</em>
                        </p>
                    </div>

                    <div style="text-align:center; margin:35px 0;">
                        <a href="{admin_list_url}" 
                           style="background:#d43939; color:#ffffff; padding:16px 36px; text-decoration:none; border-radius:50px; font-weight:600; font-size:17px; display:inline-block; box-shadow:0 6px 15px rgba(212,57,57,0.3);">
                           Aller à la gestion des utilisateurs
                        </a>
                    </div>

                    <hr style="border:none; border-top:1px solid #eee; margin:40px 0;">

                    <div style="text-align:center; color:#888; font-size:14px;">
                        <p style="margin:0;">
                        <strong>Ministère de l'Économie, du Plan et de la Coopération</strong><br>
                        République du Tchad — Unité • Travail • Progrès
                        </p>
                    </div>
                    </td>
                </tr>
                </table>

                <div style="margin-top:30px; color:#aaa; font-size:12px;">
                © 2025 Archivage INSEED — Tous droits réservés
                </div>
            </td>
        </tr>
    </table>
    </body>
    </html>
    """

    msg = Message(
        subject="Nouvelle demande d'inscription - Action requise",
        recipients=[admin.email for admin in super_admins],
        sender="Archivage DSDS-INSEED <djongwangpaklam@gmail.com>",
        html=html_body
    )
    
    try:
        mail.send(msg)
    except Exception as e:
        current_app.logger.error(f"Échec envoi email notification inscription : {e}")




# app/utils/helpers.py  (ou notification.py)
from app.models.notification import Notification
from app.models.user import User
from app import db
from flask import url_for

def create_new_registration_notification(new_user):
    """
    Crée une notification pour tous les super_admins lorsqu'un nouvel utilisateur s'inscrit
    """
    # Récupérer tous les super_admins actifs
    super_admins = User.query.filter_by(role='super_admin', is_active=True).all()
    
    if not super_admins:
        return  # Aucun super_admin → pas de notif

    title = "Nouvelle demande d’accès"
    message = f"{new_user.name} ({new_user.email}) souhaite accéder au système"
    url = url_for('admin.list_users')  # Lien direct vers la liste

    for admin in super_admins:
        notif = Notification(
            user_id=admin.id,
            title=title,
            message=message,
            url=url,
            is_read=False
        )
        db.session.add(notif)
    
    db.session.commit()