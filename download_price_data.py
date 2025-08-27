


import yfinance as yf
import pandas as pd
import os

tickers = set(pd.read_csv('data/insider_trades.csv')['ticker'])

# Create output folder
output_folder = "ticker_data"
os.makedirs(output_folder, exist_ok=True)


for ticker in tickers:
    file_path = os.path.join(output_folder, f"{ticker}.csv")
    
    # Check if file already exists
    if os.path.exists(file_path):
        print(f"Skipping {ticker}, file already exists.")
        continue

    try:
        # Download last 3 months of daily price data
        df = yf.download(
            ticker,
            period="10y",
            interval="1d",
            auto_adjust=True,
            multi_level_index=False
        )
        
        if df.empty or len(df) <= 5:
            continue

        # Save to CSV with ticker as filename
        file_path = os.path.join(output_folder, f"{ticker}.csv")
        df.to_csv(file_path)

        print(f"Saved {ticker} data to {file_path}")

    except Exception as e:
        print(f"Failed to download {ticker}: {e}")
