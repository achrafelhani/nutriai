import os
import secrets

from dotenv import load_dotenv

load_dotenv()


class Config:
    # Sans .env, une clé aléatoire est générée à chaque démarrage :
    # l'application fonctionne, mais les sessions ne survivent pas au redémarrage.
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///nutriai.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Taille maximale d'une requête (photo de repas) : 8 Mo.
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024
