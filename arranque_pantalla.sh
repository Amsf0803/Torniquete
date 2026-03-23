#!/bin/bash

# 1. Esperamos a que el servidor Flask (app.py) esté vivo
while ! wget --spider -q http://localhost:5000; do 
    sleep 2
done

# 2. En cuanto contesta, abrimos Firefox en modo kiosco en el fondo
firefox --kiosk http://localhost:5000 & 

# 3. Esperamos 5 segunditos a que cargue la interfaz y damos el click
sleep 5
xdotool mousemove 500 500 click 1
