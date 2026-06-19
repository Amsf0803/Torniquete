import mysql.connector
from mysql.connector import Error
import datetime

contra_db = "P3l0n100j0t3$"


# Configuración de tu conexión principal (donde está la tabla 'semestre')
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': contra_db
}

def obtener_lista_grupos():
    """Obtiene la lista de schemas (grupos) basándose en tu tabla Semestre."""
    try:
        conexion = mysql.connector.connect(**db_config, database="Semestre")
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT * FROM semestre LIMIT 1")
        row = cursor.fetchone()
        
        if not row:
            return []

        semestre = int(row['semestre'])
        prefijos = {
            1: {'TM': '1TM', 'CM': '3CM', 'AM': '3AM', 'MM': '3MM', 'IM': '3IM', 'PM': '3PM', 'EM': '3EM', 'LM': '3LM',
                'CM_5': '5CM', 'AM_5': '5AM', 'MM_5': '5MM', 'IM_5': '5IM', 'PM_5': '5PM', 'EM_5': '5EM', 'LM_5': '5LM'},
            2: {'TM': '2TM', 'CM': '4CM', 'AM': '4AM', 'MM': '4MM', 'IM': '4IM', 'PM': '4PM', 'EM': '4EM', 'LM': '4LM',
                'CM_5': '6CM', 'AM_5': '6AM', 'MM_5': '6MM', 'IM_5': '6IM', 'PM_5': '6PM', 'EM_5': '6EM', 'LM_5': '6LM'}
        }.get(semestre, {2}) # Default a 2 si no es 1

        lista = []
        if row['1_2_TM']:
            lista.extend([f"{prefijos['TM']}{i}" for i in range(1, row['1_2_TM'] + 1)])
        for tipo in ['CM', 'AM', 'MM', 'IM', 'PM', 'EM', 'LM']:
            if row[f'3_4_{tipo}']:
                lista.extend([f"{prefijos[tipo]}{i}" for i in range(1, row[f'3_4_{tipo}'] + 1)])
            if row[f'5_6_{tipo}']:
                lista.extend([f"{prefijos[f'{tipo}_5']}{i}" for i in range(1, row[f'5_6_{tipo}'] + 1)])
        
        cursor.close()
        conexion.close()
        return lista
    except Error as e:
        print(f"Error obteniendo grupos: {e}")
        return []

def generar_reporte():
    grupos = obtener_lista_grupos()
    fecha_hoy = datetime.datetime.now().strftime("%Y-%m-%d")
    archivo_log = f"reporte_acceso_{fecha_hoy}.txt"

    with open(archivo_log, "w", encoding="utf-8") as f:
        f.write(f"REPORTE DE ACCESOS EXITOSOS - {fecha_hoy}\n")
        f.write("="*50 + "\n\n")

        for schema in grupos:
            try:
                # Conexión dinámica al schema del grupo
                conn = mysql.connector.connect(**db_config, database=schema)
                cursor = conn.cursor(dictionary=True)
                
                # Asumimos que la tabla dentro del schema tiene el mismo nombre que el schema
                # O ajusta aquí el nombre de la tabla si es distinto
                query = f"SELECT id, nombre FROM {schema} WHERE abrio = 1"
                cursor.execute(query)
                resultados = cursor.fetchall()
                
                f.write(f"GRUPO: {schema}\n")
                if resultados:
                    for reg in resultados:
                        f.write(f" - {reg['id']} | {reg['nombre']}\n")
                else:
                    f.write(" - Sin accesos hoy.\n")
                f.write("-" * 20 + "\n")
                
                cursor.close()
                conn.close()
            except Error:
                f.write(f"GRUPO: {schema} - Error al leer schema.\n")
                continue

    print(f"✅ Reporte generado: {archivo_log}")

if __name__ == "__main__":
    generar_reporte()