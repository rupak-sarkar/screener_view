import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import os

tickers = ["AAPL", "GOOGL", "MSFT", "AMZN"]
end_date = datetime.now().date()
start_date = end_date - timedelta(days=2)
output_file = 'stock_data_last_2_days.csv'

all_data = []
for ticker in tickers:
    df = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
    if not df.empty:
        df = df.reset_index()
        df['Ticker'] = ticker
        df = df[['Date', 'Ticker', 'Open', 'High', 'Low', 'Close', 'Volume']]
        all_data.append(df)

if all_data:
    final_df = pd.concat(all_data, ignore_index=True)
    final_df.rename(columns={'Date': 'date'}, inplace=True)
    final_df['date'] = pd.to_datetime(final_df['date']).dt.strftime('%m/%d/%Y')
    final_df = final_df.round(2)
    final_df.to_csv(output_file, index=False)
    print(f"✅ Saved {len(final_df)} rows to {output_file}")
else:
    print("⚠️ No data fetched (check network or ticker symbols)")
