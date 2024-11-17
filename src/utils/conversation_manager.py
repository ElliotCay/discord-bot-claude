import os
import json
from datetime import datetime, timedelta
from collections import defaultdict
import logging

class ConversationManager:
    def __init__(self):
        self.conversations = defaultdict(list)
        self.last_activity = defaultdict(datetime.now)
        self.max_history = int(os.getenv('MAX_HISTORY', 10))
        self.timeout = int(os.getenv('CONVERSATION_TIMEOUT', 3600))  # 1 heure par défaut
        self.logger = logging.getLogger('discord_claude_bot')
        
        # Création du dossier de sauvegarde si nécessaire
        self.save_dir = 'data/conversations'
        os.makedirs(self.save_dir, exist_ok=True)

    def _cleanup_old_conversations(self):
        """Nettoie les conversations inactives"""
        current_time = datetime.now()
        channels_to_remove = []
        
        for channel_id, last_time in self.last_activity.items():
            if (current_time - last_time).total_seconds() > self.timeout:
                channels_to_remove.append(channel_id)
                
        for channel_id in channels_to_remove:
            self._save_conversation(channel_id)
            del self.conversations[channel_id]
            del self.last_activity[channel_id]

    def _save_conversation(self, channel_id):
        """Sauvegarde une conversation dans un fichier"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{self.save_dir}/{channel_id}_{timestamp}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    'channel_id': channel_id,
                    'timestamp': timestamp,
                    'messages': self.conversations[channel_id]
                }, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"Conversation sauvegardée : {filename}")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde de la conversation : {str(e)}")

    def get_conversation(self, channel_id):
        """Récupère l'historique de conversation pour un canal"""
        self._cleanup_old_conversations()
        return self.conversations[channel_id]

    def add_message(self, channel_id, message):
        """Ajoute un message à l'historique de conversation"""
        self.conversations[channel_id].append(message)
        self.last_activity[channel_id] = datetime.now()
        
        # Limite la taille de l'historique
        if len(self.conversations[channel_id]) > self.max_history * 2:  # *2 car on compte les paires Q/R
            self._save_conversation(channel_id)
            self.conversations[channel_id] = self.conversations[channel_id][-self.max_history*2:]

    def clear_conversation(self, channel_id):
        """Efface l'historique de conversation pour un canal"""
        if channel_id in self.conversations:
            self._save_conversation(channel_id)
            del self.conversations[channel_id]
            del self.last_activity[channel_id]