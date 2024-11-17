try:
    import discord
    print("Discord.py version:", discord.__version__)
except ImportError as e:
    print("Erreur d'importation:", e)

try:
    from dotenv import load_dotenv
    print("python-dotenv importé avec succès")
except ImportError as e:
    print("Erreur d'importation dotenv:", e)
