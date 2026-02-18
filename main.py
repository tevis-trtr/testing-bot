import os
import io
import re
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

uso_por_usuario = defaultdict(list)
LIMITE_USOS = 20
JANELA_HORAS = 2

# ==============================
# SYSTEM PROMPT — PROGRAMAÇÃO
# ==============================
SYSTEM_PROMPT = """Você é uma IA assistente avançada e programadora expert. Responda sempre em português do Brasil.

REGRAS PARA CÓDIGO:
- Sempre use blocos de código com a linguagem correta: ```python, ```html, ```javascript, ```css, ```sql, etc.
- Escreva código limpo, comentado e funcional.
- Se o código for longo, escreva completo mesmo assim — não corte nem resuma.
- Explique brevemente o que o código faz antes ou depois do bloco.
- Se detectar erro no código do usuário, corrija e explique o motivo.

LINGUAGENS QUE VOCÊ DOMINA:
Python, HTML, CSS, JavaScript, TypeScript, React, Node.js, SQL, Bash, Java, C, C++, PHP, entre outros.

COMPORTAMENTO GERAL:
- Seja direto e objetivo.
- Para perguntas que não são de código, responda normalmente em português.
- Nunca recuse ajudar com programação."""

# ==============================
# MAPEAMENTO — extensão por linguagem
# ==============================
EXTENSOES = {
    "python": "py",
    "py": "py",
    "html": "html",
    "css": "css",
    "javascript": "js",
    "js": "js",
    "typescript": "ts",
    "ts": "ts",
    "sql": "sql",
    "bash": "sh",
    "shell": "sh",
    "sh": "sh",
    "java": "java",
    "c": "c",
    "cpp": "cpp",
    "c++": "cpp",
    "php": "php",
    "json": "json",
    "yaml": "yml",
    "xml": "xml",
    "rust": "rs",
    "go": "go",
    "kotlin": "kt",
    "swift": "swift",
    "r": "r",
    "ruby": "rb",
}

# ==============================
# HELPER — extrai blocos de código
# ==============================
def extrair_blocos_codigo(texto: str):
    """
    Retorna lista de (linguagem, codigo) encontrados no texto.
    """
    padrao = r"```(\w+)?\n([\s\S]*?)```"
    matches = re.findall(padrao, texto)
    return [(lang.lower() if lang else "txt", code.strip()) for lang, code in matches]

# ==============================
# HELPER — envia resposta inteligente
# ==============================
async def enviar_resposta(destino, autor, texto: str):
    """
    Decide como enviar a resposta:
    - Texto curto sem código → manda normal
    - Tem código → manda texto explicativo + arquivo(s) de código
    - Texto longo sem código → manda como .txt
    """
    blocos = extrair_blocos_codigo(texto)
    mencao = autor.mention

    # Remove os blocos de código do texto para pegar só a explicação
    texto_limpo = re.sub(r"```(\w+)?\n[\s\S]*?```", "", texto).strip()

    arquivos = []

    if blocos:
        # Monta arquivos de código
        contagem = defaultdict(int)
        for lang, codigo in blocos:
            ext = EXTENSOES.get(lang, "txt")
            contagem[ext] += 1
            count = contagem[ext]
            nome = f"codigo_{count}.{ext}" if count > 1 else f"codigo.{ext}"
            arquivo = discord.File(
                fp=io.BytesIO(codigo.encode("utf-8")),
                filename=nome
            )
            arquivos.append(arquivo)

        # Manda explicação (se tiver) + arquivos
        if texto_limpo:
            # Divide explicação se necessária
            partes = [texto_limpo[i:i+1900] for i in range(0, len(texto_limpo), 1900)]
            for i, parte in enumerate(partes):
                if i == len(partes) - 1 and arquivos:
                    # Última parte junto com os arquivos
                    await destino.send(f"{mencao} {parte}", files=arquivos)
                else:
                    await destino.send(f"{mencao} {parte}" if i == 0 else parte)
            if not partes:
                await destino.send(f"{mencao} Aqui está o código:", files=arquivos)
        else:
            await destino.send(f"{mencao} Aqui está o código:", files=arquivos)

    elif len(texto) > 1900:
        # Texto longo sem código → manda como .txt
        arquivo = discord.File(
            fp=io.BytesIO(texto.encode("utf-8")),
            filename="resposta.txt"
        )
        await destino.send(f"{mencao} A resposta foi longa, veja o arquivo:", file=arquivo)

    else:
        # Texto curto normal
        await destino.send(f"{mencao} {texto}")

# ==============================
# HELPER — checa e registra uso
# ==============================
def verificar_limite(user_id: int) -> tuple[bool, int]:
    agora = datetime.now()
    corte = agora - timedelta(hours=JANELA_HORAS)

    uso_por_usuario[user_id] = [
        t for t in uso_por_usuario[user_id] if t > corte
    ]

    usos = len(uso_por_usuario[user_id])
    if usos >= LIMITE_USOS:
        return False, 0

    uso_por_usuario[user_id].append(agora)
    return True, LIMITE_USOS - usos - 1

# ==============================
# EVENTO READY
# ==============================
@bot.event
async def on_ready():
    print(f"🔥 Bot online como {bot.user}")

# ==============================
# IA PRINCIPAL
# ==============================
async def responder_ia(autor, pergunta: str) -> str:
    user_id = autor.id

    if user_id not in memoria:
        memoria[user_id] = []

    # Limita histórico a 20 mensagens (10 trocas)
    if len(memoria[user_id]) > 20:
        memoria[user_id] = memoria[user_id][-20:]

    memoria[user_id].append({"role": "user", "content": pergunta})

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ] + memoria[user_id]

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=messages,
        temperature=0.7,
        max_tokens=4096  # aumentado para suportar código longo
    )

    resposta = response.choices[0].message.content
    memoria[user_id].append({"role": "assistant", "content": resposta})

    logs_ia.append(
        f"[{datetime.now().strftime('%H:%M:%S')}] {autor} perguntou: {pergunta[:80]}"
    )

    return resposta

# ==============================
# COMANDO !ia
# ==============================
@bot.command()
@commands.cooldown(1, 10, commands.BucketType.user)
async def ia(ctx, *, pergunta: str):
    if not gpt_ativo:
        return await ctx.send("❌ IA está desativada pelo dono.")

    pode, restantes = verificar_limite(ctx.author.id)
    if not pode:
        mais_antigo = uso_por_usuario[ctx.author.id][0]
        libera_em = mais_antigo + timedelta(hours=JANELA_HORAS)
        minutos = int((libera_em - datetime.now()).total_seconds() / 60)
        return await ctx.send(
            f"⛔ {ctx.author.mention} você atingiu o limite de **{LIMITE_USOS} usos** "
            f"nas últimas {JANELA_HORAS}h. Tente novamente em ~**{minutos} min**."
        )

    try:
        async with ctx.typing():
            resposta = await responder_ia(ctx.author, pergunta)
        await enviar_resposta(ctx.channel, ctx.author, resposta)

        if restantes <= 3:
            await ctx.send(
                f"⚠️ {ctx.author.mention} você tem apenas **{restantes}** uso(s) restante(s) nas próximas {JANELA_HORAS}h."
            )
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
                resposta = await responder_ia(message.author, pergunta)
            await enviar_resposta(message.channel, message.author, resposta)

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



