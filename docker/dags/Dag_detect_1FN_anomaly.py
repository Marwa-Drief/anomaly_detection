from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String , select,DECIMAL
import pandas as pd
from datetime import datetime,timedelta

# Informations de connexion
user = 'postgres'
password = 'postgres'
host = '172.19.0.3'
port = '5432'
database = 'anomaly_detection'
# URL de la base de données
db_url = f'postgresql://{user}:{password}@{host}:{port}/{database}'
# Créer le moteur SQLAlchemy
engine = create_engine(db_url)

# Définir les métadonnées
metadata = MetaData()

def connect_to_db():
    return engine.connect()
connection=connect_to_db()
def get_table_names(connection):
    tables_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
    tables_result = connection.execute(tables_query)
    return [row['table_name'] for row in tables_result]
table_name=get_table_names(connection)
def table_to_dataframe(table_name, connection):
    table = Table(table_name, metadata, autoload_with=engine, schema='public')
    stmt = select(table)
    result = connection.execute(stmt)
    return pd.DataFrame(result.fetchall(), columns=result.keys())
#Appliquer sur les tables
customers= table_to_dataframe('customers',connection)
transactions= table_to_dataframe('transactions',connection)
products= table_to_dataframe('products',connection)
orders= table_to_dataframe('orders',connection)
orderdetails= table_to_dataframe('orderdetails',connection)
productsuppliers= table_to_dataframe('productsuppliers',connection)
dataframes = {
    'orderdetails': orderdetails,
    'productsuppliers': productsuppliers,
    'transactions': transactions,
    'products': products,
    'orders': orders,
    'customers': customers
}
#fermer la connextion 
connection.close()
#first task function
def detect__insert_anomalie():
    def detect_1nf_violations(df):
        anomalies = []

        for column in df.columns:
            # Check if the column contains non-atomic values (strings with delimiters like commas)
            non_atomic_values = df[column].apply(lambda x: isinstance(x, str) and (',' in x or ';' in x or '|' in x))
            
            violating_records = df[non_atomic_values].index.tolist()
            
            for record_id in violating_records:
                anomalies.append({
                    "Category": "1NF Violation",
                    "AnomalyType": "Non-Atomic Values",
                    "Details": f"Column '{column}' contains non-atomic values: {df.at[record_id, column]}.",
                    "RelatedRecord": f"Orders ID {record_id + 1}"  # Assuming record ID is index + 1
                })

        # Return a DataFrame with the anomalies
        if anomalies:
            anomalies_df = pd.DataFrame(anomalies)
        else:
            anomalies_df = pd.DataFrame(columns=["Category", "AnomalyType", "Details", "RelatedRecord"])
        
        return anomalies_df

   

    # Définir la table des anomalies
    anomalies_table = Table('anomalieDetected', metadata,
        Column('id', Integer, primary_key=True),
        Column('Category', String),
        Column('AnomalyType', String),
        Column('Details', String),
        Column('RelatedRecord', String),
    )

    # Créer la table si elle n'existe pas déjà
    def create_anomalies_table(engine):
        metadata.create_all(engine)

    # Insérer les anomalies détectées dans la base de données
    def insert_anomalies(df, engine2):
        # Créer la table des anomalies si elle n'existe pas déjà
        create_anomalies_table(engine2)

        # Créer une connexion à la base de données
        with engine2.connect() as connection2:
            for _, row in df.iterrows():
                # Vérifier si la ligne existe déjà
                stmt_select = select([anomalies_table]).where(
                    (anomalies_table.c.Category == row['Category']) &
                    (anomalies_table.c.AnomalyType == row['AnomalyType']) &
                    (anomalies_table.c.Details == row['Details']) &
                    (anomalies_table.c.RelatedRecord == row['RelatedRecord'])
                )

                result = connection2.execute(stmt_select).fetchone()

                # Si la ligne n'existe pas, l'insérer
                if result is None:
                    stmt_insert = anomalies_table.insert().values(
                        Category=row['Category'],
                        AnomalyType=row['AnomalyType'],
                        Details=row['Details'],
                        RelatedRecord=row['RelatedRecord']
                    )
                    connection2.execute(stmt_insert)
    anomalies_df = detect_1nf_violations(orders)
    insert_anomalies(anomalies_df, engine)
"""def correct_anomalie1fN():
    def correct_first_normal_form(df):
        # Initialiser une liste pour stocker les nouvelles lignes
        corrected_rows = []
        
        # Initialiser l'identifiant de la nouvelle commande
        new_order_id = 1
        
        # Parcourir chaque ligne de la DataFrame originale
        for index, row in df.iterrows():
            # Séparer les product_ids en liste
            product_ids = row['product_ids'].split(',')
            # Calculer le montant total par produit
            individual_amount = float(row['total_amount']) / len(product_ids)
            
            # Créer une nouvelle ligne pour chaque product_id
            for product_id in product_ids:
                corrected_rows.append({
                    'order_id': new_order_id,
                    'customer_id': row['customer_id'],
                    'product_id': product_id,
                    'order_date': row['order_date'],
                    'total_amount': individual_amount
                })
                new_order_id += 1  # Incrémenter l'identifiant de la commande
        
        # Convertir la liste de nouvelles lignes en DataFrame
        corrected_df = pd.DataFrame(corrected_rows)
    
        return corrected_df
    # Créer le moteur SQLAlchemy
    engine = create_engine(db_url)
    # Définir les métadonnées
    metadata = MetaData()
    connection=engine.connect
    ## Définir la table new_orders
    new_orders_table = Table('new_orders', metadata,
        Column('order_id', Integer, primary_key=True),
        Column('customer_id', Integer),
        Column('product_id', Integer),
        Column('order_date', String),  # Utilisez String si la date est au format chaîne
        Column('total_amount', DECIMAL(10, 2))
    )

    # Créer la table dans la base de données
    def create_new_orders_table(engine):
        metadata.create_all(engine)
    create_new_orders_table(engine)
    table_name = "new_orders"
    # Insérer les données dans la table new_orders
    def insert_dataframe_line_by_line(df, engine, table):
        
        with engine.connect() as connection:
        # Insérer les données ligne par ligne
            for _, row in df.iterrows():
                stmt = table.insert().values(
                    order_id=row['order_id'],
                    customer_id=row['customer_id'],
                    product_id=row['product_id'],
                    order_date=row['order_date'],
                    total_amount=row['total_amount']
                )
                connection.execute(stmt)
    #Appliquer la correction
    new_orders=correct_first_normal_form(orders)
    insert_dataframe_line_by_line(new_orders,engine,new_orders_table)"""

def detect_1nf_insert_anomalie():
    detect__insert_anomalie()
"""def correct_insert_new_table1FN():
    correct_anomalie1fN()"""


# Définir le DAG d'Airflow
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
    'detect_1fn_anomalies_dag',
    default_args=default_args,
    description='DAG pour détecter et insérer les anomalies dans la base de données',
    schedule_interval='*/5 * * * *',  # Exécuter toutes les 5 minutes
    #schedule_interval='@hourly',  # Exécuter toutes les heures
    catchup=False,
)

# Définir la tâche
detect_and_insert_task = PythonOperator(
    task_id='detect_1nf_and_insert_anomalies',
    python_callable=detect_1nf_insert_anomalie,
    dag=dag,
)
# Définir la tâche
"""correct_and_insert_task = PythonOperator(
    task_id='correct_1nf_and_insert_anomalies',
    python_callable=correct_insert_new_table1FN,
    dag=dag,
)"""

detect_and_insert_task
