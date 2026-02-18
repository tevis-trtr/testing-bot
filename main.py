import os
import discord
from discord.ext import commands
from groq import Groq
from datetime import datetime, timedelta
from collections import defaultdict

# ==============================
# CONFIG
# ==============================
TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OWNER_ID = 1370869648819617803

client = Groq(api_key=GROQ_API_KEY)
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ==============================
# SISTEMAS
# ==============================
gpt_ativo = True
memoria = {}
logs_ia = []

# Limite de 20 usos a cada 2 horas por pessoa
uso_por_usuario = defaultdict(list)  # {user_id: [datetime, datetime, ...]}
LIMITE_USOS = 20
JANELA_HORAS = 2

# ==============================
# HELPER — checa e registra uso
# ==============================
def verificar_limite(user_id: int) -> tuple[bool, int]:
    """
    Retorna (pode_usar, usos_restantes).
    Remove usos mais antigos que 2 horas antes de checar.
    """
    agora = datetime.now()
    corte = agora - timedelta(hours=JANELA_HORAS)

    # Limpa usos expirados
    uso_por_usuario[user_id] = [
        t for t in uso_por_usuario[user_id] if t > corte
    ]

    usos = len(uso_por_usuario[user_id])
    if usos >= LIMITE_USOS:
        return False, 0

    uso_por_usuario[user_id].append(agora)
    return True, LIMITE_USOS - usos - 1  # restantes após este uso

# ==============================
# EVENTO READY
# ==============================
@bot.event
async def on_ready():
    print(f"🔥 Bot online como {bot.user}")

# ==============================
# IA PRINCIPAL
# ==============================
async def responder_ia(ctx_or_msg, pergunta: str) -> str:
    # Suporta tanto ctx (commands) quanto message (on_message)
    author = getattr(ctx_or_msg, "author", None)
    user_id = author.id

    if user_id not in memoria:
        memoria[user_id] = []

    # Limita histórico a 20 mensagens (10 trocas)
    if len(memoria[user_id]) > 20:
        memoria[user_id] = memoria[user_id][-20:]

    memoria[user_id].append({"role": "user", "content": pergunta})

    messages = [
        {"role": "system", "content": "Você é uma IA inteligente que responde em português."}
    ] + memoria[user_id]

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        temperature=0.7,
        max_tokens=800
    )

    resposta = response.choices[0].message.content
    memoria[user_id].append({"role": "assistant", "content": resposta})

    logs_ia.append(
        f"[{datetime.now().strftime('%H:%M:%S')}] {author} perguntou: {pergunta}"
    )

    return resposta

# ==============================
# HELPER — envia mensagens longas
# ==============================
async def enviar(destino, texto: str):
    for i in range(0, len(texto), 1900):
        await destino.send(texto[i:i+1900])

# ==============================
# COMANDO !ia
# ==============================
@bot.command()
@commands.cooldown(1, 10, commands.BucketType.user)  # 1 uso a cada 10 segundos
async def ia(ctx, *, pergunta: str):
    if not gpt_ativo:
        return await ctx.send("❌ IA está desativada pelo dono.")

    pode, restantes = verificar_limite(ctx.author.id)
    if not pode:
        # Descobre quando o uso mais antigo vai expirar
        mais_antigo = uso_por_usuario[ctx.author.id][0]
        libera_em = mais_antigo + timedelta(hours=JANELA_HORAS)
        minutos = int((libera_em - datetime.now()).total_seconds() / 60)
        return await ctx.send(
            f"⛔ {ctx.author.mention} você atingiu o limite de **{LIMITE_USOS} usos** "
            f"nas últimas {JANELA_HORAS}h. Tente novamente em ~**{minutos} min**."
        )

    try:
        async with ctx.typing():
            resposta = await responder_ia(ctx, pergunta)
        await enviar(ctx, f"{ctx.author.mention} {resposta}")
        if restantes <= 3:
            await ctx.send(f"⚠️ Você tem apenas **{restantes}** uso(s) restante(s) nas próximas {JANELA_HORAS}h.")
    except Exception as e:
        await ctx.send(f"❌ Erro: {e}")

@ia.error
async def ia_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(
            f"⏳ {ctx.author.mention} aguarde **{error.retry_after:.0f}s** antes de usar `!ia` novamente."
        )
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❓ Uso correto: `!ia <sua pergunta>`")

# ==============================
# COMANDO !iaclean
# ==============================
@bot.command()
async def iaclean(ctx, membro: discord.Member = None):
    # Dono pode limpar memória de qualquer pessoa
    if membro and ctx.author.id != OWNER_ID:
        return await ctx.send("❌ Apenas o dono pode limpar a memória de outros usuários.")

    alvo = membro or ctx.author
    if alvo.id in memoria:
        del memoria[alvo.id]
        await ctx.send(f"🗑️ Memória de **{alvo.display_name}** foi apagada com sucesso!")
    else:
        await ctx.send(f"ℹ️ **{alvo.display_name}** ainda não tem memória salva.")

# ==============================
# IA POR MENÇÃO
# ==============================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if bot.user in message.mentions and gpt_ativo:
        pergunta = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if not pergunta:
            return await message.channel.send(f"{message.author.mention} Me faz uma pergunta!")

        pode, restantes = verificar_limite(message.author.id)
        if not pode:
            mais_antigo = uso_por_usuario[message.author.id][0]
            libera_em = mais_antigo + timedelta(hours=JANELA_HORAS)
            minutos = int((libera_em - datetime.now()).total_seconds() / 60)
            return await message.channel.send(
                f"⛔ {message.author.mention} você atingiu o limite de **{LIMITE_USOS} usos** "
                f"nas últimas {JANELA_HORAS}h. Tente novamente em ~**{minutos} min**."
            )

        try:
            async with message.channel.typing():
                resposta = await responder_ia(message, pergunta)
            await enviar(message.channel, f"{message.author.mention} {resposta}")
            if restantes <= 3:
                await message.channel.send(
                    f"⚠️ {message.author.mention} você tem apenas **{restantes}** uso(s) restante(s) nas próximas {JANELA_HORAS}h."
                )
        except Exception as e:
            await message.channel.send(f"❌ Erro: {e}")

    await bot.process_commands(message)

# ==============================
# START
# ==============================
bot.run(TOKEN)
