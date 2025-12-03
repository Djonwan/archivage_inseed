# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY') or 'dev-secret-change-in-production-2025!'
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_DIR)
    UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'uploads')

    # Taille maximale : 500 Mo (adapté INSEED : enquêtes lourdes, bases REDATAM, etc.)
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500 MB

    # ==========================================================
    # EXTENSIONS AUTORISÉES – SPÉCIAL INSEED / STATISTIQUE
    # ==========================================================
    ALLOWED_EXTENSIONS = {
        # ─── Documents bureautiques ───
        'pdf', 'doc', 'docx', 'dotx', 'xls', 'xlsx', 'xlsm', 'xlsb',
        'ppt', 'pptx', 'ppsx', 'odt', 'ods', 'odp','exe'

        # ─── Statistiques & Analyses ───
        'sav',      # SPSS Data (*.sav)
        'por',      # SPSS Portable
        'zsav',     # SPSS compressé
        'dta',      # Stata (*.dta) – versions <15
        'dta18',    # Stata 18+ (nouveau format)
        'rda', 'rdata', # R
        'sas7bdat', # SAS
        'sas7bcat', # SAS catalogues
        'xpt',      # SAS Transport (XPORT)
        'cspro', 'dcf', 'mgc', # CSPro 
        'redatam', 'dic', 'ptr', # REDATAM (base nationale Tchad)

        # ─── Bases de données & Exports ───
        'dbf',      # dBase / FoxPro (très fréquent en Afrique)
        'mdb', 'accdb', # Microsoft Access
        'sqlite', 'db', 'sqlite3','sql',

        # ─── Données brutes & Textes ───
        'csv', 'tsv', 'txt', 'dat', 'tab',

        # ─── Images, Cartes & Visualisations ───
        'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp',
        'svg', 'eps',

        # ─── Archives compressées (pour envoyer plusieurs fichiers) ───
        'zip', 'rar', '7z', 'tar', 'gz', 'bz2',

        # ─── Vidéos & Formations (souvent partagées) ───
        'mp4', 'avi', 'mkv', 'mov', 'wmv', 'mp3', 'wav',

        # ─── Autres formats fréquents à l’INSEED ───
        'rtf', 'html', 'htm', 'xml', 'json', 'css', 'js', 'py',
        'kml', 'kmz',     # Cartes Google Earth (RGPH)
        'shp', 'shx', 'dbf', 'prj', 'cpg', # Shapefiles GIS (très important pour cartographie)
        'gpkg',           # GeoPackage (nouveau standard)
        'geojson',

        # ─── Logiciels de collecte mobile ───
        'odk', 'xlsform', 'xform',  # ODK / KoboToolbox
    }

    # ==========================================================
    # Configuration Email 
    # ==========================================================
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'False').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'Archivage INSEED <no-reply@inseed.td>')