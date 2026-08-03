#!/usr/bin/env python3
"""
Script de prueba para verificar las keys de G4F
"""

from g4f_key_manager import G4FKeyManager

def main():
    manager = G4FKeyManager()
    
    print("="*60)
    print("Verificación de Keys de G4F")
    print("="*60)
    
    # Verificar keys expiradas por fecha
    manager.verificar_keys_expiradas_por_fecha()
    
    # Mostrar todas las keys
    print(f"\nTotal de keys: {len(manager.keys)}")
    for k in manager.keys:
        estado_emoji = "✓" if k["estado"] == "activa" else "✗"
        print(f"{estado_emoji} {k['key'][:30]}... ({k['cuenta']})")
        print(f"   Estado: {k['estado']}")
        if k.get("fecha_expiracion"):
            print(f"   Expira: {k['fecha_expiracion']}")
        print()
    
    # Mostrar estadísticas
    stats = manager.obtener_estadisticas()
    print(f"\nEstadísticas:")
    print(f"  Total: {stats['total']}")
    print(f"  Activas: {stats['activas']}")
    print(f"  Expiradas: {stats['expiradas']}")
    print(f"  Sin tokens: {stats['sin_tokens']}")
    
    # Verificar keys por expirar
    keys_por_expirar = manager.verificar_expiracion_proxima(dias_alerta=90)
    if keys_por_expirar:
        print(f"\n⚠️  Keys por expirar en los próximos 90 días ({len(keys_por_expirar)}):")
        for k in keys_por_expirar:
            print(f"  - {k['key']} ({k['cuenta']})")
            print(f"    Expira: {k['fecha_expiracion']} ({k['dias_restantes']} días)")
    
    # Obtener key activa actual
    key_activa = manager.obtener_key_activa()
    if key_activa:
        print(f"\n✓ Key activa actual: {key_activa[:30]}...")
    else:
        print("\n✗ No hay keys activas")

if __name__ == "__main__":
    main()
