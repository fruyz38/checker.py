import os
import threading
import asyncio
import aiohttp
import json
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
from flask import Flask

# --- LOGGING AYARLARI ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. FLASK SERVER (Render için keep-alive) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "CC Checker Bot Aktif! ✅"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Flask server {port} portunda başlatılıyor...")
    app.run(host="0.0.0.0", port=port, debug=False)

# --- 2. DISCORD BOT AYARLARI ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- 3. GELİŞMİŞ VERİ FORMATLAYICI ---
def format_api_response(raw_text):
    try:
        data = json.loads(raw_text)
        embed = discord.Embed(
            title="💳 Sorgu Sonucu",
            color=discord.Color.red() if data.get("success") is False else discord.Color.green()
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
    except Exception:
        ucl_tirnak = "```"
        return f"💳 **Sorgu Sonucu:**\n{ucl_tirnak}\n{raw_text[:1900]}\n{ucl_tirnak}"

# --- 4. AUTO-PING (KEEP-ALIVE) ---
@tasks.loop(minutes=10)
async def keep_alive_ping():
    self_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not self_url:
        return
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(self_url, timeout=10) as resp:
                logger.info(f"[Keep-Alive] Ping başarılı: {resp.status}")
        except Exception as e:
            logger.error(f"[Keep-Alive] Ping hatası: {e}")

@keep_alive_ping.before_loop
async def before_keep_alive_ping():
    await bot.wait_until_ready()

# --- 5. SORGULAMA MODALI ---
class CCCheckerModal(discord.ui.Modal, title="💳 CC Checker Sorgu"):
    cc_info = discord.ui.TextInput(
        label="Kart Bilgilerini Giriniz",
        placeholder="Format: no|ay|yıl|cvv",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        girdi = self.cc_info.value.strip()
       
        base_url = "https://cc-3t5u.onrender.com/puanapi.php"
        params = {'cc': girdi}
       
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(base_url, params=params, timeout=20) as resp:
                    sonuc = await resp.text()
                    mesaj = format_api_response(sonuc)
                   
                    if isinstance(mesaj, discord.Embed):
                        await interaction.followup.send(embed=mesaj, ephemeral=True)
                    else:
                        await interaction.followup.send(mesaj, ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"❌ API Hatası: {str(e)}", ephemeral=True)

# --- 6. BUTON MENÜSÜ ---
class CheckerPaneli(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Kart Sorgula", style=discord.ButtonStyle.success, emoji="💳", row=0)
    async def check_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CCCheckerModal())

# --- 7. BOT ETKİNLİKLERİ ---
@bot.event
async def on_ready():
    logger.info(f"[{bot.user.name}] Başarıyla giriş yaptı! ✅")
    if not keep_alive_ping.is_running():
        keep_alive_ping.start()
    try:
        await bot.tree.sync()
        logger.info("Komutlar senkronize edildi.")
    except Exception as e:
        logger.error(f"Komut senkronizasyon hatası: {e}")

@bot.tree.command(name="checker", description="CC Checker panelini açar.")
async def checker(interaction: discord.Interaction):
    view = CheckerPaneli()
    embed = discord.Embed(
        title="🪪 Alves CC Checker",
        description="Aşağıdaki butona tıklayarak sorgulama yapabilirsiniz.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# --- 8. ANA ÇALIŞTIRICI ---
if __name__ == "__main__":
    logger.info("Bot başlatılıyor...")
    
    # Flask'ı ayrı thread'de çalıştır
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Token kontrolü
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        logger.error("❌ DISCORD_TOKEN environment variable bulunamadı!")
        raise SystemExit("DISCORD_TOKEN eksik!")
    
    bot.run(TOKEN)
