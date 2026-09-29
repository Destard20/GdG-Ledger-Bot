#!/usr/bin/env python3
"""
Script interattivo di configurazione Satispay Business API.
1. Genera una coppia di chiavi crittografiche RSA (chiave privata salvata in satispay_private.pem).
2. Invia la chiave pubblica e il codice di attivazione alle API Satispay.
3. Riceve il KeyID univoco e aggiorna automaticamente il file .env.
"""

import argparse
import json
import os
import sys
from pathlib import Path
import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_rsa_keypair(key_size: int = 4096):
    print(f"🔑 Generazione coppia di chiavi RSA ({key_size} bit)...")
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode("utf-8")

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")

    return private_pem, public_pem


def update_env_file(key_id: str, is_staging: bool, pem_path: str = "satispay_private.pem"):
    env_path = Path(".env")
    if not env_path.exists():
        # Copia da .env.example se presente
        if Path(".env.example").exists():
            with open(".env.example", "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = ""
    else:
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()

    lines = content.splitlines()
    updated_lines = []
    found_key = False
    found_staging = False
    found_pem = False

    for line in lines:
        if line.startswith("SATISPAY_KEY_ID="):
            updated_lines.append(f'SATISPAY_KEY_ID="{key_id}"')
            found_key = True
        elif line.startswith("SATISPAY_STAGING="):
            updated_lines.append(f'SATISPAY_STAGING={"true" if is_staging else "false"}')
            found_staging = True
        elif line.startswith("SATISPAY_PRIVATE_KEY_FILE="):
            updated_lines.append(f'SATISPAY_PRIVATE_KEY_FILE="{pem_path}"')
            found_pem = True
        else:
            updated_lines.append(line)

    if not found_key:
        updated_lines.append(f'SATISPAY_KEY_ID="{key_id}"')
    if not found_staging:
        updated_lines.append(f'SATISPAY_STAGING={"true" if is_staging else "false"}')
    if not found_pem:
        updated_lines.append(f'SATISPAY_PRIVATE_KEY_FILE="{pem_path}"')

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(updated_lines) + "\n")

    print("📝 File .env aggiornato con successo.")


def main():
    parser = argparse.ArgumentParser(description="Configurazione Satispay Business API")
    parser.add_argument("--token", help="Codice di attivazione fornito dal pannello Satispay Business (6 caratteri)")
    parser.add_argument("--staging", action="store_true", help="Usa l'ambiente di Staging / Sandbox invece della produzione")
    parser.add_argument("--out", default="satispay_private.pem", help="Percorso del file in cui salvare la chiave privata RSA")
    args = parser.parse_args()

    token = args.token
    if not token:
        print("\n=== Configurazione Satispay Business API ===")
        print("Accedi al pannello Satispay Business -> Sviluppatori -> Aggiungi Token.")
        token = input("Inserisci il codice di attivazione Satispay: ").strip()

    if not token:
        print("❌ Errore: Token obbligatorio.")
        sys.exit(1)

    # 1. Genera chiavi
    private_pem, public_pem = generate_rsa_keypair(key_size=4096)

    # Salva chiave privata
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(private_pem)
    # Imposta permessi restrittivi (lettura/scrittura solo utente)
    try:
        os.chmod(args.out, 0o600)
    except Exception:
        pass
    print(f"🔒 Chiave privata salvata in: {args.out} (permessi 600)")

    # 2. Richiesta scambio chiave
    base_url = "https://staging.authservices.satispay.com" if args.staging else "https://authservices.satispay.com"
    endpoint = f"{base_url}/g_business/v1/authentication_keys"

    payload = {
        "public_key": public_pem,
        "token": token
    }

    print(f"🌐 Invio richiesta scambio chiave verso {endpoint}...")
    try:
        response = httpx.post(endpoint, json=payload, timeout=15.0)
        if response.status_code in (200, 201):
            data = response.json()
            key_id = data.get("key_id")
            print("\n🎉 Autenticazione Satispay completata con successo!")
            print(f"🔑 KeyID ottenuto: {key_id}")
            update_env_file(key_id, args.staging, args.out)
            print("\n✅ Configurazione Satispay pronta all'uso!")
        else:
            print(f"\n❌ Errore API Satispay ({response.status_code}): {response.text}")
            print("Verifica che il codice di attivazione sia valido e non sia già stato utilizzato o scaduto.")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Errore di connessione: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
