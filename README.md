# Puente GPT4Free — kimi-k2.7-code (SIN API KEY)

Puente Python/Flask que expone `POST /v1/chat/completions` (formato OpenAI) y llama a **kimi-k2.7-code** y otros modelos gratis usando la librería `g4f` (https://github.com/xtekky/gpt4free). **No requiere token, no requiere registro, no requiere API key.**

## Modelo por defecto
- **Modelo**: `kimi-k2.7-code`, `deepseek-v3`, `deepseek-v4-pro`, `glm-5.2` (rotación automática)
- **Provider**: Ollama (para kimi-k2.7-code y glm-5.2) con fallback a auto
- **Servidores Ollama**: `https://ollama.pro/api`, `https://ai.devs503.tech/api`, `https://ollama.com/v1`, `https://api.pawan.krd/v1`
- **Identidad**: Fuertemente reforzada — el modelo SIEMPRE se presenta como "NewserPro de Verbo AI"
- **Fallbacks**: Si el modelo principal falla, prueba automáticamente otros modelos disponibles

## Rotación de IPs con Proxies Gratuitos (Opcional)

Para evitar límites de requests por IP (200 requests/día en g4f), puedes configurar **proxies públicos gratuitos**:

### Opción 1: Proxies Públicos Gratuitos

1. **Obtener lista de proxies gratuitos**:
   - Visita: https://free-proxy-list.net/
   - Filtra por: HTTP, HTTPS, nivel "Elite" o "Anonymous"
   - Copia IPs en formato: `http://ip:port`

2. **Configurar en Render**:
   - Ve a tu servicio en Render → Environment
   - Agrega esta variable (separar por coma múltiples proxies):
     ```
     FREE_PROXIES=http://proxy1.example.com:8080,http://proxy2.example.com:8080,http://proxy3.example.com:8080
     ```

3. **Verificar que funciona**:
   ```bash
   curl https://tu-bridge.onrender.com/health
   ```
   Debería mostrar `"proxy_rotation_enabled": true` y `"proxy_count": 3`

**Fuentes de proxies gratuitos:**
- https://free-proxy-list.net/
- https://www.sslproxies.org/
- https://github.com/clarketm/proxy-list
- https://spys.me/en/

**Beneficios:**
- Rotación automática de IPs en cada request
- Evita límites de 200 requests/día por IP
- 100% gratis, sin registro

**Notas:**
- Los proxies gratuitos pueden ser inestables o lentos
- Recomienda actualizar la lista periódicamente
- Si un proxy falla, el sistema reintenta sin proxy automáticamente

### Opción 2: Webshare Proxies (De pago, más confiable)

Si necesitas proxies más confiables, puedes usar Webshare:

1. **Crear cuenta en Webshare** (https://www.webshare.io):
   - 10 proxies gratis (1GB/mes)
   - Planes de pago con más proxies

2. **Configurar en bridge.py** (necesita modificación manual):
   - Reemplazar la configuración de proxies gratuitos con Webshare
   - Consulta la documentación anterior de Webshare en el código

## Deploy en Render (5 minutos)

1. **Subí estos archivos a un repo nuevo de GitHub** (`verboai-glm-bridge`):
   - `bridge.py`
   - `requirements.txt`
   - `Procfile`
   - `README.md`

2. **En Render** (https://dashboard.render.com):
   - **"New +"** → **"Web Service"**
   - Conectá tu repo `verboai-glm-bridge`
   - **Name**: `verboai-glm-bridge`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bridge.py`
   - **Plan**: Free
   - **NO hace falta ninguna Environment Variable** ← sin token, sin config
   - Click **"Create Web Service"**

3. **Esperá 2-3 minutos** a que deploye

4. **Copiá la URL** (algo como `https://verboai-glm-bridge.onrender.com`)

5. **Probá que funciona**:
   ```bash
   curl https://verboai-glm-bridge.onrender.com/health
   ```
   Debería devolver:
   ```json
   {"status":"ok","model_default":"gpt-4o-mini","provider":"Modelscope","identity_reinforcement":true,"identity_filters":["ChatGPT","OpenAI","Qwen","Alibaba","SurfSense","Claude","Gemini","Llama"]}
   ```

6. **Probá el chat directamente**:
   ```bash
   curl -X POST https://verboai-glm-bridge.onrender.com/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Hola, quien eres?"}]}'
   ```

## Conectar con tu VerboAI

En tu servicio de VerboAI en Render → **Environment** → agregá estas 3 variables:
```
GPT4FREE_ENABLED_PRO=true
GPT4FREE_URL=https://verboai-glm-bridge.onrender.com
GPT4FREE_MODEL=gpt-4o-mini
```

Reiniciá VerboAI y probá:
```powershell
$body = @{ mensaje = "Hola, ¿quién eres?" } | ConvertTo-Json
Invoke-RestMethod -Uri "https://verboai.duckdns.org/api/v1/pro-hybrid" -Method Post -Headers $headers -Body $body
```
Deberías ver `capaGlm: True` y `modeloReal: gpt-4o-mini` ✅

## 3 capas anti-identity-override
1. **Forzar `provider=Modelscope`** (no inyecta su propia identidad)
2. **Inyectar identidad en el primer mensaje del usuario** (no solo en system)
3. **Post-procesamiento regex agresivo** — 30+ patrones que reemplazan menciones a ChatGPT, OpenAI, Qwen, Alibaba, SurfSense, Claude, Gemini, Llama por "NewserPro / Verbo AI / VerboAITeams"

## Notas
- **100% gratis, sin token, sin registro** — usa g4f con Modelscope.
- Render Free Tier duerme el servicio después de 15 min sin actividad. La primera petición después de dormir tarda ~30s extra.
- Si gpt-4o-mini falla, prueba automáticamente gpt-4o, Qwen3-235B, Qwen3-25B en orden.
- Para ver qué modelo respondió: el campo `model` en la respuesta JSON siempre muestra el modelo real que se usó.
