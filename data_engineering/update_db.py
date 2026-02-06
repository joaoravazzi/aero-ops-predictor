import mysql.connector

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root', 
    'password': 'Chiclete1!',
    'database': 'aero_ops',
    'use_pure': True
}

def update_database():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        print("Conectado ao banco de dados. Aplicando atualizações...")
        
        # 1. Adicionar alerta_emergencia
        try:
            cursor.execute("ALTER TABLE FACT_VOO_TELEMETRIA ADD COLUMN alerta_emergencia TINYINT(1) DEFAULT 0 AFTER motivo_atraso")
            print("[OK] Coluna 'alerta_emergencia' adicionada.")
        except mysql.connector.Error as err:
            if err.errno == 1060: # Nome de coluna duplicado
                print("[INFO] Coluna 'alerta_emergencia' já existe.")
            else: raise err

        # 2. Adicionar eta_real_min
        try:
            cursor.execute("ALTER TABLE FACT_VOO_TELEMETRIA ADD COLUMN eta_real_min DECIMAL(6,2) AFTER alerta_emergencia")
            print("[OK] Coluna 'eta_real_min' adicionada.")
        except mysql.connector.Error as err:
            if err.errno == 1060:
                print("[INFO] Coluna 'eta_real_min' já existe.")
            else: raise err

        # 3. Atualizar Comentário (Opcional)
        cursor.execute("ALTER TABLE FACT_VOO_TELEMETRIA MODIFY COLUMN status_pontualidade VARCHAR(20)")
        
        conn.commit()
        print("\nSucesso! O banco de dados está sincronizado com o script principal.")
        
    except Exception as e:
        print(f"Erro ao atualizar banco: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    update_database()
