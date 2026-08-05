#!/usr/bin/env python3
"""
Script de prueba para cargar keys desde variables de entorno
"""

import os

# Configurar variables de entorno para prueba (formato: key|cuenta|fecha_expiracion)
os.environ['G4F_KEY1'] = 'g4f_test_key_placeholder_1|test-account-1|2026-11-01'
os.environ['G4F_KEY2'] = 'g4f_test_key_placeholder_2|test-account-2|2026-11-01'
os.environ['G4F_KEY3'] = 'g4f_test_key_placeholder_3|test-account-3|2026-11-01'

from g4f_key_manager import G4FKeyManager

def main():
    manager = G4FKeyManager()
    
    print("="*60)
    print("Prueba de carga de keys desde variables de entorno")
    print("="*60)
    
    print(f"\nTotal de keys cargadas: {len(manager.keys)}")
    
    for i, k in enumerate(manager.keys, 1):
        print(f"\nKey {i}:")
        print(f"  Key: {k['key'][:20]}...")
        print(f"  Cuenta: {k['cuenta']}")
        print(f"  Estado: {k['estado']}")
        print(f"  Expira: {k['fecha_expiracion']}")
    
    print(f"\n✓ Keys cargadas exitosamente desde variables de entorno")

if __name__ == "__main__":
    main()
