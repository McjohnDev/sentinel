from datetime import datetime, time
from typing import Dict, List, Optional
import json


class AvailabilityService:
    """Service pour la gestion des fenêtres horaires de disponibilité."""
    
    @staticmethod
    def get_current_day_name() -> str:
        """
        Retourne le nom du jour actuel en minuscules (ex: 'monday').
        
        Returns:
            Nom du jour en minuscules
        """
        return datetime.utcnow().strftime('%A').lower()
    
    @staticmethod
    def parse_time(time_str: str) -> time:
        """
        Parse une chaîne de temps au format HH:MM en objet time.
        
        Args:
            time_str: Chaîne de temps au format HH:MM
            
        Returns:
            Objet time
        """
        hour, minute = map(int, time_str.split(':'))
        return time(hour, minute)
    
    @staticmethod
    def get_current_time() -> time:
        """
        Retourne l'heure actuelle en UTC.
        
        Returns:
            Objet time représentant l'heure actuelle UTC
        """
        return datetime.utcnow().time()
    
    @staticmethod
    def is_time_in_range(current_time: time, start_time: time, end_time: time) -> bool:
        """
        Vérifie si l'heure actuelle est dans une plage horaire.
        
        Args:
            current_time: Heure actuelle
            start_time: Heure de début
            end_time: Heure de fin
            
        Returns:
            True si l'heure actuelle est dans la plage, False sinon
        """
        return start_time <= current_time <= end_time
    
    @staticmethod
    def is_within_time_windows(time_windows_json: str) -> bool:
        """
        Vérifie si l'heure actuelle est dans les fenêtres horaires configurées.
        
        Args:
            time_windows_json: JSON des fenêtres horaires
                Format: {"monday": [{"start": "08:00", "end": "12:00"}, {"start": "14:00", "end": "18:00"}], ...}
                
        Returns:
            True si l'heure actuelle est dans une fenêtre horaire, False sinon
            Si aucune fenêtre n'est configurée ou si le JSON est invalide, retourne True (pas de restriction)
        """
        try:
            time_windows = json.loads(time_windows_json) if time_windows_json else {}
        except (json.JSONDecodeError, TypeError):
            # JSON invalide, pas de restriction
            return True
        
        if not time_windows:
            # Aucune fenêtre configurée, pas de restriction
            return True
        
        current_day = AvailabilityService.get_current_day_name()
        day_windows = time_windows.get(current_day, [])
        
        if not day_windows:
            # Aucune fenêtre configurée pour ce jour, pas de restriction
            return True
        
        current_time = AvailabilityService.get_current_time()
        
        # Vérifier si l'heure actuelle est dans l'une des plages
        for window in day_windows:
            start_str = window.get('start')
            end_str = window.get('end')
            
            if not start_str or not end_str:
                continue
            
            try:
                start_time = AvailabilityService.parse_time(start_str)
                end_time = AvailabilityService.parse_time(end_str)
                
                if AvailabilityService.is_time_in_range(current_time, start_time, end_time):
                    return True
            except (ValueError, TypeError):
                continue
        
        # L'heure actuelle n'est dans aucune fenêtre
        return False
    
    @staticmethod
    def should_alert_offline(
        agent_id: str,
        machine_type: str,
        last_communication: datetime,
        availability_policy: Optional[Dict] = None
    ) -> tuple[bool, str]:
        """
        Détermine si une alerte offline doit être générée pour un agent.
        
        Args:
            agent_id: ID de l'agent
            machine_type: Type de machine (server/workstation)
            last_communication: Dernière communication de l'agent
            availability_policy: Politique de disponibilité (optionnel)
                {
                    "time_windows_enabled": bool,
                    "time_windows": str (JSON),
                    "offline_threshold_seconds": int
                }
                
        Returns:
            Tuple (should_alert, reason)
                should_alert: True si une alerte doit être générée
                reason: Raison de la décision
        """
        from src.config import settings
        from datetime import timedelta
        
        # Déterminer le seuil offline
        if availability_policy and availability_policy.get('offline_threshold_seconds'):
            threshold_seconds = availability_policy['offline_threshold_seconds']
        else:
            # Utiliser le seuil par défaut selon le type de machine
            if machine_type == 'server':
                threshold_seconds = settings.server_offline_alert_threshold_seconds
            else:  # workstation
                threshold_seconds = settings.workstation_offline_alert_threshold_seconds
        
        # Vérifier si l'agent est hors ligne selon le seuil
        threshold = datetime.utcnow() - timedelta(seconds=threshold_seconds)
        is_offline = last_communication and last_communication < threshold
        
        if not is_offline:
            return False, "Agent en ligne"
        
        # Pour les serveurs, toujours alerter si hors ligne
        if machine_type == 'server':
            return True, f"Serveur hors ligne depuis {last_communication} (seuil: {threshold_seconds}s)"
        
        # Pour les postes de travail, vérifier les fenêtres horaires
        if availability_policy and availability_policy.get('time_windows_enabled'):
            time_windows = availability_policy.get('time_windows', '{}')
            
            if AvailabilityService.is_within_time_windows(time_windows):
                # L'agent est hors ligne pendant ses heures normales de fonctionnement
                return True, f"Poste hors ligne pendant fenêtre horaire (seuil: {threshold_seconds}s)"
            else:
                # L'agent est hors ligne en dehors de ses heures normales, pas d'alerte
                return False, "Poste hors ligne en dehors des fenêtres horaires normales"
        
        # Pas de politique de fenêtres horaires, utiliser le seuil par défaut
        return True, f"Poste hors ligne depuis {last_communication} (seuil: {threshold_seconds}s)"
