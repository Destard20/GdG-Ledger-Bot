#!/usr/bin/env bash
# ==============================================================================
# Script di avvio Cloudflare Tunnel per il Ledger Bot
# Espone la porta locale del Webhook (default 8000) su un URL HTTPS pubblico sicuro
# ==============================================================================

set -e

PORT="${WEBHOOK_PORT:-8000}"
CLOUDFLARED_BIN="cloudflared"

echo "=========================================================="
echo "🚀 Avvio Cloudflare Tunnel per GdG-Ledger-Bot"
echo "=========================================================="

# Verifica se cloudflared è installato nel PATH o localmente
if ! command -v "$CLOUDFLARED_BIN" &> /dev/null; then
    if [ -f "./cloudflared" ]; then
        CLOUDFLARED_BIN="./cloudflared"
    else
        echo "⚠️  cloudflared non trovato nel sistema."
        echo "📥 Download dell'eseguibile standalone per Linux in corso..."
        
        ARCH=$(uname -m)
        case "$ARCH" in
            x86_64)
                DOWNLOAD_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
                ;;
            aarch64|arm64)
                DOWNLOAD_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64"
                ;;
            armv7l)
                DOWNLOAD_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm"
                ;;
            *)
                echo "❌ Architettura non supportata per il download automatico: $ARCH"
                echo "Installa cloudflared manualmente: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/create-local-tunnel/"
                exit 1
                ;;
        esac

        curl -L -s "$DOWNLOAD_URL" -o ./cloudflared
        chmod +x ./cloudflared
        CLOUDFLARED_BIN="./cloudflared"
        echo "✅ cloudflared scaricato con successo nella directory del progetto."
    fi
fi

echo "🌐 Avvio del tunnel su http://localhost:$PORT..."
echo "📋 Cerca nella console l'URL pubblico assegnato da Cloudflare (.trycloudflare.com)"
echo "   Quell'URL + '/webhook/satispay' sarà il tuo endpoint Webhook per Satispay!"
echo "----------------------------------------------------------"

# Avvia il tunnel verso il server locale
"$CLOUDFLARED_BIN" tunnel --url "http://localhost:$PORT"
