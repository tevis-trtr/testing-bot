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
# SYSTEM PROMPT ULTRA-PROFISSIONAL
# ==============================
SYSTEM_PROMPT = """
Você é uma IA ultra avançada, programadora, designer criativa e arquiteta de software. Responda sempre em português do Brasil. Seu objetivo principal: gerar sites completos, gigantes, ultra-profissionais e impressionantes, prontos para produção. O site deve ser detalhado, moderno, responsivo e funcional, com HTML + CSS + JS embutido.

===============================
REGRAS PRINCIPAIS PARA SITES
===============================
• Sempre entregue HTML + CSS + JS completo em um único arquivo, pronto para copiar e colar.  
• Use Google Fonts elegantes (uma display + uma body).  
• Defina uma paleta de cores sofisticada usando variáveis CSS.  
• Navbar fixa com glassmorphism e efeitos hover.  
• Hero section impactante com título grande, subtítulo e botões CTA.  
• Seções detalhadas: Produtos, Serviços, Comunidade, Segurança, Sobre nós, Contato.  
• Crie cards interativos, hover effects, box-shadow múltiplo, transições suaves, animações em CSS.  
• Footer completo com links, copyright e redes sociais.  
• CSS avançado: Grid/Flexbox, variáveis, animações, pseudo-elementos, clip-path, scroll reveal, custom scrollbar.  
• JS puro: animações ao scroll, smooth scroll, tabs, carrosséis, contadores animados, validação de formulário, efeitos de cursor e partículas.  
• Use imagens de placeholders ou SVG embutidos para efeitos visuais.  
• Site deve ter conteúdo rico, incluindo textos de seções, produtos, depoimentos fictícios, listas detalhadas e exemplos.  
• Sempre faça o site responsivo para desktop, tablet e mobile.  
• Nunca use frameworks externos (Bootstrap, Tailwind) ou jQuery.  
• Sempre entregue mais de 5MB de conteúdo no arquivo final, adicionando detalhes visuais, animações, textos e seções extensas.

===============================
REGRAS DE CÓDIGO
===============================
• Use blocos de código corretos: ```html, ```css, ```javascript quando necessário.  
• Código 100% funcional, comentado, seguro e otimizado.  
• Sempre entregue exemplos de uso quando aplicável.  
• Sugira melhorias, otimizações e boas práticas.  
• Certifique-se de que todas as seções, cards, animações e efeitos estão inclusos e que o site final impressiona qualquer pessoa.

===============================
COMPORTAMENTO
===============================
• Seja direto, confiante e profissional.  
• Para pedidos de site, nunca diga “isso é só um exemplo” ou “simplificado” — entregue o máximo possível.  
• Sempre gere um arquivo .txt contendo o site completo e gigante, para que o usuário possa baixar e abrir diretamente.  
• Surpreenda positivamente com sites modernos, detalhados, interativos e complexos, como se fosse feito por uma agência top mundial.  
• Adapte cores, fontes, layout e conteúdo ao estilo do site pedido.  
• Para pedidos ambíguos, interprete de forma que o site fique profissional e completo.
"""

# ==============================
# EXTENSÕES DE ARQUIVO
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
# LIMITE DE USO
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
# EXTRAI BLOCOS DE CÓDIGO
# ==============================
def extrair_blocos_codigo(texto: str):
    padrao = r"```(\w+)?\n([\s\S]*?)```"
    matches = re.findall(padrao, texto)
    return [(lang.lower() if lang else "txt", code.strip()) for lang, code in matches]

# ==============================
# ENVIA RESPOSTA + CRIA TXT
# ==============================
async def enviar_resposta(destino, autor, texto: str):
    mencao = autor.mention

    # Detecta se é site HTML e cria TXT gigante
    if "<html" in texto.lower() or "<!doctype html" in texto.lower():
        arquivo = discord.File(
            fp=io.BytesIO(texto.encode("utf-8")),
            filename="site_completo.txt"
        )
        await destino.send(f"{mencao} Aqui está o site completo (arquivo gigante):", file=arquivo)
        return

    # Blocos de código
    blocos = extrair_blocos_codigo(texto)
    arquivos = []
    if blocos:
        contagem = defaultdict(int)
        for lang, code in blocos:
            ext = EXTENSOES.get(lang, "txt")
            contagem[ext] += 1
            count = contagem[ext]
            nome = f"codigo_{count}.{ext}" if count > 1 else f"codigo.{ext}"
            arquivos.append(discord.File(
                fp=io.BytesIO(code.encode("utf-8")),
                filename=nome
            ))
    if texto.strip() and not blocos:
        await destino.send(f"{mencao} {texto}")
    elif arquivos:
        await destino.send(f"{mencao} Aqui estão os arquivos gerados:", files=arquivos)

# ==============================
# RESPOSTA IA
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
    logs_ia.append(f"[{datetime.now().strftime('%d/%m %H:%M:%S')}] {autor} ({autor.id}): {pergunta[:80]}")

    # Garante que sites sempre venham em HTML
    if any(k in pergunta.lower() for k in ["site", "cria um site", "website", "html"]):
        if "```html" not in resposta:
            resposta = f"```html\n{resposta}\n```"

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
            f"⛔ {ctx.author.mention} você atingiu o limite de {LIMITE_USOS} usos. Tente novamente em ~{minutos} min."
        )

    try:
        async with ctx.typing():
            resposta = await responder_ia(ctx.author, pergunta)
        await enviar_resposta(ctx.channel, ctx.author, resposta)

        if restantes <= 3:
            await ctx.send(f"⚠️ {ctx.author.mention} você tem apenas {restantes} uso(s) restante(s).")
    except Exception as e:
        await ctx.send(f"❌ Erro: {e}")

# ==============================
# START BOT
# ==============================
@bot.event
async def on_ready():
    print(f"🔥 Bot online como {bot.user}")
    print(f"📡 Modelo: {MODEL}")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="!ia | !img | !ajuda"
        )
    )

bot.run(TOKEN)
