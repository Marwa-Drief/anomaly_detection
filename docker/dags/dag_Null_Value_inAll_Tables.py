from airflow import DAG
from airflow.operators.python import PythonOperator
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, select
import pandas as pd
from datetime import datetime, timedelta
from contextlib import contextmanager
import logging

# Informations de connexion à une seule base de données
user = 'postgres'
password = 'postgres'
host = '172.19.0.3'
port = '5432'
database = 'anomaly_detection'

# URL de la base de données
db_url = f'postgresql://{user}:{password}@{host}:{port}/{database}'

@contextmanager
def get_connection():
    engine = create_engine(db_url)
    try:
        connection = engine.connect()
        yield connection
    finally:
        connection.close()
        engine.dispose()

def get_table_names():
    with get_connection() as connection:
        tables_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
        tables_result = connection.execute(tables_query)
        return [row['table_name'] for row in tables_result]

def table_to_dataframe(table_name):
    with get_connection() as connection:
        metadata = MetaData()
        table = Table(table_name, metadata, autoload_with=connection.engine, schema='public')
        stmt = select(table)
        result = connection.execute(stmt)
        return pd.DataFrame(result.fetchall(), columns=result.keys())

# Fonction de détection des anomalies Null
def detect_anomalies_null():
    dataframes = {
        'orderdetails': table_to_dataframe('orderdetails'),
        'productsuppliers': table_to_dataframe('productsuppliers'),
        'transactions': table_to_dataframe('transactions'),
        'products': table_to_dataframe('products'),
        'orders': table_to_dataframe('orders'),
        'customers': table_to_dataframe('customers')
    }
    
    def detect_anomalies(df, df_name="Unnamed DataFrame"):
        anomaly_results = []
        for col in df.columns:
            null_mask = df[col].isnull()
            anomaly_results.extend([
                {
                    "Category": "Point Anomalies",
                    "AnomalyType": "Null Value",
                    "Details": f"Column '{col}' contains a null value.",
                    "RelatedRecord": f"'{df_name}' ID {i + 1}"
                }
                for i in df[null_mask].index
            ])
        return pd.DataFrame(anomaly_results)

    # Appliquer la fonction sur chaque DataFrame et combiner les résultats
    all_anomalies = pd.DataFrame()
    for name, df in dataframes.items():
        anomalies = detect_anomalies(df, df_name=name)
        all_anomalies = pd.concat([all_anomalies, anomalies], ignore_index=True)
    
    return all_anomalies

# Insertion des anomalies détectées dans la même base de données
def insert_anomalies(df):
    with get_connection() as connection:
        metadata = MetaData()
        anomalies_table = Table('anomalieDetected', metadata,
            Column('id', Integer, primary_key=True),
            Column('Category', String),
            Column('AnomalyType', String),
            Column('Details', String),
            Column('RelatedRecord', String),
        )
        metadata.create_all(connection.engine)  # Créer la table si elle n'existe pas déjà
        
        for _, row in df.iterrows():
            stmt_select = select([anomalies_table]).where(
                (anomalies_table.c.Category == row['Category']) &
                (anomalies_table.c.AnomalyType == row['AnomalyType']) &
                (anomalies_table.c.Details == row['Details']) &
                (anomalies_table.c.RelatedRecord == row['RelatedRecord'])
            )
            result = connection.execute(stmt_select).fetchone()
            if result is None:
                stmt_insert = anomalies_table.insert().values(
                    Category=row['Category'],
                    AnomalyType=row['AnomalyType'],
                    Details=row['Details'],
                    RelatedRecord=row['RelatedRecord']
                )
                connection.execute(stmt_insert)

# Fonction pour détecter et insérer les anomalies
def run_anomaly_detection():
    df_anomaly = detect_anomalies_null()
    insert_anomalies(df_anomaly)

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
    'dag_Null_Value_inAll_Tables',
    default_args=default_args,
    description='Un DAG pour détecter les anomalies dans les transactions',
    schedule_interval=timedelta(minutes=15),  # Exécuter toutes les 15 minutes
    catchup=False,
)

anomaly_detection_task = PythonOperator(
    task_id='run_anomaly_detection',
    python_callable=run_anomaly_detection,
    dag=dag,
)

anomaly_detection_task
