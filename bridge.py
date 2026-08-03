"""
Puente GPT4Free — Modelo dinámico (glm-5.2, qwen, deepseek) SIN API KEY
Con rotación de IPs vía proxies gratuitos
==========================================================================
"""

import os
import re
import logging
import random
from flask import Flask, request, jsonify
from flask_cors import CORS
import g4f

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

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

# Modelo por defecto (cambiado a modelo que funciona gratis)
DEFAULT_MODEL = os.environ.get('G4F_MODEL_OVERRIDE', 'deepseek-v3')
DEFAULT_PROVIDER = os.environ.get('G4F_PROVIDER', '')

# ============================================================
# CONFIGURACIÓN SCRAPING AVANZADO (PROVIDERS QUE USAN WEB SCRAPING)
# ============================================================
# Providers que usan scraping web en lugar de API (más robustos)
SCRAPING_PROVIDERS = [
    'DeepSeek',
    'Poe',
    'You',
    'Perplexity',
    'Phind',
    'Blackbox',
    'Cohere',
]

# Intentar obtener providers de g4f dinámicamente
AVAILABLE_SCRAPING_PROVIDERS = []
for provider_name in SCRAPING_PROVIDERS:
    try:
        if hasattr(g4f.Provider, provider_name):
            provider_class = getattr(g4f.Provider, provider_name)
            AVAILABLE_SCRAPING_PROVIDERS.append(provider_class)
            log.info(f"[Scraping] Provider disponible: {provider_name}")
    except Exception as e:
        log.warning(f"[Scraping] No se pudo cargar provider {provider_name}: {e}")

log.info(f"[Scraping] Total providers de scraping disponibles: {len(AVAILABLE_SCRAPING_PROVIDERS)}")

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
    
    g4f_client = Client(**client_kwargs)
    
    # CONFIGURACIÓN DE DEEPSEEK CON ARCHIVOS HAR
    # DeepSeek ahora requiere autenticación mediante archivos HAR exportados del navegador
    try:
        import os
        har_dir = os.path.join(os.path.dirname(__file__), 'har_and_cookies')
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

    # Detectar tipo de request para seleccionar cascada apropiada
    tipo_request = detectar_tipo_request(messages)
    log.info(f"[Cascada] Tipo de request detectado: {tipo_request}")
    
    # CASCADA DE MODELOS SEGÚN TIPO DE REQUEST
    if tipo_request == 'design':
        # Cascada para diseño/canvas/juegos (modelos especializados primero)
        modelos_disponibles = [
            modelo_a_usar,
            # Modelos especializados en diseño y código
            'claude-3-5-sonnet',  # Excelente para diseño y código
            'gpt-4o',  # Multimodal, bueno para diseño
            'deepseek-coder',  # Especializado en código
            'Qwen/Qwen3-Coder-30B-A3B-Instruct',  # Coding avanzado
            'kimi-k2.7-code',  # Coding desde ollama.pro
            'gpt-4-turbo',  # Bueno para diseño
            'claude-3-opus',  # Alta capacidad
            # Fallback a modelos generales
            'deepseek-v3',
            'deepseek-v4-pro',
            'qwen/qwen3.7-max',
            'gpt-4o-mini',
            'qwen/qwen3.7-plus',
            'deepseek-r1',
            'qwen/qwen-1.5-72b',
            'glm-5.2',  # Requiere suscripción Ollama (error 403)
        ]
    else:
        # Cascada general (modelos balanceados)
        modelos_disponibles = [
            modelo_a_usar,
            'kimi-k2.7-code',  # Nuevo modelo de coding desde ollama.pro
            'deepseek-v3',
            'deepseek-v4-pro',
            'deepseek-r1',
            'qwen/qwen3.7-max',
            'qwen/qwen3.7-plus',
            'Qwen/Qwen3-Coder-30B-A3B-Instruct',
            'gpt-4o-mini',
            'gpt-4o',
            'gemini-1.5-flash',
            'gemini-1.5-pro',
            'qwen/qwen-1.5-72b',
            'glm-5.2',  # Requiere suscripción Ollama (error 403)
        ]

    vistos = set()
    modelos_a_probar = []
    for m in modelos_disponibles:
        if m and m not in vistos:
            modelos_a_probar.append(m)
            vistos.add(m)

    # FORZAMOS PROVEEDORES: cascada inteligente con scraping primero
    if provider_desde_modelo:
        providers_a_probar = [provider_desde_modelo]
    else:
        providers_a_probar = [DEFAULT_PROVIDER] if DEFAULT_PROVIDER else []
        
        # Para requests de diseño, priorizar providers de scraping
        if tipo_request == 'design' and AVAILABLE_SCRAPING_PROVIDERS:
            log.info(f"[Cascada] Usando providers de scraping para diseño")
            for provider in AVAILABLE_SCRAPING_PROVIDERS:
                if provider not in providers_a_probar:
                    providers_a_probar.append(provider)
        
        # Auto y Ollama como fallback
        for p in ['', g4f.Provider.Ollama]:
            if p not in providers_a_probar:
                providers_a_probar.append(p)

    ultimo_error = None
    for modelo_actual in modelos_a_probar:
        for provider_actual in providers_a_probar:
            # Intentar primero con proxy si está disponible
            for usar_proxy in [True, False] if PROXY_ROTATION_ENABLED else [False]:
                try:
                    provider_name = provider_actual.__name__ if hasattr(provider_actual, '__name__') else (provider_actual or 'auto')
                    
                    # Usar proxy rotativo si está habilitado y es el primer intento
                    proxy_config = obtener_proxy_rotativo() if (usar_proxy and PROXY_ROTATION_ENABLED) else None
                    
                    log.info(f'Intentando modelo: {modelo_actual} | provider: {provider_name} | proxy: {"si" if proxy_config else "no"}')
                    
                    kwargs = {
                        'model': modelo_actual,
                        'messages': messages_reforzados,
                        'temperature': temperature,
                        'max_tokens': max_tokens,
                    }
                    if provider_actual:
                        kwargs['provider'] = provider_actual
                    if proxy_config:
                        kwargs['proxies'] = proxy_config

                    response = g4f_client.chat.completions.create(**kwargs)
                    content = response.choices[0].message.content

                    if content and content.strip():
                        content = strip_think_tags(content)
                        content = limpiar_identidad_respuesta(content)
                        log.info(f'OK | modelo: {modelo_actual} | provider: {provider_name} | proxy: {"si" if proxy_config else "no"} | {len(content)} chars')
                        return content, modelo_actual
                    else:
                        ultimo_error = f'{modelo_actual}/{provider_name}: respuesta vacia'
                        log.warning(ultimo_error)
                        break  # Si respuesta vacía, no reintentar sin proxy
                except Exception as e:
                    provider_name = provider_actual.__name__ if hasattr(provider_actual, '__name__') else (provider_actual or 'auto')
                    error_msg = f'{modelo_actual}/{provider_name}: {e}'
                    
                    if usar_proxy and PROXY_LIST:
                        log.warning(f'Fallo con proxy, reintentando sin proxy: {error_msg}')
                        continue  # Reintentar sin proxy
                    else:
                        ultimo_error = error_msg
                        log.warning(f'Fallo modelo {modelo_actual} provider {provider_name}: {e}')
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
        # Modelos especializados en diseño/canvas/juegos
        "claude-3-5-sonnet",
        "claude-3-opus",
        "deepseek-coder",
        "gpt-4-turbo",
        # Modelos generales y coding
        "kimi-k2.7-code",
        "glm-5.2",
        "qwen/qwen3.7-max",
        "qwen/qwen3.7-plus",
        "deepseek-v4-pro",
        "Qwen/Qwen3-Coder-30B-A3B-Instruct",
        "deepseek-r1",
        "deepseek-v3",
        "gpt-4o-mini",
        "gpt-4o",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "qwen/qwen-1.5-72b"
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
        'model_default': DEFAULT_MODEL,
        'provider': DEFAULT_PROVIDER or 'auto',
        'g4f_available': g4f_client is not None,
        'proxy_rotation_enabled': PROXY_ROTATION_ENABLED,
        'proxy_count': len(PROXY_LIST),
        'endpoints': {
            'chat': '/v1/chat/completions (POST, enviar "model" en el body para elegir)',
            'models': '/v1/models (GET, lista de modelos disponibles)',
            'images': '/v1/images/generations (POST)'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    log.info(f'Puente g4f iniciando en puerto {port} | modelo: {DEFAULT_MODEL} | provider: {DEFAULT_PROVIDER or "auto"}')
    app.run(host='0.0.0.0', port=port, debug=False)
