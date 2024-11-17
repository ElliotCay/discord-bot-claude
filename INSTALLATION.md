# Guide d'installation - Discord Bot Claude

## Prérequis

Avant de commencer, assurez-vous d'avoir :

1. **Python 3.8 ou supérieur** installé sur votre machine
   - Pour vérifier : `python --version` ou `python3 --version`
   - Téléchargement : [Python.org](https://www.python.org/downloads/)

2. **Un bot Discord configuré**
   - Créez une application sur [Discord Developer Portal](https://discord.com/developers/applications)
   - Créez un bot dans votre application
   - Activez les "Privileged Gateway Intents" suivants :
     - MESSAGE CONTENT INTENT
     - PRESENCE INTENT
     - SERVER MEMBERS INTENT
   - Notez le token du bot pour plus tard

3. **Une clé API Anthropic**
   - Créez un compte sur [Anthropic](https://www.anthropic.com/)
   - Obtenez votre clé API

## Installation

1. **Clonez ou téléchargez le projet**
   ```bash
   git clone <url-du-repo>
   cd discord-bot-claude
   ```

2. **Créez un environnement virtuel**
   ```bash
   # Sur macOS/Linux
   python3 -m venv venv
   source venv/bin/activate

   # Sur Windows
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. **Installez les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurez le fichier .env**
   ```bash
   # Copier le fichier exemple
   cp .env.example .env
   ```

   Éditez le fichier .env avec vos informations :
   ```env
   # Discord Configuration
   DISCORD_TOKEN=votre_token_discord
   ALLOWED_USER_ID=votre_id_utilisateur_discord
   ANTHROPIC_API_KEY=votre_cle_api_anthropic

   # Bot Configuration
   DEFAULT_MODEL=claude-3-haiku-20240307
   CONVERSATION_TIMEOUT=3600
   MAX_HISTORY=10

   # Logging Configuration
   LOG_LEVEL=DEBUG
   LOG_FILE_PATH=data/logs/bot.log
   ```

## Vérification de l'installation

1. **Testez l'installation des dépendances**
   ```bash
   python test.py
   ```
   Vous devriez voir les versions de discord.py et python-dotenv s'afficher sans erreur.

2. **Vérifiez la structure des dossiers**
   ```
   discord-bot-claude/
   ├── data/
   │   ├── logs/
   │   ├── reports/
   │   └── stats/
   ├── src/
   ├── venv/
   ├── .env
   └── run.py
   ```
   Les dossiers manquants seront créés automatiquement au premier lancement.

## Lancement du bot

1. **Démarrer le bot**
   ```bash
   # Assurez-vous que l'environnement virtuel est activé
   python run.py
   ```

2. **Vérifier le fonctionnement**
   - Le bot devrait se connecter et afficher "Bot connecté en tant que [nom_du_bot]"
   - Dans Discord, testez avec la commande `!khelp`

## Commandes disponibles

- `!kask <message>` - Question avec Claude 3.5 Haiku (défaut)
- `!kask haiku <message>` - Question avec Claude 3 Haiku (ancien)
- `!kask sonnet <message>` - Question avec Claude Sonnet
- `!kask opus <message>` - Question avec Claude Opus
- `!kstats` - Statistiques d'utilisation
- `!kexport` - Export des stats en CSV
- `!kclear` - Efface l'historique
- `!khelp` - Aide

## Résolution des problèmes courants

1. **"ModuleNotFoundError"**
   - Vérifiez que l'environnement virtuel est activé
   - Réinstallez les dépendances : `pip install -r requirements.txt`

2. **"Discord.py DiscordException"**
   - Vérifiez que le token Discord est correct
   - Vérifiez les permissions du bot

3. **"Anthropic API Error"**
   - Vérifiez que la clé API Anthropic est correcte
   - Vérifiez votre quota API

4. **"Permission Denied" pour les fichiers de log**
   - Vérifiez les droits d'écriture dans le dossier data/
   ```bash
   chmod -R 755 data/
   ```

## Support

Pour toute question ou problème :
1. Consultez les logs dans `data/logs/bot.log`
2. Consultez la [documentation Discord.py](https://discordpy.readthedocs.io/)
3. Consultez la [documentation Anthropic](https://docs.anthropic.com/)