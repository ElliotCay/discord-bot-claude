import logging
import os
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

def setup_logger():
    load_dotenv()
    
    # Création du dossier de logs s'il n'existe pas
    log_file_path = os.getenv('LOG_FILE_PATH', 'data/logs/bot.log')
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    
    # Configuration du logger
    logger = logging.getLogger('discord_claude_bot')
    logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))
    
    # Format du log
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler pour les fichiers (avec rotation)
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=10485760,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # Handler pour la console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Ajout des handlers au logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger