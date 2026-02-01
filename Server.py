from datetime import date
import mysql.connector
from mysql.connector import Error
from datetime import datetime



contraDB = "P3l0n100j0t3$"

#Aqui se revisan las suspensiones
try:
    # Conectar a la base de datos de suspensiones
    conexion = mysql.connector.connect(
        host="localhost",
        user="root",
        password=contraDB,
        database="Suspensiones"
    )
    cursor = conexion.cursor()

    hoy = date.today()

    # Obtener todas las suspensiones
    cursor.execute("SELECT boleta, grupo, nombre_alumno, fecha_inicio, fecha_fin FROM suspensiones_registro")
    suspensiones = cursor.fetchall()
    print(suspensiones);

    for boleta, grupo, nombre_alumno, fecha_inicio, fecha_fin in suspensiones:
        try:
            # Si hoy inicia la suspensión
            if fecha_inicio == hoy:
                try:
                    conexion_grupo = mysql.connector.connect(
                        host="localhost",
                        user="root",
                        password= contraDB,
                        database=grupo
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
                        host="localhost",
                        user="root",
                        password= contraDB,
                        database=grupo
                    )
                    cursor_grupo = conexion_grupo.cursor()
                    cursor_grupo.execute(f"UPDATE `{grupo}` SET inscrito = 1 WHERE boleta = %s", (boleta,))
                    conexion_grupo.commit()
                    print(f"🟢 Al Alumno {nombre_alumno} del grupo {grupo} con boleta: {boleta} se le ha sido removida su suspension.")


                    cursor_grupo.close()
                    conexion_grupo.close()

                    try:
                        conexion = mysql.connector.connect(
                            host="localhost",
                            user="root",
                            password= contraDB,
                            database="Suspensiones"
                        )

                        cursor = conexion.cursor()
                        boleta_a_eliminar = boleta
                        consulta = "DELETE FROM suspensiones_registro WHERE boleta = %s"
                        cursor.execute(consulta, (boleta_a_eliminar,))
                        conexion.commit()

                        print(f"{cursor.rowcount} fila(s) eliminada(s).")

                    except mysql.connector.Error as e:
                        print("Error al eliminar la fila:", e)

                    finally:
                        if conexion.is_connected():
                            cursor.close()
                            conexion.close()

                except Exception as e:
                    print(f"❌ Error al reactivar {boleta} en {grupo}: {e}")

            elif fecha_inicio > hoy:
                try:
                    conexion_grupo = mysql.connector.connect(
                        host="localhost",
                        user="root",
                        password= contraDB,
                        database=grupo
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
                        conexion = mysql.connector.connect(
                            host="localhost",
                            user="root",
                            password= contraDB,
                            database="Suspensiones"
                        )

                        cursor = conexion.cursor()
                        boleta_a_eliminar = boleta
                        consulta = "DELETE FROM suspensiones_registro WHERE boleta = %s"
                        cursor.execute(consulta, (boleta_a_eliminar,))
                        conexion.commit()

                        print(f"{cursor.rowcount} fila(s) eliminada(s).")

                except mysql.connector.Error as e:
                        print("Error al eliminar la fila:", e)

                finally:
                        if conexion.is_connected():
                            cursor.close()
                            conexion.close()
        except Exception as e:
            print(f"⚠️ Error al procesar boleta {boleta}: {e}")

    cursor.close()
    conexion.close()

except Exception as e:
    print(f"❌ Error general: {e}")

#Aqui se borra todo de la tabla de Pases de salida

try:
    conexion = mysql.connector.connect(
        host="localhost",
        user="root",
        password= contraDB,
        database="Pases_salida"
    )
    cursor = conexion.cursor()
    consulta = "DELETE FROM modificaciones_temporales"
    cursor.execute(consulta)  # sin parámetros
    conexion.commit()
    print(f"🗑️ {cursor.rowcount} fila(s) eliminada(s) de la base de datos de Pases de salida.")
except Exception as e:
    print(f"❌ Error al conectar a la base de datos de Pases de salida: {e}")

# Aqui se obtiene el semestre y los grupos
try:
    conexion = mysql.connector.connect(
        host="localhost",
        user="root",
        password= contraDB,
        database="Semestre"
    )
    cursor = conexion.cursor(dictionary=True)

    # Obtener todos los valores de la tabla 'semestre' en una sola consulta
    cursor.execute("""
        SELECT semestre, grupo, 1_2_TM, 3_4_CM, 3_4_AM, 3_4_MM, 3_4_IM, 3_4_PM, 3_4_EM, 3_4_LM,
            5_6_CM, 5_6_AM, 5_6_MM, 5_6_IM, 5_6_PM, 5_6_EM, 5_6_LM
        FROM semestre
        LIMIT 1
    """)
    row = cursor.fetchone()

    if row:
        semestre = int(row['semestre'])
        grupo_seleccionado = row['grupo']
        print(f"✅ Grupo seleccionado: {grupo_seleccionado}")

        # Mapear prefijos según semestre
        bloque_prefijo = {
            1: {'TM': '1TM', 'CM': '3CM', 'AM': '3AM', 'MM': '3MM', 'IM': '3IM', 'PM': '3PM', 'EM': '3EM', 'LM': '3LM',
                'CM_5': '5CM', 'AM_5': '5AM', 'MM_5': '5MM', 'IM_5': '5IM', 'PM_5': '5PM', 'EM_5': '5EM', 'LM_5': '5LM'},
            2: {'TM': '2TM', 'CM': '4CM', 'AM': '4AM', 'MM': '4MM', 'IM': '4IM', 'PM': '4PM', 'EM': '4EM', 'LM': '4LM',
                'CM_5': '6CM', 'AM_5': '6AM', 'MM_5': '6MM', 'IM_5': '6IM', 'PM_5': '6PM', 'EM_5': '6EM', 'LM_5': '6LM'}
        }

        prefijos = bloque_prefijo.get(semestre, bloque_prefijo[2])  # Por defecto semestre 2

        # Crear listas de grupos dinámicamente
        bases_datos = ["Pases_salida"]
        # Bloque 1_2
        if row['1_2_TM']:
            bases_datos.extend([f"{prefijos['TM']}{i}" for i in range(1, row['1_2_TM'] + 1)])
        # Bloque 3_4
        for tipo in ['CM', 'AM', 'MM', 'IM', 'PM', 'EM', 'LM']:
            count = row[f'3_4_{tipo}']
            if count:
                bases_datos.extend([f"{prefijos[tipo]}{i}" for i in range(1, count + 1)])
        # Bloque 5_6
        for tipo in ['CM', 'AM', 'MM', 'IM', 'PM', 'EM', 'LM']:
            count = row[f'5_6_{tipo}']
            if count:
                bases_datos.extend([f"{prefijos[f'{tipo}_5']}{i}" for i in range(1, count + 1)])

        print(f"ℹ️ Grupos disponibles para semestre {semestre}: {bases_datos}")

        if grupo_seleccionado in bases_datos:
            print(f"✅ El grupo '{grupo_seleccionado}' es válido para el semestre {semestre}")
        else:
            print(f"⚠️ El grupo '{grupo_seleccionado}' no está en la lista del semestre {semestre}")
    else:
        print("❌ No se encontró información en la tabla 'semestre'.")
        grupo_seleccionado = None
        semestre = 2
        bases_datos = []

    # Cerrar cursor y conexión
    cursor.close()
    conexion.close()

except Error as e:
    print(f"❌ Error al conectar a la base de datos 'Semestre': {e}")
    grupo_seleccionado = None
    semestre = 2
    bases_datos = []


for base_datos in bases_datos:
    try:
    # Conectar a la base de datos 'Semestre'
        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password= contraDB,
            database=f"{base_datos}"
        )

        cursor = conexion.cursor()
        cursor.execute(f"UPDATE `{base_datos}` SET abrio = 0 ")
        cursor.execute(f"UPDATE `{base_datos}` SET cerro = 0 ")
        conexion.commit()
        print(f"✅ Se han reiniciado los campos 'abrio' y 'cerro' en la base de datos '{base_datos}'.")
        
    except Error as e:
        print(f"❌ Error al conectar a la base de datos del grupo: {e}")
        continue


dia_actual = datetime.now().weekday()
print(f"el dia de hoy es numero: {dia_actual}")  # Imprime el día actual de la semana (0-6)

if dia_actual == 5 or dia_actual == 6: # 5 = Sabado, 6 = Domingo
    print("Iniciando reinicio de graficas de entrada y salida de alumnos...")
    
    conexion = None
    cursor = None
    
    try:
        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password=contraDB,
            database="Semestre"
        )
        cursor = conexion.cursor()


        query_reset_entradas = """
            UPDATE registros 
            SET lunes = 0, martes = 0, miercoles = 0, jueves = 0, viernes = 0
        """
        cursor.execute(query_reset_entradas)

        query_reset_salidas = """
            UPDATE registros_salida 
            SET lunes = 0, martes = 0, miercoles = 0, jueves = 0, viernes = 0
        """
        cursor.execute(query_reset_salidas)

        conexion.commit()
        print("✅ Se han reiniciado los valores a 0 correctamente de las graficas.")

    except Error as e:
        print(f"❌ Error al conectar o reiniciar la base de datos: {e}")
        
    finally:
        # 5. Cerrar conexiones
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()
else:
    print("Hoy no es fin de semana, no se reiniciarán las gráficas.")
