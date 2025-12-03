# archivage_inseed
# Portail d'Archivage des Données – INSEED

**Portail officiel d’archivage numérique sécurisé de l’Institut National de la Statistique, des Études Économiques et Démographiques (INSEED) **

> Système interne de gestion documentaire avec contrôle d’accès granulaire, validation des comptes par administrateur, notifications en temps réel et interface moderne.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Flask](https://img.shields.io/badge/Flask-3.0-green)
![SQLite](https://img.shields.io/badge/SQLite-Production-orange)
![Bootstrap 5](https://img.shields.io/badge/Bootstrap-5.3-purple)
![License]()

## Fonctionnalités principales

- **Inscription avec validation administrateur** (comptes créés → en attente d’activation)
- **Gestion complète des utilisateurs** (rôles : `user`, `super_admin`)
- **Système de dossiers et fichiers** avec permissions fines (lecture, édition, suppression, téléchargement)
- **Glisser-déposer** pour upload de fichiers et dossiers entiers
- **Notifications internes en temps réel** (cloche avec badge dynamique)
- **Photos de profil** avec prévisualisation et nom unique
- **Historique et traçabilité** des actions (en cours de finalisation)
- **Interface 100 % responsive** (mobile, tablette, desktop)
- **Design institutionnel INSEED** avec charte graphique officielle

## Technologies utilisées

| Technologie         | Version   | Rôle                                  |
|---------------------|-----------|---------------------------------------|
| Python              | 3.11+     | Backend                               |
| Flask               | 3.0+      | Framework web                         |
| Flask-Login         |           | Authentification                      |
| Flask-SQLAlchemy    |           | ORM & base de données                 |
| Mysql               |           | Base de données                       |
| Bootstrap 5         | 5.3       | Interface moderne                     |
| Bootstrap Icons     | 1.11      | Icônes                                |
| JavaScript (vanilla)|           | Interactions dynamiques               |




## Structure du projet
archivage-inseed/
├── app/
│   ├── init.py              # Création de l'app Flask
│   ├── models/                  # Modèles SQLAlchemy (User, Folder, File, etc.)
│   ├── routes/                  # Routes organisées par Blueprint
│   ├── static/                  # CSS, JS, images, logos
│   │   ├── img/profiles/        # Photos de profil utilisateurs
│   │   └── css/style.css
|   |   |_js
│   ├── templates/               # Templates Jinja2
│   └── utils/                   # Helpers (notifications, etc.)
├── run.py                       # Point d’entrée Flask
├── requirements.txt
├── .env                         # Variables d’environnement (ne pas committer)
└── README.md
└──config.py                     # fichier principale de configuration
└──uploads
└──create_superadmin.py          #fichier pour creer le super admin au depart dans le server



#creation d un super admin au depart avec python 
from app import create_app, db
from app.models.user import User
app = create_app()
with app.app_context():
    admin = User(name="Admin INSEED", email="admin@inseed.td", role="super_admin", is_active=True)
    admin.set_password("MotDePasseSécurisé123!")
    db.session.add(admin)
    db.session.commit()

## comment l executer 
# Sur le serveur, après le déploiement
cd /chemin/vers/archivage-inseed
source venv/bin/activate
python create_superadmin.py


