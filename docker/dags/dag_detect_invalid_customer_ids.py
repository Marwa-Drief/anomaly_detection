from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, delete, select
import logging

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Informations de connexion
user = 'postgres'
password = 'postgres'
host = '172.19.0.3'
port = '5432'
database = 'anomaly_detection'
db_url = f'postgresql://{user}:{password}@{host}:{port}/{database}'
engine = create_engine(db_url)
metadata = MetaData()

def get_table_names(connection):
    try:
        tables_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
        tables_result = connection.execute(tables_query)
        return [row['table_name'] for row in tables_result]
    except Exception as e:
        logger.error(f"Error in get_table_names: {str(e)}")
        raise

def table_to_dataframe(table_name, connection):
    try:
        table = Table(table_name, metadata, autoload_with=engine, schema='public')
        stmt = select(table)
        result = connection.execute(stmt)
        return pd.DataFrame(result.fetchall(), columns=result.keys())
    except Exception as e:
        logger.error(f"Error in table_to_dataframe for table {table_name}: {str(e)}")
        raise

def create_anomalies_table(engine):
    try:
        anomalies_table = Table('anomalieDetected', metadata,
            Column('id', Integer, primary_key=True),
            Column('Category', String),
            Column('AnomalyType', String),
            Column('Details', String),
            Column('RelatedRecord', String),
        )
        metadata.create_all(engine)
    except Exception as e:
        logger.error(f"Error in create_anomalies_table: {str(e)}")
        raise

def detect_invalid_customer_ids(df, valid_customer_ids=[1, 2, 3, 4]):
    try:
        anomaly_results = []
        if 'customer_id' in df.columns:
            invalid_mask = (~df['customer_id'].isin(valid_customer_ids)) | df['customer_id'].isna()
            anomaly_results.extend([
                {
                    "Category": "Point Anomalies",
                    "AnomalyType": "Customer ID is not valid or missing",
                    "Details": f"Column 'customer_id' contains an invalid or missing ID: {df.at[i, 'customer_id']}",
                    "RelatedRecord": f"Transaction ID {df.at[i, 'transaction_id']}"
                }
                for i in df[invalid_mask].index
            ])
        return pd.DataFrame(anomaly_results)
    except Exception as e:
        logger.error(f"Error in detect_invalid_customer_ids: {str(e)}")
        raise

def insert_anomalies(df, engine):
    try:
        create_anomalies_table(engine)
        with engine.connect() as connection:
            for _, row in df.iterrows():
                stmt_select = select([Table('anomalieDetected', metadata, autoload_with=engine)]).where(
                    (Column('Category') == row['Category']) &
                    (Column('AnomalyType') == row['AnomalyType']) &
                    (Column('Details') == row['Details']) &
                    (Column('RelatedRecord') == row['RelatedRecord'])
                )
                result = connection.execute(stmt_select).fetchone()
                if result is None:
                    stmt_insert = Table('anomalieDetected', metadata, autoload_with=engine).insert().values(
                        Category=row['Category'],
                        AnomalyType=row['AnomalyType'],
                        Details=row['Details'],
                        RelatedRecord=row['RelatedRecord']
                    )
                    connection.execute(stmt_insert)
        logger.info(f"Inserted {len(df)} new anomalies.")
    except Exception as e:
        logger.error(f"Error in insert_anomalies: {str(e)}")
        raise

def run_anomaly_detection():
    try:
        logger.info("Starting anomaly detection process")
        with engine.connect() as connection:
            transactions = table_to_dataframe('transactions', connection)
        
        logger.info(f"Loaded {len(transactions)} transactions")
        
        df_anomaly = detect_invalid_customer_ids(transactions)
        logger.info(f"Detected {len(df_anomaly)} anomalies")
        
        insert_anomalies(df_anomaly, engine)
        logger.info("Anomaly detection process completed successfully")
    except Exception as e:
        logger.error(f"Error in run_anomaly_detection: {str(e)}")
        raise

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 9, 8),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'Dag_detect_invalid_customer_ids',
    default_args=default_args,
    description='Un DAG pour détecter les anomalies dans les ID clients',
    schedule_interval=timedelta(minutes=15),
    catchup=False,
)

anomaly_detection_task = PythonOperator(
    task_id='run_anomaly_detection',
    python_callable=run_anomaly_detection,
    dag=dag,
)

anomaly_detection_task