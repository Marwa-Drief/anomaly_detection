from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, select
import pandas as pd
from datetime import datetime, timedelta
from contextlib import contextmanager
import logging

# Database connection details
user = 'postgres'
password = 'postgres'
host = '172.19.0.3'  
port = '5432'
database = 'anomaly_detection'

# Database URL
db_url = f'postgresql://{user}:{password}@{host}:{port}/{database}'

# Context manager to manage database connections
@contextmanager
def get_connection():
    engine = create_engine(db_url)
    try:
        connection = engine.connect()
        yield connection
    finally:
        connection.close()
        engine.dispose()

# Fetch table names from the database
def get_table_names():
    with get_connection() as connection:
        tables_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
        tables_result = connection.execute(tables_query)
        return [row['table_name'] for row in tables_result]

# Convert a table to a pandas DataFrame
def table_to_dataframe(table_name):
    with get_connection() as connection:
        metadata = MetaData()
        table = Table(table_name, metadata, autoload_with=connection.engine, schema='public')
        stmt = select(table)
        result = connection.execute(stmt)
        return pd.DataFrame(result.fetchall(), columns=result.keys())

# Detect collective anomalies in the `transactions` table
def detect_collective_anomalies(df, time_threshold='1min'):
    anomalies = []

    # Ensure the column `transaction_date` is in datetime format
    df['transaction_date'] = pd.to_datetime(df['transaction_date'])
    
    # Sort the DataFrame by `customer_id`, `product_id`, and `transaction_date`
    df = df.sort_values(by=['customer_id', 'product_id', 'transaction_date'])
    
    for customer_id, product_id in df.groupby(['customer_id', 'product_id']).groups:
        group = df[(df['customer_id'] == customer_id) & (df['product_id'] == product_id)]
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
        
        for group in collective_anomaly_groups:
            anomalies.append({
                "Category": "Collective Anomaly",
                "AnomalyType": "Multiple Transactions in a Short Timeframe",
                "Details": "Multiple transactions for the same product by the same customer within a short time frame.",
                "RelatedRecord": f"Transactions ID {group}"
            })

    return pd.DataFrame(anomalies, columns=["Category", "AnomalyType", "Details", "RelatedRecord"])

# Insert detected anomalies into the `anomalieDetected` table
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

# Function to detect anomalies and insert them into the database
def run_anomaly_detection():
    transactions_df = table_to_dataframe('transactions')
    anomalies_df = detect_collective_anomalies(transactions_df)
    if not anomalies_df.empty:
        insert_anomalies(anomalies_df)
    else:
        logging.info("No anomalies detected.")

# DAG configuration
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
    'Dag_Multiple_Transactions_in_Short_Timeframe',
    default_args=default_args,
    description='DAG to detect collective anomalies in transactions',
    schedule_interval=timedelta(minutes=5),
    catchup=False,
)

# PythonOperator task for anomaly detection
anomaly_detection_task = PythonOperator(
    task_id='run_anomaly_detection',
    python_callable=run_anomaly_detection,
    dag=dag,
)

anomaly_detection_task
