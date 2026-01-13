#!/bin/bash
# Ruta al proyecto
PROJECT_DIR="/Users/francisco/.gemini/antigravity/scratch/accounting_scheduler/backend"

echo "========================================="
echo "   📅  CALENDARIO IMPOSITIVO 📅"
echo "========================================="

cd "$PROJECT_DIR"

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Iniciar servidor en puerto 8002
echo "Iniciando servidor..."
python3 -m uvicorn main:app --port 8002 &
SERVER_PID=$!

# Esperar
sleep 4

# Abrir navegador
echo "Abriendo aplicación..."
open "http://localhost:8002"

echo ""
echo "✅ Sistema corriendo."
echo "Para cerrar, cierra esta ventana."

wait $SERVER_PID
