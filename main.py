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
economia = {}

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
# COMANDO IA
# ==============================

@bot.command()
async def ia(ctx, *, pergunta: str):

    if not gpt_ativo:
        return await ctx.send("❌ IA está desativada pelo dono.")

    await ctx.send("🤖 Pensando...")

    try:
        resposta = await responder_ia(ctx, pergunta)
        await ctx.send(resposta)

    except Exception as e:
        await ctx.send(f"Erro: {e}")

# ==============================
# IA POR MENÇÃO
# ==============================

@bot.event
async def on_message(message):

    global gpt_ativo

    if message.author.bot:
        return

    if bot.user in message.mentions and gpt_ativo:
        pergunta = message.content.replace(f"<@{bot.user.id}>", "")
        resposta = await responder_ia(message, pergunta)
        await message.channel.send(resposta)

    await bot.process_commands(message)

# ==============================
# COMANDOS DONO
# ==============================

def is_owner(ctx):
    return ctx.author.id == OWNER_ID

@bot.command()
async def ongpt(ctx):
    global gpt_ativo
    if not is_owner(ctx):
        return
    gpt_ativo = True
    await ctx.send("✅ IA ativada.")

@bot.command()
async def offgpt(ctx):
    global gpt_ativo
    if not is_owner(ctx):
        return
    gpt_ativo = False
    await ctx.send("⛔ IA desativada.")

@bot.command()
async def logsia(ctx):
    if not is_owner(ctx):
        return

    if not logs_ia:
        return await ctx.send("Sem logs ainda.")

    ultimos = "\n".join(logs_ia[-10:])
    await ctx.send(f"```{ultimos}```")

# ==============================
# ECONOMIA
# ==============================

@bot.command()
async def saldo(ctx):

    user = ctx.author.id

    if user not in economia:
        economia[user] = 100

    await ctx.send(f"💰 Seu saldo: {economia[user]} moedas")

@bot.command()
async def daily(ctx):

    user = ctx.author.id

    if user not in economia:
        economia[user] = 100

    economia[user] += 50

    await ctx.send("🎁 Você ganhou 50 moedas!")

# ==============================
# MODERAÇÃO
# ==============================

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    await member.kick(reason=reason)
    await ctx.send(f"{member} foi kickado.")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    await member.ban(reason=reason)
    await ctx.send(f"{member} foi banido.")

# ==============================
# START
# ==============================

bot.run(TOKEN)


