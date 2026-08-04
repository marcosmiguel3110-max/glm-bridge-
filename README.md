# Puente GPT4Free — kimi-k2.7-code (CON API KEY OPCIONAL)

Puente Python/Flask que expone `POST /v1/chat/completions` (formato OpenAI) y llama a **kimi-k2.7-code** y otros modelos gratis usando la librería `g4f` (https://github.com/xtekky/gpt4free). **Soporta modo sin API key y modo con keys de G4F encriptadas.**

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

## Seguridad y Gestión de Keys de G4F

### Sistema de Encriptación de Keys

El bridge incluye un sistema de gestión de keys de G4F con encriptación para proteger las credenciales en disco:

**Características de seguridad:**
- **Encriptación XOR + Base64**: Las keys se almacenan encriptadas en `g4f_keys.enc`
- **Clave única por máquina**: La clave de encriptación se genera basándose en el ID de la máquina y usuario del sistema
- **Rotación automática**: Cuando una key expira o se queda sin tokens, el bridge rota automáticamente a la siguiente
- **Detección de expiración**: Alerta cuando las keys están por expirar (30 días antes)
- **Archivo protegido**: `g4f_keys.enc` está en `.gitignore` para no subir al repositorio

### Configurar Keys de G4F

1. **Ejecutar el gestor de keys**:
   ```bash
   python g4f_key_manager.py
   ```

2. **Agregar una nueva key**:
   - Ve a https://g4f.dev/members
   - Inicia sesión con GitHub
   - Copia la API key
   - En el gestor, selecciona "Agregar nueva key"
   - Pega la key y el nombre de la cuenta
   - Ingresa la fecha de expiración si la conoces

3. **Verificar keys**:
   - Opción 2: Ver keys activas
   - Opción 3: Verificar todas las keys
   - Opción 4: Ver estadísticas
   - Opción 5: Ver keys por expirar

### Variables de Entorno (Opcional)

**Para configurar múltiples keys en Render:**

En Render → Environment, agrega estas variables (formato: `key|cuenta|fecha_expiracion`):

```bash
G4F_KEY1=g4f_u_mrtf2a_ffc2388b79b164701958ffcdf8b50b65044cfd4183dcdb79_a1e6c221|marcosmiguel3110-max|2026-11-01
G4F_KEY2=g4f_u_msdvcb_27795f75f5f0435162a99064c3d988c6b27cbeb5a4be3b76_4e4e7132|xddxx9664-crypto|2026-11-01
G4F_KEY3=g4f_u_msdvfr_4915d588987a7c724ce70a9760148150b0cfd13f0bd6c6e2_1fe53ed4|ccat84222-afk|2026-11-01
```

**Para configurar una sola key (alternativa):**

```bash
export G4F_API_KEY="tu-key-de-g4f-aqui"
```

**Para configurar la clave de encriptación (opcional):**

```bash
export G4F_ENCRYPTION_KEY="tu-clave-secreta-aqui"
```

### Seguridad Adicional

- **Nunca compartas** el archivo `g4f_keys.enc`
- **Nunca subas** `g4f_keys.enc` al repositorio (está en `.gitignore`)
- **Usa cuentas de GitHub separadas** para cada key (5M tokens por cuenta)
- **Configura alertas** 30 días antes de la expiración de las keys
- **Rotación periódica**: Registra nuevas cuentas antes de que expiren las actuales

### Alertas por Email (Opcional)

El sistema puede enviar alertas por email cuando las keys estén por expirar:

**Configurar SMTP:**
```bash
# Para Gmail (recomendado)
export SMTP_USER="marcos.miguel.3110@gmail.com"
export SMTP_PASSWORD="tu_app_password"

# El email de alertas se configura automáticamente a marcos.miguel.3110@gmail.com
```

**Obtener App Password de Gmail:**
1. Ve a https://myaccount.google.com/apppasswords
2. Activa la verificación en 2 pasos si no está activa
3. Crea una nueva App Password
4. Usa esa contraseña como `SMTP_PASSWORD`

**Funcionamiento:**
- Las alertas se envían automáticamente 30 días antes de la expiración
- Solo se envían a `marcos.miguel.3110@gmail.com`
- No aparecen en el chat del bridge (silencioso)
- Puedes enviar alertas manualmente con el gestor (opción 6)

**Sin configuración SMTP:**
- El sistema funciona normalmente sin SMTP
- Las alertas solo se muestran en consola al ejecutar el gestor
- El bridge no muestra alertas en el chat
