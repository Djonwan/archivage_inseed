# create_superadmin.py
# À exécuter UNE SEULE FOIS après le premier déploiement
from app import create_app, db
from app.models.user import User

app = create_app()

with app.app_context():
    # Vérifie si un super_admin existe déjà
    if User.query.filter_by(role='super_admin').first():
        print("Un super administrateur existe déjà !")
    else:
        admin = User(
            name="Administrateur INSEED",
            email="admin@inseed.td",           # ← Change cette adresse
            role="super_admin",
            is_active=True
        )
        admin.set_password("TonMotDePasseTrèsSécurisé2025!")  # ← Change-le obligatoirement !
        db.session.add(admin)
        db.session.commit()
        print("Super administrateur créé avec succès !")
        print(f"Email : admin@inseed.td")
        print(f"Mot de passe : TonMotDePasseTrèsSécurisé2025!")