# Puente GPT4Free — gpt-4o-mini (SIN API KEY)

Puente Python/Flask que expone `POST /v1/chat/completions` (formato OpenAI) y llama a **gpt-4o-mini** gratis usando la librería `g4f` (https://github.com/xtekky/gpt4free). **No requiere token, no requiere registro, no requiere API key.**

## Modelo por defecto
- **Modelo**: `glm-5.2`, `qwen/qwen3.7-plus`, `deepseek-v4-pro` (rotación automática)
- **Provider**: Ollama (para glm-5.2) con fallback a auto
- **Identidad**: Fuertemente reforzada — el modelo SIEMPRE se presenta como "NewserPro de Verbo AI"
- **Fallbacks**: Si el modelo principal falla, prueba automáticamente otros modelos disponibles

## Rotación de IPs con Webshare (Opcional)

Para evitar límites de requests por IP (24h cooldown), puedes configurar **Webshare proxies**:

1. **Crear cuenta gratis en Webshare** (https://www.webshare.io):
   - 10 proxies gratis (1GB/mes)
   - Sin tarjeta de crédito

2. **Obtener credenciales del proxy**:
   - Proxy Host
   - Proxy Port
   - Username
   - Password

3. **Configurar en Render**:
   - Ve a tu servicio en Render → Environment
   - Agrega estas variables:
     ```
     WEBSHARE_ENABLED=true
     WEBSHARE_PROXY_HOST=your-proxy-host
     WEBSHARE_PROXY_PORT=your-proxy-port
     WEBSHARE_PROXY_USER=your-username
     WEBSHARE_PROXY_PASS=your-password
     ```

4. **Verificar que funciona**:
   ```bash
   curl https://tu-bridge.onrender.com/health
   ```
   Debería mostrar `"webshare_enabled": true` y `"webshare_proxies_count": 1`

**Beneficios:**
- Rotación automática de IPs en cada request
- Evita límites de 24h por IP
- 80M+ IPs disponibles (plan de pago)

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
