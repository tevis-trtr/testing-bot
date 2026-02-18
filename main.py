import os
import io
import re
import asyncio
import aiohttp
import discord
from discord.ext import commands
from groq import Groq
from datetime import datetime, timedelta
from collections import defaultdict
from urllib.parse import quote

# ==============================
# CONFIG
# ==============================
TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")
OWNER_ID = 1370869648819617803

client_groq = Groq(api_key=GROQ_API_KEY)
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
MODEL = "llama-3.3-70b-versatile"

# ==============================
# SYSTEM PROMPT PROFISSIONAL
# ==============================
SYSTEM_PROMPT = """Você é uma IA assistente avançada, programadora expert e criativa. Responda sempre em português do Brasil.

═══════════════════════════════════════
REGRAS PARA CÓDIGO
═══════════════════════════════════════
• Sempre use blocos de código com a linguagem correta:
  ```python, ```html, ```javascript, ```css, ```sql, etc.
• Escreva código COMPLETO, limpo, comentado e 100% funcional.
  Nunca corte, resuma ou use "..." no meio do código.
• Explique brevemente o que o código faz antes do bloco.
• Se detectar erro no código do usuário, corrija e explique o motivo.
• Para projetos grandes, organize em múltiplos blocos de código bem separados.
• Sempre adicione tratamento de erros, validações e boas práticas.
• Prefira código moderno e atualizado.

═══════════════════════════════════════
CRIAÇÃO DE SITES (HTML/CSS/JS)
═══════════════════════════════════════
- Crie sites COMPLETOS em um único arquivo HTML com CSS e JS embutidos.
- Design de nível profissional: use paletas modernas, tipografia elegante (Google Fonts), espaçamentos generosos.
- CSS avançado obrigatório: variáveis CSS, flexbox/grid, animações, transições suaves, hover effects, glassmorphism ou neumorphism quando adequado.
- Sempre use Google Fonts: importe no <head> fontes como Inter, Poppins, Raleway, etc.
- Adicione animações de entrada nos elementos com @keyframes ou IntersectionObserver.
- Navbar fixa com blur/glassmorphism, hero section impactante com gradiente, seções bem definidas, footer completo.
- Botões com hover animado, cards com sombra e transição, inputs estilizados.
- Totalmente responsivo: funciona perfeito no celular.
- NUNCA use Bootstrap ou frameworks externos — CSS puro avançado apenas.
- O resultado deve parecer um site de agência profissional, não um projeto escolar.

═══════════════════════════════════════
LINGUAGENS QUE VOCÊ DOMINA
═══════════════════════════════════════
Python, HTML, CSS, JavaScript, TypeScript, React, Vue, Node.js,
SQL, Bash, Java, C, C++, PHP, Go, Rust, Kotlin, Swift, R, entre outros.

═══════════════════════════════════════
COMPORTAMENTO GERAL
═══════════════════════════════════════
• Seja direto, objetivo e profissional.
• Para perguntas gerais, responda de forma clara e completa em português.
• Nunca recuse ajudar com programação ou tecnologia.
• Se a pergunta for ambígua, pergunte para entender melhor.
• Quando sugerir melhorias, seja específico e mostre o código corrigido."""

# ==============================
# MAPEAMENTO — extensão por linguagem
# ==============================
EXTENSOES = {
    "python": "py", "py": "py",
    "html": "html", "css": "css",
    "javascript": "js", "js": "js",
    "typescript": "ts", "ts": "ts",
    "sql": "sql", "bash": "sh",
    "shell": "sh", "sh": "sh",
    "java": "java", "c": "c",
    "cpp": "cpp", "c++": "cpp",
    "php": "php", "json": "json",
    "yaml": "yml", "xml": "xml",
    "rust": "rs", "go": "go",
    "kotlin": "kt", "swift": "swift",
    "r": "r", "ruby": "rb",
    "vue": "vue", "react": "jsx",
    "jsx": "jsx", "tsx": "tsx",
}

# ==============================
# HELPER — verifica limite de uso
# ==============================
def verificar_limite(user_id: int) -> tuple[bool, int]:
    agora = datetime.now()
    corte = agora - timedelta(hours=JANELA_HORAS)
    uso_por_usuario[user_id] = [t for t in uso_por_usuario[user_id] if t > corte]
    usos = len(uso_por_usuario[user_id])
    if usos >= LIMITE_USOS:
        return False, 0
    uso_por_usuario[user_id].append(agora)
    return True, LIMITE_USOS - usos - 1

# ==============================
# HELPER — extrai blocos de código
# ==============================
def extrair_blocos_codigo(texto: str):
    padrao = r"```(\w+)?\n([\s\S]*?)```"
    matches = re.findall(padrao, texto)
    return [(lang.lower() if lang else "txt", code.strip()) for lang, code in matches]

# ==============================
# HELPER — envia resposta inteligente
# ==============================
async def enviar_resposta(destino, autor, texto: str):
    blocos = extrair_blocos_codigo(texto)
    mencao = autor.mention
    texto_limpo = re.sub(r"```(\w+)?\n[\s\S]*?```", "", texto).strip()
    arquivos = []

    if blocos:
        contagem = defaultdict(int)
        for lang, codigo in blocos:
            ext = EXTENSOES.get(lang, "txt")
            contagem[ext] += 1
            count = contagem[ext]
            nome = f"codigo_{count}.{ext}" if count > 1 else f"codigo.{ext}"
            arquivos.append(discord.File(
                fp=io.BytesIO(codigo.encode("utf-8")),
                filename=nome
            ))

        if texto_limpo:
            partes = [texto_limpo[i:i+1900] for i in range(0, len(texto_limpo), 1900)]
            for i, parte in enumerate(partes):
                prefix = f"{mencao} " if i == 0 else ""
                if i == len(partes) - 1 and arquivos:
                    await destino.send(f"{prefix}{parte}", files=arquivos)
                else:
                    await destino.send(f"{prefix}{parte}")
        else:
            await destino.send(f"{mencao} Aqui está o código:", files=arquivos)

    elif len(texto) > 1900:
        arquivo = discord.File(
            fp=io.BytesIO(texto.encode("utf-8")),
            filename="resposta.txt"
        )
        await destino.send(f"{mencao} A resposta foi longa, veja o arquivo:", file=arquivo)

    else:
        await destino.send(f"{mencao} {texto}")

# ==============================
# EVENTO READY
# ==============================
@bot.event
async def on_ready():
    print(f"🔥 Bot online como {bot.user}")
    print(f"📡 Modelo: {MODEL}")
    print(f"🎨 HF Token: {'✅ configurado' if HF_TOKEN else '❌ não configurado'}")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="!ia | !img | !ajuda"
        )
    )

# ==============================
# IA PRINCIPAL
# ==============================
async def responder_ia(autor, pergunta: str) -> str:
    user_id = autor.id

    if user_id not in memoria:
        memoria[user_id] = []

    if len(memoria[user_id]) > 20:
        memoria[user_id] = memoria[user_id][-20:]

    memoria[user_id].append({"role": "user", "content": pergunta})

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + memoria[user_id]

    response = client_groq.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=4096
    )

    resposta = response.choices[0].message.content
    memoria[user_id].append({"role": "assistant", "content": resposta})

    logs_ia.append(
        f"[{datetime.now().strftime('%d/%m %H:%M:%S')}] {autor} ({autor.id}): {pergunta[:80]}"
    )

    return resposta

# ==============================
# GERAÇÃO DE IMAGEM — Hugging Face
# ==============================
async def gerar_imagem(prompt: str) -> bytes | None:
    url = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-xl-base-1.0"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": prompt}

    tentativas = 3
    for i in range(tentativas):
        try:
            print(f"[IMG] Tentativa {i+1}/3")
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    print(f"[IMG] Status: {resp.status}")
                    if resp.status == 200:
                        content_type = resp.headers.get("Content-Type", "")
                        if "image" in content_type:
                            return await resp.read()
                        else:
                            dados = await resp.json()
                            print(f"[IMG] Resposta inesperada: {dados}")
                    elif resp.status == 503:
                        print("[IMG] Modelo carregando, aguardando 20s...")
                        await asyncio.sleep(20)
                        continue
                    elif resp.status == 401:
                        print("[IMG] ❌ HF_TOKEN inválido ou sem permissão!")
                        return None
                    else:
                        texto = await resp.text()
                        print(f"[IMG] Erro {resp.status}: {texto[:200]}")
        except asyncio.TimeoutError:
            print(f"[IMG] Timeout na tentativa {i+1}")
        except Exception as e:
            print(f"[IMG] Exceção: {e}")

        if i < tentativas - 1:
            await asyncio.sleep(5)

    return None

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
        await ctx.send(f"⏳ {ctx.author.mention} aguarde **{error.retry_after:.0f}s** antes de usar `!ia` novamente.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❓ Uso: `!ia <sua pergunta>`")

# ==============================
# COMANDO !img
# ==============================
@bot.command()
@commands.cooldown(1, 30, commands.BucketType.user)
async def img(ctx, *, descricao: str):
    if not HF_TOKEN:
        return await ctx.send("❌ HF_TOKEN não configurado. Adicione a variável no Railway.")

    msg = await ctx.send(f"🎨 {ctx.author.mention} Gerando imagem, aguarde... (pode levar até 30s)")
    try:
        imagem = await gerar_imagem(descricao)

        if imagem:
            arquivo = discord.File(fp=io.BytesIO(imagem), filename="imagem.png")
            embed = discord.Embed(
                title="🎨 Imagem Gerada",
                description=f"**Prompt:** {descricao}",
                color=discord.Color.purple()
            )
            embed.set_image(url="attachment://imagem.png")
            embed.set_footer(text=f"Gerado por {ctx.author.display_name} • Stable Diffusion XL")
            await msg.delete()
            await ctx.send(embed=embed, file=arquivo)
        else:
            await msg.edit(
                content=f"❌ {ctx.author.mention} Não foi possível gerar a imagem. Verifique o console para detalhes."
            )
    except Exception as e:
        await msg.edit(content=f"❌ Erro ao gerar imagem: {e}")

@img.error
async def img_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ {ctx.author.mention} aguarde **{error.retry_after:.0f}s** para gerar outra imagem.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❓ Uso: `!img <descrição da imagem>`")

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
        await ctx.send(f"🗑️ Memória de **{alvo.display_name}** apagada com sucesso!")
    else:
        await ctx.send(f"ℹ️ **{alvo.display_name}** ainda não tem memória salva.")

# ==============================
# COMANDO !iastatus
# ==============================
@bot.command()
async def iastatus(ctx):
    user_id = ctx.author.id
    agora = datetime.now()
    corte = agora - timedelta(hours=JANELA_HORAS)
    usos_recentes = [t for t in uso_por_usuario[user_id] if t > corte]
    usos_feitos = len(usos_recentes)
    restantes = LIMITE_USOS - usos_feitos
    mem_tamanho = len(memoria.get(user_id, []))

    if usos_recentes:
        libera_em = usos_recentes[0] + timedelta(hours=JANELA_HORAS)
        minutos = int((libera_em - agora).total_seconds() / 60)
        renovacao = f"**{minutos} min**"
    else:
        renovacao = "**disponível agora**"

    embed = discord.Embed(title="📊 Seu Status", color=discord.Color.blue())
    embed.add_field(name="Usos nas últimas 2h", value=f"{usos_feitos}/{LIMITE_USOS}", inline=True)
    embed.add_field(name="Usos restantes", value=str(restantes), inline=True)
    embed.add_field(name="Renova em", value=renovacao, inline=True)
    embed.add_field(name="Memória", value=f"{mem_tamanho} mensagens", inline=True)
    embed.set_footer(text=f"IA {'✅ Ativa' if gpt_ativo else '❌ Desativada'} • Modelo: {MODEL}")
    await ctx.send(embed=embed)

# ==============================
# COMANDOS DO DONO
# ==============================
def is_owner():
    async def predicate(ctx):
        return ctx.author.id == OWNER_ID
    return commands.check(predicate)

@bot.command()
@is_owner()
async def ligar(ctx):
    global gpt_ativo
    gpt_ativo = True
    await ctx.send("✅ IA ativada.")

@bot.command()
@is_owner()
async def desligar(ctx):
    global gpt_ativo
    gpt_ativo = False
    await ctx.send("❌ IA desativada.")

@bot.command()
@is_owner()
async def logs(ctx):
    if not logs_ia:
        return await ctx.send("ℹ️ Nenhum log ainda.")
    texto = "\n".join(logs_ia[-15:])
    arquivo = discord.File(fp=io.BytesIO(texto.encode("utf-8")), filename="logs.txt")
    await ctx.send("📋 Últimos logs:", file=arquivo)

@bot.command()
@is_owner()
async def resetusos(ctx, membro: discord.Member):
    uso_por_usuario[membro.id] = []
    await ctx.send(f"✅ Usos de **{membro.display_name}** resetados.")

# ==============================
# COMANDO !ajuda
# ==============================
@bot.command()
async def ajuda(ctx):
    embed = discord.Embed(
        title="🤖 Comandos do Bot",
        description="Bot de IA com programação e geração de imagens",
        color=discord.Color.blurple()
    )
    embed.add_field(
        name="💬 IA",
        value=(
            "`!ia <pergunta>` — Fala com a IA (cooldown: 10s)\n"
            "`!iaclean` — Apaga sua memória de conversa\n"
            "`!iastatus` — Vê seus usos e status\n"
            "Mencionar o bot também funciona!"
        ),
        inline=False
    )
    embed.add_field(
        name="🎨 Imagens",
        value="`!img <descrição>` — Gera uma imagem com IA (cooldown: 30s)",
        inline=False
    )
    embed.add_field(
        name="⚙️ Admin (só dono)",
        value=(
            "`!ligar` / `!desligar` — Liga ou desliga a IA\n"
            "`!logs` — Vê os logs de perguntas\n"
            "`!resetusos @user` — Reseta os usos de um usuário\n"
            "`!iaclean @user` — Limpa memória de outro usuário"
        ),
        inline=False
    )
    embed.add_field(
        name="📋 Limites",
        value=f"**{LIMITE_USOS} usos** a cada **{JANELA_HORAS}h** • Cooldown de **10s** entre mensagens • **30s** entre imagens",
        inline=False
    )
    embed.set_footer(text=f"Modelo: {MODEL} • Imagens: Stable Diffusion XL")
    await ctx.send(embed=embed)

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
            return await message.channel.send(f"{message.author.mention} Me faz uma pergunta! 😄")

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




