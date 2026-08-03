#!/bin/bash
# Script de sauvegarde automatique PostgreSQL pour CBC Supervision Platform

# Configuration
DB_NAME="cbc_supervision"
DB_USER="cbc_user"
DB_PASSWORD="cbc_password"
DB_HOST="localhost"
DB_PORT="5432"

# Répertoire de sauvegarde
BACKUP_DIR="/home/bryan_curtis/Desktop/CBC - AGENT/server/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/cbc_supervision_$DATE.sql.gz"

# Créer le répertoire de sauvegarde s'il n'existe pas
mkdir -p "$BACKUP_DIR"

# Effectuer la sauvegarde
echo "Début de la sauvegarde de la base de données $DB_NAME..."
PGPASSWORD=$DB_PASSWORD pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME | gzip > "$BACKUP_FILE"

# Vérifier si la sauvegarde a réussi
if [ $? -eq 0 ]; then
    echo "Sauvegarde réussie: $BACKUP_FILE"
    
    # Conserver uniquement les 7 derniers jours de sauvegardes
    find "$BACKUP_DIR" -name "cbc_supervision_*.sql.gz" -mtime +7 -delete
    echo "Anciennes sauvegardes (plus de 7 jours) supprimées"
else
    echo "Erreur lors de la sauvegarde"
    exit 1
fi
