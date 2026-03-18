from flask import request, redirect, Flask, Response, render_template, jsonify, url_for, flash, session
import threading
import numpy as np
import pygame
import requests
import re
from datetime import datetime, timedelta, date
import mysql.connector
from mysql.connector import Error
import random
import socket
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import json
import os

"""

Instrucciones:
    a) Inserta a la base de datos los siguientes valores en la tabla y schema llamada 6MM4:

        Boleta:
            2024160385
            Tu boleta
            2024160324
            2024160095
            2024160001
            Nota: Como recomendacion pongan la boleta de tipo Varchar o en otras palabras como texto y no como numero :)
        Nombres:
            Andre
            (Tu nombre)
            Ebani
            Felipe
            Pedro

        Inscritos:
            Usa un ciclo para que sea 1 inscrito y 1 no y asi.
            Nota: Los valores de inscrito deben ser tipo INT 1 y 0
        
    b) Ahora mandaras mediante el html el numero de boleta, asi que tu ruta debera de recibir el numero de boleta y buscarla en la base de datos para
        extraer todos los datos que insertaste y mandarlos de vuelta al html para mostrar todo :D

    Pueden ver los codigos y htmls que hay en la carpeta sin problema pero aviso que si piensan que esto es complejo lo de los archivos de aca estan mas kbrones
    pero ps se pueden dar ideas para ver que hacer si es q le entienden

    c) Una vez acabado avisar a alguno de los que estan supervisando el examen (de preferencia avisenme a mi (soy andre) ya que yo soy el q mas le sabe xd)
        Y una vez que les den el visto bueno en la terminal agregar sus examen al git y subirlos al log de git.  Osea un git add . y un git commit m"" 
        y ponen de comentario lo siguiente: Examen Ingreso LIA (su nombre)

"""

# Que grupo?
grupo_seleccionado = ""



#==============Esto no le muevan si no le saben xd (Es la configuracion default no toquen nada o ya no va a jalar)======>
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = 'clave_secreta_segura'

contra_db = "P3l0n100j0t3$"



conexion = mysql.connector.connect(
                    host="localhost",
                    user="root",
                    password= contra_db,
                    database=grupo_seleccionado
                )

cursor = conexion.cursor()
#==========================================================================================================>

# Aqui es para la parte a)

cursor.execute() #Aqui poner tu query
conexion.commit() # Este dejenlo ahi no lo toquen solo procuren que este despues de su query


# ========================>

@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Aqui haran la parte b)
    """
    if request.method == 'POST':
        boleta = request.form["boleta"]
        print(boleta)


    return render_template('examen.html')

"""Recuerda que en el return debes de poner igual los datos que vas a enviar al html ejemplo:

    return render_template('reset.html', confirmacion=1, segunda_confirmacion=1, borrado_exitoso=True)

"""



# Esto tampoco le muevan
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
