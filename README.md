# Discord Claude Bot

Un bot Discord personnel utilisant l'API Claude d'Anthropic.

## Fonctionnalités

- Utilisation de l'API Claude (Haiku, Sonnet, Opus)
- Mémoire des conversations
- Suivi des coûts et rapports quotidiens
- Réponse aux mentions et aux réponses
- Accès restreint à un seul utilisateur

## Installation

1. Cloner le repository
```bash
git clone <repository-url>
cd discord_claude_bot
```

2. Créer un environnement virtuel
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

3. Installer les dépendances
```bash
pip install -r requirements.txt
```

4. Copier le fichier .env.example vers .env et configurer les variables
```bash
cp .env.example .env
```

5. Lancer le bot
```bash
python run.py
```

## Configuration

Modifier le fichier .env avec vos propres valeurs :
- DISCORD_TOKEN : Token de votre bot Discord
- ALLOWED_USER_ID : Votre ID utilisateur Discord
- ANTHROPIC_API_KEY : Votre clé API Anthropic

## Commandes

- `!kask <message>` - Poser une question (utilise Claude Haiku)
- `!kask-sonnet <message>` - Poser une question avec Claude Sonnet
- `!kask-opus <message>` - Poser une question avec Claude Opus
- `!kstats` - Afficher les statistiques d'utilisation
- `!kexport` - Exporter les statistiques en CSV
- `!kclear` - Effacer l'historique de conversation
- `!khelp` - Afficher l'aide

## Maintenance

Les logs sont stockés dans `data/logs/`
Les rapports de coûts sont générés dans `data/reports/`