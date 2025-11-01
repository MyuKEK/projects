# main.py
import os
import discord
from discord.ui import Button, View, Modal, TextInput
from discord import TextStyle
from discord.ext import commands

# --- Konfiguration ---
# ⚠️ PLATZHALTER: ERSETZE DIESE MIT DEINEN TATSÄCHLICHEN WERTEN! ⚠️
# Laden des Tokens aus Umgebungsvariablen empfohlen.
TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = 123456789012345678      # SERVER-ID
APPLICATION_CHANNEL_ID = 123456789012345679  # Kanal-ID für eingereichte Bewerbungen
STAFF_ROLE_ID = 123456789012345680         # Rolle, die Bewerbungen bearbeiten darf
WELCOME_CHANNEL_ID = 123456789012345681    # Kanal-ID für die Bewerbungsnachricht

APPLICATION_MESSAGE_ID = None # ID der Haupt-Bewerbungsnachricht

# --- Bot Initialisierung ---
intents = discord.Intents.default()
intents.members = True          
intents.message_content = False 

bot = commands.Bot(command_prefix="!", intents=intents)

# --- Views und Modals ---

# View für den Bewerbungs-Startknopf
class ApplicationStartView(View):
    def __init__(self):
        super().__init__(timeout=None) # Persistent

    @discord.ui.button(label="Hier Bewerben! 📝", style=discord.ButtonStyle.primary, custom_id="apply_button")
    async def apply_button_callback(self, interaction: discord.Interaction, button: Button):
        # Öffnet das Bewerbungs-Modal
        await interaction.response.send_modal(ApplicationModal())

# Modal für das Bewerbungsformular (max. 5 Felder)
class ApplicationModal(Modal, title="Bewerbungsformular"):
    name_age = TextInput(label="Dein Name und Alter:", placeholder="Max Mustermann, 25", style=TextStyle.short, required=True, max_length=100)
    application_role = TextInput(label="Als was möchtest du dich Bewerben?", placeholder="Developer, Discord Moderator...", style=TextStyle.short, required=True, max_length=100)
    why_join = TextInput(label="Warum bewirbst du dich bei uns?", placeholder="Ich möchte mich bewerben, weil...", style=TextStyle.long, required=True, max_length=1000)
    experience = TextInput(label="Welche relevanten Erfahrungen besitzt du?", placeholder="Ich habe Erfahrung mit...", style=TextStyle.long, required=True, max_length=1000)
    questions_misc = TextInput(label="Fragen & Sonstiges (optional):", placeholder="Ich habe keine Fragen.", style=TextStyle.long, required=False, max_length=500)

    def __init__(self):
        super().__init__(timeout=None) 

    async def on_submit(self, interaction: discord.Interaction):
        # Verarbeitet das abgesendete Modal und sendet die Bewerbung in den Staff-Kanal
        applicant = interaction.user
        application_channel = bot.get_channel(APPLICATION_CHANNEL_ID)

        if not application_channel or not isinstance(application_channel, discord.TextChannel):
            await interaction.response.send_message("Hoppla! Der Bewerbungskanal konnte nicht gefunden werden. Bitte wende dich an die Serverleitung.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Neue Bewerbung von {applicant.display_name}",
            description=f"**Bewerber:** {applicant.mention} (`{applicant.id}`)",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=applicant.avatar.url if applicant.avatar else applicant.default_avatar.url)
        
        embed.add_field(name="Name und Alter", value=self.name_age.value, inline=False)
        embed.add_field(name="Bewirbt sich als", value=self.application_role.value, inline=False)
        embed.add_field(name="Warum bewerben?", value=self.why_join.value, inline=False)
        embed.add_field(name="Erfahrungen", value=self.experience.value, inline=False)
        embed.add_field(name="Fragen & Sonstiges", value=self.questions_misc.value if self.questions_misc.value else "*Keine Angabe*", inline=False)
        embed.add_field(name="Status", value="Neu (Wartet auf Bearbeitung)", inline=False)
        
        embed.set_footer(text=f"Bewerber ID: {applicant.id}")
        embed.timestamp = discord.utils.utcnow()

        # Sendet Bewerbung mit Bearbeitungsknöpfen
        await application_channel.send(embed=embed, view=ApplicationReviewView(applicant.id))
        
        await interaction.response.send_message("Wunderbar! Deine Bewerbung ist bei uns eingegangen und wird in Kürze geprüft. Vielen Dank!", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message("Oh nein! Beim Absenden gab es leider einen Fehler. Versuche es bitte gleich noch einmal.", ephemeral=True)


# View für die Bearbeitung einer Bewerbung
class ApplicationReviewView(View):
    def __init__(self, applicant_id: int):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id

    async def _check_permissions(self, interaction: discord.Interaction) -> bool:
        # Prüft, ob der Nutzer die Staff-Rolle oder manage_roles hat
        staff_role = discord.utils.get(interaction.user.roles, id=STAFF_ROLE_ID) if interaction.user.roles else None
        
        if not interaction.user.guild_permissions.manage_roles and not staff_role:
            await interaction.response.send_message("Entschuldigung, aber du hast nicht die notwendige Berechtigung, um Bewerbungen zu bearbeiten.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Annehmen ✅", style=discord.ButtonStyle.success, custom_id="accept_application")
    async def accept_button_callback(self, interaction: discord.Interaction, button: Button):
        if not await self._check_permissions(interaction): return
        await interaction.response.send_modal(AcceptConfirmationModal(self.applicant_id, interaction.message))

    @discord.ui.button(label="Ablehnen ❌", style=discord.ButtonStyle.danger, custom_id="reject_application")
    async def reject_button_callback(self, interaction: discord.Interaction, button: Button):
        if not await self._check_permissions(interaction): return
        await interaction.response.send_modal(RejectConfirmationModal(self.applicant_id, interaction.message))

    @discord.ui.button(label="In Bearbeitung 🔄", style=discord.ButtonStyle.secondary, custom_id="process_application")
    async def process_button_callback(self, interaction: discord.Interaction, button: Button):
        if not await self._check_permissions(interaction): return

        applicant = bot.get_user(self.applicant_id)
        reviewer = interaction.user
        
        # DM an Bewerber
        if applicant:
            try:
                dm_embed = discord.Embed(title="Super Neuigkeiten: Deine Bewerbung ist in Bearbeitung! 🥳", description=f"Jemand aus unserem Team ({reviewer.mention}) hat sich deine Bewerbung geschnappt und schaut sie sich jetzt genauer an. Wir melden uns bald wieder!", color=discord.Color.gold())
                await applicant.send(embed=dm_embed)
                await interaction.response.send_message(f"Die Bewerbung von {applicant.display_name} wurde erfolgreich als 'In Bearbeitung' markiert und der Bewerber wurde benachrichtigt.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message(f"Die Bewerbung wurde als 'In Bearbeitung' markiert. **Hinweis:** Konnte dem Bewerber keine Direktnachricht senden (DMs eventuell deaktiviert).", ephemeral=True)
            except Exception:
                await interaction.response.send_message(f"Ein kleiner Fehler ist beim Benachrichtigen aufgetreten, aber der Status der Bewerbung ist aktualisiert.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Die Bewerbung wurde als 'In Bearbeitung' markiert. Konnte den Bewerber leider nicht finden (ID: {self.applicant_id}).", ephemeral=True)

        # Aktualisiere die Bewerbungsnachricht
        original_embed = interaction.message.embeds[0]
        original_title_base = original_embed.title.split(' von ', 1)[0]
        original_embed.title = f"{original_title_base} - In Bearbeitung 🟡"
        original_embed.color = discord.Color.gold()
        
        new_fields_for_embed = [field for field in original_embed.fields if field.name not in ["Status", "Kommentar (Admin)", "Grund (Admin)"]]
        original_embed.clear_fields()
        for field in new_fields_for_embed: original_embed.add_field(name=field.name, value=field.value, inline=field.inline)

        original_embed.add_field(name="Status", value=f"In Bearbeitung von {reviewer.mention}", inline=False)
        await interaction.message.edit(embed=original_embed, view=ApplicationReviewView(self.applicant_id)) 


# Modal zur Bestätigung des Annehmens
class AcceptConfirmationModal(Modal, title="Bewerbung Annehmen"):
    comment_input = TextInput(label="Kommentar für den Bewerber (optional):", placeholder="Willkommen im Team!", style=TextStyle.long, required=False, max_length=500)
    
    def __init__(self, applicant_id: int, original_message: discord.Message):
        super().__init__(timeout=300) 
        self.applicant_id = applicant_id
        self.original_message = original_message

    async def on_submit(self, interaction: discord.Interaction):
        applicant = bot.get_user(self.applicant_id)
        reviewer = interaction.user
        comment = self.comment_input.value if self.comment_input.value else "Deine Bewerbung wurde angenommen. Willkommen im Team!"

        await interaction.response.send_message(f"Alles klar! Bewerbung als 'Angenommen' markiert.", ephemeral=True)
            
        # DM an Bewerber
        if applicant:
            try:
                dm_embed = discord.Embed(title="Herzlichen Glückwunsch! Du bist im Team! 🎉", description=f"**Nachricht vom Staff-Team:**\n{comment}\n\nWir freuen uns riesig auf dich!", color=discord.Color.green())
                await applicant.send(embed=dm_embed)
            except discord.Forbidden:
                await interaction.followup.send(f"Hinweis: Konnte {applicant.mention} nicht direkt benachrichtigen (DMs blockiert).", ephemeral=True)

        # Aktualisiere die Bewerbungsnachricht und entferne die Knöpfe
        original_embed = self.original_message.embeds[0]
        original_embed.title = f"Bewerbung angenommen ✅ von {reviewer.display_name}"
        original_embed.color = discord.Color.green()
        
        new_fields_for_embed = [field for field in original_embed.fields if field.name not in ["Status", "Kommentar (Admin)", "Grund (Admin)"]]
        original_embed.clear_fields()
        for field in new_fields_for_embed: original_embed.add_field(name=field.name, value=field.value, inline=field.inline)

        original_embed.add_field(name="Status", value=f"Angenommen von {reviewer.mention}", inline=False)
        if comment: original_embed.add_field(name="Kommentar (Admin)", value=comment, inline=False)
        
        await self.original_message.edit(embed=original_embed, view=None)


# Modal zur Bestätigung des Ablehnens
class RejectConfirmationModal(Modal, title="Bewerbung Ablehnen"):
    reason_input = TextInput(label="Grund für die Ablehnung (optional):", placeholder="Leider konnten wir deine Bewerbung diesmal nicht berücksichtigen...", style=TextStyle.long, required=False, max_length=500)
    
    def __init__(self, applicant_id: int, original_message: discord.Message):
        super().__init__(timeout=300) 
        self.applicant_id = applicant_id
        self.original_message = original_message

    async def on_submit(self, interaction: discord.Interaction):
        applicant = bot.get_user(self.applicant_id)
        reviewer = interaction.user
        reason = self.reason_input.value if self.reason_input.value else "Leider konnten wir deine Bewerbung diesmal nicht berücksichtigen."

        await interaction.response.send_message(f"Ok, Bewerbung als 'Abgelehnt' markiert.", ephemeral=True)

        # DM an Bewerber
        if applicant:
            try:
                dm_embed = discord.Embed(title="Schade! Deine Bewerbung konnte dieses Mal leider nicht berücksichtigt werden. 😔", description=f"**Begründung vom Staff-Team:**\n{reason}\n\nLass den Kopf nicht hängen, versuche es gerne zu einem späteren Zeitpunkt erneut!", color=discord.Color.red())
                await applicant.send(embed=dm_embed)
            except discord.Forbidden:
                await interaction.followup.send(f"Hinweis: Konnte {applicant.mention} nicht direkt benachrichtigen (DMs blockiert).", ephemeral=True)

        # Aktualisiere die Bewerbungsnachricht und entferne die Knöpfe
        original_embed = self.original_message.embeds[0]
        original_embed.title = f"Bewerbung abgelehnt ❌ von {reviewer.display_name}"
        original_embed.color = discord.Color.red()
        
        new_fields_for_embed = [field for field in original_embed.fields if field.name not in ["Status", "Kommentar (Admin)", "Grund (Admin)"]]
        original_embed.clear_fields()
        for field in new_fields_for_embed: original_embed.add_field(name=field.name, value=field.value, inline=field.inline)

        original_embed.add_field(name="Status", value=f"Abgelehnt von {reviewer.mention}", inline=False)
        if reason: original_embed.add_field(name="Grund (Admin)", value=reason, inline=False)
        
        await self.original_message.edit(embed=original_embed, view=None)


# Funktion zum Erstellen/Aktualisieren der Bewerbungsnachricht
async def setup_application_message():
    # Erstellt oder aktualisiert die Bewerbungsnachricht im Willkommenskanal.
    global APPLICATION_MESSAGE_ID
    
    guild = bot.get_guild(GUILD_ID)
    if not guild: return print(f"Achtung: Der konfigurierte Server (Guild ID) wurde nicht gefunden.")
    
    welcome_channel = guild.get_channel(WELCOME_CHANNEL_ID)
    if not welcome_channel or not isinstance(welcome_channel, discord.TextChannel): return print(f"Achtung: Der Willkommenskanal (Welcome Channel ID) wurde nicht gefunden.")
    
    embed = discord.Embed(title="Werde Teil unseres Teams! 🚀", description="Klicke auf den Knopf, um das **Bewerbungsformular** zu starten. Wir freuen uns auf deine Verstärkung!", color=discord.Color.orange())
    
    # 1. Versuch: Gespeicherte Nachricht abrufen und bearbeiten
    if APPLICATION_MESSAGE_ID:
        try:
            message = await welcome_channel.fetch_message(APPLICATION_MESSAGE_ID)
            if message.author == bot.user and message.embeds:
                await message.edit(embed=embed, view=ApplicationStartView())
                return print(f"Bewerbungsnachricht erfolgreich aktualisiert.")
        except:
            APPLICATION_MESSAGE_ID = None

    # 2. Versuch: Im Nachrichtenverlauf suchen
    if not APPLICATION_MESSAGE_ID:
        try:
            async for message in welcome_channel.history(limit=50):
                if (message.author == bot.user and message.embeds and "Werde Teil unseres Teams!" in message.embeds[0].title):
                    await message.edit(embed=embed, view=ApplicationStartView())
                    APPLICATION_MESSAGE_ID = message.id
                    return print(f"Alte Bewerbungsnachricht gefunden und aktualisiert.")
        except:
            pass
    
    # 3. Fallback: Neue Nachricht erstellen
    try:
        new_message = await welcome_channel.send(embed=embed, view=ApplicationStartView())
        APPLICATION_MESSAGE_ID = new_message.id
        print(f"Neue Bewerbungsnachricht erfolgreich erstellt.")
    except:
        print("Fehler: Ich habe keine Berechtigung, Nachrichten im Willkommenskanal zu senden.")


# --- Bot Events ---

@bot.event
async def on_ready():
    # Wird aufgerufen, wenn der Bot online ist.
    print(f"Bot ist online als {bot.user.name}")
    await bot.wait_until_ready()

    # Füge die persistenten Views hinzu
    bot.add_view(ApplicationStartView())
    bot.add_view(ApplicationReviewView(0)) 
    
    # Erstelle/aktualisiere die Bewerbungsnachricht
    await setup_application_message()
    print(f"Bot ist einsatzbereit und lauscht auf Befehle.")

@bot.event
async def on_guild_join(guild):
    # Wird aufgerufen, wenn der Bot einem Server beitritt.
    print(f"Bot wurde zu Server hinzugefügt: {guild.name}")
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            await channel.send(f"Hey! Ich bin {bot.user.name}, dein Bewerbungs-Manager. Bitte die Konfigurations-IDs (Token, Channel, Role) setzen und mich neu starten, damit das System startet.")
            break

@bot.event
async def on_message_delete(message):
    # Prüft, ob die Bewerbungsnachricht gelöscht wurde und erstellt ggf. eine neue.
    global APPLICATION_MESSAGE_ID
    if (APPLICATION_MESSAGE_ID and message.id == APPLICATION_MESSAGE_ID and message.author == bot.user):
        APPLICATION_MESSAGE_ID = None
        await setup_application_message()

# --- Bot starten ---
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except Exception as e:
            print(f"Fehler beim Starten des Bots: {e}")