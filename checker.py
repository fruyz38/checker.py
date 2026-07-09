import os
import threading
import aiohttp
import json
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
from flask import Flask

# --- LOGGING (Hata görmek için) ---
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# --- FLASK SERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "CC Checker Bot Aktif! ✅"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🚀 Flask server {port} portunda başlatılıyor...")
    app.run(host="0.0.0.0", port=port, debug=False)

# --- DISCORD BOT ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- FORMATLAYICI ---
def format_api_response(raw_text):
    try:
        data = json.loads(raw_text)
        embed = discord.Embed(
            title="💳 Sorgu Sonucu",
            color=discord.Color.red() if not data.get("success") else discord.Color.green()
        )
        embed.add_field(name="✅ Durum", value=data.get("status", "Bilinmiyor"), inline=True)
        embed.add_field(name="Success", value=str(data.get("success", "N/A")), inline=True)
       
        if "card" in data:
            embed.add_field(name="🃏 Kart", value=f"`{data['card']}`", inline=False)
        if "message" in data:
            embed.add_field(name="📝 Mesaj", value=data["message"], inline=False)
       
        if "bin_info" in data and isinstance(data["bin_info"], dict):
            bin_info = data["bin_info"]
            embed.add_field(name="🏦 BIN Bilgileri", value="\u200b", inline=False)
            embed.add_field(name="Scheme", value=bin_info.get("scheme", "-"), inline=True)
            embed.add_field(name="Type", value=bin_info.get("type", "-"), inline=True)
            embed.add_field(name="Issuer", value=bin_info.get("issuer", "-"), inline=True)
            embed.add_field(name="Tier", value=bin_info.get("tier", "-"), inline=True)
            embed.add_field(name="Country", value=bin_info.get("country", "-"), inline=True)
        return embed
    except Exception as e:
        logger.error(f"Formatlama hatası: {e}")
        return f"💳 **Sorgu Sonucu:**\n```\n{raw_text[:1900]}\n```"

# --- KEEP ALIVE ---
@tasks.loop(minutes=10)
async def keep_alive_ping():
    self_url = os.environ.get("RENDER_EXTERNAL_URL")
    if self_url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self_url, timeout=10) as resp:
                    logger.info(f"[Keep-Alive] Ping OK: {resp.status}")
        except Exception as e:
            logger.warning(f"[Keep-Alive] Hata: {e}")

@keep_alive_ping.before_loop
async def before_keep_alive_ping():
    await bot.wait_until_ready()

# --- MODAL ---
class CCCheckerModal(discord.ui.Modal, title="💳 CC Checker Sorgu"):
    cc_info = discord.ui.TextInput(label="Kart Bilgilerini Giriniz", placeholder="no|ay|yıl|cvv", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        girdi = self.cc_info.value.strip()
        base_url = "https://cc-3t5u.onrender.com/puanapi.php"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, params={'cc': girdi}, timeout=20) as resp:
                    sonuc = await resp.text()
                    mesaj = format_api_response(sonuc)
                    if isinstance(mesaj, discord.Embed):
                        await interaction.followup.send(embed=mesaj, ephemeral=True)
                    else:
                        await interaction.followup.send(mesaj, ephemeral=True)
        except Exception as e:
            logger.error(f"API Hatası: {e}")
            await interaction.followup.send(f"❌ API Hatası: {str(e)}", ephemeral=True)

# --- VIEW ---
class CheckerPaneli(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Kart Sorgula", style=discord.ButtonStyle.success, emoji="💳")
    async def check_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CCCheckerModal())

# --- EVENTS ---
@bot.event
async def on_ready():
    logger.info(f"✅ {bot.user} Başarıyla giriş yaptı!")
    if not keep_alive_ping.is_running():
        keep_alive_ping.start()
    try:
        await bot.tree.sync()
        logger.info("✅ Slash komutları senkronize edildi.")
    except Exception as e:
        logger.error(f"Sync hatası: {e}")

@bot.tree.command(name="checker", description="CC Checker panelini açar.")
async def checker(interaction: discord.Interaction):
    view = CheckerPaneli()
    embed = discord.Embed(title="🪪 Zynex CC Checker", description="Aşağıdaki butona tıklayarak sorgulama yapabilirsiniz.", color=discord.Color.green())
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# --- START ---
if __name__ == "__main__":
    logger.info("=== BOT BAŞLATILIYOR ===")
    logger.info(f"PORT: {os.environ.get('PORT')}")
    logger.info(f"RENDER_EXTERNAL_URL: {os.environ.get('RENDER_EXTERNAL_URL')}")
    
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        logger.critical("❌ DISCORD_TOKEN bulunamadı! Lütfen Render Environment'a ekleyin.")
        raise SystemExit(1)
    
    logger.info("✅ Token bulundu, Flask thread başlatılıyor...")
    threading.Thread(target=run_flask, daemon=True).start()
    
    bot.run(TOKEN)
