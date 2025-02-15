from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, select

# Informations de connexion pour la base de données 'anomaly_detection'
user = 'postgres'
password = 'postgres'
host = '172.19.0.3'
port = '5432'
database = 'anomaly_detection'

# URL de la base de données
db_url = f'postgresql://{user}:{password}@{host}:{port}/{database}'

# Créer le moteur SQLAlchemy pour se connecter à la base de données 'anomaly_detection'
engine = create_engine(db_url)
metadata = MetaData()

# Fonction pour récupérer les noms de table dans la base de données
def get_table_names(connection):
    tables_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
    tables_result = connection.execute(tables_query)
    return [row['table_name'] for row in tables_result]

# Fonction pour convertir une table en DataFrame pandas
def table_to_dataframe(table_name, connection):
    table = Table(table_name, metadata, autoload_with=engine, schema='public')
    stmt = select(table)
    result = connection.execute(stmt)
    return pd.DataFrame(result.fetchall(), columns=result.keys())

# Connexion à la base de données
connection = engine.connect()

# Charger les tables en DataFrame
customers = table_to_dataframe('customers', connection)
transactions = table_to_dataframe('transactions', connection)
products = table_to_dataframe('products', connection)
orders = table_to_dataframe('orders', connection)
orderdetails = table_to_dataframe('orderdetails', connection)
productsuppliers = table_to_dataframe('productsuppliers', connection)

# Fermer la connexion à la base de données
connection.close()

# Définir la table des anomalies dans la base de données 'anomaly_detection'
anomalies_table = Table('anomalieDetected', metadata,
    Column('id', Integer, primary_key=True),
    Column('Category', String),
    Column('AnomalyType', String),
    Column('Details', String),
    Column('RelatedRecord', String),
)

# Créer la table des anomalies si elle n'existe pas déjà
def create_anomalies_table(engine):
    metadata.create_all(engine)

# Fonction pour détecter les anomalies dans la colonne 'quantity'
def detect_quantity_anomalies(df):
    anomaly_results = []

    # Vérifier si la colonne 'quantity' existe dans le DataFrame
    if 'quantity' in df.columns:
        def is_numeric(value):
            try:
                # Tentative de conversion de la valeur en nombre entier ou décimal
                float(value)
                return True
            except ValueError:
                return False
        
        # Masque des valeurs non numériques
        non_numeric_mask = ~df['quantity'].apply(is_numeric)
        
        # Enregistrer les anomalies
        anomaly_results.extend([
            {
                "Category": "Point Anomalies",
                "AnomalyType": "Non-numeric Quantity",
                "Details": f"Column 'quantity' contains a non-numeric value.",
                "RelatedRecord": f"Transaction ID {i + 1}"  # Index starts from 0, so adding 1 for a 1-based index
            }
            for i in df[non_numeric_mask].index
        ])

    # Convertir les anomalies en DataFrame
    anomalies_df = pd.DataFrame(anomaly_results)
    
    return anomalies_df

# Insérer les anomalies détectées dans la table 'anomalieDetected'
def insert_anomalies(df, engine):
    # Créer la table des anomalies si elle n'existe pas déjà
    create_anomalies_table(engine)

    # Insérer les anomalies dans la table
    with engine.connect() as connection:
        for _, row in df.iterrows():
            # Vérifier si l'anomalie existe déjà
            stmt_select = select([anomalies_table]).where(
                (anomalies_table.c.Category == row['Category']) &
                (anomalies_table.c.AnomalyType == row['AnomalyType']) &
                (anomalies_table.c.Details == row['Details']) &
                (anomalies_table.c.RelatedRecord == row['RelatedRecord'])
            )
            result = connection.execute(stmt_select).fetchone()

            # Si l'anomalie n'existe pas, l'insérer
            if result is None:
                stmt_insert = anomalies_table.insert().values(
                    Category=row['Category'],
                    AnomalyType=row['AnomalyType'],
                    Details=row['Details'],
                    RelatedRecord=row['RelatedRecord']
                )
                connection.execute(stmt_insert)

# Tâche pour exécuter la détection d'anomalies
def run_anomaly_detection():
    df_anomaly = detect_quantity_anomalies(transactions)
    insert_anomalies(df_anomaly, engine)

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
    'Dag_Non-numeric-Quantity',
    default_args=default_args,
    description='Un DAG pour détecter les anomalies dans les transactions',
    schedule_interval='*/5 * * * *',  # Exécuter toutes les 5 minutes
    catchup=False,
)

# Opérateur Python pour exécuter la détection d'anomalies
anomaly_detection_task = PythonOperator(
    task_id='run_anomaly_detection',
    python_callable=run_anomaly_detection,
    dag=dag,
)

anomaly_detection_task
