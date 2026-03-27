import sys
from datetime import date, datetime, timedelta
import mysql.connector
from mysql.connector import Error

contraDB = "P3l0n100j0t3$"

# --- 1. LÓGICA DE CONTROL DE REINICIOS (DÍA OBJETIVO) ---
try:
    conexion_reinicios = mysql.connector.connect(
        host="localhost",
        user="root",
        password=contraDB,
        database="Semestre"
    )
    cursor_reinicios = conexion_reinicios.cursor()

    now = datetime.now()
    
    # Si son las 23:00 o más, preparamos el sistema para mañana.
    # Si es antes (ej. reinicio por apagón a las 2am), preparamos el sistema para hoy.
    if now.hour >= 23:
        target_date = now + timedelta(days=1)
    else:
        target_date = now

    dias_semana = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']
    target_day_name = dias_semana[target_date.weekday()]

    cursor_reinicios.execute(f"SELECT {target_day_name} FROM reinicios LIMIT 1")
    resultado = cursor_reinicios.fetchone()

    if resultado is None:
        print("⚠️ Tabla 'reinicios' vacía. Inserta la fila inicial con ceros.")
        ya_reiniciado = 0
    else:
        ya_reiniciado = resultado[0]

    if ya_reiniciado == 1:
        print(f"✅ El sistema ya fue reiniciado previamente para el día: {target_day_name.upper()}.")
        print("Omitiendo ejecución de rutinas para no afectar accesos...")
        cursor_reinicios.close()
        conexion_reinicios.close()
        sys.exit(0) # 🛑 Detiene la ejecución del script aquí de forma limpia.

    print(f"⚙️ Iniciando rutinas de reinicio para preparar el día: {target_day_name.upper()}...")
    cursor_reinicios.close()
    conexion_reinicios.close()

except Exception as e:
    print(f"❌ Error al comprobar la tabla de reinicios: {e}")
    # Si falla la conexión a esta tabla, dejamos que el script continúe por seguridad.


# --- 2. CÓDIGO ORIGINAL (SUSPENSIONES, PASES, SEMESTRES, GRAFICAS) ---

#Aqui se revisan las suspensiones
try:
    conexion = mysql.connector.connect(
        host="localhost",
        user="root",
        password=contraDB,
        database="Suspensiones"
    )
    cursor = conexion.cursor()
    hoy = date.today()

    cursor.execute("SELECT boleta, grupo, nombre_alumno, fecha_inicio, fecha_fin FROM suspensiones_registro")
    suspensiones = cursor.fetchall()
    print(suspensiones)

    for boleta, grupo, nombre_alumno, fecha_inicio, fecha_fin in suspensiones:
        try:
            # Si hoy inicia la suspensión
            if fecha_inicio == hoy:
                try:
                    conexion_grupo = mysql.connector.connect(
                        host="localhost", user="root", password= contraDB, database=grupo
                    )
                    cursor_grupo = conexion_grupo.cursor()
                    cursor_grupo.execute(f"UPDATE `{grupo}` SET inscrito = 2 WHERE boleta = %s", (boleta,))
                    conexion_grupo.commit()
                    print(f"🟡 El Alumno {nombre_alumno} del grupo {grupo} con boleta: {boleta} esta suspendido desde hoy.")
                    cursor_grupo.close()
                    conexion_grupo.close()
                except Exception as e:
                    print(f"❌ Error al suspender {boleta} en {grupo}: {e}")

            # Si hoy termina la suspensión
            elif fecha_fin <= hoy:
                try:
                    conexion_grupo = mysql.connector.connect(
                        host="localhost", user="root", password= contraDB, database=grupo
                    )
                    cursor_grupo = conexion_grupo.cursor()
                    cursor_grupo.execute(f"UPDATE `{grupo}` SET inscrito = 1 WHERE boleta = %s", (boleta,))
                    conexion_grupo.commit()
                    print(f"🟢 Al Alumno {nombre_alumno} del grupo {grupo} con boleta: {boleta} se le ha sido removida su suspension.")
                    cursor_grupo.close()
                    conexion_grupo.close()

                    try:
                        conexion_susp = mysql.connector.connect(
                            host="localhost", user="root", password= contraDB, database="Suspensiones"
                        )
                        cursor_susp = conexion_susp.cursor()
                        cursor_susp.execute("DELETE FROM suspensiones_registro WHERE boleta = %s", (boleta,))
                        conexion_susp.commit()
                        print(f"{cursor_susp.rowcount} fila(s) eliminada(s).")
                    except mysql.connector.Error as e:
                        print("Error al eliminar la fila:", e)
                    finally:
                        if conexion_susp.is_connected():
                            cursor_susp.close()
                            conexion_susp.close()
                except Exception as e:
                    print(f"❌ Error al reactivar {boleta} en {grupo}: {e}")

            elif fecha_inicio > hoy:
                try:
                    conexion_grupo = mysql.connector.connect(
                        host="localhost", user="root", password= contraDB, database=grupo
                    )
                    cursor_grupo = conexion_grupo.cursor()
                    cursor_grupo.execute(f"UPDATE `{grupo}` SET inscrito = 1 WHERE boleta = %s", (boleta,))
                    conexion_grupo.commit()
                    print(f"🟢 Al Alumno {nombre_alumno} del grupo {grupo} con boleta: {boleta} se le ha sido removida su suspension por algun error externo.")
                    cursor_grupo.close()
                    conexion_grupo.close()
                except Exception as e:
                    print(f"❌ Error al reactivar {boleta} en {grupo}: {e}")
                
                try:
                    conexion_susp = mysql.connector.connect(
                        host="localhost", user="root", password= contraDB, database="Suspensiones"
                    )
                    cursor_susp = conexion_susp.cursor()
                    cursor_susp.execute("DELETE FROM suspensiones_registro WHERE boleta = %s", (boleta,))
                    conexion_susp.commit()
                    print(f"{cursor_susp.rowcount} fila(s) eliminada(s).")
                except mysql.connector.Error as e:
                    print("Error al eliminar la fila:", e)
                finally:
                    if conexion_susp.is_connected():
                        cursor_susp.close()
                        conexion_susp.close()
        except Exception as e:
            print(f"⚠️ Error al procesar boleta {boleta}: {e}")

    cursor.close()
    conexion.close()
except Exception as e:
    print(f"❌ Error general en suspensiones: {e}")

# Aqui se borra todo de la tabla de Pases de salida
try:
    conexion = mysql.connector.connect(
        host="localhost", user="root", password= contraDB, database="Pases_salida"
    )
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM modificaciones_temporales")
    conexion.commit()
    print(f"🗑️ {cursor.rowcount} fila(s) eliminada(s) de la base de datos de Pases de salida.")
except Exception as e:
    print(f"❌ Error al conectar a la base de datos de Pases de salida: {e}")

# Aqui se obtiene el semestre y los grupos
try:
    conexion = mysql.connector.connect(
        host="localhost", user="root", password= contraDB, database="Semestre"
    )
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("""
        SELECT semestre, grupo, 1_2_TM, 3_4_CM, 3_4_AM, 3_4_MM, 3_4_IM, 3_4_PM, 3_4_EM, 3_4_LM,
            5_6_CM, 5_6_AM, 5_6_MM, 5_6_IM, 5_6_PM, 5_6_EM, 5_6_LM
        FROM semestre LIMIT 1
    """)
    row = cursor.fetchone()

    if row:
        semestre = int(row['semestre'])
        grupo_seleccionado = row['grupo']
        print(f"✅ Grupo seleccionado: {grupo_seleccionado}")

        bloque_prefijo = {
            1: {'TM': '1TM', 'CM': '3CM', 'AM': '3AM', 'MM': '3MM', 'IM': '3IM', 'PM': '3PM', 'EM': '3EM', 'LM': '3LM',
                'CM_5': '5CM', 'AM_5': '5AM', 'MM_5': '5MM', 'IM_5': '5IM', 'PM_5': '5PM', 'EM_5': '5EM', 'LM_5': '5LM'},
            2: {'TM': '2TM', 'CM': '4CM', 'AM': '4AM', 'MM': '4MM', 'IM': '4IM', 'PM': '4PM', 'EM': '4EM', 'LM': '4LM',
                'CM_5': '6CM', 'AM_5': '6AM', 'MM_5': '6MM', 'IM_5': '6IM', 'PM_5': '6PM', 'EM_5': '6EM', 'LM_5': '6LM'}
        }
        prefijos = bloque_prefijo.get(semestre, bloque_prefijo[2])

        bases_datos = ["Pases_salida"]
        if row['1_2_TM']:
            bases_datos.extend([f"{prefijos['TM']}{i}" for i in range(1, row['1_2_TM'] + 1)])
        for tipo in ['CM', 'AM', 'MM', 'IM', 'PM', 'EM', 'LM']:
            count = row[f'3_4_{tipo}']
            if count:
                bases_datos.extend([f"{prefijos[tipo]}{i}" for i in range(1, count + 1)])
        for tipo in ['CM', 'AM', 'MM', 'IM', 'PM', 'EM', 'LM']:
            count = row[f'5_6_{tipo}']
            if count:
                bases_datos.extend([f"{prefijos[f'{tipo}_5']}{i}" for i in range(1, count + 1)])

        print(f"ℹ️ Grupos disponibles para semestre {semestre}: {bases_datos}")
    else:
        bases_datos = []

    cursor.close()
    conexion.close()
except Error as e:
    print(f"❌ Error al conectar a la base de datos 'Semestre': {e}")
    bases_datos = []

for base_datos in bases_datos:
    try:
        conexion = mysql.connector.connect(
            host="localhost", user="root", password= contraDB, database=f"{base_datos}"
        )
        cursor = conexion.cursor()
        cursor.execute(f"UPDATE `{base_datos}` SET abrio = 0, cerro = 0")
        conexion.commit()
        print(f"✅ Se han reiniciado los campos 'abrio' y 'cerro' en '{base_datos}'.")
    except Error as e:
        print(f"❌ Error al reiniciar grupo {base_datos}: {e}")
        continue

dia_actual = datetime.now().weekday()
if dia_actual == 5 or dia_actual == 6:
    print("Iniciando reinicio de graficas de entrada y salida de alumnos...")
    try:
        conexion = mysql.connector.connect(
            host="localhost", user="root", password=contraDB, database="Semestre"
        )
        cursor = conexion.cursor()
        cursor.execute("UPDATE registros SET lunes = 0, martes = 0, miercoles = 0, jueves = 0, viernes = 0")
        cursor.execute("UPDATE registros_salida SET lunes = 0, martes = 0, miercoles = 0, jueves = 0, viernes = 0")
        conexion.commit()
        print("✅ Se han reiniciado los valores a 0 correctamente de las graficas.")
    except Error as e:
        print(f"❌ Error al reiniciar graficas: {e}")
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conexion' in locals() and conexion.is_connected(): conexion.close()
else:
    print("Hoy no es fin de semana, no se reiniciarán las gráficas.")


# --- 3. CONFIRMACIÓN FINAL: ACTUALIZAR LA TABLA 'reinicios' ---
# Este bloque solo se alcanza si el script no fue detenido por el sys.exit(0) del principio.
try:
    conexion_final = mysql.connector.connect(
        host="localhost",
        user="root",
        password=contraDB,
        database="Semestre"
    )
    cursor_final = conexion_final.cursor()

    # Preparamos el query para que el 'target_day' se vuelva 1, y TODOS LOS DEMÁS se vuelvan 0.
    updates = []
    for dia in dias_semana:
        if dia == target_day_name:
            updates.append(f"{dia} = 1")
        else:
            updates.append(f"{dia} = 0")

    query_update = f"UPDATE reinicios SET {', '.join(updates)}"
    
    cursor_final.execute(query_update)
    conexion_final.commit()

    print(f"🎉 ÉXITO: El día {target_day_name.upper()} se ha marcado como completado (1) y el resto de la semana se limpió (0).")

    cursor_final.close()
    conexion_final.close()

except Exception as e:
    print(f"❌ Error al intentar marcar el reinicio como completado al final del script: {e}")