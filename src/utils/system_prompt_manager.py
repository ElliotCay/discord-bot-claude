import os
import json
from datetime import datetime
import logging

class SystemPromptManager:
    def __init__(self):
        self.logger = logging.getLogger('discord_claude_bot')
        
        # Création du dossier de données si nécessaire
        self.data_dir = 'data/system_prompts'
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Fichier pour stocker les prompts
        self.prompts_file = f"{self.data_dir}/prompts.json"
        
        # Structure des données
        self.prompts = {}
        self.active_prompt = None
        
        # Chargement des données existantes
        self._load_prompts()
    
    def _load_prompts(self):
        """Charge les prompts depuis le fichier"""
        try:
            if os.path.exists(self.prompts_file):
                with open(self.prompts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.prompts = data.get('prompts', {})
                    self.active_prompt = data.get('active_prompt')
                self.logger.info("Prompts système chargés avec succès")
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement des prompts système: {str(e)}")

    def _save_prompts(self):
        """Sauvegarde les prompts dans le fichier"""
        try:
            with open(self.prompts_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'prompts': self.prompts,
                    'active_prompt': self.active_prompt
                }, f, indent=2, ensure_ascii=False)
            self.logger.info("Prompts système sauvegardés avec succès")
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde des prompts système: {str(e)}")

    def create_prompt(self, name: str, content: str) -> bool:
        """Crée ou met à jour un prompt système"""
        try:
            # Validation basique du nom
            name = name.strip()
            if not name or not content:
                return False
                
            timestamp = datetime.now().isoformat()
            is_update = name in self.prompts
            
            self.prompts[name] = {
                'content': content,
                'created_at': self.prompts[name]['created_at'] if is_update else timestamp,
                'updated_at': timestamp
            }
            
            self._save_prompts()
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors de la création du prompt système: {str(e)}")
            return False

    def delete_prompt(self, name: str) -> bool:
        """Supprime un prompt système"""
        try:
            if name in self.prompts:
                del self.prompts[name]
                if self.active_prompt == name:
                    self.active_prompt = None
                self._save_prompts()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Erreur lors de la suppression du prompt système: {str(e)}")
            return False

    def get_prompt(self, name: str) -> dict:
        """Récupère un prompt système spécifique"""
        return self.prompts.get(name)

    def get_all_prompts(self) -> dict:
        """Récupère tous les prompts système"""
        return self.prompts

    def set_active_prompt(self, name: str) -> bool:
        """Définit le prompt système actif"""
        if name in self.prompts or name is None:
            self.active_prompt = name
            self._save_prompts()
            return True
        return False

    def get_active_prompt(self) -> tuple:
        """Récupère le prompt système actif"""
        if self.active_prompt and self.active_prompt in self.prompts:
            return self.active_prompt, self.prompts[self.active_prompt]['content']
        return None, None