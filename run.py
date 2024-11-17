import asyncio
import os
from dotenv import load_dotenv
from src.bot.client import DiscordBot
from src.utils.logger import setup_logger

def main():
    # Charger les variables d'environnement
    load_dotenv()
    
    # Configuration du logger
    logger = setup_logger()
    logger.info("Démarrage du bot...")
    
    # Vérification des variables d'environnement requises
    required_env_vars = [
        'DISCORD_TOKEN',
        'ALLOWED_USER_ID',
        'ANTHROPIC_API_KEY'
    ]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Variables d'environnement manquantes : {', '.join(missing_vars)}")
        return
    
    # Création et démarrage du bot
    bot = DiscordBot()
    
    try:
        asyncio.run(bot.start(os.getenv('DISCORD_TOKEN')))
    except KeyboardInterrupt:
        logger.info("Arrêt du bot...")
        asyncio.run(bot.close())
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution du bot : {e}")
        asyncio.run(bot.close())

if __name__ == "__main__":
    main()