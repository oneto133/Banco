import mysql.connector
from mysql.connector import Error

def conectar_e_consultar():
    conn = None

    try:
        conn = mysql.connector.connect(
            host="localhost",
            database="genio",
            user="root",
            password="root"
        )
        if conn.is_connected:
            print("Conectado com sucesso!")
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM extrato")
            registros = cursor.fetchall()
            print("\n dados da tabela usuários")
            for row in registros:
                print(row)
            
            cursor.close()

    except Error as e:
        print(f"Erro de conexão {e}")

    finally:
        if conn and conn.is_connected():
            conn.close()
            print("Conexão fechada")

conectar_e_consultar()
