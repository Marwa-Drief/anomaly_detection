from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, delete,select
    
import psycopg2

def Correct_Non_numeric_Quantity():
    # Connexion à la base de données PostgreSQL
    conn = psycopg2.connect(
        dbname="corr",
        user="postgres",
        password="postgres",
        host="172.19.0.3",
        port="5432"
    )

    # Créer un curseur
    cur = conn.cursor()

    # Dictionnaire pour remplacer les mots par les chiffres correspondants
    number_words = {
        'one':'1',
        'two': '2',
        'three': '3',
        'four': '4',
        'five': '5',
        'six': '6',
        'seven': '7',
        'eight': '8',
        'nine': '9',
        'ten': '10'
    }

    # Exécuter les mises à jour pour chaque mot dans le dictionnaire
    for word, digit in number_words.items():
        query = f"""
        UPDATE Transactions
        SET quantity = %s
        WHERE quantity = %s;
        """
        cur.execute(query, (digit, word))

    # Valider les changements
    conn.commit()

    # Fermer le curseur et la connexion
    cur.close()
    conn.close()

    print("Anomalies textuelles corrigées avec succès dans la table Transactions.")

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
    'correction_Dag_no_NumericValues',
    default_args=default_args,
    description='Un DAG pour détecter les anomalies dans les transactions',
    schedule_interval='*/5 * * * *',  # Exécuter toutes les 5 minutes
    #schedule_interval='@hourly',  # Exécuter toutes les heures
    catchup=False,
)

anomaly_detection_task = PythonOperator(
    task_id='Correct_Non_numeric_Quantity',
    python_callable=Correct_Non_numeric_Quantity,
    dag=dag,
)

anomaly_detection_task
