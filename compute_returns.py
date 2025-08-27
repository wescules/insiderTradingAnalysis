import pandas as pd
import os
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm

def get_ticker_price_history(ticker):
    prices = pd.read_csv(f"ticker_data/{ticker}.csv", skiprows=3, 
                             names=["Date", "Close", "High", "Low", "Open", "Volume"], parse_dates=["Date"], index_col="Date")
    for col in ["Close", "High", "Low", "Open", "Volume"]:
        prices[col] = pd.to_numeric(prices[col], errors="coerce")
    return prices

def compute_forward_returns(ticker, trade_date, horizons=[1, 5, 15, 30, 60, 90, 180]):
    filepath = f"ticker_data/{ticker}.csv"
    if not os.path.exists(filepath):
        return {f"fwd_{h}d": None for h in horizons}
    
    # Load price history
    prices = get_ticker_price_history(ticker)
    prices.sort_index(inplace=True)

    # If trade_date is not a trading day, move forward to next available trading day
    if trade_date not in prices.index:
        future_dates = prices.index[prices.index >= trade_date]
        if future_dates.empty:
            return {f"fwd_{h}d": None for h in horizons}
        trade_date = future_dates[0]

    results = {}
    entry_price = prices.loc[trade_date, "Close"]

    trade_idx = prices.index.get_loc(trade_date)
    for h in horizons:
        future_idx = trade_idx + h
        if future_idx < len(prices):
            future_price = prices.iloc[future_idx]["Close"]
            results[f"fwd_{h}d"] = ((future_price - entry_price) / entry_price) * 100
        else:
            results[f"fwd_{h}d"] = None
    return results

# Apply to all trades
def process_row(row):
    # print(f"Processing row: {row['ticker']} on {row['trade_date']}")
    ticker = row["ticker"]
    trade_date = row["trade_date"]
    returns = compute_forward_returns(ticker, trade_date)
    return {**row.to_dict(), **returns}


if __name__ == '__main__':
    # Load insider trades
    print("Loading insider trades...")
    trades = pd.read_csv("data/insider_trades.csv", parse_dates=["trade_date"])

    # Strip time part from trade_date
    print("Normalizing trade dates...")
    trades["trade_date"] = trades["trade_date"].dt.normalize()  # keep only YYYY-MM-DD

    print("Computing forward returns...")
    all_returns = []
    with ProcessPoolExecutor() as executor:
        results = list(tqdm(
            executor.map(process_row, [row for _, row in trades.iterrows()]),
            total=len(trades),
            desc="Processing trades"
        ))
        all_returns.extend(results)


    print("Saving results...")
    results_df = pd.DataFrame(all_returns)
    results_df.to_csv("insider_trades_with_returns.csv", index=False)

