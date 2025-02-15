from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, delete,select
    
import psycopg2

  
def detect_and_correct_collective_anomalie():
    # Fonction pour détecter et corriger les anomalies collectives
    def detect_and_correct_collective_anomalies(connection, time_threshold='1min'):
        # Charger les données depuis la base de données
        query = "SELECT transaction_id, customer_id, product_id, transaction_date FROM Transactions"
        df = pd.read_sql(query, connection)
        
        # Assurez-vous que la colonne transaction_date est bien en format datetime
        df['transaction_date'] = pd.to_datetime(df['transaction_date'])
        
        # Trier le DataFrame par customer_id, product_id, et transaction_date
        df = df.sort_values(by=['customer_id', 'product_id', 'transaction_date'])
        
        cursor = connection.cursor()

        # Parcourir le DataFrame pour détecter les transactions collectives et corriger les anomalies
        for (customer_id, product_id), group in df.groupby(['customer_id', 'product_id']):
            group['time_diff'] = group['transaction_date'].diff().dt.total_seconds().fillna(float('inf'))
            
            collective_anomaly_groups = []
            current_group = []
            
            for index, row in group.iterrows():
                if row['time_diff'] <= pd.Timedelta(time_threshold).total_seconds():
                    current_group.append(row['transaction_id'])
                else:
                    if len(current_group) > 1:
                        collective_anomaly_groups.append(current_group)
                    current_group = [row['transaction_id']]
            
            if len(current_group) > 1:
                collective_anomaly_groups.append(current_group)
            
            # Appliquer les corrections pour les anomalies détectées
            for group in collective_anomaly_groups:
                # Exemple : Supprimer toutes les transactions dupliquées sauf la première
                delete_query = f"""
                    DELETE FROM Transactions
                    WHERE transaction_id IN ({','.join(map(str, group[1:]))});
                """
                cursor.execute(delete_query)
                connection.commit()

        cursor.close()

    # Exemple de connexion à la base de données
    connection = psycopg2.connect(
        dbname="corr",
        user="postgres",
        password="postgres",
        host="172.19.0.3"
    )

    # Appel de la fonction pour détecter et corriger les anomalies
    detect_and_correct_collective_anomalies(connection)

    # Fermer la connexion
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
    'Corrrect_Dag_detect_and_correct_collective_anomalie',
    default_args=default_args,
    description='Un DAG pour détecter les anomalies dans les transactions',
    schedule_interval='*/5 * * * *',  # Exécuter toutes les 5 minutes
    #schedule_interval='@hourly',  # Exécuter toutes les heures
    catchup=False,
)

anomaly_detection_task = PythonOperator(
    task_id='detect_and_correct_collective_anomalie',
    python_callable=detect_and_correct_collective_anomalie,
    dag=dag,
)

anomaly_detection_task
