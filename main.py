import os
import discord
from discord.ext import commands
from groq import Groq
from datetime import datetime

# ==============================
# CONFIG
# ==============================

TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

OWNER_ID = 1370869648819617803  # <-- COLOQUE SEU ID AQUI

client = Groq(api_key=GROQ_API_KEY)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ==============================
# SISTEMAS
# ==============================

gpt_ativo = True
memoria = {}
logs_ia = []

# ==============================
# EVENTO READY
# ==============================

@bot.event
async def on_ready():
    print(f"🔥 Bot online como {bot.user}")

# ==============================
# IA PRINCIPAL
# ==============================

async def responder_ia(ctx, pergunta):
    global logs_ia

    if ctx.author.id not in memoria:
        memoria[ctx.author.id] = []

    memoria[ctx.author.id].append({"role": "user", "content": pergunta})

    messages = [
        {"role": "system", "content": "Você é uma IA inteligente que responde em português."}
    ] + memoria[ctx.author.id]

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        temperature=0.7,
        max_tokens=800
    )

    resposta = response.choices[0].message.content
    memoria[ctx.author.id].append({"role": "assistant", "content": resposta})

    logs_ia.append(
        f"[{datetime.now().strftime('%H:%M:%S')}] {ctx.author} perguntou: {pergunta}"
    )

    return resposta

# ==============================
# COMANDO !IA
# ==============================

@bot.command()
async def ia(ctx, *, pergunta: str):
    if not gpt_ativo:
        return await ctx.send(f"❌ IA está desativada pelo dono.")

    try:
        resposta = await responder_ia(ctx, pergunta)
        # Responde marcando a pessoa
        await ctx.send(f"{ctx.author.mention} {resposta}")

    except Exception as e:
        await ctx.send(f"Erro: {e}")

# ==============================
# IA POR MENÇÃO
# ==============================

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if bot.user in message.mentions and gpt_ativo:
        pergunta = message.content.replace(f"<@{bot.user.id}>", "").strip()
        resposta = await responder_ia(message, pergunta)
        await message.channel.send(f"{message.author.mention} {resposta}")

    await bot.process_commands(message)

# ==============================
# START
# ==============================

bot.run(TOKEN)
