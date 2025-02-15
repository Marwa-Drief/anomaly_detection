from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import psycopg2

import psycopg2

def correct_transactions_anomalies():
    try:
        # Connexion à la base de données PostgreSQL
        conn = psycopg2.connect(
            dbname="corr",
            user="postgres",
            password="postgres",
            host="172.19.0.3",
        )
        cur = conn.cursor()

        # 1. Correction des valeurs nulles en utilisant la valeur la plus fréquente
        columns_to_check = ["customer_id", "product_id", "transaction_date", "quantity", "total_amount"]

        for column in columns_to_check:
            cur.execute(f'''
                SELECT {column}, COUNT(*) as freq
                FROM Transactions
                WHERE {column} IS NOT NULL
                GROUP BY {column}
                ORDER BY freq DESC
                LIMIT 1;
            ''')
            most_frequent_value = cur.fetchone()

            if most_frequent_value:
                most_frequent_value = most_frequent_value[0]

                # Mise à jour des valeurs nulles avec la valeur la plus fréquente
                cur.execute(f'''
                    UPDATE Transactions
                    SET {column} = %s
                    WHERE {column} IS NULL;
                ''', (most_frequent_value,))
                conn.commit()

        print("Correction des anomalies dans la table Transactions réussie.")

    except Exception as error:
        print(f"Erreur lors de la correction des anomalies : {error}")
    
    finally:
        if conn:
            cur.close()
            conn.close() 
 
# Configuration du DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 8, 18),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'correction_Dag_Valeu_NULL',
    default_args=default_args,
    description='Un DAG pour détecter les anomalies dans les transactions',
    schedule_interval='*/5 * * * *',  # Exécuter toutes les 5 minutes
    #schedule_interval='@hourly',  # Exécuter toutes les heures
    catchup=False,
)

anomaly_correction_task = PythonOperator(
    task_id='correct_transactions_anomalies',
    python_callable=correct_transactions_anomalies,
    dag=dag,
)

anomaly_correction_task
