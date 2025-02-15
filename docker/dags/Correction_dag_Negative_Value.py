from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import psycopg2

def correct_negative_values():
    try:
        # Connexion à la base de données PostgreSQL
        conn = psycopg2.connect(
            dbname="corr",
            user="postgres",
            password="postgres",
            host="172.19.0.3",
        )
        cur = conn.cursor()

        # Correction des valeurs négatives dans la colonne 'quantity'
        update_quantity_query = '''
        UPDATE Transactions
        SET quantity = REPLACE(quantity, '-', '')
        WHERE quantity LIKE '-%';
        '''
        cur.execute(update_quantity_query)

        # Correction des valeurs négatives dans la colonne 'total_amount'
        update_total_amount_query = '''
        UPDATE Transactions
        SET total_amount = total_amount * -1
        WHERE total_amount < 0;
        '''
        cur.execute(update_total_amount_query)

        conn.commit()

        print("Anomalies corrigées avec succès.")

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
    'correction_Dag_Negative_Value',
    default_args=default_args,
    description='Un DAG pour détecter les anomalies dans les transactions',
    schedule_interval='*/5 * * * *',  # Exécuter toutes les 5 minutes
    #schedule_interval='@hourly',  # Exécuter toutes les heures
    catchup=False,
)

anomaly_correction_task = PythonOperator(
    task_id='correct_negative_values',
    python_callable=correct_negative_values,
    dag=dag,
)

anomaly_correction_task
