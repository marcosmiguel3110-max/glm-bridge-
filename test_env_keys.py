#!/usr/bin/env python3
"""
Script de prueba para cargar keys desde variables de entorno
"""

import os
import json

# Configurar variables de entorno para prueba
os.environ['G4F_KEYS_JSON1'] = '{"key":"g4f_u_mrtf2a_ffc2388b79b164701958ffcdf8b50b65044cfd4183dcdb79_a1e6c221","cuenta":"marcosmiguel3110-max","fecha_expiracion":"2026-11-01","estado":"activa"}'
os.environ['G4F_KEYS_JSON2'] = '{"key":"g4f_u_msdvcb_27795f75f5f0435162a99064c3d988c6b27cbeb5a4be3b76_4e4e7132","cuenta":"xddxx9664-crypto","fecha_expiracion":"2026-11-01","estado":"activa"}'
os.environ['G4F_KEYS_JSON3'] = '{"key":"g4f_u_msdvfr_4915d588987a7c724ce70a9760148150b0cfd13f0bd6c6e2_1fe53ed4","cuenta":"ccat84222-afk","fecha_expiracion":"2026-11-01","estado":"activa"}'

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
