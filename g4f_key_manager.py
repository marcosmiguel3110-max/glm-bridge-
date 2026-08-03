#!/usr/bin/env python3
"""
Gestor de Keys de G4F
Sistema para rotar múltiples keys de G4F y detectar expiración
CON ENCRIPTACIÓN SIMPLE PARA PROTEGER LAS KEYS EN DISCO
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
    
    def cargar_keys(self) -> List[Dict]:
        """Cargar keys desde archivo encriptado"""
        # Primero intentar migrar del archivo JSON sin encriptar
        if os.path.exists(KEYS_FILE_JSON) and not os.path.exists(KEYS_FILE):
            print("[Migración] Detectado archivo JSON sin encriptar, migrando a formato encriptado...")
            try:
                with open(KEYS_FILE_JSON, 'r') as f:
                    keys = json.load(f)
                self.guardar_keys(keys)
                os.remove(KEYS_FILE_JSON)
                print("[Migración] Migración completada, archivo JSON eliminado")
                return keys
            except Exception as e:
                print(f"[Migración] Error migrando archivo: {e}")
        
        # Cargar desde archivo encriptado
        if os.path.exists(KEYS_FILE):
            try:
                with open(KEYS_FILE, 'r') as f:
                    datos_encriptados = f.read()
                datos_json = self._desencriptar_datos(datos_encriptados)
                return json.loads(datos_json)
            except Exception as e:
                print(f"[Error] No se pudo desencriptar el archivo de keys: {e}")
                print("[Error] El archivo puede estar corrupto o la clave de encriptación cambió")
                return []
        
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
    
    # Mostrar alerta de keys por expirar
    keys_por_expirar = manager.verificar_expiracion_proxima(dias_alerta=30)
    if keys_por_expirar:
        print("\n" + "="*60)
        print("⚠️  ALERTA: Keys por expirar pronto")
        print("="*60)
        for k in keys_por_expirar:
            print(f"  - {k['key']} ({k['cuenta']})")
            print(f"    Expira: {k['fecha_expiracion']} ({k['dias_restantes']} días)")
        print("="*60)
    
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
        print("6. Limpiar keys expiradas")
        print("7. Instrucciones para registrar nueva cuenta")
        print("8. Salir")
        
        opcion = input("\nSelecciona una opción (1-8): ")
        
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
            manager.limpiar_keys_expiradas()
        
        elif opcion == "7":
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
        
        elif opcion == "8":
            print("Saliendo...")
            break
        
        else:
            print("Opción inválida")

if __name__ == "__main__":
    main()
