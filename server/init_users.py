#!/usr/bin/env python3
"""
Script d'initialisation des utilisateurs par défaut.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from src.database import engine, SessionLocal
from src.models import User, UserRole
from src.auth_service import AuthService


def init_default_users():
    """Crée les utilisateurs par défaut si ils n'existent pas."""
    db: Session = SessionLocal()
    
    try:
        # Créer les utilisateurs par défaut
        default_users = [
            {
                "username": "operator",
                "email": "operator@cbcam.cm",
                "password": "Operator123!",
                "role": UserRole.OPERATOR
            },
            {
                "username": "readonly",
                "email": "readonly@cbcam.cm",
                "password": "Readonly123!",
                "role": UserRole.READ_ONLY
            }
        ]
        
        print("🔧 Création des utilisateurs par défaut...")
        
        for user_data in default_users:
            try:
                user = AuthService.create_user(
                    db,
                    user_data["username"],
                    user_data["email"],
                    user_data["password"],
                    user_data["role"]
                )
                print(f"✅ Utilisateur créé: {user.username} ({user.email}) - Rôle: {user.role.value}")
            except ValueError as e:
                print(f"⚠️  Utilisateur {user_data['username']} existe déjà: {e}")
        
        db.commit()
        
        # Afficher tous les utilisateurs
        all_users = db.query(User).all()
        print("\n📋 Tous les utilisateurs de la base de données:")
        print("=" * 50)
        for user in all_users:
            print(f"👤 {user.username}")
            print(f"   Email: {user.email}")
            print(f"   Rôle: {user.role.value}")
            print(f"   Actif: {user.is_active}")
            print(f"   Créé le: {user.created_at}")
            print()
        
        print("\n� Identifiants de connexion par défaut (si mot de passe inconnu):")
        print("=" * 50)
        for user_data in default_users:
            print(f"👤 {user_data['username']}")
            print(f"   Email: {user_data['email']}")
            print(f"   Mot de passe: {user_data['password']}")
            print(f"   Rôle: {user_data['role'].value}")
            print()
        
        print("🎉 Initialisation terminée avec succès!")
        
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    init_default_users()
