from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, select
import pandas as pd
from datetime import datetime, timedelta
from contextlib import contextmanager
import logging

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Informations de connexion fournies
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

def detect_excessively_high_total_amount(df_transactions, df_products, threshold_factor=1.5):
    try:
        df_transactions['quantity'] = pd.to_numeric(df_transactions['quantity'], errors='coerce')
        df_transactions['total_amount'] = pd.to_numeric(df_transactions['total_amount'], errors='coerce')
        df_products['price'] = pd.to_numeric(df_products['price'], errors='coerce')

        df_transactions = df_transactions.dropna(subset=['quantity', 'total_amount'])
        df_products = df_products.dropna(subset=['price'])

        df = pd.merge(df_transactions, df_products, on='product_id', how='left')
        df['expected_amount'] = df['price'] * df['quantity']

        df_anomalies = df[df['total_amount'] > (df['expected_amount'] * threshold_factor)]

        anomalies_df = pd.DataFrame({
            "Category": "Point Anomalies",
            "AnomalyType": "Excessively High Total Amount",
            "Details": df_anomalies.apply(
                lambda row: f"Transaction ID {row['transaction_id']} has a total amount of {row['total_amount']} which exceeds the expected amount of {row['expected_amount']}.",
                axis=1
            ),
            "RelatedRecord": df_anomalies.apply(
                lambda row: f"Transaction ID {row['transaction_id']}", axis=1
            )
        })

        return anomalies_df
    except Exception as e:
        logger.error(f"Error in detect_excessively_high_total_amount: {str(e)}")
        raise

def create_anomalies_table(engine):
    metadata = MetaData()
    anomalies_table = Table('anomalieDetected', metadata,
        Column('id', Integer, primary_key=True),
        Column('Category', String),
        Column('AnomalyType', String),
        Column('Details', String),
        Column('RelatedRecord', String),
    )
    metadata.create_all(engine)

def insert_anomalies(df, engine):
    try:
        create_anomalies_table(engine)
        with engine.connect() as connection:
            anomalies_table = Table('anomalieDetected', MetaData(), autoload_with=engine)
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
        logger.info(f"Inserted {len(df)} new anomalies.")
    except Exception as e:
        logger.error(f"Error in insert_anomalies: {str(e)}")
        raise

def run_anomaly_detection(**kwargs):
    try:
        logger.info("Starting anomaly detection process")
        engine = create_engine(db_url)

        transactions = table_to_dataframe('transactions')
        products = table_to_dataframe('products')

        logger.info(f"Loaded {len(transactions)} transactions and {len(products)} products")

        df_anomaly = detect_excessively_high_total_amount(transactions, products, threshold_factor=1.5)
        logger.info(f"Detected {len(df_anomaly)} anomalies")

        insert_anomalies(df_anomaly, engine)
        logger.info("Anomaly detection process completed successfully")
    except Exception as e:
        logger.error(f"Error in run_anomaly_detection: {str(e)}")
        raise

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'dag_detect_excessively_high_total_amount',
    default_args=default_args,
    description='DAG pour détecter les anomalies de montant excessif dans les transactions',
    schedule_interval=timedelta(minutes=15),
    catchup=False,
)

anomaly_detection_task = PythonOperator(
    task_id='run_anomaly_detection',
    python_callable=run_anomaly_detection,
    provide_context=True,
    dag=dag,
)

anomaly_detection_task
