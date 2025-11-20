# app/utils/security.py
from werkzeug.security import generate_password_hash, check_password_hash

def hash_password(password: str) -> str:
    """Génère un hash compatible avec Flask (pbkdf2:sha256)"""
    return generate_password_hash(password)

def check_password(stored_hash: str, password: str) -> bool:
    """Vérifie un mot de passe haché avec Werkzeug"""
    try:
        return check_password_hash(stored_hash, password)
    except Exception as e:
        print(f"Erreur check_password: {e}")  # Pour debug
        return False