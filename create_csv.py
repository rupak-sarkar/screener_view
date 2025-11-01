import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import os

tickers = ["AAPL", "GOOGL", "MSFT", "AMZN"]
end_date = datetime.now().date()
start_date = end_date - timedelta(days=2)
output_file = 'stock_data_last_2_days.csv'

final_df=pd.DataFrame()
for ticker in tickers:
    df = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
    if not df.empty:
        df = df.reset_index()
        df.columns=df.columns.get_level_values("Price")
        df['Ticker'] = ticker
        df = df[['Date', 'Ticker', 'Open', 'High', 'Low', 'Close', 'Volume']]
        final_df=pd.concat([final_df,df])
if final_df:
    final_df.to_csv(output_file, index=False)
    print(f"✅ Saved {len(final_df)} rows to {output_file}")
else:
    print("⚠️ No data fetched (check network or ticker symbols)")

