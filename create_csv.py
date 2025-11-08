
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import yfinance as yf
import os
import time

# Step 1: Scrape tickers from Screener.in
base_url = "https://www.screener.in/screens/2650136/good-stocks/?page="
hrefs = []

for page_num in range(1, 11):
    url = base_url + str(page_num)
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if 'company' in href:
                hrefs.append(href)
        time.sleep(1)  # polite scraping
    except Exception as e:
        print(f"Error fetching page {page_num}: {e}")

# Extract tickers
df_scraped = pd.DataFrame(hrefs, columns=['Column1'])
df_scraped['Company Name'] = df_scraped['Column1'].str.split('/').str[2]
df_scraped['Final Ticker'] = df_scraped['Company Name'] + '.NS'
df_scraped = df_scraped.drop_duplicates(subset='Final Ticker')

tickers = df_scraped['Final Ticker'].tolist()
end_date = datetime.now().date()
start_date = end_date - timedelta(days=1)
output_file = 'stock_data_last_2_days.csv'

final_df=pd.DataFrame()
for ticker in tickers:
    df = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
    if not df.empty:
        df = df.reset_index()
        df.columns=df.columns.get_level_values("Price")
        df['Ticker'] = ticker
        df = df[['Date', 'Ticker', 'Open', 'High', 'Low', 'Close', 'Volume']]
        df[['Open', 'High', 'Low', 'Close']] = df[['Open', 'High', 'Low', 'Close']].round(2)
        final_df=pd.concat([final_df,df])
if not final_df.empty:
    final_df.to_csv(output_file, mode='a', header=not os.path.exists(output_file), index=False)
    print(f"✅ Saved {len(final_df)} rows to {output_file}")
else:
    print("⚠️ No data fetched (check network or ticker symbols)")
