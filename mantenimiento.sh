#!/bin/bash
echo "====================================="
echo "Iniciando mantenimiento nocturno: $(date)"

# 1. Apagar el sistema principal
echo "Deteniendo app.py..."
systemctl stop app_torniquete.service

# 2. Ejecutar sacar_entradas.py para guardar los registros
echo "Ejecutando sacar_entradas.py..."
/usr/bin/python3 /home/lab-ia/Torniquete/sacar_entradas.py

# 3. Ejecutar la limpieza/reinicio de base de datos
echo "Ejecutando server.py..."
/usr/bin/python3 /home/lab-ia/Torniquete/server.py

# 4. Volver a prender el sistema principal
echo "Iniciando app.py..."
systemctl start app_torniquete.service

echo "Mantenimiento completado con éxito."
echo "====================================="

