import os
import json
from datetime import datetime, date, timedelta
import logging
from collections import defaultdict
import pandas as pd

class CostTracker:
    def __init__(self):
        self.logger = logging.getLogger('discord_claude_bot')
        
        # Création des dossiers nécessaires
        self.data_dir = 'data/stats'
        self.reports_dir = 'data/reports'
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)
        
        # Fichier pour les statistiques permanentes
        self.stats_file = f"{self.data_dir}/all_stats.json"
        
        # Chargement des coûts depuis les variables d'environnement avec valeurs par défaut
        self.costs = {
            'claude-3-5-haiku-20241022': {  # Nouveau modèle
                'input': float(os.getenv('HAIKU_3_5_PROMPT_COST', '0.001')),
                'output': float(os.getenv('HAIKU_3_5_COMPLETION_COST', '0.005'))
            },
            'claude-3-haiku-20240307': {
                'input': float(os.getenv('HAIKU_PROMPT_COST', '0.00025')),
                'output': float(os.getenv('HAIKU_COMPLETION_COST', '0.00025'))
            },
            'claude-3-sonnet-20240229': {
                'input': float(os.getenv('SONNET_PROMPT_COST', '0.003')),
                'output': float(os.getenv('SONNET_COMPLETION_COST', '0.003'))
            },
            'claude-3-opus-20240229': {
                'input': float(os.getenv('OPUS_PROMPT_COST', '0.008')),
                'output': float(os.getenv('OPUS_COMPLETION_COST', '0.008'))
            }
        }
        
        # Charger les statistiques existantes
        self.stats = self._load_stats()
        
    def _load_stats(self):
        """Charge les statistiques depuis le fichier"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    stats = json.load(f)
                self.logger.info("Statistiques chargées avec succès")
                return stats
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement des stats: {str(e)}")
        
        # Retourner une structure vide si le fichier n'existe pas ou est corrompu
        return {}

    def _save_stats(self):
        """Sauvegarde les statistiques dans le fichier"""
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, indent=2)
            self.logger.info("Statistiques sauvegardées avec succès")
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde des stats: {str(e)}")

    def track_request(self, model: str, input_tokens: int, output_tokens: int):
        """Enregistre une requête à l'API"""
        today = date.today().isoformat()
        
        # Calcul des coûts
        input_cost = (input_tokens / 1000) * self.costs[model]['input']
        output_cost = (output_tokens / 1000) * self.costs[model]['output']
        total_cost = input_cost + output_cost
        
        # Initialiser la structure si nécessaire
        if today not in self.stats:
            self.stats[today] = {
                'total_cost': 0.0,
                'total_tokens': 0,
                'requests': 0,
                'model_usage': defaultdict(int),
                'token_usage': defaultdict(lambda: {'input': 0, 'output': 0})
            }
        
        # Mise à jour des statistiques
        self.stats[today]['total_cost'] += total_cost
        self.stats[today]['total_tokens'] += (input_tokens + output_tokens)
        self.stats[today]['requests'] += 1
        self.stats[today]['model_usage'][model] = self.stats[today]['model_usage'].get(model, 0) + 1
        
        if model not in self.stats[today]['token_usage']:
            self.stats[today]['token_usage'][model] = {'input': 0, 'output': 0}
        
        self.stats[today]['token_usage'][model]['input'] += input_tokens
        self.stats[today]['token_usage'][model]['output'] += output_tokens
        
        # Sauvegarde après chaque mise à jour
        self._save_stats()
        
        # Log de la requête
        self.logger.info(
            f"Requête: {model} - {input_tokens}/{output_tokens} tokens "
            f"- Coût: ${total_cost:.4f}"
        )

    def _aggregate_stats(self, start_date, end_date):
        """Agrège les statistiques sur une période donnée"""
        aggregated = {
            'total_cost': 0.0,
            'total_tokens': 0,
            'requests': 0,
            'model_usage': defaultdict(int),
            'token_usage': defaultdict(lambda: {'input': 0, 'output': 0})
        }
        
        for date_str, daily_stats in self.stats.items():
            if start_date <= date_str <= end_date:
                aggregated['total_cost'] += daily_stats['total_cost']
                aggregated['total_tokens'] += daily_stats['total_tokens']
                aggregated['requests'] += daily_stats['requests']
                
                for model, count in daily_stats['model_usage'].items():
                    aggregated['model_usage'][model] += count
                
                for model, tokens in daily_stats['token_usage'].items():
                    if model not in aggregated['token_usage']:
                        aggregated['token_usage'][model] = {'input': 0, 'output': 0}
                    aggregated['token_usage'][model]['input'] += tokens['input']
                    aggregated['token_usage'][model]['output'] += tokens['output']
        
        return aggregated

    def generate_report(self, period='day'):
        """Génère un rapport pour la période spécifiée (day, week, all)"""
        today = date.today().isoformat()
        
        if period == 'day':
            stats = self._aggregate_stats(today, today)
            title = f"Rapport quotidien - {today}"
        elif period == 'week':
            week_start = (date.today() - timedelta(days=6)).isoformat()
            stats = self._aggregate_stats(week_start, today)
            title = f"Rapport hebdomadaire - Du {week_start} au {today}"
        else:  # 'all'
            if not self.stats:
                return "Aucune statistique disponible"
            start_date = min(self.stats.keys())
            stats = self._aggregate_stats(start_date, today)
            title = f"Rapport complet - Du {start_date} au {today}"

        report = f"""# {title}

## Résumé
- Nombre total de requêtes : {stats['requests']:,}
- Coût total : ${stats['total_cost']:.4f}
- Tokens totaux : {stats['total_tokens']:,}

## Utilisation par modèle"""

        for model, count in stats['model_usage'].items():
            token_usage = stats['token_usage'].get(model, {'input': 0, 'output': 0})
            report += f"\n### {model}\n"
            report += f"- Nombre de requêtes : {count:,}\n"
            report += f"- Tokens en entrée : {token_usage['input']:,}\n"
            report += f"- Tokens en sortie : {token_usage['output']:,}\n"
            
        # Sauvegarde du rapport
        try:
            filename = f"{self.reports_dir}/report_{period}_{today}.md"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report)
            self.logger.info(f"Rapport généré : {filename}")
        except Exception as e:
            self.logger.error(f"Erreur lors de la génération du rapport : {str(e)}")
            
        return report

    def export_stats_to_csv(self, start_date=None, end_date=None):
        """Exporte les statistiques dans un fichier CSV"""
        try:
            # Préparation des données
            data = []
            for date_str, stats in sorted(self.stats.items()):
                if start_date and date_str < start_date:
                    continue
                if end_date and date_str > end_date:
                    continue
                    
                row = {
                    'date': date_str,
                    'requests': stats['requests'],
                    'total_cost': stats['total_cost'],
                    'total_tokens': stats['total_tokens']
                }
                
                for model in self.costs.keys():
                    row[f'{model}_requests'] = stats['model_usage'].get(model, 0)
                    row[f'{model}_input_tokens'] = stats['token_usage'].get(model, {}).get('input', 0)
                    row[f'{model}_output_tokens'] = stats['token_usage'].get(model, {}).get('output', 0)
                
                data.append(row)
            
            # Création du DataFrame et export
            if data:
                df = pd.DataFrame(data)
                filename = f"{self.reports_dir}/stats_export_{date.today().isoformat()}.csv"
                df.to_csv(filename, index=False)
                self.logger.info(f"Stats exportées vers : {filename}")
                return filename
            else:
                self.logger.warning("Pas de données à exporter")
                return None
                
        except Exception as e:
            self.logger.error(f"Erreur lors de l'export des stats : {str(e)}")
            return None