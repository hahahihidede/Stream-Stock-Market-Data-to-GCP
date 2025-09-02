import base64
import json
from datetime import datetime
import logging
import os
import pg8000.dbapi

# --- CLOUD SQL CONFIGURATION ---
# These variables are intended to be set via environment variables,
# as shown in the deployment command in the README.
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD") # No default, should be injected.
DB_HOST = os.environ.get("DB_HOST")         # No default, should be injected.
DB_NAME = os.environ.get("DB_NAME", "trading-db-sb")
TABLE_NAME = "market_ticks"

# --- PUB/SUB CONFIGURATION ---
PROJECT_ID = os.environ.get('GCP_PROJECT') # Gets project ID from Cloud Functions environment
PUB_SUB_SUBSCRIPTION = f"projects/{PROJECT_ID}/subscriptions/market-tick-data-sub"


class CloudSQLConnectionPool:
    _connection = None # Using a simple singleton for demonstration; production might use proper pooling

    @classmethod
    def get_connection(cls):
        if cls._connection is None or not cls._connection.is_open: # Check if connection exists and is open
            try:
                cls._connection = pg8000.dbapi.connect(
                    user=DB_USER,
                    password=DB_PASSWORD,
                    host=DB_HOST,
                    database=DB_NAME
                )
                logging.info(f"Successfully established new Cloud SQL connection to {DB_HOST}/{DB_NAME}")
            except Exception as e:
                logging.error(f"Failed to connect to Cloud SQL: {e}")
                raise
        return cls._connection

    @classmethod
    def close_connection(cls):
        if cls._connection and cls._connection.is_open:
            cls._connection.close()
            logging.info("Cloud SQL connection closed.")

def process_pubsub_message(event, context):
    """
    Cloud Function triggered by a Pub/Sub message.
    Parses tick data and inserts it into Cloud SQL.
    """
    
    if 'data' not in event:
        logging.error('No data found in Pub/Sub message. Skipping processing.')
        return

    try:
        # Pub/Sub message data is base64 encoded
        pubsub_message_data = base64.b64decode(event['data']).decode('utf-8')
        tick_data = json.loads(pubsub_message_data)

        logging.info(f"Received tick for {tick_data.get('symbol')} at price {tick_data.get('price')}.")

        # Convert timestamp string to datetime object
        # Ensure timestamp format from publisher expects 'Z' for UTC
        tick_data['timestamp'] = datetime.fromisoformat(tick_data['timestamp'])

        conn = None
        try:
            conn = CloudSQLConnectionPool.get_connection()
            cursor = conn.cursor()

            insert_query = f"""
            INSERT INTO {TABLE_NAME} (symbol, timestamp, price, volume)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (symbol, timestamp) DO NOTHING;
            """

            cursor.execute(insert_query, (
                tick_data['symbol'],
                tick_data['timestamp'],
                tick_data['price'],
                tick_data['volume']
            ))
            conn.commit()
            logging.info(f"Successfully inserted tick for {tick_data['symbol']}.")

        except Exception as e:
            logging.error(f"Error inserting data for {tick_data.get('symbol')}: {e}")
            if conn:
                conn.rollback()  # Rollback transaction on error
            raise  # Re-raise for Cloud Functions error handling
        finally:
            # Ensure the connection is closed after each invocation.
            CloudSQLConnectionPool.close_connection()
        
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in Pub/Sub message: {e}. Message: {pubsub_message_data}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during message processing: {e}")
        raise # Re-raise for Cloud Functions error handling

