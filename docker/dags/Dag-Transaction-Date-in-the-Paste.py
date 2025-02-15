from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, select
from contextlib import contextmanager
from datetime import datetime, timedelta
import pandas as pd
import logging

# Informations de connexion à la base de données unique
user = 'postgres'
password = 'postgres'
host = '172.19.0.3'
port = '5432'
database = 'anomaly_detection'

# URL pour la base de données anomaly_detection
db_url = f'postgresql://{user}:{password}@{host}:{port}/{database}'

@contextmanager
def get_connection(db_url):
    engine = create_engine(db_url)
    try:
        connection = engine.connect()
        yield connection
    finally:
        connection.close()
        engine.dispose()

def get_table_names():
    with get_connection(db_url) as connection:
        tables_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
        tables_result = connection.execute(tables_query)
        return [row['table_name'] for row in tables_result]

def table_to_dataframe(table_name):
    with get_connection(db_url) as connection:
        metadata = MetaData()
        table = Table(table_name, metadata, autoload_with=connection.engine, schema='public')
        stmt = select(table)
        result = connection.execute(stmt)
        return pd.DataFrame(result.fetchall(), columns=result.keys())

def detect_contextual_anomalies(df):
    anomalies = []
    expected_date_range = pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31")
    
    for index, row in df.iterrows():
        transaction_date = pd.Timestamp(row['transaction_date'])
        
        if not (expected_date_range[0] <= transaction_date <= expected_date_range[1]):
            anomalies.append({
                "Category": "Contextual Anomaly",
                "AnomalyType": "Transaction Date in the Past",
                "Details": f"The transaction_date is {transaction_date.strftime('%Y-%m-%d')}, which is outside the expected range.",
                "RelatedRecord": f"Transaction ID {row['transaction_id']}"
            })
    
    return pd.DataFrame(anomalies, columns=["Category", "AnomalyType", "Details", "RelatedRecord"])

def insert_anomalies(df):
    with get_connection(db_url) as connection:
        metadata = MetaData()
        anomalies_table = Table('anomalieDetected', metadata,
            Column('id', Integer, primary_key=True),
            Column('Category', String),
            Column('AnomalyType', String),
            Column('Details', String),
            Column('RelatedRecord', String),
        )
        metadata.create_all(connection.engine)

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

def run_anomaly_detection():
    try:
        transactions = table_to_dataframe('transactions')
        df_anomalies = detect_contextual_anomalies(transactions)
        
        if not df_anomalies.empty:
            logging.info(f"Inserting {len(df_anomalies)} detected anomalies")
            insert_anomalies(df_anomalies)
        else:
            logging.info("No anomalies detected")
    
    except Exception as e:
        logging.error(f"Error during anomaly detection: {str(e)}")
        raise

# Définir les arguments par défaut pour le DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Définir le DAG
dag = DAG(
    'detect_transaction_date_anomalies_dag',
    default_args=default_args,
    description='DAG for detecting transaction date anomalies',
    schedule_interval=timedelta(minutes=5),
    catchup=False,
)

# Définir la tâche utilisant PythonOperator
anomaly_detection_task = PythonOperator(
    task_id='run_anomaly_detection',
    python_callable=run_anomaly_detection,
    dag=dag,
)

anomaly_detection_task
