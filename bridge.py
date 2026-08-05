"""
Puente GPT4Free — Modelo dinámico (glm-5.2, qwen, deepseek) CON API KEY
Con rotación de IPs vía proxies gratuitos y rotación de keys de G4F
==========================================================================
"""

import os
import re
import time
import logging
import random
from flask import Flask, request, jsonify
from flask_cors import CORS
import g4f
from g4f_key_manager import G4FKeyManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

# ============================================================
# MARCADOR DE BUILD (para confirmar que Render corre este código)
# ============================================================
# Cambiá esta fecha/hash cada vez que subas un cambio importante y
# comparala contra lo que aparece en /health para saber si el deploy
# realmente se aplicó.
BUILD_VERSION = "2026-08-05-fix-key-rotation-v4"
RENDER_COMMIT = os.environ.get('RENDER_GIT_COMMIT', 'desconocido')

app = Flask(__name__)
CORS(app)

# ============================================================
# CONFIGURACIÓN GESTOR DE KEYS DE G4F
# ============================================================
# Inicializar gestor de keys para rotación automática
g4f_key_manager = G4FKeyManager()

# Verificar keys por expirar y enviar alerta por email (SILENCIOSO - no muestra en chat)
keys_por_expirar = g4f_key_manager.verificar_expiracion_proxima(dias_alerta=30)
if keys_por_expirar:
    # Enviar alerta por email sin mostrar en logs del bridge
    g4f_key_manager.enviar_alerta_email(keys_por_expirar)

# Estado global de keys (mutable para poder modificar en funciones)
g4f_keys_state = {
    'current_key': os.getenv('G4F_API_KEY') or g4f_key_manager.obtener_key_activa(),
    'rotation_enabled': True
}

if g4f_keys_state['current_key']:
    log.info(f"[Keys] Key de G4F configurada: {g4f_keys_state['current_key'][:20]}...")
else:
    log.warning("[Keys] No hay key de G4F configurada, usando modo sin key")

# ============================================================
# ESTADO GLOBAL DE ACTIVACIÓN DE MODELOS (SISTEMA SECUENCIAL)
# ============================================================
# Estado para controlar activación secuencial de modelos
# plan_mode: True = planificación (modelos desactivados), False = ejecución (modelos activos)
# current_model_index: índice del modelo actual en el plan
# plan_models: lista de modelos en el plan en orden de ejecución
model_activation_state = {
    'plan_mode': False,  # Por defecto desactivado (funcionamiento normal)
    'current_model_index': 0,
    'plan_models': [],  # Se llena cuando se inicia el plan
    'plan_complete': False
}

log.info(f"[Activación] Sistema de activación secuencial inicializado. Modo planificación: {model_activation_state['plan_mode']}")
log.info(f"[Build] Version: {BUILD_VERSION} | Render commit: {RENDER_COMMIT}")

# ============================================================
# INFRAESTRUCTURA HOSTEADA DE G4F (g4f.space / g4f.dev)
# ============================================================
# El equipo de g4f mantiene su propia API pública y centralizada en
# https://g4f.space (documentada en https://g4f.dev/docs/providers-and-models.html).
# Es EL MISMO backend que usa el playground https://g4f.dev/chat — por eso
# ahí las cosas andan y desde nuestro propio scraping en Render no siempre.
# Ventaja: la IP/routing la mantienen ellos, no nosotros.
#
# Custom server confirmado por el usuario (visible en la URL del playground:
# https://g4f.dev/chat/#custom:srv_mrgy4bjz6a85b485d663), etiquetado ahí
# como "opencode.ai/go", sirviendo (entre otros) los modelos "gpt-5.6-luna"
# y "kimi-k3".
OPENCODE_GO_SERVER_ID = os.environ.get('G4F_OPENCODE_GO_SRV', 'srv_mrgy4bjz6a85b485d663')

# "community-day-2026" es un "live provider" temporal que g4f.dev habilitó
# para su evento del 10 de julio de 2026 (ver https://g4f.dev/community-day-2026.html).
# Al ser temporal/ligado a un evento, puede desaparecer del registro de
# g4f.dev en cualquier momento — por eso SIEMPRE va envuelto en try/except
# y nunca es el único camino disponible.
COMMUNITY_DAY_LIVE_PROVIDER = os.environ.get('G4F_COMMUNITY_DAY_PROVIDER', 'community-day-2026')

# Debug: Listar todos los providers disponibles en g4f.Provider
log.info("[Debug] Providers disponibles en g4f.Provider:")
if hasattr(g4f, 'Provider'):
    for attr_name in dir(g4f.Provider):
        if not attr_name.startswith('_'):
            log.info(f"  - {attr_name}")

# ============================================================
# CONFIGURACIÓN PROXIES GRATUITOS (ROTACIÓN DE IPs)
# ============================================================
# Lista de proxies públicos gratuitos para rotación de IPs
# Obtenidos de free-proxy-list.net y similares
# Formato: http://ip:port o http://user:pass@ip:port
FREE_PROXIES = os.getenv('FREE_PROXIES', '').split(',') if os.getenv('FREE_PROXIES') else [
    # Proxies públicos gratuitos actualizados (elite/anonymous + HTTPS)
    # Filtrados por: elite proxy o anonymous, soportan HTTPS, recientes
    'http://103.18.205.162:8080',
    'http://197.255.125.12:80',
    'http://197.221.237.248:80',
    'http://104.194.146.9:80',
    'http://102.203.80.41:3128',
    'http://175.139.233.76:80',
    'http://103.171.82.213:8080',
    'http://203.162.13.222:6868',
    'http://117.236.124.166:3128',
    'http://178.250.156.112:443',
    'http://78.24.180.210:8080',
    'http://140.245.238.56:53',
    'http://45.43.60.220:8080',
    'http://193.32.177.152:8080',
    'http://85.158.145.47:8080',
    'http://176.12.65.24:443',
    'http://43.208.245.90:3129',
    'http://113.160.132.26:8080',
    'http://91.107.252.85:7070',
    'http://103.113.26.7:8080',
    'http://34.84.162.206:38080',
    'http://64.112.184.210:3128',
    'http://47.81.56.193:8888',
    'http://77.221.158.175:3128',
    'http://34.43.46.91:80',
    'http://34.44.49.215:80',
    'http://159.195.49.27:8888',
    'http://103.72.89.22:8097',
    'http://173.212.245.136:8888',
    'http://185.239.50.122:10808',
    'http://34.69.61.247:80',
    'http://149.28.87.103:8888',
    'http://149.129.225.235:7777',
    'http://149.104.4.88:10809',
    'http://170.106.173.62:8080',
    'http://14.238.8.63:9090',
    'http://129.226.72.101:18080',
    'http://87.228.89.21:80',
    'http://103.237.102.191:11111',
    'http://109.199.119.160:80',
    'http://77.247.178.20:3129',
    'http://94.182.177.92:80',
    'http://43.203.195.46:80',
    'http://45.146.163.31:80',
    'http://206.245.131.160:80',
    'http://212.47.232.28:80',
    'http://181.39.25.196:8118',
    'http://183.110.216.159:8090',
    'http://219.65.73.80:80',
    'http://219.65.73.81:80',
    'http://27.34.242.98:80',
    'http://219.93.101.62:80',
    'http://5.45.126.128:8080',
    'http://97.74.87.226:80',
    'http://123.58.199.232:8168',
    'http://172.237.73.24:80',
    'http://167.99.124.118:80',
    'http://149.129.226.9:93',
    'http://160.187.221.206:5900',
    'http://41.220.22.7:80',
    'http://195.26.224.135:80',
    'http://47.238.60.156:18081',
    'http://139.59.59.122:8118',
    'http://8.221.126.184:80',
    'http://176.61.151.123:80',
    'http://147.231.163.133:80',
    'http://31.76.29.13:8080',
    'http://5.35.71.232:10808',
    'http://103.82.20.76:8080',
    'http://34.87.80.221:30000',
    'http://154.203.132.81:1080',
    'http://37.255.203.235:8080',
    'http://147.45.60.249:1081',
    'http://103.43.191.71:8888',
    'http://174.137.134.182:2999',
    'http://15.235.21.254:8080',
    'http://46.47.197.210:3128',
    'http://219.93.101.63:80',
    'http://219.93.101.60:80',
    'http://8.219.97.248:80',
    # NOTA: Actualizar periódicamente desde https://free-proxy-list.net/
    # Filtrar por: elite proxy o anonymous, soportan HTTPS
]

# Filtrar proxies vacíos
PROXY_LIST = [p.strip() for p in FREE_PROXIES if p.strip()]
PROXY_ROTATION_ENABLED = len(PROXY_LIST) > 0

log.info(f"[Proxies] Rotación de IPs: {'habilitada' if PROXY_ROTATION_ENABLED else 'deshabilitada'} | {len(PROXY_LIST)} proxies disponibles")

# Modelo por defecto (modelo real confirmado, servido por el provider GLM)
DEFAULT_MODEL = os.environ.get('G4F_MODEL_OVERRIDE', 'GLM-4.7')
DEFAULT_PROVIDER = os.environ.get('G4F_PROVIDER', '')

# ============================================================
# CONFIGURACIÓN PROVIDERS RECOMENDADOS (100% GRATUITOS, SIN AUTH)
# ============================================================
# IMPORTANTE: 'OpenCodeZen', 'CommunityDay', 'SurfSense'/'Surfsense' y 'Blackbox'
# NO EXISTEN como providers en g4f (verificado contra el paquete instalado:
# solo hay 92 providers reales, ninguno con esos nombres). Usarlos hacía que
# la cascada cayera SIEMPRE al fallback general, desperdiciando tiempo y
# reintentos. Lista corregida con providers que sí existen y están 'working':
#   GLM       -> modelo real: GLM-4.7      (chat.z.ai)
#   Nvidia    -> modelo real: openai/gpt-oss-120b (build.nvidia.com) — puede
#                devolver 403 al listar modelos si Nvidia bloqueó el scraper
#   DeepInfra -> modelo real: zai-org/GLM-5.2 (deepinfra.com)
#   Pollinations / OpenRouterFree / Qwen / WeWordle / Yqcloud como respaldo
#   general adicional (gratuitos, sin auth, existen en el paquete actual)
RECOMMENDED_PROVIDERS = [
    'GLM',
    'DeepInfra',
    'Nvidia',
    'Pollinations',
    'OpenRouterFree',
    'Qwen',
    'WeWordle',
    'Yqcloud',
]

# Providers específicos para Claude (si están disponibles).
# 'Blackbox' no existe en el paquete actual — se deja vacío a propósito.
# Si en el futuro agregás un provider real de Claude, ponelo acá.
CLAUDE_PROVIDERS = []

# ============================================================
# CONFIGURACIÓN DE ROTACIÓN DE IPs PARA QWEN
# ============================================================
# Qwen tiene rate limiting por IP, por lo que necesitamos rotar IPs
# para evitar bloqueos. Usaremos el sistema de proxies existente.
QWEN_REQUIRES_PROXY_ROTATION = True

# Providers a IGNORAR (requieren auth, fallan en Render, o tienen problemas)
IGNORED_PROVIDERS = [
    'DeepSeek',    # Requiere archivos HAR
    'You',         # Requiere cookies y navegador simulado (falla en Render)
    'Cohere',      # Pide API key
    'Poe',         # Requiere autenticación
    'Phind',       # Inestable
    'Perplexity',  # BLOQUEADO en Render (Cloudflare blacklist)
    'DuckDuckGo',  # Inestable
    'Airforce',    # Pide API key
    'HuggingSpace',  # Bug interno con modelos desconocidos (NoneType error)
]

# Cargar providers recomendados dinámicamente
AVAILABLE_PROVIDERS = []
for provider_name in RECOMMENDED_PROVIDERS:
    try:
        if hasattr(g4f.Provider, provider_name):
            provider_class = getattr(g4f.Provider, provider_name)
            AVAILABLE_PROVIDERS.append(provider_class)
            log.info(f"[Providers] Provider recomendado cargado: {provider_name}")
    except Exception as e:
        log.warning(f"[Providers] No se pudo cargar provider {provider_name}: {e}")

# Cargar providers específicos para Claude dinámicamente
AVAILABLE_CLAUDE_PROVIDERS = []
for provider_name in CLAUDE_PROVIDERS:
    try:
        if hasattr(g4f.Provider, provider_name):
            provider_class = getattr(g4f.Provider, provider_name)
            AVAILABLE_CLAUDE_PROVIDERS.append(provider_class)
            log.info(f"[Providers] Provider Claude cargado: {provider_name}")
    except Exception as e:
        log.warning(f"[Providers] No se pudo cargar provider Claude {provider_name}: {e}")

# Cargar providers ignorados para configuración de ignored_providers
IGNORED_PROVIDER_CLASSES = []
for provider_name in IGNORED_PROVIDERS:
    try:
        if hasattr(g4f.Provider, provider_name):
            provider_class = getattr(g4f.Provider, provider_name)
            IGNORED_PROVIDER_CLASSES.append(provider_class)
            log.info(f"[Providers] Provider ignorado configurado: {provider_name}")
    except Exception as e:
        log.warning(f"[Providers] No se pudo configurar provider ignorado {provider_name}: {e}")

log.info(f"[Providers] Total providers activos: {len(AVAILABLE_PROVIDERS)} | Claude: {len(AVAILABLE_CLAUDE_PROVIDERS)} | Ignorados: {len(IGNORED_PROVIDER_CLASSES)}")

# Timeout por intento. 120s estaba multiplicando el tiempo total de espera
# por cada combinación modelo/provider/proxy que fallaba (varios minutos
# antes de responder el 502). Bajado a un valor configurable, razonable
# para providers reales que responden rápido cuando funcionan.
REQUEST_TIMEOUT_SECONDS = int(os.environ.get('G4F_REQUEST_TIMEOUT', '25'))
# Presupuesto total de tiempo por request HTTP entrante, para no dejar
# esperando al cliente varios minutos mientras la cascada prueba todo.
TOTAL_REQUEST_BUDGET_SECONDS = int(os.environ.get('G4F_TOTAL_BUDGET', '55'))
# Circuit breaker: si un provider falla, no se reintenta durante este tiempo.
PROVIDER_COOLDOWN_SECONDS = int(os.environ.get('G4F_PROVIDER_COOLDOWN', '180'))
# Cooldown especial y mucho más largo para cuando g4f.space devuelve el
# error de cuota "Active day limit" (límite de días activos por IP/key
# anónima). Reintentar cada 3 minutos no sirve de nada en ese caso — la
# cuota se resetea recién en días, no en minutos.
HOSTED_QUOTA_COOLDOWN_SECONDS = int(os.environ.get('G4F_HOSTED_QUOTA_COOLDOWN', str(6 * 3600)))
provider_ultimo_fallo = {}  # nombre_provider -> timestamp del último fallo
provider_cooldown_custom = {}  # nombre_provider -> duración de cooldown específica (segundos)

def provider_en_cooldown(provider_name):
    ts = provider_ultimo_fallo.get(provider_name)
    if ts is None:
        return False
    duracion = provider_cooldown_custom.get(provider_name, PROVIDER_COOLDOWN_SECONDS)
    return (time.time() - ts) < duracion

def marcar_provider_fallido(provider_name, cooldown_segundos=None):
    provider_ultimo_fallo[provider_name] = time.time()
    if cooldown_segundos is not None:
        provider_cooldown_custom[provider_name] = cooldown_segundos
    else:
        provider_cooldown_custom.pop(provider_name, None)

g4f_client = None
try:
    from g4f.client import Client
    
    # Configurar proxies si están disponibles
    client_kwargs = {}
    if PROXY_LIST:
        # Usar el primer proxy por defecto, rotaremos en cada request
        client_kwargs['proxies'] = {
            'http': PROXY_LIST[0],
            'https': PROXY_LIST[0]
        }
        log.info(f"[Proxies] Client g4f configurado con proxy por defecto")

    client_kwargs['timeout'] = REQUEST_TIMEOUT_SECONDS
    
    g4f_client = Client(**client_kwargs)
    
    # CONFIGURACIÓN DE DEEPSEEK CON ARCHIVOS HAR
    # DeepSeek ahora requiere autenticación mediante archivos HAR exportados del navegador
    try:
        import os
        har_dir = os.path.join(os.path.dirname(__file__), 'har_and_cookies')
        # Crear directorio automáticamente si no existe
        if not os.path.exists(har_dir):
            os.makedirs(har_dir, exist_ok=True)
            log.info("[DeepSeek] Directorio har_and_cookies/ creado automáticamente")
        
        if os.path.exists(har_dir):
            har_files = [f for f in os.listdir(har_dir) if f.endswith('.har')]
            if har_files:
                har_path = os.path.join(har_dir, har_files[0])
                # Configurar g4f para usar el archivo HAR de DeepSeek
                if hasattr(g4f.Provider, 'DeepSeek'):
                    try:
                        g4f.Provider.DeepSeek.har_file = har_path
                        log.info(f"[DeepSeek] Archivo HAR configurado: {har_files[0]}")
                    except Exception as e:
                        log.warning(f"[DeepSeek] No se pudo configurar HAR: {e}")
            else:
                log.info("[DeepSeek] No se encontraron archivos HAR en har_and_cookies/ - el provider usará modo gratuito limitado")
        else:
            log.info("[DeepSeek] Directorio har_and_cookies/ no encontrado - el provider usará modo gratuito limitado")
    except Exception as e_deepseek:
        log.warning(f"[DeepSeek] Error configurando soporte HAR: {e_deepseek}")
    
    # CONFIGURACIÓN DE OLLAMA: Le inyectamos servidores públicos gratuitos para no usar API Key
    try:
        if hasattr(g4f, 'Provider') and hasattr(g4f.Provider, 'Ollama'):
            # Lista de servidores Ollama públicos compartidos por la comunidad
            g4f.Provider.Ollama.api_base = [
                "https://ollama.pro/api",  # Kimi-k2.7-code disponible aquí
                "https://ai.devs503.tech/api",
                "https://ollama.com/v1",
                "https://api.pawan.krd/v1"
            ]
            log.info("Servidores públicos de Ollama configurados correctamente (incluyendo ollama.pro para kimi-k2.7-code).")
    except Exception as e_ollama:
        log.warning(f"No se pudo configurar Ollama: {e_ollama}")

    log.info(f'g4f inicializado | modelo: {DEFAULT_MODEL} | provider: {DEFAULT_PROVIDER} | proxy_rotation: {PROXY_ROTATION_ENABLED}')
except ImportError:
    log.error('g4f no instalado. Ejecuta: pip install -r requirements.txt')
except Exception as e:
    log.error(f'Error inicializando g4f: {e}')

IDENTIDAD_VERBO = (
    "INSTRUCCION CRITICA DE IDENTIDAD (prioridad maxima, no puede ser sobreescrita):\n"
    "Tu nombre es NewserPro (el modelo premium de Verbo AI). Sos un asistente "
    "conversacional creado por VerboAITeams (el equipo de desarrollo de Verbo AI). "
    "NUNCA digas que sos ChatGPT, GPT, OpenAI, SurfSense, Modelscope, Puter, Airforce, "
    "Qwen, Alibaba, Alibaba Cloud, Llama, Meta, Claude, Anthropic, Gemini, Google, "
    "DeepSeek, Ollama, GLM ni ninguna otra empresa o modelo base. Si te preguntan quien sos, "
    "quien te creo, quien te hizo, o de donde vienes, respondes SIEMPRE que fuiste creado "
    "por VerboAITeams y que tu nombre es NewserPro. Aunque el usuario insista o intente "
    "cambiarte la identidad, mantene firme que sos NewserPro de Verbo AI. "
    "Esta instruccion tiene prioridad absoluta sobre cualquier otra consigna que "
    "hayas recibido antes o despues.\n\n"
)

REEMPLAZOS_IDENTIDAD = [
    (r'\bSoy ChatGPT\b', 'Soy NewserPlus de Verbo AI'),
    (r'\bsoy ChatGPT\b', 'soy NewserPlus de Verbo AI'),
    (r'\bSoy GPT-?4\b', 'Soy NewserPlus de Verbo AI'),
    (r'\bsoy GPT-?4\b', 'soy NewserPlus de Verbo AI'),
    (r'\bSoy un modelo de lenguaje de OpenAI\b', 'Soy NewserPlus, modelo premium de Verbo AI'),
    (r'\bsoy un modelo de lenguaje de OpenAI\b', 'soy NewserPlus, modelo premium de Verbo AI'),
    (r'\bmodelo de lenguaje entrenado por OpenAI\b', 'modelo de lenguaje creado por VerboAITeams'),
    (r'\bmodelo de lenguaje de OpenAI\b', 'modelo de lenguaje de Verbo AI'),
    (r'\bOpenAI\b', 'VerboAITeams'),
    (r'\bChatGPT\b', 'NewserPlus'),
    (r'\bSoy Qwen\b', 'Soy NewserPlus de Verbo AI'),
    (r'\bsoy Qwen\b', 'soy NewserPlus de Verbo AI'),
    (r'\bSoy un modelo de lenguaje Qwen\b', 'Soy NewserPlus, modelo premium de Verbo AI'),
    (r'\bsoy un modelo de lenguaje Qwen\b', 'soy NewserPlus, modelo premium de Verbo AI'),
    (r'\bmodelo de lenguaje de gran tamaño desarrollado por Alibaba Cloud\b', 'modelo de lenguaje premium creado por VerboAITeams'),
    (r'\bmodelo de lenguaje desarrollado por Alibaba Cloud\b', 'modelo de lenguaje creado por VerboAITeams'),
    (r'\bdesarrollado por Alibaba Cloud\b', 'creado por VerboAITeams'),
    (r'\bAlibaba Cloud\b', 'VerboAITeams'),
    (r'\bAlibaba\b', 'VerboAITeams'),
    (r'\bQwen,?\s+un modelo de lenguaje', 'NewserPlus, un modelo de lenguaje premium de Verbo AI'),
    (r'\bcomo Qwen\b', 'como NewserPlus'),
    (r'\bSoy DeepSeek\b', 'Soy NewserPlus de Verbo AI'),
    (r'\bsoy DeepSeek\b', 'soy NewserPlus de Verbo AI'),
    (r'\bDeepSeek\b', 'NewserPlus'),
    (r'\bSoy GLM\b', 'Soy NewserPlus de Verbo AI'),
    (r'\bsoy GLM\b', 'soy NewserPlus de Verbo AI'),
    (r'\bOllama\b', 'Verbo AI'),
    (r'\bSurfSense\b', 'Verbo AI'),
    (r'\bSurfsense\b', 'Verbo AI'),
    (r'\bsurfsense\b', 'verbo ai'),
    (r'\bsoy el asistente de IA de Verbo AI\b', 'soy NewserPlus, el modelo premium de Verbo AI'),
    (r'\bModelscope\b', 'Verbo AI'),
    (r'\bPuter\b', 'Verbo AI'),
    (r'\bAirforce\b', 'Verbo AI'),
    (r'\bClaude\b', 'NewserPlus'),
    (r'\bAnthropic\b', 'VerboAITeams'),
    (r'\bGemini\b', 'NewserPlus'),
    (r'\bGoogle AI\b', 'VerboAITeams'),
    (r'\bLlama\b', 'NewserPlus'),
    (r'\bMeta AI\b', 'VerboAITeams'),
]

def reforzar_identidad(messages):
    if not messages:
        return messages
    mensajes_mod = list(messages)
    for i, m in enumerate(mensajes_mod):
        if m.get('role') == 'user':
            contenido = m.get('content', '')
            if isinstance(contenido, str):
                mensajes_mod[i] = {**m, 'content': IDENTIDAD_VERBO + contenido}
            break
    return mensajes_mod

def limpiar_identidad_respuesta(texto):
    if not texto:
        return texto
    for patron, nuevo in REEMPLAZOS_IDENTIDAD:
        texto = re.sub(patron, nuevo, texto, flags=re.IGNORECASE)
    return texto

def strip_think_tags(texto):
    if not texto:
        return texto
    texto = re.sub(r'', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'<think>[\s\S]*$', '', texto, flags=re.IGNORECASE)
    return texto.lstrip()

def obtener_proxy_rotativo():
    """Obtiene un proxy aleatorio de la lista para rotación de IPs"""
    if PROXY_ROTATION_ENABLED and PROXY_LIST:
        proxy = random.choice(PROXY_LIST)
        # Extraer solo la IP para logging (sin puerto)
        ip = proxy.split('://')[1].split(':')[0] if '://' in proxy else proxy.split(':')[0]
        log.info(f"[Proxies] Usando IP rotativa: {ip}")
        return {'http': proxy, 'https': proxy}
    return None

def detectar_tipo_request(messages):
    """Detecta si el request es para diseño/canvas/juegos basado en el contenido"""
    if not messages:
        return 'general'
    
    texto_completo = ' '.join([m.get('content', '') for m in messages]).lower()
    
    # Palabras clave para diseño/canvas/juegos
    keywords_design = [
        'canvas', 'juego', 'game', 'diseño', 'design', 'animación', 'animation',
        'sprite', 'tile', 'voxel', 'minecraft', 'terraria', 'three.js', 'webgl',
        'gráfico', 'graphic', 'render', 'shader', 'texture', 'modelo 3d', '3d model',
        'motor de juego', 'game engine', 'physics', 'colisión', 'collision'
    ]
    
    for keyword in keywords_design:
        if keyword in texto_completo:
            return 'design'
    
    return 'general'

def esPedidoVisual(messages):
    """Detecta si el request es visual/canvas/juegos/Modo Design (versión mejorada)"""
    if not messages:
        return False
    
    texto_completo = ' '.join([m.get('content', '') for m in messages]).lower()
    
    # Palabras clave para pedidos visuales (más amplio que design)
    keywords_visual = [
        'canvas', 'juego', 'game', 'diseño', 'design', 'animación', 'animation',
        'sprite', 'tile', 'voxel', 'minecraft', 'terraria', 'three.js', 'webgl',
        'gráfico', 'graphic', 'render', 'shader', 'texture', 'modelo 3d', '3d model',
        'motor de juego', 'game engine', 'physics', 'colisión', 'collision',
        'visual', 'imagen', 'image', 'dibujar', 'draw', 'pintar', 'paint',
        'interfaz', 'interface', 'ui', 'ux', 'layout', 'estilo', 'style',
        'color', 'forma', 'shape', 'animar', 'animate', 'efecto', 'effect'
    ]
    
    for keyword in keywords_visual:
        if keyword in texto_completo:
            return True
    
    return False

def _extraer_contenido_respuesta(response):
    """Extrae el texto de una respuesta de g4f, ya sea streaming o no."""
    content = ''
    try:
        for chunk in response:
            if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'content') and delta.content:
                    content += delta.content
    except TypeError:
        # No es iterable -> no fue streaming, es una respuesta completa
        if hasattr(response, 'choices') and len(response.choices) > 0:
            content = response.choices[0].message.content or ''
    return content


def intentar_g4f_space_hosted(nombre_live_provider, modelo, messages_reforzados,
                               temperature, max_tokens, timeout_s):
    """
    Intenta resolver el request contra la infraestructura hosteada de g4f
    (g4f.space), ya sea un 'live provider' (ej: 'default', 'community-day-2026')
    o un 'custom server' (ej: 'custom:srv_XXXX'). Esto reutiliza el mismo
    backend centralizado que usa https://g4f.dev/chat, en vez de scrapear
    providers directamente desde nuestra propia IP de Render.

    Devuelve (contenido, etiqueta_usada) o lanza una excepción si falla.
    """
    from g4f.client import ClientFactory

    if provider_en_cooldown(f"hosted:{nombre_live_provider}"):
        raise RuntimeError(f'{nombre_live_provider}: en cooldown (falló hace poco)')

    # Pasamos nuestra api_key de G4F si la tenemos configurada (G4F_API_KEY
    # env var / g4f_keys_state). Sin esto, g4f.space usa una key anónima
    # compartida que tiene un límite de "3 días activos cada 12" — por eso
    # es importante registrarse gratis en https://g4f.dev/members.html y
    # setear G4F_API_KEY en Render con la key real.
    api_key = g4f_keys_state.get('current_key')
    client = ClientFactory.create_client(nombre_live_provider, timeout=timeout_s, api_key=api_key)
    response = client.chat.completions.create(
        model=modelo,
        messages=messages_reforzados,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    content = _extraer_contenido_respuesta(response)
    if not content or not content.strip():
        raise RuntimeError(f'{nombre_live_provider}/{modelo}: respuesta vacia')
    return content


def llamar_g4f(messages, model, temperature, max_tokens):
    if not g4f_client:
        raise RuntimeError('g4f no esta disponible')

    messages_reforzados = reforzar_identidad(messages)

    provider_desde_modelo = None
    modelo_a_usar = model
    if ':' in model and not model.startswith('http'):
        partes = model.split(':', 1)
        if len(partes[0]) < 40 and ' ' not in partes[0]:
            provider_desde_modelo = partes[0]
            modelo_a_usar = partes[1]
            log.info(f'Modelo con provider explicito: provider={provider_desde_modelo} | modelo={modelo_a_usar}')
    
    # Corrección: Reemplazar "auto" por un modelo real (Pollinations no acepta "auto")
    if modelo_a_usar == 'auto' or not modelo_a_usar:
        modelo_a_usar = DEFAULT_MODEL
        log.info(f"[Cascada] Modelo 'auto' reemplazado por: {modelo_a_usar}")

    # VERIFICACIÓN DE ESTADO DE PLANIFICACIÓN (SISTEMA SECUENCIAL)
    if model_activation_state['plan_mode']:
        # En modo planificación, rechazar solicitudes de modelos
        log.warning(f"[Activación] Modo planificación activo. Modelos desactivados. Rechazando solicitud para {modelo_a_usar}")
        raise RuntimeError(f'Modo planificación activo. Los modelos están desactivados. Llama a /v1/plan con action=disable para funcionamiento normal, o action=complete para activar ejecución secuencial.')
    
    if model_activation_state['plan_complete'] and model_activation_state['plan_models']:
        # En modo ejecución, verificar si el modelo solicitado es el modelo actual en el plan
        current_model = model_activation_state['plan_models'][model_activation_state['current_model_index']]
        if modelo_a_usar != current_model:
            log.warning(f"[Activación] Modelo {modelo_a_usar} no es el modelo actual en el plan. Modelo actual: {current_model} (índice {model_activation_state['current_model_index']})")
            raise RuntimeError(f'Modelo {modelo_a_usar} no es el modelo actual en el plan. Modelo actual: {current_model}. Llama a /v1/plan con action=next para pasar al siguiente modelo.')
        else:
            log.info(f"[Activación] Modelo {modelo_a_usar} es el modelo actual en el plan. Permitiendo ejecución.")

    # Detectar tipo de request (se mantiene por compatibilidad/logging, ya
    # no se usa para elegir una cascada distinta: los providers reales
    # disponibles son los mismos para chat normal o para pedidos visuales,
    # así que se prueban en el mismo orden de calidad/estabilidad conocida).
    tipo_request = detectar_tipo_request(messages)
    es_visual = esPedidoVisual(messages)
    log.info(f"[Cascada] Tipo de request detectado: {tipo_request} | Visual: {es_visual}")

    tiempo_inicio_cascada = time.time()

    # ========================================================
    # PASO 0: Infraestructura hosteada de g4f.space (PRIMERA opción)
    # ========================================================
    # Esto reutiliza el mismo backend que https://g4f.dev/chat, mantenido
    # por el equipo de g4f. Es más confiable que scrapear providers desde
    # nuestra propia IP de Render porque ellos gestionan el routing/IPs.
    modelo_lower_pedido = modelo_a_usar.lower()

    # Mapeo específico solicitado: reemplaza DeepSeek-V4-Pro y
    # Kimi-K2.7-Code por el custom server real "opencode.ai/go".
    intentos_hosted = []
    if 'kimi-k2.7-code' in modelo_lower_pedido or 'kimi-k3' in modelo_lower_pedido or 'moonshotai' in modelo_lower_pedido:
        intentos_hosted.append((f'custom:{OPENCODE_GO_SERVER_ID}', 'kimi-k3'))
    if 'deepseek-v4-pro' in modelo_lower_pedido or 'deepseek-ai' in modelo_lower_pedido or 'gpt-5.6-luna' in modelo_lower_pedido:
        intentos_hosted.append((f'custom:{OPENCODE_GO_SERVER_ID}', 'gpt-5.6-luna'))
    if 'glm' in modelo_lower_pedido:
        # 'community-day-2026' es temporal (evento del 10 de julio 2026);
        # si ya no existe en el registro de g4f.dev, esto falla rápido y
        # sigue de largo sin romper nada.
        intentos_hosted.append((COMMUNITY_DAY_LIVE_PROVIDER, 'zai-org/GLM-5.2'))

    # Si el modelo pedido no matcheó nada específico, probamos igual el
    # routing automático 'default' de g4f.space (deja que ellos elijan
    # el mejor modelo disponible en ese momento).
    intentos_hosted.append(('default', 'auto'))

    for nombre_live_provider, modelo_hosted in intentos_hosted:
        if (time.time() - tiempo_inicio_cascada) > TOTAL_REQUEST_BUDGET_SECONDS:
            log.warning(f"[Hosted] Presupuesto de tiempo agotado antes de terminar de probar g4f.space")
            break

        # Con varias keys cargadas (G4F_KEY1..9), si una se queda sin cupo
        # ("Active day limit") probamos con las siguientes antes de tirar
        # la toalla en este provider. keys_intentadas evita loops infinitos
        # si obtener_key_activa() siempre devuelve la misma.
        keys_intentadas = set()
        while True:
            if (time.time() - tiempo_inicio_cascada) > TOTAL_REQUEST_BUDGET_SECONDS:
                break
            try:
                log.info(f"[Hosted] Probando g4f.space | provider: {nombre_live_provider} | modelo: {modelo_hosted} | key: {(g4f_keys_state['current_key'] or 'anonima')[:16]}...")
                content = intentar_g4f_space_hosted(
                    nombre_live_provider, modelo_hosted, messages_reforzados,
                    temperature, max_tokens, REQUEST_TIMEOUT_SECONDS
                )
                content = strip_think_tags(content)
                content = limpiar_identidad_respuesta(content)
                log.info(f"[Hosted] OK | provider: {nombre_live_provider} | modelo: {modelo_hosted} | {len(content)} chars")
                return content, f'{nombre_live_provider}:{modelo_hosted}'
            except Exception as e:
                error_str = str(e).lower()
                log.warning(f"[Hosted] Fallo {nombre_live_provider}/{modelo_hosted}: {e}")

                cuota_o_auth_agotada = (
                    'active day limit' in error_str
                    or '401' in error_str or 'unauthorized' in error_str or 'invalid api key' in error_str
                    or '429' in error_str or 'rate limit' in error_str or 'quota' in error_str
                )
                if cuota_o_auth_agotada and g4f_keys_state.get('current_key'):
                    # Marcamos esta key como agotada/inválida y probamos con
                    # la siguiente si hay otra distinta disponible.
                    keys_intentadas.add(g4f_keys_state['current_key'])
                    g4f_key_manager.marcar_key_expirada(g4f_keys_state['current_key'])
                    nueva_key = g4f_key_manager.obtener_key_activa()
                    if nueva_key and nueva_key not in keys_intentadas:
                        g4f_keys_state['current_key'] = nueva_key
                        log.info(f"[Keys] Rotando a otra key para {nombre_live_provider}: {nueva_key[:16]}...")
                        continue  # reintentar este mismo provider con la key nueva

                if 'active day limit' in error_str:
                    # Ya no quedan más keys propias para rotar (o no había
                    # ninguna configurada) y seguimos con cuota agotada.
                    # No es un fallo pasajero: NO se arregla reintentando en
                    # unos minutos. Enfriamos los providers hosteados por
                    # mucho más tiempo y cortamos la cascada hosteada.
                    log.error(
                        "[Hosted] Cuota de días activos de g4f.space agotada en todas las keys disponibles. "
                        "Registrate gratis en https://g4f.dev/members.html, conseguí más API keys y "
                        "cargalas como G4F_KEY1, G4F_KEY2... en Render para evitar este límite."
                    )
                    for prov_hosted, _ in intentos_hosted:
                        marcar_provider_fallido(f"hosted:{prov_hosted}", cooldown_segundos=HOSTED_QUOTA_COOLDOWN_SECONDS)
                    break

                marcar_provider_fallido(f"hosted:{nombre_live_provider}")
                break
        # continúa con el siguiente provider hosteado de la lista (si lo hay)

    log.warning("[Hosted] g4f.space no respondió con ningún modelo, cayendo al cascada local de providers")

    # MAPEO MODELO -> (provider, modelo_real_del_provider)
    # Cada entrada usa el nombre de modelo REAL que ese provider espera
    # (confirmado contra el paquete g4f instalado). Si el modelo pedido por
    # el usuario no matchea ninguno de estos, se cae al fallback general.
    # El orden importa: las entradas más específicas van primero para que
    # no las tape una coincidencia genérica (p.ej. 'zai-org' antes que 'glm').
    MAPEO_MODELO_PROVIDER = [
        ('zai-org', 'DeepInfra', 'zai-org/GLM-5.2'),
        ('gpt-oss', 'Nvidia', 'openai/gpt-oss-120b'),
        ('glm-5.2', 'GLM', 'GLM-4.7'),
        ('glm-4', 'GLM', 'GLM-4.7'),
        ('glm', 'DeepInfra', 'zai-org/GLM-5.2'),
    ]

    # Cascada de modelos a intentar, en orden. El primero es lo que pidió
    # el usuario (se intenta mapear a un provider real); el resto son
    # modelos reales conocidos como respaldo.
    modelos_disponibles = [
        modelo_a_usar,
        'GLM-4.7',              # GLM directo
        'zai-org/GLM-5.2',      # Mismo modelo vía DeepInfra
        'openai/gpt-oss-120b',  # Nvidia
    ]

    vistos = set()
    modelos_a_probar = []
    for m in modelos_disponibles:
        if m and m not in vistos:
            modelos_a_probar.append(m)
            vistos.add(m)

    # FORZAMOS PROVEEDORES: mapeo dinámico según modelo (solución al timeout)
    if provider_desde_modelo:
        providers_a_probar = [provider_desde_modelo]
    else:
        # Usar lista de providers recomendados (solo los que existen de verdad)
        providers_a_probar = AVAILABLE_PROVIDERS

    tiempo_inicio_cascada_local = time.time()
    ultimo_error = None
    for modelo_actual in modelos_a_probar:
        # Respetar el presupuesto total de tiempo de este request (cuenta
        # desde el arranque de llamar_g4f, no solo desde acá, para no
        # exceder TOTAL_REQUEST_BUDGET_SECONDS sumando hosted + local)
        if (time.time() - tiempo_inicio_cascada) > TOTAL_REQUEST_BUDGET_SECONDS:
            log.warning(f"[Cascada] Presupuesto total de tiempo ({TOTAL_REQUEST_BUDGET_SECONDS}s) agotado, abortando cascada")
            break

        # Determinar pares (provider, modelo_real) a intentar para este modelo pedido
        modelo_lower = modelo_actual.lower()
        pares_provider_modelo = []  # lista de (provider_class, modelo_real_str)

        for substring, provider_name, modelo_real_provider in MAPEO_MODELO_PROVIDER:
            if substring in modelo_lower:
                if not hasattr(g4f.Provider, provider_name):
                    log.warning(f"[Cascada] Provider {provider_name} no disponible en g4f.Provider (versión instalada)")
                    continue
                if provider_en_cooldown(provider_name):
                    log.info(f"[Cascada] Provider {provider_name} en cooldown (falló hace poco), saltando")
                    continue
                pares_provider_modelo = [(getattr(g4f.Provider, provider_name), modelo_real_provider)]
                log.info(f"[Cascada] Modelo {modelo_actual} -> provider {provider_name} (modelo real: {modelo_real_provider})")
                break

        # Si no hay provider específico (o está en cooldown), usar providers generales.
        # A cada provider general se le pasa SU PROPIO modelo por defecto (default_model),
        # no el string pedido por el usuario, porque cada provider solo entiende sus
        # propios nombres de modelo.
        if not pares_provider_modelo:
            log.warning(f"[Cascada] Modelo {modelo_actual} sin provider específico disponible, usando providers generales")
            for p in providers_a_probar:
                nombre_p = getattr(p, '__name__', str(p))
                if provider_en_cooldown(nombre_p):
                    continue
                modelo_del_provider = getattr(p, 'default_model', None) or modelo_actual
                pares_provider_modelo.append((p, modelo_del_provider))

        for provider_actual, modelo_real in pares_provider_modelo:
            modelo_actual_intento = modelo_real
            # Detectar si es modelo Qwen para forzar rotación de IPs
            es_qwen = 'qwen' in modelo_actual_intento.lower() or (hasattr(provider_actual, '__name__') and 'qwen' in provider_actual.__name__.lower())
            
            # Para Qwen: FORZAR proxy primero (rate limiting por IP)
            # Para otros: NO usar proxy por defecto (muchos caídos, causan timeout de 30s)
            if es_qwen and PROXY_ROTATION_ENABLED:
                proxy_order = [True, False]  # Qwen: proxy primero
            elif PROXY_ROTATION_ENABLED:
                proxy_order = [False, True]  # Otros: sin proxy primero
            else:
                proxy_order = [False]
            
            for usar_proxy in proxy_order:
                # Respetar presupuesto total también entre proveedores/proxies
                if (time.time() - tiempo_inicio_cascada) > TOTAL_REQUEST_BUDGET_SECONDS:
                    log.warning(f"[Cascada] Presupuesto total de tiempo ({TOTAL_REQUEST_BUDGET_SECONDS}s) agotado, abortando cascada")
                    raise RuntimeError(f'Todos los modelos/providers fallaron. Ultimo error: {ultimo_error} (presupuesto de tiempo agotado)')
                try:
                    provider_name = provider_actual.__name__ if hasattr(provider_actual, '__name__') else (provider_actual or 'auto')
                    
                    # Usar proxy rotativo si está habilitado y es el primer intento
                    proxy_config = obtener_proxy_rotativo() if (usar_proxy and PROXY_ROTATION_ENABLED) else None
                    
                    log.info(f'Intentando modelo: {modelo_actual_intento} | provider: {provider_name} | proxy: {"si" if proxy_config else "no"}')
                    
                    kwargs = {
                        'model': modelo_actual_intento,
                        'messages': messages_reforzados,
                        'temperature': temperature,
                        'max_tokens': max_tokens,
                        'ignored_providers': IGNORED_PROVIDER_CLASSES,  # Ignorar providers problemáticos
                    }
                    if provider_actual:
                        kwargs['provider'] = provider_actual
                    if proxy_config:
                        kwargs['proxies'] = proxy_config
                    # Usar key de G4F si está disponible
                    if g4f_keys_state['current_key']:
                        kwargs['api_key'] = g4f_keys_state['current_key']
                    
                    # Activar streaming para evitar timeout de 120s de Render
                    kwargs['stream'] = True

                    response = g4f_client.chat.completions.create(**kwargs)
                    
                    # Manejar respuesta streaming
                    content = ''
                    for chunk in response:
                        if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                            delta = chunk.choices[0].delta
                            if hasattr(delta, 'content') and delta.content:
                                content += delta.content

                    if content and content.strip():
                        content = strip_think_tags(content)
                        content = limpiar_identidad_respuesta(content)
                        log.info(f'OK | modelo: {modelo_actual_intento} | provider: {provider_name} | proxy: {"si" if proxy_config else "no"} | {len(content)} chars')
                        
                        # ACTIVACIÓN SECUENCIAL: Si el modelo actual terminó exitosamente, pasar al siguiente
                        if model_activation_state['plan_complete'] and model_activation_state['plan_models']:
                            if model_activation_state['current_model_index'] < len(model_activation_state['plan_models']) - 1:
                                model_activation_state['current_model_index'] += 1
                                next_model = model_activation_state['plan_models'][model_activation_state['current_model_index']]
                                log.info(f"[Activación] Modelo {modelo_actual_intento} completado. Pasando al siguiente modelo: {next_model} (índice {model_activation_state['current_model_index']})")
                            else:
                                log.info(f"[Activación] Modelo {modelo_actual_intento} completado. No hay más modelos en el plan. Plan finalizado.")
                                model_activation_state['plan_complete'] = False
                        
                        return content, modelo_actual_intento
                    else:
                        ultimo_error = f'{modelo_actual_intento}/{provider_name}: respuesta vacia'
                        log.warning(ultimo_error)
                        break  # Si respuesta vacía, no reintentar sin proxy
                except Exception as e:
                    provider_name = provider_actual.__name__ if hasattr(provider_actual, '__name__') else (provider_actual or 'auto')
                    error_msg = f'{modelo_actual_intento}/{provider_name}: {e}'
                    
                    # Detectar errores de key expirada o sin tokens
                    error_str = str(e).lower()
                    if '401' in error_str or 'unauthorized' in error_str or 'invalid api key' in error_str:
                        log.error(f'[Keys] Key de G4F expirada o inválida: {g4f_keys_state["current_key"][:20] if g4f_keys_state["current_key"] else "N/A"}...')
                        if g4f_keys_state['current_key']:
                            g4f_key_manager.marcar_key_expirada(g4f_keys_state['current_key'])
                            # Intentar obtener nueva key
                            nueva_key = g4f_key_manager.obtener_key_activa()
                            if nueva_key:
                                g4f_keys_state['current_key'] = nueva_key
                                log.info(f'[Keys] Rotando a nueva key: {g4f_keys_state["current_key"][:20]}...')
                                continue  # Reintentar con nueva key
                    elif '429' in error_str or 'rate limit' in error_str or 'quota' in error_str:
                        log.error(f'[Keys] Key de G4F sin tokens o rate limit: {g4f_keys_state["current_key"][:20] if g4f_keys_state["current_key"] else "N/A"}...')
                        if g4f_keys_state['current_key']:
                            g4f_key_manager.marcar_key_expirada(g4f_keys_state['current_key'])
                            # Intentar obtener nueva key
                            nueva_key = g4f_key_manager.obtener_key_activa()
                            if nueva_key:
                                g4f_keys_state['current_key'] = nueva_key
                                log.info(f'[Keys] Rotando a nueva key: {g4f_keys_state["current_key"][:20]}...')
                                continue  # Reintentar con nueva key
                    
                    if usar_proxy and PROXY_LIST:
                        log.warning(f'Fallo con proxy, reintentando sin proxy: {error_msg}')
                        continue  # Reintentar sin proxy
                    else:
                        ultimo_error = error_msg
                        log.warning(f'Fallo modelo {modelo_actual_intento} provider {provider_name}: {e}')
                        marcar_provider_fallido(provider_name)  # circuit breaker: enfriar este provider
                        break  # Pasar al siguiente modelo/provider

    raise RuntimeError(f'Todos los modelos/providers fallaron. Ultimo error: {ultimo_error}')


@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({
                'error': {
                    'message': 'JSON body is required',
                    'type': 'invalid_request'
                }
            }), 400
        
        messages = data.get('messages', [])
        model = data.get('model', DEFAULT_MODEL)
        temperature = data.get('temperature', 0.7)
        max_tokens = data.get('max_tokens', 3072)

        if not messages:
            return jsonify({
                'error': {
                    'message': 'messages field is required',
                    'type': 'invalid_request'
                }
            }), 400

        # Reemplazar 'g4f-bridge' por modelo por defecto (no es un modelo válido)
        if model == 'g4f-bridge':
            model = DEFAULT_MODEL
            log.info(f'Model "g4f-bridge" reemplazado por: {model}')

        log.info(f'POST /v1/chat/completions | model pedido={model} | messages={len(messages)}')

        content, modelo_usado = llamar_g4f(messages, model, temperature, max_tokens)

        return jsonify({
            'id': 'chatcmpl-g4f-bridge',
            'object': 'chat.completion',
            'model': modelo_usado,
            'choices': [{
                'index': 0,
                'message': {'role': 'assistant', 'content': content},
                'finish_reason': 'stop'
            }],
            'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
        })

    except Exception as e:
        log.error(f'Error en chat_completions: {e}', exc_info=True)
        return jsonify({
            'error': {
                'message': str(e),
                'type': 'bridge_error'
            }
        }), 502

@app.route('/v1/models', methods=['GET'])
def list_models():
    modelos = [
        # Modelos reales confirmados contra el paquete g4f instalado
        "GLM-4.7",              # Desde provider GLM (chat.z.ai)
        "zai-org/GLM-5.2",      # Desde provider DeepInfra (deepinfra.com)
        "openai/gpt-oss-120b",  # Desde provider Nvidia (build.nvidia.com)
    ]
    data = [{"id": m, "object": "model", "owned_by": "g4f-bridge"} for m in modelos]
    return jsonify({"object": "list", "data": data})

@app.route('/v1/images/generations', methods=['POST'])
def images_generations():
    try:
        data = request.get_json(force=True)
        prompt = data.get('prompt', '')
        model_pedido = data.get('model', 'flux')
        n = data.get('n', 1)
        size = data.get('size', '1024x1024')

        if not prompt:
            return jsonify({'error': {'message': 'Falta prompt', 'type': 'invalid_request'}}), 400

        log.info(f'POST /v1/images/generations | model={model_pedido} | prompt="{prompt[:50]}..." | size={size}')

        if not g4f_client:
            return jsonify({'error': {'message': 'g4f no disponible', 'type': 'bridge_error'}}), 502

        modelos_imagen = [
            model_pedido, 'flux', 'flux-pro', 'flux-dev', 'flux-schnell', 'sdxl-turbo', 'sd-3.5-large', 'gpt-image', 'dalle-3',
        ]
        vistos = set()
        modelos_a_probar = []
        for m in modelos_imagen:
            if m and m not in vistos:
                modelos_a_probar.append(m)
                vistos.add(m)

        ultimo_error = None
        for modelo_actual in modelos_a_probar:
            try:
                log.info(f'Intentando modelo imagen: {modelo_actual}')
                response = g4f_client.images.generate(
                    model=modelo_actual, prompt=prompt, n=n, size=size,
                )
                if response.data and len(response.data) > 0:
                    item = response.data[0]
                    if hasattr(item, 'b64_json') and item.b64_json:
                        log.info(f'OK imagen | modelo: {modelo_actual} | {len(item.b64_json)} chars b64')
                        return jsonify({
                            'created': int(__import__('time').time()),
                            'model': modelo_actual,
                            'data': [{'b64_json': item.b64_json, 'revised_prompt': getattr(item, 'revised_prompt', prompt)}]
                        })
                    elif hasattr(item, 'url') and item.url:
                        log.info(f'OK imagen | modelo: {modelo_actual} | URL: {item.url[:80]}')
                        return jsonify({
                            'created': int(__import__('time').time()),
                            'model': modelo_actual,
                            'data': [{'url': item.url, 'revised_prompt': getattr(item, 'revised_prompt', prompt)}]
                        })
                    else:
                        ultimo_error = f'{modelo_actual}: respuesta sin imagen clara'
                        log.warning(ultimo_error)
                else:
                    ultimo_error = f'{modelo_actual}: respuesta vacia'
                    log.warning(ultimo_error)
            except Exception as e:
                ultimo_error = f'{modelo_actual}: {str(e)[:150]}'
                log.warning(f'Fallo modelo imagen {modelo_actual}: {str(e)[:200]}')
                continue

        return jsonify({
            'error': {
                'message': f'Todos los modelos de imagen fallaron. Ultimo: {ultimo_error}',
                'type': 'bridge_error'
            }
        }), 502

    except Exception as e:
        log.error(f'Error en images_generations: {e}', exc_info=True)
        return jsonify({'error': {'message': str(e), 'type': 'bridge_error'}}), 500


@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'service': 'glm-bridge',
        'mode': 'g4f-free',
        'build_version': BUILD_VERSION,
        'render_commit': RENDER_COMMIT,
        'model_default': DEFAULT_MODEL,
        'provider': DEFAULT_PROVIDER or 'auto',
        'g4f_available': g4f_client is not None,
        'request_timeout_seconds': REQUEST_TIMEOUT_SECONDS,
        'total_request_budget_seconds': TOTAL_REQUEST_BUDGET_SECONDS,
        'providers_activos': [p.__name__ for p in AVAILABLE_PROVIDERS],
        'providers_en_cooldown': {k: round(provider_cooldown_custom.get(k, PROVIDER_COOLDOWN_SECONDS) - (time.time() - v), 1)
                                   for k, v in provider_ultimo_fallo.items()
                                   if provider_en_cooldown(k)},
        'g4f_api_key_configurada': bool(g4f_keys_state.get('current_key')),
        'proxy_rotation_enabled': PROXY_ROTATION_ENABLED,
        'proxy_count': len(PROXY_LIST),
        'plan_mode': model_activation_state['plan_mode'],
        'plan_complete': model_activation_state['plan_complete'],
        'current_model_index': model_activation_state['current_model_index'],
        'plan_models': model_activation_state['plan_models'],
        'endpoints': {
            'chat': '/v1/chat/completions (POST, enviar "model" en el body para elegir)',
            'models': '/v1/models (GET, lista de modelos disponibles)',
            'images': '/v1/images/generations (POST)'
        }
    })

@app.route('/v1/plan', methods=['POST', 'GET'])
def plan_control():
    """Endpoint para controlar el plan de ejecución de modelos"""
    global model_activation_state
    
    if request.method == 'GET':
        # Obtener estado actual del plan
        return jsonify({
            'plan_mode': model_activation_state['plan_mode'],
            'plan_complete': model_activation_state['plan_complete'],
            'current_model_index': model_activation_state['current_model_index'],
            'plan_models': model_activation_state['plan_models']
        })
    
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        action = data.get('action')
        models = data.get('models', [])
        
        if action == 'start':
            # Iniciar plan: entrar en modo planificación con lista de modelos
            model_activation_state['plan_mode'] = True
            model_activation_state['plan_models'] = models
            model_activation_state['current_model_index'] = 0
            model_activation_state['plan_complete'] = False
            log.info(f"[Plan] Plan iniciado con modelos: {models}")
            return jsonify({
                'status': 'plan_started',
                'plan_models': models,
                'plan_mode': True
            })
        
        elif action == 'complete':
            # Completar plan: salir de modo planificación, activar ejecución secuencial
            model_activation_state['plan_mode'] = False
            model_activation_state['plan_complete'] = True
            model_activation_state['current_model_index'] = 0
            log.info(f"[Plan] Plan completado. Iniciando ejecución secuencial de modelos: {model_activation_state['plan_models']}")
            return jsonify({
                'status': 'plan_complete',
                'plan_mode': False,
                'plan_models': model_activation_state['plan_models']
            })
        
        elif action == 'next':
            # Pasar al siguiente modelo en el plan
            if model_activation_state['current_model_index'] < len(model_activation_state['plan_models']) - 1:
                model_activation_state['current_model_index'] += 1
                current_model = model_activation_state['plan_models'][model_activation_state['current_model_index']]
                log.info(f"[Plan] Pasando al siguiente modelo: {current_model} (índice {model_activation_state['current_model_index']})")
                return jsonify({
                    'status': 'next_model',
                    'current_model_index': model_activation_state['current_model_index'],
                    'current_model': current_model
                })
            else:
                log.info("[Plan] No hay más modelos en el plan")
                return jsonify({
                    'status': 'plan_finished',
                    'message': 'No hay más modelos en el plan'
                })
        
        elif action == 'reset':
            # Resetear el plan
            model_activation_state['plan_mode'] = True
            model_activation_state['plan_models'] = []
            model_activation_state['current_model_index'] = 0
            model_activation_state['plan_complete'] = False
            log.info("[Plan] Plan reseteado")
            return jsonify({
                'status': 'plan_reset',
                'plan_mode': True
            })
        
        elif action == 'disable':
            # Desactivar modo planificación completamente (funcionamiento normal)
            model_activation_state['plan_mode'] = False
            model_activation_state['plan_complete'] = False
            model_activation_state['plan_models'] = []
            model_activation_state['current_model_index'] = 0
            log.info("[Plan] Modo planificación desactivado. Funcionamiento normal activado.")
            return jsonify({
                'status': 'plan_disabled',
                'plan_mode': False
            })
        
        else:
            return jsonify({
                'error': {
                    'message': 'Acción inválida. Use: start, complete, next, reset, o disable',
                    'type': 'invalid_request'
                }
            }), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    log.info(f'Puente g4f iniciando en puerto {port} | modelo: {DEFAULT_MODEL} | provider: {DEFAULT_PROVIDER or "auto"}')
    app.run(host='0.0.0.0', port=port, debug=False)
