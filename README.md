# Real-time Market Data Ingestion Pipeline on Google Cloud

## Overview

This repository contains the code and a comprehensive guide to deploy a real-time market data ingestion pipeline on Google Cloud Platform (GCP). The pipeline captures live stock tick data from Polygon.io, processes it using a Cloud Function, and stores it in a PostgreSQL database managed by Cloud SQL. This project demonstrates event-driven serverless architectures, private network connectivity, and robust data persistence in a cloud environment.

## Project Background

The primary goal of this project is to showcase how to build a scalable and managed solution for capturing continuous financial data streams. This kind of pipeline is fundamental for applications requiring real-time analytics, algorithmic trading, or dynamic dashboard updates. It addresses common challenges encountered in cloud deployments, such as setting up real-time messaging, secure private network connectivity, and managing Identity and Access Management (IAM) policies in an enterprise GCP context.

## Technical Requirements

To deploy and run this pipeline, you will need:

*   **Google Cloud Platform (GCP) Project:** Ensure you have an active GCP project. Replace `your-gcp-project-id` with your actual Project ID.
*   **GCP Billing Account:** Enabled for the project.
*   **Google Cloud SDK (`gcloud` CLI):** Installed and authenticated on your local machine or Cloud Shell.
    *   Ensure you are logged in: `gcloud auth login`
    *   Set your project: `gcloud config set project your-gcp-project-id`
*   **Python 3.11+:** Installed locally for the publisher script.
*   **Polygon.io API Key:** A valid API key from [Polygon.io](https://polygon.io/). This key is essential for fetching real-time market data.
*   **Cloud SQL Instance Private IP:** The private IP address of your Cloud SQL PostgreSQL instance will be needed for connection configuration. This will be dynamically retrieved during setup.
*   **Network Name:** Your project's VPC network name (e.g., `vpcdce` or `default`). Used for private connectivity.
*   **Cloud SQL Password:** A strong root password for your Cloud SQL instance.

## GCP Services Used & Their Roles

This solution leverages several key GCP services, each playing a specific role within the pipeline:

1.  **Cloud Pub/Sub:**
    *   **Role:** Real-time messaging service. Acts as the ingestion point for market tick data, decoupling data producers from consumers.
    *   **Interaction:** Receives data from the publisher and triggers the Cloud Function upon message arrival.
2.  **Cloud Functions (2nd Gen):**
    *   **Role:** Serverless compute platform. Processes incoming Pub/Sub messages, extracts market data, and inserts it into Cloud SQL. (2nd Gen functions run on Cloud Run).
    *   **Interaction:** Triggered by Pub/Sub, runs Python code, and connects to Cloud SQL.
3.  **Serverless VPC Access:**
    *   **Role:** Provides private network connectivity. Enables Cloud Functions (serverless) to securely connect to resources inside a Virtual Private Cloud (VPC), like Cloud SQL's private IP.
    *   **Interaction:** Acts as a bridge, routing traffic from the Cloud Function to Cloud SQL over the private network.
4.  **Cloud SQL (PostgreSQL):**
    *   **Role:** Fully managed relational database service. Stores the ingested market tick data persistently.
    *   **Interaction:** Receives data inserts from the Cloud Function via its private IP address.
5.  **Cloud Storage (GCS):**
    *   **Role:** Object storage service. Used as a staging bucket during Cloud Function deployment, where your function's code and dependencies are temporarily stored.
    *   **Interaction:** Cloud Build uploads the function's source code and dependencies to a GCS bucket before building the container image.
6.  **Cloud Build:**
    *   **Role:** CI/CD platform. Used by `gcloud functions deploy` (behind the scenes) to build the Cloud Function's container image from source code.
    *   **Interaction:** Executes build steps defined by the deployment process, pushing the resulting image to Artifact Registry.
7.  **Eventarc:**
    *   **Role:** Serverless eventing infrastructure. Manages the event triggers (e.g., Pub/Sub messages) for 2nd Gen Cloud Functions.
    *   **Interaction:** Ensures that new Pub/Sub messages reliably trigger the execution of the deployed Cloud Function.
8.  **Cloud Run:**
    *   **Role:** Fully managed compute platform. This is the underlying service where 2nd Gen Cloud Functions are hosted and executed.
    *   **Interaction:** Manages the scaling, execution, and networking of the Cloud Function instances.

## Architecture Diagram (Mermaid Syntax)

### Data Flow (Runtime Flow)

This diagram illustrates how data flows through the pipeline from the publisher to the database in real-time.

```mermaid
graph TD
    subgraph Publisher Application
        A[Python Script: market_data_publisher.py]
    end

    subgraph Google Cloud Platform (GCP)
        subgraph Cloud Pub/Sub
            B(Topic: market-tick-topic-sb)
            C(Subscription: market-tick-data-sub)
        end

        subgraph Cloud Functions (2nd Gen)
            D[Cloud Function: process_market_ticks]
        end

        subgraph Serverless VPC Access
            E[Connector: trading-vpc-connector]
        end

        subgraph Cloud SQL (PostgreSQL)
            F[Instance: trading-sql-instance-sb]
            G[Database: trading-db-sb<br>Table: market_ticks]
        end
    end

    A -- Sends JSON Data --> B
    B -- Message Published --> C
    C -- Triggers --> D
    D -- Private Connection via Connector --> E
    E -- Connects to Private IP --> F
    F -- Saves INSERT Data --> G
Service Deployment Flow (Setup Flow)
This diagram outlines the process of deploying and configuring the GCP services to enable the pipeline.

mermaid
graph TD
    subgraph User Interaction
        A[Developer (via gcloud CLI)]
    end

    subgraph GCP Core Services
        B(APIs Activated)
        C(Cloud SQL Instance & DB)
        D(Cloud Pub/Sub Topic & Subscription)
        E(Cloud Storage Bucket - Code Staging)
        F(Custom Cloud Function Service Account)
        G(Serverless VPC Access Connector)
    end

    subgraph Cloud Functions Backend
        H(Cloud Build: Container Build)
        I(Artifact Registry: Image Storage)
        J(Cloud Run: Function Hosting)
        K(Eventarc: Trigger Management)
    L(IAM Roles Assigned)
    end

    A -- Activate APIs --> B
    A -- Create/Configure --> C
    A -- Create/Configure --> D
    A -- Create/Configure --> E
    A -- Create/Configure --> F
    A -- Create/Configure --> G

    A -- Assign IAM Roles --> L
    L -- Enable Interaction For --> F
    L -- Enable Trigger For --> K

    A -- `gcloud functions deploy` --> H
    H -- Uploads Code & Dependencies --> E
    H -- Builds Image & Pushes --> I
    I -- Deploys as Service --> J
    J -- Is Configured by --> K
    K -- Manages Triggers for --> D & J
Installation & Deployment Guide
A. Initial IAM Setup
IAM is a critical enabling layer for all service interactions. Ensure these IAM roles are assigned in your your-gcp-project-id project. Replace placeholders like your-gcp-user-email@your-domain.com, your-gcp-project-id, and YOUR_PROJECT_NUMBER with your actual values.

For your user account (your-gcp-user-email@your-domain.com):

Editor (roles/editor): Highly recommended for initial setup and debugging, as it grants broad permissions for resource creation and management.

(Alternatively, if Editor is too broad or restricted by Organization Policy, ensure you have specific roles like Cloud SQL Admin, Pub/Sub Editor, Storage Admin, Cloud Functions Admin, Compute Network Admin, Service Account User, Project IAM Admin, Logs Viewer, Cloud Run Admin.)

For the Cloud Functions Service Account (trading-cf-sa@your-gcp-project-id.iam.gserviceaccount.com):

Cloud Functions Invoker (roles/cloudfunctions.invoker)

Pub/Sub Subscriber (roles/pubsub.subscriber)

Cloud SQL Client (roles/cloudsql.client)

Logs Writer (roles/logging.logWriter)

For the Pub/Sub Service Agent (service-YOUR_PROJECT_NUMBER@gcp-sa-pubsub.iam.gserviceaccount.com):

Cloud Run Invoker (roles/run.invoker) - Crucial for Pub/Sub to trigger 2nd Gen Cloud Functions. You can find your YOUR_PROJECT_NUMBER in your GCP Console dashboard (e.g., 403974804730).

B. One-Shot Setup and Deployment Script
This single shell script will handle the creation of all GCP resources, the configuration of IAM roles for service accounts, the creation of Python code files (with injected dynamic values), and the deployment of the Cloud Function.

Before Running:

Replace all your-gcp-project-id placeholders with your actual GCP Project ID.

Replace YOUR_CLOUD_SQL_PASSWORD with a strong password for your Cloud SQL instance.

Replace YOUR_VPC_NETWORK_NAME with your actual VPC network name (e.g., vpcdce or default).

Set your Polygon.io API Key as an environment variable in your shell: export POLYGON_API_KEY='YOUR_POLYGON_API_KEY_HERE' (replace with your actual key).

Execute the script: Copy the entire script below and paste it into your Cloud Shell terminal. Press Enter. This script is designed to be executed as one contiguous block.

bash
#!/bin/bash
# This script automates the full setup and deployment of a real-time market data ingestion pipeline on GCP.
#
# Before running:
# 1. Replace 'your-gcp-project-id' with your actual GCP Project ID.
# 2. Replace 'YOUR_CLOUD_SQL_PASSWORD' with a strong password for your Cloud SQL instance.
# 3. Replace 'YOUR_VPC_NETWORK_NAME' with your actual VPC network name (e.g., 'vpcdce' or 'default').
# 4. Set your Polygon.io API Key as an environment variable before executing this script:
#    export POLYGON_API_KEY='YOUR_POLYGON_API_KEY_HERE'
#    (Replace 'YOUR_POLYGON_API_KEY_HERE' with your actual Polygon.io API key)
#
# This script is designed to be executed as one contiguous block.
# It includes cleanup of potentially half-created resources from previous runs.

set -e # Exit immediately if a command exits with a non-zero status.

# --- User Configuration (REPLACE THESE PLACEHOLDERS) ---
PROJECT_ID="your-gcp-project-id"
CLOUD_SQL_PASSWORD="YOUR_CLOUD_SQL_PASSWORD"
VPC_NETWORK_NAME="YOUR_VPC_NETWORK_NAME" # e.g., vpcdce or default

# --- Dynamic Variables (Fetched during execution) ---
PROJECT_NUMBER=""
SQL_PRIVATE_IP=""
SERVICE_ACCOUNT_CF="trading-cf-sa@${PROJECT_ID}.iam.gserviceaccount.com"
PUB_SUB_SERVICE_AGENT=""

# --- Function to check if a resource is ready ---
wait_for_ready() {
    local RESOURCE_NAME="$1"
    local RESOURCE_TYPE="$2" # e.g., "sql instances", "compute networks vpc-access connectors"
    local FIELD="$3" # e.g., state, status
    local EXPECTED_VALUE="$4" # e.g., RUNNABLE, READY, ACTIVE

    echo "Waiting for ${RESOURCE_TYPE} (${RESOURCE_NAME}) to be ${EXPECTED_VALUE}..."
    for i in $(seq 1 120); do # Max 10 minutes (120 * 5s)
        CURRENT_STATE=$(gcloud "${RESOURCE_TYPE}" describe "${RESOURCE_NAME}" --project="${PROJECT_ID}" --format="value(${FIELD})" 2>/dev/null || echo "NOT_FOUND")
        if [[ "${CURRENT_STATE}" == "${EXPECTED_VALUE}" ]]; then
            echo "${RESOURCE_TYPE} is ${EXPECTED_VALUE}."
            return 0
        fi
        echo -n "."
        sleep 5
    done
    echo "Error: ${RESOURCE_TYPE} did not become ${EXPECTED_VALUE} in time."
    exit 1
}

# --- Cleanup Function (for re-runs) ---
cleanup_resources() {
    echo "--- Cleaning up previous resources (if any) ---"
    gcloud pubsub subscriptions delete market-tick-data-sub --project=${PROJECT_ID} --quiet || true
    gcloud pubsub topics delete market-tick-topic-sb --project=${PROJECT_ID} --quiet || true
    gcloud sql instances delete trading-sql-instance-sb --project=${PROJECT_ID} --quiet || true
    gsutil rb -f gs://${PROJECT_ID}-dataflow-temp/ || true
    gcloud iam service-accounts delete ${SERVICE_ACCOUNT_CF} --project=${PROJECT_ID} --quiet || true
    gcloud compute networks vpc-access connectors delete trading-vpc-connector --region=asia-southeast2 --project=${PROJECT_ID} --quiet || true
    
    # Attempt to remove IAM bindings to avoid conflicts (less aggressive than deleting SA)
    PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)" 2>/dev/null || echo "")
    if [[ -n "$PROJECT_NUMBER" ]]; then
        PUB_SUB_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"
        gcloud projects remove-iam-policy-binding ${PROJECT_ID} --member="serviceAccount:${PUB_SUB_SERVICE_AGENT}" --role="roles/run.invoker" --quiet || true
    fi
    sleep 10
    echo "--- Cleanup complete ---"
}

# --- Main Script Execution ---
echo "--- Starting Real-time Market Data Ingestion Pipeline Setup ---"

# Step 0: Initial Cleanup (Mandatory for a clean start)
cleanup_resources

# Step 1: Set Project ID
gcloud config set project ${PROJECT_ID}

# Step 2: Activate necessary APIs
echo "1. Activating necessary GCP APIs..."
gcloud services enable \
    cloudresourcemanager.googleapis.com \
    sqladmin.googleapis.com \
    pubsub.googleapis.com \
    storage.googleapis.com \
    cloudfunctions.googleapis.com \
    vpcaccess.googleapis.com \
    eventarc.googleapis.com \
    run.googleapis.com \
    --project=${PROJECT_ID} --quiet
sleep 60 # Wait for API activation propagation

# Step 3: Fetch Project Number (needed for Pub/Sub Service Agent)
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")
PUB_SUB_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"

# Step 4: Create Cloud SQL Instance (Private IP only)
echo "2. Creating Cloud SQL Instance..."
gcloud sql instances create trading-sql-instance-sb \
    --database-version=POSTGRES_14 \
    --region=asia-southeast2 \
    --root-password=${CLOUD_SQL_PASSWORD} \
    --database-flags=cloudsql.iam_authentication=Off \
    --tier=db-f1-micro \
    --storage-size=20GB \
    --storage-type=SSD \
    --network=${VPC_NETWORK_NAME} \
    --no-assign-public-ip \
    --project=${PROJECT_ID} \
    --quiet
wait_for_ready trading-sql-instance-sb "sql instances" state RUNNABLE

SQL_PRIVATE_IP=$(gcloud sql instances describe trading-sql-instance-sb --project=${PROJECT_ID} --format="value(ipAddresses.IP_ADDRESS.0)")
echo "Cloud SQL Private IP is: ${SQL_PRIVATE_IP}"

# Step 5: Create Cloud SQL Database & Table
echo "3. Creating database trading-db-sb and market_ticks table in Cloud SQL..."
gcloud sql databases create trading-db-sb \
    --instance=trading-sql-instance-sb \
    --project=${PROJECT_ID} --quiet
sleep 5 # Small delay for DB creation to register

# Connect to SQL and create table (requires user IAM to have Cloud SQL Admin)
gcloud sql connect trading-sql-instance-sb --user=postgres --project=${PROJECT_ID} <<EOF
CREATE TABLE IF NOT EXISTS market_ticks (
    symbol VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    volume INTEGER NOT NULL,
    PRIMARY KEY (symbol, timestamp)
);
EOF

# Step 6: Create Pub/Sub Topic and Subscription
echo "4. Creating Pub/Sub Topic and Subscription..."
gcloud pubsub topics create market-tick-topic-sb --project=${PROJECT_ID} --quiet
gcloud pubsub subscriptions create market-tick-data-sub \
    --topic=market-tick-topic-sb \
    --ack-deadline=600 \
    --message-retention-duration=7d \
    --project=${PROJECT_ID} --quiet

# Step 7: Create GCS Bucket for Cloud Function Staging
echo "5. Creating GCS Bucket for Cloud Function staging..."
gsutil mb -p ${PROJECT_ID} -l asia-southeast2 gs://${PROJECT_ID}-dataflow-temp

# Step 8: Create Cloud Functions Service Account
echo "6. Creating Cloud Functions Service Account (${SERVICE_ACCOUNT_CF})..."
gcloud iam service-accounts create trading-cf-sa \
    --display-name="Trading Cloud Function Service Account" \
    --project=${PROJECT_ID}

# Step 9: Create Serverless VPC Access Connector
echo "7. Creating Serverless VPC Access Connector..."
gcloud compute networks vpc-access connectors create trading-vpc-connector \
    --region=asia-southeast2 \
    --network=${VPC_NETWORK_NAME} \
    --range=10.8.0.0/28 \
    --project=${PROJECT_ID} \
    --quiet
wait_for_ready trading-vpc-connector "compute networks vpc-access connectors" state READY

# Step 10: Assign IAM Roles to Service Accounts
echo "8. Assigning necessary IAM roles..."
# Roles for Cloud Function Service Account
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_CF}" \
    --role="roles/cloudfunctions.invoker" --quiet
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_CF}" \
    --role="roles/pubsub.subscriber" --quiet
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_CF}" \
    --role="roles/cloudsql.client" --quiet
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_CF}" \
    --role="roles/logging.logWriter" --quiet
# Role for Pub/Sub Service Agent (to invoke Cloud Function)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${PUB_SUB_SERVICE_AGENT}" \
    --role="roles/run.invoker" --quiet
sleep 30 # Waiting for IAM role propagation

# Step 11: Create Code Files with Injected Values
echo "9. Creating Python code files with injected configuration..."

# market_data_publisher.py
cat <<EOF > market_data_publisher.py
import json
import time
import os
import random
import requests
from datetime import datetime, timezone
from google.cloud import pubsub_v1

# --- CONFIGURATION ---
PROJECT_ID = "${PROJECT_ID}"
TOPIC_ID = "market-tick-topic-sb"
POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY")

SYMBOLS = ["GOOGL", "AAPL", "MSFT", "AMZN", "NVDA", "TSLA", "META", "NFLX"] 
POLYGON_QUOTE_URL = "https://api.polygon.io/v2/last/trade/{ticker}"

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

def get_realtime_quote(symbol):
    if not POLYGON_API_KEY:
        print("Error: POLYGON_API_KEY environment variable not set.")
        return None

    url = POLYGON_QUOTE_URL.format(ticker=symbol)
    params = {"apiKey": POLYGON_API_KEY}

    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data and data.get("status") == "ok" and "results" in data and data["results"]:
            last_trade = data["results"]
            timestamp_ns = last_trade.get("t")
            dt_object = datetime.fromtimestamp(timestamp_ns / 1_000_000_000, tz=timezone.utc)
            iso_timestamp = dt_object.isoformat(timespec='milliseconds') + 'Z'

            return {
                "symbol": symbol,
                "timestamp": iso_timestamp,
                "price": last_trade.get("p"),
                "volume": last_trade.get("s")
            }
        elif data and data.get("status") == "ERROR":
            print(f"Polygon.io API Error for {symbol}: {data.get('error')}")
            return None
        else:
            print(f"No valid data or 'results' found for {symbol}. Response: {data}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Request to Polygon.io failed for {symbol}: {e}")
        return None
    except json.JSONDecodeError:
        print(f"Failed to decode JSON response for {symbol}. Response text: {response.text}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred in get_realtime_quote: {e}")
        return None

def publish_message(data):
    try:
        message_data = json.dumps(data).encode("utf-8")
        future = publisher.publish(topic_path, message_data)
        message_id = future.result()
        print(f"Published message ID: {message_id} -> {data['symbol']} Price: {data['price']} Volume: {data['volume']}")
        
    except Exception as e:
        print(f"Error publishing message to Pub/Sub: {e}")

if __name__ == "__main__":
    if not POLYGON_API_KEY:
        print("Please set the POLYGON_API_KEY environment variable before running this script.")
        print("Example: export POLYGON_API_KEY='YOUR_API_KEY'")
        exit(1)

    print("Starting market data publisher...")
    print(f"Publishing to topic: {topic_path}")
    print("Press Ctrl+C to stop.")
    
    try:
        while True:
            symbol_to_fetch = random.choice(SYMBOLS)
            tick_data = get_realtime_quote(symbol_to_fetch)
            
            if tick_data:
                publish_message(tick_data)
            
            time.sleep(random.uniform(1, 3))
    except KeyboardInterrupt:
        print("\nStopping publisher.")
    except Exception as e:
        print(f"An unexpected error occurred in main loop: {e}")
EOF

# main.py (Cloud Function Code)
cat <<EOF > main.py
import base64
import json
from datetime import datetime
import logging
import os
import pg8000.dbapi

# --- CLOUD SQL CONFIGURATION ---
DB_USER = "postgres"
DB_PASSWORD = "${CLOUD_SQL_PASSWORD}"
DB_HOST = "${SQL_PRIVATE_IP}"
DB_NAME = "trading-db-sb"
TABLE_NAME = "market_ticks"

# --- PUB/SUB CONFIGURATION ---
PROJECT_ID = os.environ.get('GCP_PROJECT')
PUB_SUB_SUBSCRIPTION = f"projects/{PROJECT_ID}/subscriptions/market-tick-data-sub"


class CloudSQLConnectionPool:
    _connection = None

    @classmethod
    def get_connection(cls):
        if cls._connection is None or not cls._connection._is_closed: # Check if connection exists and is open
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
        if cls._connection and not cls._connection._is_closed:
            cls._connection.close()
            logging.info("Cloud SQL connection closed.")

def process_pubsub_message(event, context):
    if 'data' not in event:
        logging.error('No data found in Pub/Sub message. Skipping processing.')
        return

    try:
        pubsub_message_data = base64.b64decode(event['data']).decode('utf-8')
        tick_data = json.loads(pubsub_message_data)

        logging.info(f"Received tick for {tick_data.get('symbol')} at price {tick_data.get('price')}.")

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
                conn.rollback()
            raise
        
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in Pub/Sub message: {e}. Message: {pubsub_message_data}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during message processing: {e}")
        raise
EOF

# requirements.txt
cat <<EOF > requirements.txt
requests
google-cloud-pubsub
pg8000
EOF

# Step 12: Deploy the Cloud Function
echo "10. Deploying the Cloud Function..."
gcloud functions deploy process_market_ticks \
    --runtime python311 \
    --trigger-topic market-tick-topic-sb \
    --entry-point process_pubsub_message \
    --region asia-southeast2 \
    --service-account ${SERVICE_ACCOUNT_CF} \
    --vpc-connector trading-vpc-connector \
    --timeout 30s \
    --set-env-vars DB_USER=postgres,DB_PASSWORD=${CLOUD_SQL_PASSWORD},DB_HOST=${SQL_PRIVATE_IP},DB_NAME=trading-db-sb \
    --project=${PROJECT_ID}

echo "--- Pipeline Setup and Deployment Complete ---"

echo "--- Next Steps: Run Publisher and Verify ---"
echo "1. Run the publisher: python3 market_data_publisher.py (in a new Cloud Shell tab)"
echo "2. Verify data in Cloud SQL Studio (check logs in Cloud Functions console too)"
E. Testing and Verification
After the script completes successfully, follow these steps to verify the pipeline's functionality:

Run the Market Data Publisher: Open a new Cloud Shell tab and execute:

bash
python3 market_data_publisher.py
This script will start fetching real-time data from Polygon.io and publishing it to Pub/Sub. Keep this tab open and running.

Confirm Pub/Sub Message Flow:

Go to GCP Console > Pub/Sub > Topics.

Click on your market-tick-topic-sb topic.

Go to the "Messages" tab.

Click "VIEW MESSAGES" and ensure "Pull" is selected. You should see messages appearing, indicating the publisher is actively sending data.

Monitor Cloud Function Logs (First Line of Defense):

Go to GCP Console > Cloud Functions.

Click on your process_market_ticks function.

Navigate to the "Logs" tab.

Observe the logs. You should expect to see INFO level entries from your Python code, such as:

Successfully connected to Cloud SQL: YOUR_CLOUD_SQL_PRIVATE_IP/trading-db-sb

Received tick for [SYMBOL] at price [PRICE].

Successfully inserted tick for [SYMBOL].

If you see any ERROR level logs, that indicates an issue within the function's execution or connectivity to Cloud SQL.

Verify Data in Cloud SQL (End-to-End Confirmation):

Go to GCP Console > SQL.

Click on your trading-sql-instance-sb instance.

Navigate to "Cloud SQL Studio".

Connect to your database (trading-db-sb) using postgres as the user and YOUR_CLOUD_SQL_PASSWORD as the password.

Execute the following SQL query to retrieve the latest data:

SQL
SELECT * FROM market_ticks ORDER BY timestamp DESC LIMIT 10;
Success Confirmation: If you see rows of market tick data appearing in the query results, your real-time data ingestion pipeline is successfully operational! This confirms data is flowing from Polygon.io, through your publisher, Pub/Sub, Cloud Function, and finally into your Cloud SQL database.

Cleanup
To avoid incurring unexpected charges, remember to clean up all created resources after you are done.

bash
# Set Project ID
gcloud config set project your-gcp-project-id

# Stop publisher script if running (Ctrl+C in its terminal)

# Delete Cloud Function
gcloud functions delete process_market_ticks --region=asia-southeast2 --project=your-gcp-project-id --quiet || true

# Delete Serverless VPC Access Connector
gcloud compute networks vpc-access connectors delete trading-vpc-connector --region=asia-southeast2 --project=your-gcp-project-id --quiet || true

# Delete Pub/Sub Subscription
gcloud pubsub subscriptions delete market-tick-data-sub --project=your-gcp-project-id --quiet || true

# Delete Pub/Sub Topic
gcloud pubsub topics delete market-tick-topic-sb --project=your-gcp-project-id --quiet || true

# Delete Cloud SQL Instance
gcloud sql instances delete trading-sql-instance-sb --project=your-gcp-project-id --quiet || true

# Delete GCS Bucket
gsutil rm -r gs://your-gcp-project-id-dataflow-temp/ || true

# Delete Cloud Functions Service Account
gcloud iam service-accounts delete trading-cf-sa@your-gcp-project-id.iam.gserviceaccount.com --project=your-gcp-project-id --quiet || true

# Important: Manually review and remove IAM roles assigned to your user account and the Pub/Sub Service Agent
# in GCP Console > IAM & Admin > IAM.
# E.g., Cloud SQL Admin, Cloud Functions Admin, Cloud Run Admin, Cloud Run Invoke
