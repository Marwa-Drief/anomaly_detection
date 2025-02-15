from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import psycopg2

def correct_1nf_violations():
    try:
        # Connexion à la base de données PostgreSQL
        conn = psycopg2.connect(
            dbname="corr",
            user="postgres",
            password="postgres",
            host="172.19.0.3",
        )
        cur = conn.cursor()

        # Étape 1 : Sélectionner toutes les lignes de la table Orders
        select_orders_query = '''
        SELECT order_id, customer_id, order_date, total_amount, product_ids
        FROM Orders;
        '''
        cur.execute(select_orders_query)
        rows = cur.fetchall()

        # Étape 2 : Mettre à jour chaque ligne pour ne garder qu'un seul product_id
        update_query = '''
        UPDATE Orders
        SET product_ids = %s
        WHERE order_id = %s;
        '''

        for row in rows:
            order_id, customer_id, order_date, total_amount, product_ids = row
            
            # Diviser les product_ids et prendre le premier
            first_product_id = product_ids.split(',')[0].strip()
            
            # Mettre à jour la ligne avec un seul product_id
            cur.execute(update_query, (first_product_id, order_id))

        conn.commit()

        print("Table Orders mise à jour avec succès, violations 1FN corrigées.")

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
    'correction_Dag_1FN',
    default_args=default_args,
    description='Un DAG pour corriger les violations 1FN dans la table Orders',
    schedule_interval='*/5 * * * *',  # Exécuter toutes les 5 minutes
    catchup=False,
)

anomaly_correction_task = PythonOperator(
    task_id='correct_1nf_violations',
    python_callable=correct_1nf_violations,
    dag=dag,
)

anomaly_correction_task