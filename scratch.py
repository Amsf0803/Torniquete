import mysql.connector

try:
    db = mysql.connector.connect(host='localhost', user='root', password='P3l0n100j0t3$', database='Casos_curiosos')
    cursor = db.cursor()
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    print("Tables:", tables)
    
    cursor.execute("SELECT * FROM Casos_curiosos LIMIT 5")
    rows = cursor.fetchall()
    print("Rows in Casos_curiosos:", rows)
    
    # Check if there are boleta tables
    for table in tables:
        t_name = table[0]
        if t_name != "Casos_curiosos":
            print(f"\nChecking table: {t_name}")
            cursor.execute(f"SELECT * FROM `{t_name}`")
            print(cursor.fetchall())
            break
except Exception as e:
    print(e)
