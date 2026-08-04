#!/usr/bin/env python3
"""
Gestor de Keys de G4F
Sistema para rotar múltiples keys de G4F y detectar expiración
CON ENCRIPTACIÓN SIMPLE PARA PROTEGER LAS KEYS EN DISCO
CON ALERTAS POR EMAIL
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import base64
import hashlib

# Archivo de configuración de keys (encriptado)
KEYS_FILE = os.path.join(os.path.dirname(__file__), 'g4f_keys.enc')
KEYS_FILE_JSON = os.path.join(os.path.dirname(__file__), 'g4f_keys.json')  # Versión sin encriptar (para migración)

# URL de G4F para verificar key
G4F_API_URL = "https://g4f.space/v1/chat/completions"

# Configuración de alertas por email (Brevo API REST - mismo servicio que códigos)
ALERT_EMAIL = os.getenv('G4F_ALERT_EMAIL', 'marcos.miguel.3110@gmail.com')
BREVO_API_KEY = os.getenv('BREVO_API_KEY', '')
BREVO_SENDER_EMAIL = os.getenv('BREVO_SENDER_EMAIL', 'xddxx9664@11672850.brevosend.com')
BREVO_SENDER_NAME = os.getenv('BREVO_SENDER_NAME', 'VerboAI G4F Key Manager')

class G4FKeyManager:
    def __init__(self):
        self.encryption_key = self._get_or_create_encryption_key()
        self.keys = self.cargar_keys()
    
    def _get_or_create_encryption_key(self) -> str:
        """Obtener o crear clave de encriptación basada en el sistema"""
        # Usar una combinación de MACHINE_GUID y usuario del sistema
        # Esto hace que la clave sea única para cada máquina
        try:
            import uuid
            machine_id = str(uuid.getnode())
            username = os.getenv('USERNAME', os.getenv('USER', 'default'))
            salt = 'g4f-key-manager-salt-2024'
            
            # Crear clave de encriptación XOR
            key_material = f"{machine_id}-{username}-{salt}"
            key_hash = hashlib.sha256(key_material.encode()).hexdigest()
            return key_hash
        except Exception as e:
            # Fallback: usar clave de entorno
            env_key = os.getenv('G4F_ENCRYPTION_KEY')
            if env_key:
                return env_key
            # Clave de fallback (no recomendado para producción)
            return 'default-fallback-key-please-set-G4F_ENCRYPTION_KEY'
    
    def _encriptar_datos(self, datos: str) -> str:
        """Encriptar datos usando XOR + base64"""
        key = self.encryption_key
        encriptado = []
        for i, char in enumerate(datos):
            key_char = key[i % len(key)]
            encriptado.append(chr(ord(char) ^ ord(key_char)))
        encriptado_str = ''.join(encriptado)
        return base64.b64encode(encriptado_str.encode()).decode()
    
    def _desencriptar_datos(self, datos_encriptados: str) -> str:
        """Desencriptar datos usando XOR + base64"""
        key = self.encryption_key
        datos = base64.b64decode(datos_encriptados).decode()
        desencriptado = []
        for i, char in enumerate(datos):
            key_char = key[i % len(key)]
            desencriptado.append(chr(ord(char) ^ ord(key_char)))
        return ''.join(desencriptado)
    
    def _cargar_keys_desde_env(self) -> List[Dict]:
        """Cargar keys desde variables de entorno G4F_KEYS_JSON1, G4F_KEYS_JSON2, etc."""
        keys = []
        
        # Buscar variables de entorno G4F_KEYS_JSON1, G4F_KEYS_JSON2, etc.
        for i in range(1, 10):  # Soportar hasta 10 keys
            env_key = f'G4F_KEYS_JSON{i}'
            env_value = os.getenv(env_key)
            
            if env_value:
                try:
                    key_data = json.loads(env_value)
                    if isinstance(key_data, dict):
                        keys.append(key_data)
                except json.JSONDecodeError:
                    print(f"[Error] Formato inválido en {env_key}")
        
        return keys if keys else None
    
    def cargar_keys(self) -> List[Dict]:
        """Cargar keys desde archivo encriptado o variables de entorno"""
        # Primero intentar cargar desde variables de entorno
        keys_from_env = self._cargar_keys_desde_env()
        if keys_from_env:
            return keys_from_env
        
        # Si no hay variables de entorno, intentar desde archivo encriptado
        if not os.path.exists(KEYS_FILE) and os.path.exists(KEYS_FILE_JSON):
            self._migrar_a_encriptado()
        
        if not os.path.exists(KEYS_FILE):
            # Crear archivo vacío
            self.guardar_keys([])
            return []
        
        try:
            with open(KEYS_FILE, 'r', encoding='utf-8') as f:
                contenido = f.read()
            
            if not contenido:
                return []
            
            datos = self._desencriptar_datos(contenido)
            return json.loads(datos)
        except Exception as e:
            print(f"[Error] Cargando keys: {e}")
            return []
    
    def guardar_keys(self, keys=None):
        """Guardar keys en archivo encriptado"""
        if keys is None:
            keys = self.keys
        datos_json = json.dumps(keys, indent=2)
        datos_encriptados = self._encriptar_datos(datos_json)
        with open(KEYS_FILE, 'w') as f:
            f.write(datos_encriptados)
    
    def agregar_key(self, key: str, cuenta: str = "manual", fecha_expiracion: str = None):
        """Agregar una nueva key"""
        key_info = {
            "key": key,
            "cuenta": cuenta,
            "fecha_agregada": datetime.now().isoformat(),
            "ultima_verificacion": None,
            "estado": "activa",
            "tokens_usados": 0,
            "tokens_restantes": 5000000,  # 5 millones por defecto
            "fecha_expiracion": fecha_expiracion
        }
        self.keys.append(key_info)
        self.guardar_keys()
        print(f"✓ Key agregada: {key[:20]}... ({cuenta})")
        if fecha_expiracion:
            print(f"  Expira: {fecha_expiracion}")
    
    def obtener_key_activa(self) -> Optional[str]:
        """Obtener una key activa (rotación round-robin)"""
        keys_activas = [k for k in self.keys if k["estado"] == "activa"]
        if not keys_activas:
            return None
        
        # Rotación simple: usar la primera disponible
        return keys_activas[0]["key"]
    
    def verificar_key(self, key: str) -> bool:
        """Verificar si una key es válida haciendo una petición de prueba"""
        try:
            response = requests.post(
                G4F_API_URL,
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 1
                },
                timeout=10
            )
            
            # Actualizar información de la key
            for k in self.keys:
                if k["key"] == key:
                    k["ultima_verificacion"] = datetime.now().isoformat()
                    if response.status_code == 401:
                        k["estado"] = "expirada"
                        print(f"✗ Key expirada: {key[:20]}...")
                    elif response.status_code == 429:
                        k["estado"] = "sin_tokens"
                        print(f"✗ Key sin tokens: {key[:20]}...")
                    else:
                        k["estado"] = "activa"
                    self.guardar_keys()
                    break
            
            return response.status_code == 200
        except Exception as e:
            print(f"Error verificando key: {e}")
            return False
    
    def verificar_todas_keys(self):
        """Verificar todas las keys"""
        print(f"\nVerificando {len(self.keys)} keys...")
        for k in self.keys:
            self.verificar_key(k["key"])
    
    def marcar_key_expirada(self, key: str):
        """Marcar una key como expirada"""
        for k in self.keys:
            if k["key"] == key:
                k["estado"] = "expirada"
                k["fecha_expiracion"] = datetime.now().isoformat()
                self.guardar_keys()
                print(f"✗ Key marcada como expirada: {key[:20]}...")
                break
    
    def obtener_estadisticas(self) -> Dict:
        """Obtener estadísticas de las keys"""
        total = len(self.keys)
        activas = len([k for k in self.keys if k["estado"] == "activa"])
        expiradas = len([k for k in self.keys if k["estado"] == "expirada"])
        sin_tokens = len([k for k in self.keys if k["estado"] == "sin_tokens"])
        
        return {
            "total": total,
            "activas": activas,
            "expiradas": expiradas,
            "sin_tokens": sin_tokens
        }
    
    def verificar_expiracion_proxima(self, dias_alerta: int = 7) -> List[Dict]:
        """Verificar keys que expiran pronto"""
        hoy = datetime.now()
        keys_por_expirar = []
        
        for k in self.keys:
            if k["fecha_expiracion"] and k["estado"] == "activa":
                fecha_exp = datetime.fromisoformat(k["fecha_expiracion"])
                dias_restantes = (fecha_exp - hoy).days
                
                if dias_restantes <= dias_alerta:
                    keys_por_expirar.append({
                        "key": k["key"][:20] + "...",
                        "cuenta": k["cuenta"],
                        "fecha_expiracion": k["fecha_expiracion"],
                        "dias_restantes": dias_restantes
                    })
        
        return keys_por_expirar
    
    def enviar_alerta_email(self, keys_por_expirar: List[Dict]):
        """Enviar alerta por email sobre keys por expirar usando API REST de Brevo"""
        if not BREVO_API_KEY:
            print("[Alertas] No hay configuración de API de Brevo, no se enviará email")
            return False
        
        if not keys_por_expirar:
            return False
        
        try:
            # Construir cuerpo del email HTML
            body = f"""
            <html>
            <body>
                <h2>⚠️ ALERTA: Keys de G4F por expirar</h2>
                <p>Las siguientes keys de G4F están por expirar:</p>
                <ul>
            """
            
            for k in keys_por_expirar:
                body += f"""
                    <li>
                        <strong>Cuenta:</strong> {k['cuenta']}<br>
                        <strong>Key:</strong> {k['key']}<br>
                        <strong>Expira:</strong> {k['fecha_expiracion']}<br>
                        <strong>Días restantes:</strong> {k['dias_restantes']}
                    </li>
                """
            
            body += """
                </ul>
                <p><strong>Acción requerida:</strong></p>
                <ol>
                    <li>Ve a https://g4f.dev/members</li>
                    <li>Registra nuevas cuentas de GitHub</li>
                    <li>Copia las nuevas API keys</li>
                    <li>Ejecuta: python g4f_key_manager.py</li>
                    <li>Selecciona "Agregar nueva key" para cada nueva cuenta</li>
                </ol>
                <p><em>Este mensaje fue enviado automáticamente por el Gestor de Keys de G4F</em></p>
            </body>
            </html>
            """
            
            # Enviar email usando API REST de Brevo
            url = "https://api.brevo.com/v3/smtp/email"
            headers = {
                "accept": "application/json",
                "api-key": BREVO_API_KEY,
                "content-type": "application/json"
            }
            
            payload = {
                "sender": {
                    "name": BREVO_SENDER_NAME,
                    "email": BREVO_SENDER_EMAIL
                },
                "to": [
                    {
                        "email": ALERT_EMAIL,
                        "name": "Marco Miguel"
                    }
                ],
                "subject": f"⚠️ ALERTA: Keys de G4F por expirar ({len(keys_por_expirar)} keys)",
                "htmlContent": body
            }
            
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 201 or response.status_code == 200:
                print(f"[Alertas] Email enviado a {ALERT_EMAIL}")
                return True
            else:
                print(f"[Alertas] Error enviando email: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"[Alertas] Error enviando email: {e}")
            return False
    
    def verificar_keys_expiradas_por_fecha(self):
        """Marcar keys como expiradas si la fecha ya pasó"""
        hoy = datetime.now()
        keys_actualizadas = False
        
        for k in self.keys:
            if k["fecha_expiracion"] and k["estado"] == "activa":
                fecha_exp = datetime.fromisoformat(k["fecha_expiracion"])
                if fecha_exp < hoy:
                    k["estado"] = "expirada"
                    k["fecha_expiracion_real"] = k["fecha_expiracion"]
                    print(f"✗ Key expirada por fecha: {k['key'][:20]}... ({k['cuenta']})")
                    keys_actualizadas = True
        
        if keys_actualizadas:
            self.guardar_keys()
    
    def limpiar_keys_expiradas(self):
        """Eliminar keys expiradas del archivo"""
        self.keys = [k for k in self.keys if k["estado"] != "expirada"]
        self.guardar_keys()
        print(f"✓ Keys expiradas eliminadas")

def main():
    manager = G4FKeyManager()
    
    # Verificar keys expiradas por fecha al iniciar
    manager.verificar_keys_expiradas_por_fecha()
    
    # Verificar keys por expirar y enviar alerta por email
    keys_por_expirar = manager.verificar_expiracion_proxima(dias_alerta=30)
    if keys_por_expirar:
        print("\n" + "="*60)
        print("⚠️  ALERTA: Keys por expirar pronto")
        print("="*60)
        for k in keys_por_expirar:
            print(f"  - {k['key']} ({k['cuenta']})")
            print(f"    Expira: {k['fecha_expiracion']} ({k['dias_restantes']} días)")
        print("="*60)
        
        # Enviar alerta por email automáticamente
        print("\nEnviando alerta por email...")
        manager.enviar_alerta_email(keys_por_expirar)
    
    print("\n" + "="*60)
    print("Gestor de Keys de G4F")
    print("="*60)
    
    while True:
        print("\nOpciones:")
        print("1. Agregar nueva key")
        print("2. Ver keys activas")
        print("3. Verificar todas las keys")
        print("4. Ver estadísticas")
        print("5. Ver keys por expirar")
        print("6. Enviar alerta por email")
        print("7. Limpiar keys expiradas")
        print("8. Instrucciones para registrar nueva cuenta")
        print("9. Configurar SMTP para alertas")
        print("10. Salir")
        
        opcion = input("\nSelecciona una opción (1-10): ")
        
        if opcion == "1":
            key = input("Ingresa la key de G4F: ").strip()
            cuenta = input("Nombre de la cuenta (ej: github-1): ").strip() or "manual"
            fecha_exp = input("Fecha de expiración (YYYY-MM-DD, opcional): ").strip()
            if key:
                manager.agregar_key(key, cuenta, fecha_exp if fecha_exp else None)
        
        elif opcion == "2":
            activas = [k for k in manager.keys if k["estado"] == "activa"]
            print(f"\nKeys activas ({len(activas)}):")
            for k in activas:
                print(f"  - {k['key'][:20]}... ({k['cuenta']})")
                if k.get("fecha_expiracion"):
                    print(f"    Expira: {k['fecha_expiracion']}")
        
        elif opcion == "3":
            manager.verificar_todas_keys()
        
        elif opcion == "4":
            stats = manager.obtener_estadisticas()
            print(f"\nEstadísticas:")
            print(f"  Total: {stats['total']}")
            print(f"  Activas: {stats['activas']}")
            print(f"  Expiradas: {stats['expiradas']}")
            print(f"  Sin tokens: {stats['sin_tokens']}")
        
        elif opcion == "5":
            keys_por_expirar = manager.verificar_expiracion_proxima(dias_alerta=30)
            if keys_por_expirar:
                print(f"\nKeys por expirar en los próximos 30 días ({len(keys_por_expirar)}):")
                for k in keys_por_expirar:
                    print(f"  - {k['key']} ({k['cuenta']})")
                    print(f"    Expira: {k['fecha_expiracion']} ({k['dias_restantes']} días)")
            else:
                print("\n✓ No hay keys por expirar en los próximos 30 días")
        
        elif opcion == "6":
            keys_por_expirar = manager.verificar_expiracion_proxima(dias_alerta=30)
            if keys_por_expirar:
                print("\nEnviando alerta por email...")
                manager.enviar_alerta_email(keys_por_expirar)
            else:
                print("\nNo hay keys por expirar para enviar alerta")
        
        elif opcion == "7":
            manager.limpiar_keys_expiradas()
        
        elif opcion == "8":
            print("\n" + "="*60)
            print("Instrucciones para registrar nueva cuenta de G4F")
            print("="*60)
            print("1. Ve a: https://g4f.dev/members")
            print("2. Haz clic en 'Sign in with GitHub'")
            print("3. Inicia sesión con una cuenta de GitHub diferente")
            print("4. Copia la API key que aparece en el dashboard")
            print("5. Vuelve a este script y selecciona 'Agregar nueva key'")
            print("6. Pega la key y el nombre de la cuenta")
            print("7. Ingresa la fecha de expiración si la conoces")
            print("\nNota: Cada cuenta de GitHub te da 5 millones de tokens")
            print("="*60)
        
        elif opcion == "9":
            print("\n" + "="*60)
            print("Configurar SMTP para alertas por email")
            print("="*60)
            print("\nConfiguración actual:")
            print(f"  Email de alertas: {ALERT_EMAIL}")
            print(f"  Servidor SMTP: {SMTP_SERVER}")
            print(f"  Puerto SMTP: {SMTP_PORT}")
            print(f"  Usuario SMTP: {SMTP_USER if SMTP_USER else 'No configurado'}")
            print(f"  Password SMTP: {'Configurado' if SMTP_PASSWORD else 'No configurado'}")
            print("\nPara configurar SMTP, establece estas variables de entorno:")
            print("  SMTP_USER=tu_email@gmail.com")
            print("  SMTP_PASSWORD=tu_app_password")
            print("\nPara Gmail, necesitas usar una App Password:")
            print("  1. Ve a https://myaccount.google.com/apppasswords")
            print("  2. Crea una nueva App Password")
            print("  3. Usa esa contraseña como SMTP_PASSWORD")
            print("="*60)
        
        elif opcion == "10":
            print("Saliendo...")
            break
        
        else:
            print("Opción inválida")

if __name__ == "__main__":
    main()
