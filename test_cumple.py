import os
import sys
from app import procesar_entrada_dual, datos_accesos

# URL for 2024160385
url = "https://www.saes.cecyt16.ipn.mx/valqr/ValidaHorario.aspx?Bl=auVpq6cnuPVH1ghS5iXpC%2fI1L92fzgk5zoQY5caI1k0%3d"

# Process it
print("Calling procesar_entrada_dual...")
procesar_entrada_dual(url, True)

# Check state
print(datos_accesos["izquierda"])
