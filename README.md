# Stream-Stock-Market-Data-to-GCP
1. Project Background
This project demonstrates a robust real-time data ingestion pipeline on Google Cloud Platform (GCP), designed to stream market tick data into a PostgreSQL database. It showcases a scalable and managed solution for continuous financial data capture, crucial for analytics, algorithmic trading, or real-time monitoring. The project highlights best practices for setting up cloud infrastructure, managing resources, and navigating complex Identity and Access Management (IAM) policies within an enterprise GCP environment.

2. Technical Requirements
To deploy and run this pipeline, you will need:

Google Cloud Platform (GCP) Project: Replace your-gcp-project-id with your actual GCP Project ID.

GCP Billing Account: Enabled for the project.

Google Cloud SDK (gcloud CLI): Installed and authenticated on your local machine or Cloud Shell.

Ensure gcloud auth login and gcloud config set project your-gcp-project-id are executed.

Python 3.11+: Installed locally for the publisher script.

Polygon.io API Key: A valid API key from Polygon.io. This key should be securely stored as an environment variable POLYGON_API_KEY for the publisher script.

Cloud SQL Instance Private IP: The private IP address of your Cloud SQL PostgreSQL instance will be needed for connection configuration. Use YOUR_CLOUD_SQL_PRIVATE_IP as a placeholder.

Network Name: Your project's VPC network name (e.g., vpcdce or default). Use YOUR_VPC_NETWORK_NAME as a placeholder.

Cloud SQL Password: The root password for your Cloud SQL instance. Use YOUR_CLOUD_SQL_PASSWORD as a placeholder.

3. GCP Services Used & Their Roles
This solution leverages several key GCP services, each playing a specific role:

Cloud Pub/Sub: A fully managed real-time messaging service. It acts as the ingestion point for market tick data, decoupling the data producer (publisher) from the data consumer (Cloud Function).

Cloud Functions (2nd Gen): A serverless compute platform that runs your code in response to events. It serves as the event-driven processor, triggered by new messages in Pub/Sub, parsing the data, and inserting it into Cloud SQL. (2nd Gen functions run on Cloud Run).

Serverless VPC Access: A networking feature that allows serverless environments (like Cloud Functions/Cloud Run) to connect to resources within a Virtual Private Cloud (VPC) network via a private IP address. This is crucial for connecting to Cloud SQL's private IP.

Cloud SQL (PostgreSQL): A fully managed relational database service. It serves as the durable storage layer for the ingested market tick data. Configured with private IP for enhanced security.

Cloud Storage (GCS): An object storage service. It's used as a staging bucket during the deployment of Cloud Functions, where your function's code and dependencies are temporarily stored.

Cloud Build: A serverless CI/CD platform. It's used by gcloud functions deploy behind the scenes to build your Cloud Function's container image from your source code.

Eventarc: A serverless eventing platform for GCP. For 2nd Gen Cloud Functions, Eventarc creates and manages the triggers that connect Pub/Sub messages to your Cloud Function.

Cloud Run: The fully managed compute platform that acts as the underlying infrastructure for Cloud Functions (2nd Gen). Your Cloud Function is deployed as a Cloud Run service.

4. Installation & Deployment Guide
A. Initial IAM Setup
Ensure these IAM roles are assigned in your your-gcp-project-id project. Replace placeholders like your-gcp-user-email@your-domain.com, your-gcp-project-id, and YOUR_PROJECT_NUMBER with your actual values.

For your user account (your-gcp-user-email@your-domain.com):

Editor (roles/editor): Highly recommended for initial setup and debugging.

(Alternatively, if Editor is too broad, ensure you have specific roles like Cloud SQL Admin, Pub/Sub Editor, Storage Admin, Cloud Functions Admin, Compute Network Admin, Service Account User, Project IAM Admin, Logs Viewer, Cloud Run Admin.)

For the Cloud Functions Service Account (trading-cf-sa@your-gcp-project-id.iam.gserviceaccount.com):

Cloud Functions Invoker (roles/cloudfunctions.invoker)

Pub/Sub Subscriber (roles/pubsub.subscriber)

Cloud SQL Client (roles/cloudsql.client)

Logs Writer (roles/logging.logWriter)

For the Pub/Sub Service Agent (service-YOUR_PROJECT_NUMBER@gcp-sa-pubsub.iam.gserviceaccount.com):

Cloud Run Invoker (roles/run.invoker) - Crucial for Pub/Sub to trigger 2nd Gen Cloud Functions. You can find your YOUR_PROJECT_NUMBER in your GCP Console dashboard.

B. Initial GCP Resource Setup (Step-by-Step Execution)
Execute these commands sequentially in your Cloud Shell. Replace all placeholders.

bash
# Set Project ID
gcloud config set project your-gcp-project-id

# Enable all necessary APIs
gcloud services enable \
    cloudresourcemanager.googleapis.com \
    sqladmin.googleapis.com \
    pubsub.googleapis.com \
    storage.googleapis.com \
    cloudfunctions.googleapis.com \
    vpcaccess.googleapis.com \
    eventarc.googleapis.com \
    run.googleapis.com \
    --project=your-gcp-project-id --quiet

sleep 60 # Wait for API activation propagation

# Clean up existing resources that might interfere (if any)
# Use || true to prevent script from stopping if resource not found
gcloud pubsub subscriptions delete market-tick-data-sub --project=your-gcp-project-id --quiet || true
gcloud pubsub topics delete market-tick-topic-sb --project=your-gcp-project-id --quiet || true
gcloud sql instances delete trading-sql-instance-sb --project=your-gcp-project-id --quiet || true
gsutil rb -f gs://your-gcp-project-id-dataflow-temp/ || true
gcloud iam service-accounts delete trading-cf-sa@your-gcp-project-id.iam.gserviceaccount.com --project=your-gcp-project-id --quiet || true
gcloud compute networks vpc-access connectors delete trading-vpc-connector --region=asia-southeast2 --project=your-gcp-project-id --quiet || true
sleep 10 # Give some time for deletion to propagate

# Create Cloud SQL Instance (PostgreSQL) - Private IP only
# Replace YOUR_VPC_NETWORK_NAME with your actual VPC network name (e.g., vpcdce or default)
gcloud sql instances create trading-sql-instance-sb \
    --database-version=POSTGRES_14 \
    --region=asia-southeast2 \
    --root-password=YOUR_CLOUD_SQL_PASSWORD \
    --database-flags=cloudsql.iam_authentication=Off \
    --tier=db-f1-micro \
    --storage-size=20GB \
    --storage-type=SSD \
    --network=YOUR_VPC_NETWORK_NAME \
    --no-assign-public-ip \
    --project=your-gcp-project-id \
    --quiet

# Wait for the instance to be ready
gcloud sql instances describe trading-sql-instance-sb --project=your-gcp-project-id --format="value(state)" | grep -q "RUNNABLE"

# Get Cloud SQL Private IP (needed for code configuration)
SQL_PRIVATE_IP=$(gcloud sql instances describe trading-sql-instance-sb --project=your-gcp-project-id --format="value(ipAddresses.IP_ADDRESS.0)")
echo "Cloud SQL Private IP is: $SQL_PRIVATE_IP"

# Create database in Cloud SQL
gcloud sql databases create trading-db-sb \
    --instance=trading-sql-instance-sb \
    --project=your-gcp-project-id --quiet

# Create initial table in Cloud SQL
# This requires your user account to have Cloud SQL Admin role
(gcloud sql connect trading-sql-instance-sb --user=postgres --project=your-gcp-project-id <<EOF
CREATE TABLE IF NOT EXISTS market_ticks (
    symbol VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    volume INTEGER NOT NULL,
    PRIMARY KEY (symbol, timestamp)
);
EOF
) || true # Use || true to prevent script from stopping if connection has issues but table is created

# Create Pub/Sub Topic
gcloud pubsub topics create market-tick-topic-sb \
    --project=your-gcp-project-id --quiet

# Create Pub/Sub Subscription
gcloud pubsub subscriptions create market-tick-data-sub \
    --topic=market-tick-topic-sb \
    --ack-deadline=600 \
    --message-retention-duration=7d \
    --project=your-gcp-project-id --quiet

# Create GCS Bucket for Cloud Function Staging
# Replace your-gcp-project-id with your actual project ID in the bucket name
gsutil mb -p your-gcp-project-id -l asia-southeast2 gs://your-gcp-project-id-dataflow-temp

# Create Cloud Functions Service Account
gcloud iam service-accounts create trading-cf-sa \
    --display-name="Trading Cloud Function Service Account" \
    --project=your-gcp-project-id

# Create Serverless VPC Access Connector
# Replace YOUR_VPC_NETWORK_NAME with your actual VPC network name (e.g., vpcdce or default)
gcloud compute networks vpc-access connectors create trading-vpc-connector \
    --region=asia-southeast2 \
    --network=YOUR_VPC_NETWORK_NAME \
    --range=10.8.0.0/28 \
    --project=your-gcp-project-id \
    --quiet
echo "Connector creation may take 2-3 minutes. Please wait."
gcloud compute networks vpc-access connectors describe trading-vpc-connector --region=asia-southeast2 --project=your-gcp-project-id --format="value(state)" | grep -q "READY"

echo "Initial GCP resource setup complete!"
echo "Please update YOUR_CLOUD_SQL_PRIVATE_IP in main.py with the IP you got from 'echo \$SQL_PRIVATE_IP' command."
C. Source Code Files
Create these files in your local project directory or Cloud Shell. Remember to replace placeholders.

market_data_publisher.py
This script fetches real-time "last trade" data from Polygon.io and publishes it to a Pub/Sub topic. Set your Polygon.io API Key as an environment variable POLYGON_API_KEY.
