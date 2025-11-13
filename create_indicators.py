import pandas as pd
import numpy as np
from pandas.tseries.offsets import BDay
from datetime import date

# Get the current local date
today = date.today()
 
# Load the CSV
df = pd.read_csv("stock_data_last_2_days.csv", parse_dates=["Date"])
 
# Ensure numeric types
for col in ["Open", "High", "Low", "Close", "Volume"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")
 
# Sort
df.sort_values(by=["Ticker", "Date"], inplace=True)
 
# Append 26 future business days
future_days = 26
tickers = df["Ticker"].unique()
latest_date = today
future_dates = pd.date_range(start=latest_date + BDay(1), periods=future_days, freq=BDay())
future_rows = pd.DataFrame([(date, ticker) for ticker in tickers for date in future_dates], columns=["Date", "Ticker"])
for col in ["Open", "High", "Low", "Close", "Volume"]:
    future_rows[col] = np.nan
 
df_extended = pd.concat([df, future_rows], ignore_index=True)
df_extended.sort_values(by=["Ticker", "Date"], inplace=True)
#assigning index 
df_extended['index'] = df_extended.groupby('Ticker').cumcount() + 1
df_extended['SMA_9'] = (
    df_extended.sort_values(['Ticker', 'index'])
      .groupby('Ticker')['Close']
      .transform(lambda x: x.rolling(window=9).mean())
)
df_extended['SMA_22'] = (
    df_extended.sort_values(['Ticker', 'index'])
      .groupby('Ticker')['Close']
      .transform(lambda x: x.rolling(window=20).mean())
)
df_extended["STD_22"] = (
    df_extended.sort_values(['Ticker', 'index'])
      .groupby('Ticker')['Close']
      .transform(lambda x: x.rolling(window=20).std())
)
df_extended['SMA_52'] = (
    df_extended.sort_values(['Ticker', 'index'])
      .groupby('Ticker')['Close']
      .transform(lambda x: x.rolling(window=50).mean())
)
df_extended['SMA_200'] = (
    df_extended.sort_values(['Ticker', 'index'])
      .groupby('Ticker')['Close']
      .transform(lambda x: x.rolling(window=200).mean())
)

def compute_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

df_extended['RSI_14'] = (
    df_extended.groupby('Ticker')['Close']
      .transform(lambda x: compute_rsi(x, period=14))
)
df_extended["BB_Upper"] = df_extended["SMA_22"] + 2 * df_extended["STD_22"]
df_extended["BB_Lower"] = df_extended["SMA_22"] - 2 * df_extended["STD_22"]


def bollinger_flag(row):
    if pd.isna(row['BB_Upper']) or pd.isna(row['BB_Lower']):
        return np.nan
    elif row['Close'] > row['BB_Upper']:
        return "BBH"
    elif row['Close'] < row['BB_Lower']:
        return 'BBL'
    else:
        return np.nan
        
df_extended['BB_Flag'] = df_extended.apply(bollinger_flag, axis=1)

def compute_senkou(group):
    # Conversion Line (Tenkan-sen)
    conv_line = (group["High"].rolling(window=9, min_periods=1).max() + group["Low"].rolling(window=9, min_periods=1).min()) / 2
    
    # Base Line (Kijun-sen)
    base_line = (group["High"].rolling(window=20, min_periods=1).max() + group["Low"].rolling(window=20, min_periods=1).min()) / 2
    
    # Senkou Span A (Leading Span A)
    group["Senkou_Span_A"] = ((conv_line + base_line) / 2).shift(20)
    
    # Senkou Span B (Leading Span B)
    span_b = (group["High"].rolling(window=50, min_periods=1).max() + group["Low"].rolling(window=50, min_periods=1).min()) / 2
    group["Senkou_Span_B"] = span_b.shift(20)
    
    return group


df_extended = df_extended.groupby("Ticker").apply(compute_senkou).reset_index(drop=True)

def compute_knoxville_divergence(group, rsi_period=14, momentum_period=20):
    # RSI (already computed, but recompute for clarity)
    delta = group['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=rsi_period).mean()
    avg_loss = loss.rolling(window=rsi_period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # Momentum
    momentum = group['Close'] - group['Close'].shift(momentum_period)

    # Knoxville Divergence logic
    divergence_flag = []
    start_price = None
    end_price = None

    for i in range(len(group)):
        if rsi.iloc[i] < 30 and momentum.iloc[i] > 0:  # Bullish divergence start
            start_price = group['Close'].iloc[i]
            divergence_flag.append('Bullish Start')
        elif start_price and momentum.iloc[i] < 0:  # Bullish divergence end
            end_price = group['Close'].iloc[i]
            divergence_flag.append(f'Bullish End ({start_price}→{end_price})')
            start_price = None
        elif rsi.iloc[i] > 70 and momentum.iloc[i] < 0:  # Bearish divergence start
            start_price = group['Close'].iloc[i]
            divergence_flag.append('Bearish Start')
        elif start_price and momentum.iloc[i] > 0:  # Bearish divergence end
            end_price = group['Close'].iloc[i]
            divergence_flag.append(f'Bearish End ({start_price}→{end_price})')
            start_price = None
        else:
            divergence_flag.append(None)

    group['Knoxville_Divergence'] = divergence_flag
    return group

# Apply to each ticker group
df_extended = df_extended.groupby('Ticker').apply(compute_knoxville_divergence).reset_index(drop=True)

# Save to CSV
df_extended.to_csv("stock_data_with_indicators.csv", index=False)

