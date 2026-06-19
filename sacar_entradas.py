import mysql.connector
from mysql.connector import Error
import datetime
import os

# --- Configuración ---
contra_db = "P3l0n100j0t3$"
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': contra_db
}
CARPETA_DESTINO = "/home/amsf08/Codigos/Torniquete/entradas"

def obtener_lista_grupos():
    """Obtiene la lista de schemas (grupos) basándose en tu tabla Semestre."""
    try:
        conexion = mysql.connector.connect(**db_config, database="Semestre")
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT * FROM semestre LIMIT 1")
        row = cursor.fetchone()
        
        if not row:
            print("❌ No se encontró información en 'semestre'")
            return []

        semestre = int(row['semestre'])
        # Diccionario de prefijos según tu estructura
        bloque_prefijo = {
            1: {'TM': '1TM', 'CM': '3CM', 'AM': '3AM', 'MM': '3MM', 'IM': '3IM', 'PM': '3PM', 'EM': '3EM', 'LM': '3LM',
                'CM_5': '5CM', 'AM_5': '5AM', 'MM_5': '5MM', 'IM_5': '5IM', 'PM_5': '5PM', 'EM_5': '5EM', 'LM_5': '5LM'},
            2: {'TM': '2TM', 'CM': '4CM', 'AM': '4AM', 'MM': '4MM', 'IM': '4IM', 'PM': '4PM', 'EM': '4EM', 'LM': '4LM',
                'CM_5': '6CM', 'AM_5': '6AM', 'MM_5': '6MM', 'IM_5': '6IM', 'PM_5': '6PM', 'EM_5': '6EM', 'LM_5': '6LM'}
        }
        
        prefijos = bloque_prefijo.get(semestre, bloque_prefijo[2])

        lista = []
        # Procesar grupos TM
        if row.get('1_2_TM'):
            lista.extend([f"{prefijos['TM']}{i}" for i in range(1, row['1_2_TM'] + 1)])
        
        # Procesar grupos 3_4
        for tipo in ['CM', 'AM', 'MM', 'IM', 'PM', 'EM', 'LM']:
            count = row.get(f'3_4_{tipo}')
            if count:
                lista.extend([f"{prefijos[tipo]}{i}" for i in range(1, count + 1)])
        
        # Procesar grupos 5_6
        for tipo in ['CM', 'AM', 'MM', 'IM', 'PM', 'EM', 'LM']:
            count = row.get(f'5_6_{tipo}')
            if count:
                lista.extend([f"{prefijos[f'{tipo}_5']}{i}" for i in range(1, count + 1)])
        
        cursor.close()
        conexion.close()
        return lista
    except Error as e:
        print(f"❌ Error al conectar a 'Semestre': {e}")
        return []

def generar_reporte():
    grupos = obtener_lista_grupos()
    if not grupos:
        print("⚠️ No hay grupos para procesar.")
        return

    fecha_hoy = datetime.datetime.now().strftime("%Y-%m-%d")
    if not os.path.exists(CARPETA_DESTINO):
        os.makedirs(CARPETA_DESTINO)
    
    ruta_completa = os.path.join(CARPETA_DESTINO, f"reporte_acceso_{fecha_hoy}.txt")

    with open(ruta_completa, "w", encoding="utf-8") as f:
        f.write(f"REPORTE DE ACCESOS EXITOSOS - {fecha_hoy}\n")
        f.write("="*50 + "\n\n")

        for schema in grupos:
            try:
                conn = mysql.connector.connect(**db_config, database=schema)
                cursor = conn.cursor(dictionary=True)
                
                # CAMBIO AQUÍ: Usamos SELECT * para evitar errores de nombres de columna
                # Filtramos por 'abrio' que es la que tú confirmaste que existe.
                query = f"SELECT * FROM {schema} WHERE abrio = 1"
                cursor.execute(query)
                resultados = cursor.fetchall()
                
                f.write(f"GRUPO: {schema}\n")
                if resultados:
                    for reg in resultados:
                        # Buscamos qué columnas existen en el resultado para imprimir
                        # Esto evita el error si 'id' o 'nombre' se llaman distinto
                        # Intentamos buscar nombres comunes de columnas
                        id_val = reg.get('id') or reg.get('boleta') or reg.get('numero') or "N/A"
                        nom_val = reg.get('nombre') or reg.get('nombre_completo') or "Sin nombre"
                        
                        f.write(f" - ID: {id_val} | Nombre: {nom_val}\n")
                else:
                    f.write(" - Sin accesos hoy.\n")
                f.write("-" * 20 + "\n")
                
                cursor.close()
                conn.close()
            except Error as e:
                f.write(f"GRUPO: {schema} - Error al leer la tabla: {e}\n")
                continue

    print(f"✅ Reporte generado: {ruta_completa}")

if __name__ == "__main__":
    generar_reporte()