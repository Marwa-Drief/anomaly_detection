from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import psycopg2
def correct_excessively_high_total_amount_in_db(connection):
    try:
        # Créer un curseur pour interagir avec la base de données
        cursor = connection.cursor()

        # Étape 1 : Mettre à jour les enregistrements avec des montants excessivement élevés
        cursor.execute("""
            UPDATE transactions t
            SET total_amount = p.price *  CAST(t.quantity AS numeric)
            FROM products p
            WHERE t.product_id = p.product_id
            AND t.total_amount != (p.price * CAST(t.quantity AS numeric)) ;
        """)

        # Valider les changements dans la base de données
        connection.commit()

        print("Les anomalies ont été corrigées dans la base de données.")

    except Exception as e:
        # Annuler les changements en cas d'erreur
        connection.rollback()
        print(f"Une erreur s'est produite : {e}")
    finally:
        # Fermer le curseur
        cursor.close()

connection = psycopg2.connect(
            dbname="corr",
            user="postgres",
            password="postgres",
            host="172.19.0.3",
        )
def Correction_dag_high_total_amount():
    correct_excessively_high_total_amount_in_db(connection)
   # Fermer la connexion après avoir terminé
    connection.close()
 
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
    'Correction_dag_high_total_amount',
    default_args=default_args,
    description='Un DAG pour détecter les anomalies dans les transactions',
    schedule_interval='*/5 * * * *',  # Exécuter toutes les 5 minutes
    #schedule_interval='@hourly',  # Exécuter toutes les heures
    catchup=False,
)

anomaly_correction_task = PythonOperator(
    task_id='Correction_dag_high_total_amount',
    python_callable=Correction_dag_high_total_amount,
    dag=dag,
)

anomaly_correction_task
