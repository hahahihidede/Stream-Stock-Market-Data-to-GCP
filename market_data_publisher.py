import json
import time
import os
import random
import requests
from datetime import datetime, timezone
from google.cloud import pubsub_v1

# --- CONFIGURATION ---
# Get GCP Project ID from environment variable.
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
TOPIC_ID = "market-tick-topic-sb"
# Get API key from environment variable (RECOMMENDED for security)
POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY")

# List of stock tickers to fetch
SYMBOLS = ["GOOGL", "AAPL", "MSFT", "AMZN", "NVDA", "TSLA", "META", "NFLX"] 

# Polygon.io API endpoint for last trade
POLYGON_QUOTE_URL = "https://api.polygon.io/v2/last/trade/{ticker}"

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

def get_realtime_quote(symbol):
    """Fetches a real-time last trade quote for a given symbol from Polygon.io."""
    if not POLYGON_API_KEY:
        print("Error: POLYGON_API_KEY environment variable not set.")
        return None

    url = POLYGON_QUOTE_URL.format(ticker=symbol)
    params = {"apiKey": POLYGON_API_KEY}

    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        
        if data and data.get("status") == "ok" and "results" in data and data["results"]:
            last_trade = data["results"]
            # Polygon.io timestamp is in Unix Nanoseconds for v2/last/trade. Convert to ISO 8601.
            timestamp_ns = last_trade.get("t") # 't' is the nanosecond timestamp
            dt_object = datetime.fromtimestamp(timestamp_ns / 1_000_000_000, tz=timezone.utc)
            iso_timestamp = dt_object.isoformat(timespec='milliseconds') + 'Z' # Ensure 'Z' for UTC

            return {
                "symbol": symbol,
                "timestamp": iso_timestamp,
                "price": last_trade.get("p"), # 'p' is price
                "volume": last_trade.get("s")  # 's' is size/volume
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
    """Publishes a market tick message to Pub/Sub."""
    try:
        message_data = json.dumps(data).encode("utf-8")
        future = publisher.publish(topic_path, message_data)
        message_id = future.result() # Blocks until the message is published
        print(f"Published message ID: {message_id} -> {data['symbol']} Price: {data['price']} Volume: {data['volume']}")
        
    except Exception as e:
        print(f"Error publishing message to Pub/Sub: {e}")

if __name__ == "__main__":
    # Validate that required environment variables are set
    if not PROJECT_ID:
        print("Error: The GCP_PROJECT_ID environment variable is not set.")
        print("Please set it to your Google Cloud Project ID and re-run the script.")
        print("Example: export GCP_PROJECT_ID='your-gcp-project-id'")
        exit(1)

    if not POLYGON_API_KEY:
        print("Error: The POLYGON_API_KEY environment variable is not set.")
        print("Please set it before running this script.")
        print("Example: export POLYGON_API_KEY='YOUR_API_KEY'")
        exit(1)

    print("Starting market data publisher...")
    print(f"Publishing to topic: {topic_path}")
    print("Press Ctrl+C to stop.")
    
    try:
        while True:
            # Randomly select a symbol from our list
            symbol_to_fetch = random.choice(SYMBOLS)
            tick_data = get_realtime_quote(symbol_to_fetch)
            
            if tick_data:
                publish_message(tick_data)
            
            # Wait for a random interval between 1 and 3 seconds
            time.sleep(random.uniform(1, 3))
    except KeyboardInterrupt:
        print("\nStopping publisher.")
    except Exception as e:
        print(f"An unexpected error occurred in main loop: {e}")

