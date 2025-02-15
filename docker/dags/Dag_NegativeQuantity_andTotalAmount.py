from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, DateTime, select

# Database connection information
user = 'postgres'
password = 'postgres'
host = '172.19.0.3'
port = '5432'
database = 'anomaly_detection'
db_url = f'postgresql://{user}:{password}@{host}:{port}/{database}'

engine = create_engine(db_url)
metadata = MetaData()

def get_table_names(connection):
    tables_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
    tables_result = connection.execute(tables_query)
    return [row['table_name'] for row in tables_result]

def table_to_dataframe(table_name, connection):
    table = Table(table_name, metadata, autoload_with=engine, schema='public')
    stmt = select(table)
    result = connection.execute(stmt)
    return pd.DataFrame(result.fetchall(), columns=result.keys())

def detect_negative_values(df):
    anomalies_list = []

    if 'quantity' in df.columns:
        for index, row in df.iterrows():
            try:
                quantity = float(row['quantity'])
                if quantity < 0:
                    anomalies_list.append({
                        "transaction_id": row['transaction_id'],
                        "Category": "Point Anomalies",
                        "AnomalyType": "Negative Value",
                        "ColumnName": "quantity",
                        "Details": f"Transaction ID {row['transaction_id']} has a negative quantity: {quantity}.",
                        "RelatedRecord":f"Transaction ID {row['transaction_id']}"
                    })
            except ValueError:
                continue

    if 'total_amount' in df.columns:
        for index, row in df.iterrows():
            if row['total_amount'] < 0:
                anomalies_list.append({
                    "transaction_id": row['transaction_id'],
                    "Category": "Point Anomalies",
                    "AnomalyType": "Negative Value",
                    "ColumnName": "total_amount",
                    "Details": f"Transaction ID {row['transaction_id']} has a negative total amount: {row['total_amount']}.",
                    "RelatedRecord": f"Transaction ID {row['transaction_id']}"
                })

    return pd.DataFrame(anomalies_list)

def create_anomalies_table(engine):
    anomalies_table = Table('anomalieDetected', metadata,
        Column('id', Integer, primary_key=True),
        Column('Category', String),
        Column('AnomalyType', String),
        Column('Details', String),
        Column('RelatedRecord', String),
    )
    metadata.create_all(engine)
    return anomalies_table

def insert_anomalies(df, engine):
    anomalies_table = create_anomalies_table(engine)
    with engine.connect() as connection:
        for _, row in df.iterrows():
            stmt_select = select(anomalies_table).where(
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
    with engine.connect() as connection:
        table_names = get_table_names(connection)
        transactions = table_to_dataframe('transactions', connection)
    
    df_anomaly = detect_negative_values(transactions)
    
    insert_anomalies(df_anomaly, engine)

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
    'Dag_NegativeQuantity_andTotalAmount',
    default_args=default_args,
    description='A DAG to detect anomalies in transactions',
    schedule_interval='*/5 * * * *',
    catchup=False,
)

anomaly_detection_task = PythonOperator(
    task_id='run_anomaly_detection',
    python_callable=run_anomaly_detection,
    dag=dag,
)

anomaly_detection_task