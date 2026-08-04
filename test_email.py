#!/usr/bin/env python3
"""
Script de prueba para enviar email de alerta de G4F
"""

from g4f_key_manager import G4FKeyManager

def main():
    manager = G4FKeyManager()
    
    print("="*60)
    print("Prueba de envío de email con Brevo API REST")
    print("="*60)
    
    # Verificar configuración API
    from g4f_key_manager import BREVO_API_KEY, BREVO_SENDER_EMAIL, BREVO_SENDER_NAME, ALERT_EMAIL
    print(f"\nConfiguración API:")
    print(f"  API Key: {BREVO_API_KEY[:20]}..." if BREVO_API_KEY else "  API Key: No configurada")
    print(f"  Sender Email: {BREVO_SENDER_EMAIL}")
    print(f"  Sender Name: {BREVO_SENDER_NAME}")
    print(f"  Email destino: {ALERT_EMAIL}")
    
    # Crear datos de prueba (keys por expirar)
    keys_por_expirar = [
        {
            "key": "g4f_test_key...",
            "cuenta": "test-account",
            "fecha_expiracion": "2026-11-01T00:00:00",
            "dias_restantes": 89
        }
    ]
    
    print(f"\nEnviando email de prueba...")
    resultado = manager.enviar_alerta_email(keys_por_expirar)
    
    if resultado:
        print("\n✓ Email enviado exitosamente a marcos.miguel.3110@gmail.com")
        print("  Revisa tu bandeja de entrada para verificar")
    else:
        print("\n✗ Error enviando email")
        print("  Verifica la configuración de API de Brevo")

if __name__ == "__main__":
    main()
