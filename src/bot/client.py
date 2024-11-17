import os
import discord
from discord.ext import commands
import logging

class DiscordBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guild_messages = True
        intents.guilds = True
        intents.members = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        
        self.logger = logging.getLogger('discord_claude_bot')
        self.allowed_user_id = int(os.getenv('ALLOWED_USER_ID'))
    
    async def setup_hook(self):
        try:
            self.logger.info("Tentative de chargement du cog Claude...")
            await self.load_extension('src.cogs.claude_commands')
            self.logger.info("Cog Claude chargé avec succès")
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement du cog Claude: {str(e)}")
            raise e
    
    async def on_ready(self):
        self.logger.info(f'Bot connecté en tant que {self.user.name}')
        await self.change_presence(activity=discord.Game(name="!kask pour discuter"))
        
        self.logger.info("Commandes disponibles :")
        for command in self.commands:
            self.logger.info(f"- {command.name}")
    
    async def on_message(self, message: discord.Message):
        """Gestion des messages reçus"""
        if message.author == self.user:
            return

        # Ignore les messages avec @everyone ou des mentions de rôles
        if message.mention_everyone or any(role.mention in message.content for role in message.guild.roles):
            return

        # Vérifie si le message est une commande ou mentionne spécifiquement le bot
        is_bot_command = message.content.startswith('!k')
        is_bot_mention = self.user.mentioned_in(message) and not any(role.mention in message.content for role in message.guild.roles)
        
        if not (is_bot_command or is_bot_mention):
            return

        self.logger.info("\n=== Nouveau message reçu ===")
        self.logger.info(f"ID : {message.id}")
        self.logger.info(f"Auteur : {message.author.name} (ID: {message.author.id})")
        self.logger.info(f"Contenu : {message.content}")
        self.logger.info(f"Canal : {message.channel.name} (ID: {message.channel.id})")

        # Vérifie si l'utilisateur est autorisé
        if message.author.id != self.allowed_user_id:
            if is_bot_command or is_bot_mention:
                self.logger.warning(f"Tentative d'utilisation non autorisée par {message.author.name}")
                allowed_user = await self.fetch_user(self.allowed_user_id)
                if allowed_user:
                    await message.channel.send(f"Désolé, je ne réponds qu'à mon propriétaire {allowed_user.mention}. 🔒")
                else:
                    await message.channel.send("Désolé, je ne réponds qu'à mon propriétaire. 🔒")
            return

        claude_cog = self.get_cog('ClaudeCommands')
        if not claude_cog:
            self.logger.error("Le cog ClaudeCommands n'est pas chargé")
            return

        # Vérifier si c'est une commande avec référence
        if message.reference and message.content.startswith('!k'):
            try:
                self.logger.info("=== Commande avec référence détectée ===")
                referenced_message = await message.channel.fetch_message(message.reference.message_id)
                self.logger.info(f"Message référencé trouvé :")
                self.logger.info(f"- Auteur : {referenced_message.author.name}")
                self.logger.info(f"- Contenu : {referenced_message.content}")
                self.logger.info(f"- ID : {referenced_message.id}")

                command_content = message.content[2:]  # Enlève '!k'
                self.logger.info(f"Contenu de la commande : {command_content}")
                self.logger.info("Transmission au gestionnaire de réponses contextuelles...")
                await claude_cog.handle_contextual_command(message, referenced_message)
                return
            except discord.NotFound:
                self.logger.warning(f"Message référencé non trouvé : {message.reference.message_id}")
            except Exception as e:
                self.logger.error(f"Erreur lors de la gestion de la commande contextuelle : {e}")

        # Traitement normal des commandes
        await self.process_commands(message)