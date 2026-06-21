import os
import threading
import asyncio
import aiohttp
import json
import discord
from discord import app_commands
from discord.ext import commands, tasks
from flask import Flask

# --- 1. RENDER İÇİN ARKA PLAN FLASK SERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "CC Checker Bot Aktif!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- 2. DISCORD BOT AYARLARI ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- 3. VERİ FORMATLAYICI ---
def format_api_response(raw_text):
    ucl_tirnak = "```"
    try:
        data = json.loads(raw_text)
        if isinstance(data, dict):
            pretty_json = json.dumps(data, indent=4, ensure_ascii=False)
            return f"💳 **Sorgu Sonucu:**\n{ucl_tirnak}json\n{pretty_json[:1800]}\n{ucl_tirnak}"
    except Exception:
        pass
    return f"💳 **Sorgu Sonucu:**\n{ucl_tirnak}\n{raw_text[:1900]}\n{ucl_tirnak}"

# --- 4. AUTO-PING (KEEP-ALIVE) SİSTEMİ ---
@tasks.loop(minutes=10)
async def keep_alive_ping():
    self_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not self_url:
        return
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(self_url, timeout=10) as resp:
                print(f"[Keep-Alive] Ping basarili: {resp.status}")
        except Exception as e:
            print(f"[Keep-Alive] Ping hatasi: {e}")

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
        
        # Hizalama hatası olmaması için burayı netleştirdim
        base_url = "[https://cc-3t5u.onrender.com/puanapi.php](https://cc-3t5u.onrender.com/puanapi.php)"
        params = {'cc': girdi}
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(base_url, params=params, timeout=20) as resp:
                    sonuc = await resp.text()
                    mesaj = format_api_response(sonuc)
                    await interaction.followup.send(mesaj, ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"❌ API Hatası: {str(e)}", ephemeral=True)

# --- 6. GÖRSEL BUTONLAR MENÜSÜ ---
class CheckerPaneli(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Kart Sorgula", style=discord.ButtonStyle.success, emoji="💳", row=0)
    async def check_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CCCheckerModal())

# --- 7. BOT ETKİNLİKLERİ ---
@bot.event
async def on_ready():
    print(f"[{bot.user.name}] Başarıyla giriş yaptı.")
    if not keep_alive_ping.is_running():
        keep_alive_ping.start()
    try:
        await bot.tree.sync()
    except Exception as e:
        print(f"❌ Komut senkronizasyon hatası: {e}")

@bot.tree.command(name="checker", description="CC Checker panelini açar.")
async def checker(interaction: discord.Interaction):
    view = CheckerPaneli()
    embed = discord.Embed(
        title="🪪 Zynex CC Checker",
        description="Aşağıdaki butona tıklayarak sorgulama yapabilirsiniz.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# --- 8. ANA ÇALIŞTIRICI ---
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    TOKEN = os.environ.get("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
