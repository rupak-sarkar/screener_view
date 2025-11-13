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

final_df = pd.DataFrame()
usd_to_inr = 83.0  # Approx conversion rate

for ticker in tickers:
    try:
        # Download price data
        df = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
        if not df.empty:
            df = df.reset_index()
            df.columns = df.columns.get_level_values("Price")
            df['Ticker'] = ticker
            df = df[['Date', 'Ticker', 'Open', 'High', 'Low', 'Close', 'Volume']]
            df[['Open', 'High', 'Low', 'Close']] = df[['Open', 'High', 'Low', 'Close']].round(2)

            # Fetch additional info
            stock = yf.Ticker(ticker)
            info = stock.info
            market_cap = info.get('marketCap', None)
            industry = info.get('industry', None)

            # Get balance sheet for Debt/Equity
            balance_sheet = stock.balance_sheet
            if not balance_sheet.empty:
                total_debt = balance_sheet.loc['Total Liabilities'][0] if 'Total Liabilities' in balance_sheet.index else None
                total_equity = balance_sheet.loc['Total Stockholder Equity'][0] if 'Total Stockholder Equity' in balance_sheet.index else None
            else:
                total_debt, total_equity = None, None

            # Calculate Debt/Equity Ratio
            debt_equity_ratio = round(total_debt / total_equity, 2) if total_debt and total_equity and total_equity != 0 else None

            # Convert Market Cap to INR Crores
            market_cap_cr = round((market_cap * usd_to_inr) / 10_000_000, 2) if market_cap else None

            # Add new columns
            df['MarketCap(Cr)'] = market_cap_cr
            df['DebtEquityRatio'] = debt_equity_ratio
            df['Industry'] = industry

            final_df = pd.concat([final_df, df])
    except Exception as e:
        print(f"Error processing ticker {ticker}: {e}")

# Save to CSV
if not final_df.empty:
    final_df.to_csv(output_file, mode='a', header=not os.path.exists(output_file), index=False)
    print(f"✅ Saved {len(final_df)} rows to {output_file}")
else:
    print("⚠️ No data fetched (check network or ticker symbols)")
