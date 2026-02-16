import yfinance as yf
import json
import os
from datetime import datetime
import pytz
import pandas as pd
import logging

# --- Configuration and Constants ---
PORTFOLIO_FILE = "portfolio.json"
HISTORY_FILE = "stock_history.json"
LOG_FILE = "error_log.txt"
TZ = pytz.timezone('Israel')
MAX_HISTORY_ROWS = 10000 # Increased limit for long-term accumulation

# Setup logging
logging.basicConfig(
    filename=LOG_FILE, 
    level=logging.ERROR, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def ensure_files_exist():
    """Ensures critical files exist before processing to prevent CI/CD crashes."""
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)
            print(f"Created new {HISTORY_FILE}")
    
    if not os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
            # Default fallback if portfolio is missing
            json.dump({"SPY": 1}, f)
            print(f"Created default {PORTFOLIO_FILE}")

def load_json_safe(file_path):
    """Loads JSON file with a fallback for corrupted files."""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        logging.error(f"Failed to load {file_path}: {e}")
    return []

def main():
    ensure_files_exist()
    
    # Load portfolio holdings
    holdings_data = load_json_safe(PORTFOLIO_FILE)
    if isinstance(holdings_data, list): # Basic safety if format varies
        holdings = holdings_data[0] if holdings_data else {"SPY": 1}
    else:
        holdings = holdings_data

    tickers = list(holdings.keys())
    # Ensure SPY is always present for benchmark comparisons
    if "SPY" not in tickers:
        tickers.append("SPY")

    # Load existing history
    history = load_json_safe(HISTORY_FILE)

    # 1. Initial Backfill (If history is empty)
    if not history:
        print("Empty history detected. Starting 1-year backfill...")
        try:
            # Downloading 1 year of daily data
            data = yf.download(tickers, period="1y", interval="1d", progress=False)
            if not data.empty:
                close_prices = data['Close'].ffill().bfill()
                for date, row in close_prices.iterrows():
                    # Clean data: remove NaNs
                    prices = {t: round(float(v), 2) for t, v in row.to_dict().items() if pd.notna(v)}
                    if prices:
                        history.append({
                            "timestamp": date.strftime("%Y-%m-%d %H:%M:%S"),
                            "prices": prices
                        })
                print(f"Backfill complete. Added {len(history)} records.")
        except Exception as e:
            logging.error(f"Backfill failed: {e}")

    # 2. Current Sampling (Fetch latest prices)
    try:
        # Fetching latest 1-day data to get the most recent minute/close
        current_batch = yf.download(tickers, period="1d", interval="1m", progress=False)
        if not current_batch.empty:
            last_row = current_batch['Close'].iloc[-1]
            new_timestamp = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
            
            # Prepare and validate prices
            current_prices = {t: round(float(v), 2) for t, v in last_row.to_dict().items() if pd.notna(v)}
            
            # Deduplication: Check if we already sampled this minute
            is_duplicate = False
            if history:
                last_entry_ts = history[-1]['timestamp']
                # Check if same date and hour/minute
                if last_entry_ts[:16] == new_timestamp[:16]:
                    is_duplicate = True
            
            if not is_duplicate and current_prices:
                history.append({
                    "timestamp": new_timestamp,
                    "prices": current_prices
                })
                print(f"Added current sample at {new_timestamp}")
    except Exception as e:
        logging.error(f"Sampling error: {e}")
        print(f"Error sampling current prices: {e}")

    # 3. Save and Persist
    # We keep a large buffer (MAX_HISTORY_ROWS) to ensure long-term data accumulation
    # while preventing the file from growing to an unmanageable size for Git.
    history = sorted(history, key=lambda x: x['timestamp']) # Ensure chronological order
    final_history = history[-MAX_HISTORY_ROWS:]
    
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(final_history, f, indent=4)
        print(f"Successfully saved {len(final_history)} records to {HISTORY_FILE}")
    except Exception as e:
        logging.error(f"Save failed: {e}")

if __name__ == "__main__":
    main()
