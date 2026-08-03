#!/usr/bin/env python3
"""
Gestor de Keys de G4F
Sistema para rotar múltiples keys de G4F y detectar expiración
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Archivo de configuración de keys
KEYS_FILE = os.path.join(os.path.dirname(__file__), 'g4f_keys.json')

# URL de G4F para verificar key
G4F_API_URL = "https://g4f.space/v1/chat/completions"

class G4FKeyManager:
    def __init__(self):
        self.keys = self.cargar_keys()
    
    def cargar_keys(self) -> List[Dict]:
        """Cargar keys desde archivo JSON"""
        if os.path.exists(KEYS_FILE):
            with open(KEYS_FILE, 'r') as f:
                return json.load(f)
        return []
    
    def guardar_keys(self):
        """Guardar keys en archivo JSON"""
        with open(KEYS_FILE, 'w') as f:
            json.dump(self.keys, f, indent=2)
    
    def agregar_key(self, key: str, cuenta: str = "manual"):
        """Agregar una nueva key"""
        key_info = {
            "key": key,
            "cuenta": cuenta,
            "fecha_agregada": datetime.now().isoformat(),
            "ultima_verificacion": None,
            "estado": "activa",
            "tokens_usados": 0,
            "tokens_restantes": 5000000  # 5 millones por defecto
        }
        self.keys.append(key_info)
        self.guardar_keys()
        print(f"✓ Key agregada: {key[:20]}... ({cuenta})")
    
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
    
    def limpiar_keys_expiradas(self):
        """Eliminar keys expiradas del archivo"""
        self.keys = [k for k in self.keys if k["estado"] != "expirada"]
        self.guardar_keys()
        print(f"✓ Keys expiradas eliminadas")

def main():
    manager = G4FKeyManager()
    
    print("="*60)
    print("Gestor de Keys de G4F")
    print("="*60)
    
    while True:
        print("\nOpciones:")
        print("1. Agregar nueva key")
        print("2. Ver keys activas")
        print("3. Verificar todas las keys")
        print("4. Ver estadísticas")
        print("5. Limpiar keys expiradas")
        print("6. Salir")
        
        opcion = input("\nSelecciona una opción (1-6): ")
        
        if opcion == "1":
            key = input("Ingresa la key de G4F: ").strip()
            cuenta = input("Nombre de la cuenta (ej: github-1): ").strip() or "manual"
            if key:
                manager.agregar_key(key, cuenta)
        
        elif opcion == "2":
            activas = [k for k in manager.keys if k["estado"] == "activa"]
            print(f"\nKeys activas ({len(activas)}):")
            for k in activas:
                print(f"  - {k['key'][:20]}... ({k['cuenta']})")
        
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
            manager.limpiar_keys_expiradas()
        
        elif opcion == "6":
            print("Saliendo...")
            break
        
        else:
            print("Opción inválida")

if __name__ == "__main__":
    main()
