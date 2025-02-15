from flask import Flask, render_template, request, jsonify
import psycopg2
from psycopg2 import OperationalError
import pandas as pd
import io
from flask import send_file
from datetime import datetime

app = Flask(__name__)

def create_conn(db_name="anomaly_detection"):
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user="postgres",
            password="postgres",
            host="localhost",
            port="5432"
        )
    except OperationalError as e:
        print(f"The error '{e}' occurred")
    return conn

def fetch_anomalies(category_filter=None, type_filter=None):
    conn = create_conn()
    cursor = conn.cursor()
    
    query = 'SELECT * FROM "anomalieDetected" WHERE TRUE'
    params = []
    
    if category_filter:
        query += ' AND "Category" = %s'
        params.append(category_filter)
    
    if type_filter:
        query += ' AND "AnomalyType" = %s'
        params.append(type_filter)
    
    cursor.execute(query, tuple(params))
    anomalies = cursor.fetchall()
    cursor.close()
    conn.close()
    return anomalies



@app.route('/')
def index():
    category_filter = request.args.get('category', None)
    type_filter = request.args.get('type', None)
    
    anomalies = fetch_anomalies(category_filter, type_filter)
    return render_template('index.html', anomalies=anomalies)

@app.route('/get_suggestions')
def get_suggestions():
    anomaly_type = request.args.get('anomaly_type')
    
    suggestions_dict = {
        "Excessively High Total Amount": [
            "Review the transaction details for any data entry errors.",
            "Check if multiple items were accidentally entered as a single high-value item.",
            "Verify if there's a decimal point misplacement in the total amount.",
            "Investigate if this is a legitimate high-value transaction (e.g., bulk purchase).",
            "Compare with the customer's purchase history to see if this is unusual."
        ],
        "Customer ID is not valid or missing": [
            "Check the customer database for any recent updates or migrations.",
            "Verify if the customer ID was entered correctly at the point of sale.",
            "Investigate if there's a system issue preventing proper customer ID assignment.",
            "Consider implementing a validation check for customer IDs at data entry points.",
            "Review the process for handling anonymous or guest transactions."
        ],
        "Non-Atomic Values": [
            "Review the data entry process for the 'product_ids' field.",
            "Implement data validation to ensure only single values are entered in this field.",
            "Check if there's a need to support multiple product IDs, and if so, redesign the field.",
            "Investigate if this is a result of a data migration or system integration issue.",
            "Train staff on proper data entry procedures for product IDs."
        ],
        "Multiple Transactions in a Short Timeframe": [
            "Review the transactions to determine if they are legitimate (e.g., bulk buying).",
            "Check for potential duplicate entries or system glitches causing repeated submissions.",
            "Implement a warning system for rapid successive transactions from the same customer.",
            "Investigate if this pattern indicates potential fraudulent activity.",
            "Consider implementing a cool-down period or captcha for online transactions."
        ],
        "Negative Value": [
            "Check if this is a legitimate negative entry (e.g., a refund or adjustment).",
            "Verify the data entry process for handling returns or corrections.",
            "Implement validation to prevent accidental negative entries for standard transactions.",
            "Review the system's handling of currency or unit conversions.",
            "Investigate if there's a software bug causing incorrect sign for certain transactions."
        ],
        "Non-numeric Value": [
            "Review the data type constraints in the database for this field.",
            "Check for any recent changes in data input forms that might allow non-numeric entries.",
            "Implement strict input validation for numeric fields in all entry points.",
            "Investigate if this is caused by a character encoding or data conversion issue.",
            "Review and standardize the process for handling special cases (e.g., 'N/A' entries)."
        ]
    }
    
    suggestions = suggestions_dict.get(anomaly_type, [
        "Review the data for inconsistencies related to this specific anomaly type.",
        "Consult with the relevant department for clarification on this unusual data pattern.",
        "Consider implementing additional data validation rules to prevent this type of anomaly.",
        "Investigate recent system changes or updates that might have introduced this issue.",
        "Document this anomaly type for future reference and potential system improvements."
    ])
    
    return jsonify(suggestions=suggestions)
def fetch_statistics():
    conn = create_conn()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM "anomalieDetected"')
    total_anomalies = cursor.fetchone()[0]
    
    # Count anomalies by time period
    cursor.execute('''
        SELECT COUNT(*) FROM "anomalieDetected" WHERE "detected_at" >= NOW() - INTERVAL '1 day'
    ''')
    anomalies_per_day = cursor.fetchone()[0]

    cursor.execute('''
        SELECT COUNT(*) FROM "anomalieDetected" WHERE "detected_at" >= NOW() - INTERVAL '1 week'
    ''')
    anomalies_per_week = cursor.fetchone()[0]

    cursor.execute('''
        SELECT COUNT(*) FROM "anomalieDetected" WHERE "detected_at" >= NOW() - INTERVAL '1 month'
    ''')
    anomalies_per_month = cursor.fetchone()[0]

    cursor.execute('''
        SELECT COUNT(*) FROM "anomalieDetected" WHERE "detected_at" >= NOW() - INTERVAL '1 year'
    ''')
    anomalies_per_year = cursor.fetchone()[0]

    cursor.execute('''
        SELECT "Category", COUNT(*) 
        FROM "anomalieDetected"
        GROUP BY "Category"
    ''')
    anomalies_by_category = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return {
        'total_anomalies': total_anomalies,
        'anomalies_per_day': anomalies_per_day,
        'anomalies_per_week': anomalies_per_week,
        'anomalies_per_month': anomalies_per_month,
        'anomalies_per_year': anomalies_per_year,
        'anomalies_by_category': anomalies_by_category
    }

def fetch_anomalies_by_table():
    conn = create_conn()
    cursor = conn.cursor()
    
    table_names = ["Customers", "Products", "Transaction", "Orders", "OrderDetails"]
    
    anomalies_by_table = {table_name: 0 for table_name in table_names}
    
    for table_name in table_names:
        cursor.execute(f'''
            SELECT COUNT(*)
            FROM "anomalieDetected"
            WHERE "RelatedRecord" LIKE %s
        ''', (f'{table_name} ID%',))
        count = cursor.fetchone()[0]
        anomalies_by_table[table_name] = count
    
    cursor.close()
    conn.close()
    
    return anomalies_by_table

@app.route('/statistiques')
def statistiques():
    today_date = datetime.now().strftime('%Y-%m-%d')
    
    # Get statistics
    try:
        stats = fetch_statistics()
    except Exception as e:
        print(f"Error fetching statistics: {e}")
        stats = {
            'total_anomalies': 0,
            'anomalies_per_day': 0,
            'anomalies_per_week': 0,
            'anomalies_per_month': 0,
            'anomalies_per_year': 0,
            'anomalies_by_category': []
        }
    
    # Get anomalies by table
    try:
        anomalies = fetch_anomalies_by_table()
    except Exception as e:
        print(f"Error fetching anomalies by table: {e}")
        anomalies = {table: 0 for table in ["Customers", "Products", "Transaction", "Orders", "OrderDetails"]}
    
    return render_template('statistiques.html', 
                           stats=stats, 
                           anomalies=anomalies,
                           current_date=today_date)

@app.route('/download_csv')
def download_csv():
    conn = create_conn()
    
    query = 'SELECT "Category", "AnomalyType", "Details", "RelatedRecord" FROM "anomalieDetected"'
    df = pd.read_sql_query(query, conn)
    
    conn.close()
    
    csv = df.to_csv(index=False)
    buffer = io.BytesIO(csv.encode())
    
    return send_file(
        io.BytesIO(buffer.getvalue()),
        download_name='anomalies.csv',
        as_attachment=True,
        mimetype='text/csv'
    )

@app.route('/get_anomalies_by_category')
def get_anomalies_by_category():
    stats = fetch_statistics()
    categories, counts = zip(*stats['anomalies_by_category'])
    return jsonify({
        'categories': categories,
        'counts': counts
    })

@app.route('/get_anomalies_by_table')
def get_anomalies_by_table():
    anomalies_by_table = fetch_anomalies_by_table()
    tables, counts = zip(*anomalies_by_table.items())
    return jsonify({
        'tables': tables,
        'counts': counts
    })

@app.route('/about_anomalies')
def about_anomalies():
    return render_template('about_anomalies.html')
@app.route('/correct_anomaly', methods=['POST'])
def correct_anomaly():
    conn = create_conn("corr")  # Utilise la base de données "corr"
    cursor = conn.cursor()
   
   
    try:
        # Corriger les quantités négatives avec un cast explicite
        cursor.execute("""
            UPDATE "transactions"
            SET quantity = ABS(quantity::numeric)
            WHERE quantity::numeric < 0
        """)
        quantities_corrected = cursor.rowcount
        
        # Corriger les montants totaux négatifs avec un cast explicite
        cursor.execute("""
            UPDATE "transactions"
            SET total_amount = ABS(total_amount::numeric)
            WHERE total_amount::numeric < 0
        """)
        amounts_corrected = cursor.rowcount
        
        conn.commit()
        return jsonify({
            'success': True, 
            'message': f'Corrections appliquées avec succès. Quantités: {quantities_corrected}, Montants: {amounts_corrected}'
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
        
    finally:
        cursor.close()
        conn.close()



if __name__ == '__main__':
    app.run(debug=True, port=3002)