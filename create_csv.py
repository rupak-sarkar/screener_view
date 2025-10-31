import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import os

# Define tickers
tickers = ["AAPL", "GOOGL", "MSFT", "AMZN"]

# Date range: last 2 days
end_date = datetime.now().date()
start_date = end_date - timedelta(days=2)

# Output file
output_file = 'stock_data_last_2_days.csv'

# Fetch and format data
all_data = []
for ticker in tickers:
    data = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
    if not data.empty:
        data.reset_index(inplace=True)
        data['Ticker'] = ticker
        data = data[['Date', 'Ticker', 'Open', 'High', 'Low', 'Close', 'Volume']]
        all_data.append(data)

# Combine all tickers into one DataFrame
if all_data:
    final_df = pd.concat(all_data, ignore_index=True)
    final_df.rename(columns={'Date': 'date'}, inplace=True)
    final_df['date'] = final_df['date'].dt.strftime('%m/%d/%Y')  # Format date
    final_df = final_df.round(2)  # Round numeric values
    final_df.to_csv(output_file, index=False)
    print(f"✅ Saved {len(final_df)} rows to {output_file}")
else:
    print("⚠️ No data fetched (check network or ticker symbols)")
