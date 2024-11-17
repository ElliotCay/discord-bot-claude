from discord.ext import commands
import discord
import anthropic
import os
import json
from datetime import datetime, timedelta
import logging
from ..utils.conversation_manager import ConversationManager
from ..utils.cost_tracker import CostTracker
from ..utils.system_prompt_manager import SystemPromptManager

class ClaudeCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('discord_claude_bot')
        self.system_prompt_manager = SystemPromptManager()
        
        try:
            api_key = os.getenv('ANTHROPIC_API_KEY')
            self.logger.info(f"API Key présente : {'Oui' if api_key else 'Non'}")
            self.client = anthropic.Anthropic(
                api_key=api_key,
                timeout=30.0,  # Timeout en secondes
                max_retries=2  # Limite les retries
            )
            self.logger.info("Client Anthropic initialisé avec succès")
        except Exception as e:
            self.logger.error(f"Erreur lors de l'initialisation du client Anthropic: {str(e)}")
            raise e
        
        self.conversation_manager = ConversationManager()
        self.cost_tracker = CostTracker()
    
        # Définition des modèles disponibles
        self.models = {
            'kask': 'claude-3-5-haiku-20241022',  # Nouveau modèle par défaut
            'kask-haiku': 'claude-3-haiku-20240307',  # Ancien modèle Haiku
            'kask-sonnet': 'claude-3-sonnet-20240229',
            'kask-opus': 'claude-3-opus-20240229'
        }

        # Définition des coûts par modèle (prix par 1K tokens)
        self.costs = {
            'claude-3-5-haiku-20241022': {'input': 0.001, 'output': 0.005},  # Nouveau modèle
            'claude-3-haiku-20240307': {'input': 0.00025, 'output': 0.00025},
            'claude-3-sonnet-20240229': {'input': 0.003, 'output': 0.003},
            'claude-3-opus-20240229': {'input': 0.008, 'output': 0.008}
        }

    def calculate_cost(self, model, input_tokens, output_tokens):
        """Calcule le coût détaillé d'une requête"""
        model_costs = self.costs[model]
        input_cost = (input_tokens / 1000) * model_costs['input']
        output_cost = (output_tokens / 1000) * model_costs['output']
        total_cost = input_cost + output_cost
        
        return {
            'input_cost': input_cost,
            'output_cost': output_cost,
            'total_cost': total_cost,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens
        }

    async def send_response(self, ctx, response_text, cost_details):
        """Envoie la réponse"""
        if len(response_text) > 2000:  # Limite standard de Discord
            chunks = [response_text[i:i+2000] for i in range(0, len(response_text), 2000)]
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(response_text)

    async def get_message_chain(self, channel, message_id):
        """Récupère la chaîne complète des messages liés"""
        messages = []
        current_id = message_id
        max_depth = 10  # Limite de profondeur pour éviter les boucles infinies
        
        self.logger.info(f"\n=== Début de la récupération de la chaîne de messages ===")
        self.logger.info(f"Message initial ID: {message_id}")
        
        while current_id and len(messages) < max_depth:
            try:
                current_message = await channel.fetch_message(current_id)
                self.logger.info(f"\nMessage trouvé dans la chaîne:")
                self.logger.info(f"ID: {current_message.id}")
                self.logger.info(f"Auteur: {current_message.author.name}")
                self.logger.info(f"Contenu: {current_message.content}")
                
                # Ajouter le message au début de la liste pour maintenir l'ordre chronologique
                messages.insert(0, current_message)
                
                # Vérifier s'il y a un message parent
                if current_message.reference:
                    current_id = current_message.reference.message_id
                    self.logger.info(f"Ce message répond au message: {current_id}")
                else:
                    self.logger.info("Fin de la chaîne (pas de référence)")
                    break
                
            except discord.NotFound:
                self.logger.error(f"Message {current_id} non trouvé")
                break
            except Exception as e:
                self.logger.error(f"Erreur lors de la récupération du message {current_id}: {str(e)}")
                break
        
        self.logger.info(f"\nNombre total de messages dans la chaîne: {len(messages)}")
        return messages
    
    def format_message_chain(self, messages):
        """Formate la chaîne de messages pour Claude"""
        formatted_conversation = []
        
        self.logger.info("\n=== Formatage de la chaîne de messages ===")
        
        for idx, msg in enumerate(messages):
            # Déterminer le rôle en fonction de l'auteur
            is_bot = msg.author.id == self.bot.user.id
            role = "assistant" if is_bot else "user"
            
            # Nettoyer le contenu si nécessaire
            content = msg.content
            if not is_bot:
                # Nettoyer les mentions du bot et les commandes
                content = content.replace(f'<@{self.bot.user.id}>', '').strip()
                if content.startswith('!k'):
                    content = content[content.index(' ')+1:] if ' ' in content else ''
            
            # Si le contenu n'est pas vide après nettoyage
            if content.strip():
                self.logger.info(f"\nMessage {idx + 1}:")
                self.logger.info(f"Role: {role}")
                self.logger.info(f"Contenu original: {msg.content}")
                self.logger.info(f"Contenu nettoyé: {content}")
                
                formatted_conversation.append({
                    "role": role,
                    "content": content
                })
        
        return formatted_conversation

    async def handle_claude_request(self, ctx, message, model_key):
        """Version complète optimisée"""
        if not message and not ctx.message.reference:
            await ctx.send(f"Merci de fournir un message avec la commande !{model_key}")
            return

        if ctx.message.reference:
            await self.handle_contextual_command(
                ctx.message, 
                await ctx.channel.fetch_message(ctx.message.reference.message_id), 
                model_key
            )
            return

        try:
            # Message d'attente modifiable
            wait_message = await ctx.send("⏳ Génération de la réponse en cours... (~30s)")
        
            start_time = datetime.now()
            
            # Récupération du prompt système
            prompt_name, system_prompt = self.system_prompt_manager.get_active_prompt()
            
            # Log de début
            start_time = datetime.now()
            self.logger.info(f"\n=== Nouvelle requête Claude ===\n⏰ Début : {start_time.strftime('%H:%M:%S.%f')[:-3]}")

            # Construction des messages
            messages = [{
                "role": "user",
                "content": [{"type": "text", "text": message}]
            }]

            # Ajout du system prompt si présent
            if system_prompt:
                messages.insert(0, {
                    "role": "system",
                    "content": [{"type": "text", "text": system_prompt}]
                })

            # Appel API
            response = self.client.messages.create(
                model=self.models[model_key],
                max_tokens=1000,
                messages=messages,
                temperature=0.7
            )
            
            # Logs et mesures
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            self.logger.info(f"⏱️ Durée : {duration:.2f}s - Tokens : {response.usage.input_tokens}/{response.usage.output_tokens}")

            # Mise à jour du message d'attente avec le temps réel
            await wait_message.edit(content=f"⌛ Réponse générée en {duration:.2f}s")
            
            # Tracking des coûts
            self.cost_tracker.track_request(
                model=self.models[model_key],
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens
            )

            # Envoi des réponses
            if system_prompt:
                await ctx.send(f"🔧 Prompt : `{prompt_name}`")
            
            await self.send_response(ctx, response.content[0].text, None)

        except Exception as e:
            self.logger.error(f"Erreur Claude: {str(e)}")
            await ctx.send("❌ Désolé, une erreur s'est produite lors de la génération de la réponse.")
    
    async def handle_contextual_command(self, command_message, referenced_message, model_key='kask'):
        """Gère une commande !k* qui répond à un message spécifique"""
        self.logger.info("\n=== Traitement d'une commande contextuelle ===")
        try:
            # Message d'attente modifiable
            wait_message = await command_message.channel.send("⏳ Génération de la réponse en cours... (~30s)")
            
            # Récupération et formatage de la chaîne de messages
            message_chain = await self.get_message_chain(command_message.channel, referenced_message.id)
            
            # Construction des messages
            messages = []
            
            # Ajout du prompt système si présent
            prompt_name, system_prompt = self.system_prompt_manager.get_active_prompt()
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": [{"type": "text", "text": system_prompt}]
                })
            
            # Ajout de l'historique des messages
            for msg in message_chain:
                role = "assistant" if msg.author.id == self.bot.user.id else "user"
                content = msg.content
                if role == "user":
                    content = content.replace(f'<@{self.bot.user.id}>', '').strip()
                    if content.startswith('!k'):
                        content = content[content.index(' ')+1:] if ' ' in content else ''
                
                if content.strip():
                    messages.append({
                        "role": role,
                        "content": [{"type": "text", "text": content}]
                    })

            # Ajout de la nouvelle commande si présente
            command_content = command_message.content[len(model_key) + 2:].strip()
            if command_content:
                messages.append({
                    "role": "user",
                    "content": [{"type": "text", "text": command_content}]
                })

            start_time = datetime.now()
            
            # Appel API
            response = self.client.messages.create(
                model=self.models[model_key],
                max_tokens=1000,
                messages=messages,
                temperature=0.7
            )

            # Calcul de la durée
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Mise à jour du message d'attente
            await wait_message.edit(content=f"⌛ Réponse générée en {duration:.2f}s")

            # Tracking des coûts
            self.cost_tracker.track_request(
                model=self.models[model_key],
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens
            )

            # Envoi de la réponse
            if system_prompt:
                await command_message.channel.send(f"🔧 Prompt : `{prompt_name}`")
            await self.send_response(command_message.channel, response.content[0].text, None)

        except Exception as e:
            self.logger.error(f"Erreur lors du traitement de la commande contextuelle : {e}", exc_info=True)
            await command_message.reply("❌ Désolé, une erreur s'est produite lors du traitement de votre commande.")

    @commands.command(name='kask')
    async def kask(self, ctx, model_arg=None, *, message=None):
        """
        Pose une question à Claude avec choix du modèle optionnel
        Usage: !kask [modèle] message
        Modèles disponibles: haiku (ancien), sonnet, opus
        """
        # Gérer les réponses contextuelles
        if ctx.message.reference:
            await self.handle_contextual_command(ctx.message, await ctx.channel.fetch_message(ctx.message.reference.message_id))
            return

        # Si pas de message du tout
        if not model_arg:
            await ctx.send("Usage: !kask [modèle] message\nModèles disponibles: haiku (ancien), sonnet, opus")
            return

        # Détecter si le premier argument est un modèle
        selected_model = 'kask'  # modèle par défaut
        if model_arg.lower() in ['haiku', 'sonnet', 'opus']:
            if not message:  # Si on a spécifié un modèle mais pas de message
                await ctx.send("Merci de fournir un message avec la commande !kask")
                return
            selected_model = f'kask-{model_arg.lower()}'
            if model_arg.lower() == 'haiku':
                selected_model = 'kask-haiku'  # Pour utiliser l'ancien Haiku
        else:
            # Si le premier argument n'est pas un modèle, c'est le début du message
            message = f"{model_arg} {message if message else ''}"

        # Utiliser handle_claude_request pour traiter la demande
        await self.handle_claude_request(ctx, message, selected_model)



    @commands.command(name='kstats')
    async def kstats(self, ctx, period='day'):
        """Affiche les statistiques d'utilisation (day/week/all)"""
        try:
            report = self.cost_tracker.generate_report(period)
            # Découpage du rapport en chunks si nécessaire
            max_length = 1990  # Limite de Discord moins une marge
            chunks = [report[i:i + max_length] for i in range(0, len(report), max_length)]
            for chunk in chunks:
                await ctx.send(f"```md\n{chunk}\n```")
        except Exception as e:
            self.logger.error(f"Erreur lors de la génération des stats: {str(e)}")
            await ctx.send("Désolé, une erreur s'est produite lors de la génération des statistiques.")

    @commands.command(name='kexport')
    async def export_stats(self, ctx):
        """Exporte toutes les statistiques en CSV"""
        file_path = self.cost_tracker.export_stats_to_csv()
        if file_path:
            await ctx.send(
                "Voici l'export des statistiques :", 
                file=discord.File(file_path)
            )
        else:
            await ctx.send("Désolé, une erreur s'est produite lors de l'export des statistiques.")

    @commands.command(name='kclear')
    async def clear_conversation(self, ctx):
        """Efface l'historique de la conversation courante"""
        self.conversation_manager.clear_conversation(ctx.channel.id)
        await ctx.send("Historique de conversation effacé.")

    @commands.command(name='khelp')
    async def help_command(self, ctx):
        """Affiche la liste des commandes disponibles"""
        help_text = """**Liste des commandes disponibles**

    🤖 Commandes de conversation :
    - `!kask <message>` - Poser une question en utilisant Claude 3.5 Haiku (par défaut)
    - `!kask haiku <message>` - Poser une question en utilisant Claude 3 Haiku (ancienne version)
    - `!kask sonnet <message>` - Poser une question en utilisant Claude Sonnet
    - `!kask opus <message>` - Poser une question en utilisant Claude Opus
    - `!kclear` - Efface l'historique de la conversation courante

    📊 Commandes de statistiques :
    - `!kstats` - Affiche les statistiques d'utilisation du jour
    - `!kexport` - Exporte toutes les statistiques au format CSV

    🔧 Commandes de prompt système :
    - `!ksys create <nom> <prompt>` - Créer un prompt système
    - `!ksys list` - Lister les prompts système
    - `!ksys show <nom>` - Afficher un prompt système
    - `!ksys use <nom>` - Utiliser un prompt système
    - `!ksys clear` - Désactiver le prompt système actif
    - `!ksys delete <nom>` - Supprimer un prompt système

    ℹ️ Commande d'aide :
    - `!khelp` - Affiche ce message d'aide

    Note : Le bot ne répond qu'à son propriétaire pour des raisons de sécurité et de coût."""
        await ctx.send(help_text)    

    @commands.command(name='ksys')
    async def system_prompt(self, ctx, action=None, name=None, *, content=None):
        """Gère les prompts système"""
        help_text = """**Gestion des prompts système**
        
    - `!ksys create <nom> <prompt>` - Créer/modifier un prompt système
    - `!ksys list` - Lister tous les prompts système
    - `!ksys show <nom>` - Afficher un prompt système spécifique
    - `!ksys use <nom>` - Utiliser un prompt système
    - `!ksys clear` - Désactiver l'utilisation du prompt système
    - `!ksys delete <nom>` - Supprimer un prompt système"""

        if not action:
            await ctx.send(help_text)
            return

        action = action.lower()

        if action == 'list':
            prompts = self.system_prompt_manager.get_all_prompts()
            if not prompts:
                await ctx.send("Aucun prompt système défini.")
                return

            active_name, _ = self.system_prompt_manager.get_active_prompt()
            
            response = "**Prompts système disponibles :**\n\n"
            for name, data in prompts.items():
                active_marker = "✅ " if name == active_name else "  "
                created = datetime.fromisoformat(data['created_at']).strftime("%d/%m/%Y")
                updated = datetime.fromisoformat(data['updated_at']).strftime("%d/%m/%Y")
                response += f"{active_marker}`{name}`\n"
                response += f"  Créé le : {created}\n"
                response += f"  Dernière modification : {updated}\n\n"

            await ctx.send(response)

        elif action == 'show':
            if not name:
                await ctx.send("❌ Veuillez spécifier le nom du prompt à afficher.")
                return

            prompt = self.system_prompt_manager.get_prompt(name)
            if not prompt:
                await ctx.send(f"❌ Prompt '{name}' non trouvé.")
                return

            response = f"**Prompt système : {name}**\n\n"
            response += f"```\n{prompt['content']}\n```\n"
            response += f"Créé le : {datetime.fromisoformat(prompt['created_at']).strftime('%d/%m/%Y')}\n"
            response += f"Dernière modification : {datetime.fromisoformat(prompt['updated_at']).strftime('%d/%m/%Y')}"
            
            await ctx.send(response)

        elif action == 'create':
            if not name or not content:
                await ctx.send("❌ Veuillez spécifier un nom et un contenu pour le prompt.")
                return

            if self.system_prompt_manager.create_prompt(name, content):
                await ctx.send(f"✅ Prompt système '{name}' créé/modifié avec succès.")
            else:
                await ctx.send("❌ Erreur lors de la création du prompt système.")

        elif action == 'use':
            if not name:
                await ctx.send("❌ Veuillez spécifier le nom du prompt à utiliser.")
                return

            if self.system_prompt_manager.set_active_prompt(name):
                await ctx.send(f"✅ Prompt système '{name}' activé.")
            else:
                await ctx.send(f"❌ Prompt '{name}' non trouvé.")

        elif action == 'clear':
            self.system_prompt_manager.set_active_prompt(None)
            await ctx.send("✅ Plus aucun prompt système actif.")

        elif action == 'delete':
            if not name:
                await ctx.send("❌ Veuillez spécifier le nom du prompt à supprimer.")
                return

            if self.system_prompt_manager.delete_prompt(name):
                await ctx.send(f"✅ Prompt système '{name}' supprimé.")
            else:
                await ctx.send(f"❌ Prompt '{name}' non trouvé.")

        else:
            await ctx.send(f"❌ Action '{action}' non reconnue.\n\n{help_text}")

    @commands.command(name='ktest')
    async def test_latency(self, ctx):
        """Test simple de la latence de l'API Claude"""
        ping_time = datetime.now()
        
        try:
            async with ctx.typing():
                request_time = datetime.now()
                
                response = self.client.messages.create(
                    model=self.models['kask'],  # Utilise le modèle par défaut (Haiku 3.5)
                    max_tokens=10,  # Limite petite car on attend juste "OK"
                    messages=[{
                        "role": "user",
                        "content": [{"type": "text", "text": "Répond par 'OK' si tu as bien reçu mon message"}]
                    }],
                    temperature=0
                )
                
                response_time = datetime.now()
                status = "OK" if response and response.content[0].text.strip().upper() == "OK" else "KO"
                
                # Formatage des timestamps
                time_format = "%H:%M:%S.%f"
                result = (
                    f"```\n"
                    f"Test de latence :\n"
                    f"Ping      : {ping_time.strftime(time_format)}\n"
                    f"Requête   : {request_time.strftime(time_format)}\n"
                    f"Réponse   : {response_time.strftime(time_format)}\n"
                    f"Status    : {status}\n"
                    f"```"
                )
            
            await ctx.send(result)
            
        except Exception as e:
            self.logger.error(f"Erreur lors du test de latence: {str(e)}")
            await ctx.send(
                f"```\n"
                f"Test de latence :\n"
                f"Ping      : {ping_time.strftime('%H:%M:%S.%f')}\n"
                f"Status    : KO (Erreur lors de la requête)\n"
                f"```"
            )

    @commands.command(name='ktest2')
    async def test_latency_raw(self, ctx):
        """Test brut de la latence de l'API Claude sans aucun système annexe"""
        ping_time = datetime.now()
        
        try:
            request_time = datetime.now()
            # Requête directe sans le ctx.typing() ni autre chose
            response = self.client.messages.create(
                model=self.models['kask'],
                max_tokens=10,
                messages=[{
                    "role": "user",
                    "content": [{"type": "text", "text": "Reply with OK"}]
                }],
                temperature=0
            )
            response_time = datetime.now()
            
            status = "OK" if response and response.content[0].text.strip().upper() == "OK" else "KO"
            
            time_format = "%H:%M:%S.%f"
            result = (
                f"```\n"
                f"Test de latence brut :\n"
                f"Ping      : {ping_time.strftime(time_format)}\n"
                f"Requête   : {request_time.strftime(time_format)}\n"
                f"Réponse   : {response_time.strftime(time_format)}\n"
                f"Status    : {status}\n"
                f"```"
            )
            
            await ctx.send(result)
            
        except Exception as e:
            self.logger.error(f"Erreur lors du test de latence: {str(e)}")
            await ctx.send(f"Error: {str(e)}")

    @commands.command(name='ktest3')
    async def test_latency_raw_http(self, ctx):
        """Test avec requests directement"""
        import requests
        import time
        
        ping_time = datetime.now()
        
        try:
            request_time = datetime.now()
            
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'x-api-key': os.getenv('ANTHROPIC_API_KEY'),
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json'
                },
                json={
                    'model': 'claude-3-5-haiku-20241022',
                    'max_tokens': 10,
                    'messages': [{
                        'role': 'user',
                        'content': [{"type": "text", "text": "Reply with OK"}]
                    }]
                },
                timeout=30
            )
            
            response_time = datetime.now()
            
            status = "OK" if response.status_code == 200 else "KO"
            
            time_format = "%H:%M:%S.%f"
            result = (
                f"```\n"
                f"Test de latence HTTP brut :\n"
                f"Ping      : {ping_time.strftime(time_format)}\n"
                f"Requête   : {request_time.strftime(time_format)}\n"
                f"Réponse   : {response_time.strftime(time_format)}\n"
                f"Status    : {status}\n"
                f"HTTP Status: {response.status_code}\n"
                f"```"
            )
            
            await ctx.send(result)
            
        except Exception as e:
            self.logger.error(f"Erreur lors du test de latence: {str(e)}")
            await ctx.send(f"Error: {str(e)}")

    @commands.command(name='ktest4')
    async def test_latency_with_debug(self, ctx):
        """Test de latence avec debug réseau (logs serveur uniquement)"""
        import requests
        import urllib3
        import logging
        from io import StringIO
        
        # Capture les logs réseau dans un buffer
        log_capture = StringIO()
        ch = logging.StreamHandler(log_capture)
        ch.setLevel(logging.DEBUG)
        urllib3_logger = logging.getLogger('urllib3')
        urllib3_logger.addHandler(ch)
        
        ping_time = datetime.now()
        
        try:
            request_time = datetime.now()
            
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'x-api-key': os.getenv('ANTHROPIC_API_KEY'),
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json'
                },
                json={
                    'model': 'claude-3-5-haiku-20241022',
                    'max_tokens': 10,
                    'messages': [{
                        'role': 'user',
                        'content': [{"type": "text", "text": "Reply with OK"}]
                    }]
                },
                timeout=30
            )
            
            response_time = datetime.now()
            
            # Log détaillé côté serveur uniquement
            self.logger.info("=== Détails du test de latence ===")
            self.logger.info(f"Logs réseau:\n{log_capture.getvalue()}")
            self.logger.info(f"Temps total: {(response_time - ping_time).total_seconds()}s")
            self.logger.info(f"Status: {response.status_code}")
            
            # Message minimal sur Discord
            result = (
                f"```\n"
                f"🔍 Test de latence détaillé\n"
                f"➔ Durée totale : {(response_time - ping_time).total_seconds():.2f}s\n"
                f"➔ Status : {'✅' if response.status_code == 200 else '❌'}\n"
                f"```"
            )
            
            await ctx.send(result)
            
        except Exception as e:
            self.logger.error(f"Erreur lors du test détaillé: {str(e)}")
            await ctx.send("```\n❌ Test échoué\n```")
        finally:
            # Nettoyage des handlers
            urllib3_logger.removeHandler(ch)

    @commands.command(name='kping')
    async def ping_anthropic(self, ctx):
        """Test le temps de connexion TCP vers l'API Anthropic"""
        import socket
        import time
        
        try:
            await ctx.send("🔄 Test de connexion TCP vers api.anthropic.com...")
            
            start_time = time.time()
            
            # Création du socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            
            # Connexion
            s.connect(('api.anthropic.com', 443))
            
            end_time = time.time()
            duration = (end_time - start_time) * 1000  # en millisecondes
            
            s.close()
            
            # Log détaillé côté serveur
            self.logger.info(f"Test TCP réussi en {duration:.2f}ms")
            
            # Réponse minimaliste sur Discord
            await ctx.send(f"✅ Connexion TCP établie en {duration:.2f}ms")
            
        except socket.timeout:
            self.logger.error("Timeout lors du test TCP")
            await ctx.send("❌ Timeout lors de la connexion")
        except Exception as e:
            self.logger.error(f"Erreur lors du test TCP: {str(e)}")
            await ctx.send("❌ Erreur lors du test")

    @commands.command(name='kcurl')
    async def curl_anthropic(self, ctx):
        """Test détaillé avec cURL (version sécurisée)"""
        import subprocess
        import time
        
        try:
            await ctx.send("🔄 Test de connexion HTTPS...")
            
            start_time = time.time()
            
            # curl avec options limitées pour la sécurité
            process = subprocess.Popen([
                'curl', 
                '-w', '%{time_connect}, %{time_starttransfer}, %{time_total}',  # On récupère juste les timings
                '-s',  # Silencieux
                '-o', '/dev/null',  # Pas de output
                'https://api.anthropic.com/v1/messages'
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            output, error = process.communicate()
            
            end_time = time.time()
            total_duration = (end_time - start_time) * 1000
            
            # Log complet côté serveur
            self.logger.info(f"=== Test cURL détaillé ===")
            self.logger.info(f"Timings bruts: {output}")
            if error:
                self.logger.info(f"Erreurs/Infos: {error}")
                
            # Parse les timings
            try:
                connect, starttransfer, total = map(float, output.split(','))
                
                # Message Discord avec uniquement les timings essentiels
                result = (
                    f"```\n"
                    f"Test de connexion HTTPS :\n"
                    f"➔ Connexion TCP : {connect*1000:.2f}ms\n"
                    f"➔ Premier octet : {starttransfer*1000:.2f}ms\n"
                    f"➔ Temps total   : {total*1000:.2f}ms\n"
                    f"```"
                )
                
                await ctx.send(result)
                
            except:
                await ctx.send("✅ Test terminé (voir logs pour détails)")
            
        except Exception as e:
            self.logger.error(f"Erreur lors du test cURL: {str(e)}")
            await ctx.send("❌ Erreur lors du test")

# Ajout de la fonction setup nécessaire pour le chargement du cog
async def setup(bot):
    await bot.add_cog(ClaudeCommands(bot))