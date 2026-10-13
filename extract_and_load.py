import os
import yfinance as yf
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from datetime import datetime, timedelta

# 1. Configurar conexión con BigQuery usando tu llave JSON
KEY_PATH = "gcp_key.json"
credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
client = bigquery.Client(credentials=credentials, project=credentials.project_id)

# 2. Definir las acciones a monitorear (Grandes empresas de tecnología)
TICKERS = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN']
DATASET_ID = "ecommerce_data"  # El dataset que creaste en BigQuery
TABLE_ID = f"{credentials.project_id}.{DATASET_ID}.daily_stock_prices"

print("🔍 Descargando datos reales de Yahoo Finance...")

# 3. Descargar el historial de los últimos 30 días para tener datos con qué comparar
all_data = []

for ticker in TICKERS:
    stock = yf.Ticker(ticker)
    df = stock.history(period="1y")  # Último mes de datos
    
    if not df.empty:
        df = df.reset_index()
        df['Date'] = pd.to_datetime(df['Date']).dt.date
        df['Ticker'] = ticker
        
        # Calcular el retorno porcentual diario respecto al día anterior
        df['Daily_Return_Pct'] = (df['Close'].pct_change() * 100).round(2)
        
        # Seleccionar y renombrar columnas clave
        df_clean = df[['Date', 'Ticker', 'Open', 'High', 'Low', 'Close', 'Volume', 'Daily_Return_Pct']].copy()
        all_data.append(df_clean)

# Unir todas las acciones en un solo DataFrame
final_df = pd.concat(all_data, ignore_index=True)
final_df = final_df.dropna()  # Quitar primeros registros que tienen retorno nulo

print(f"✅ Se obtuvieron {len(final_df)} registros reales del mercado.")
print(final_df.tail())

# 4. Configurar la subida a BigQuery
job_config = bigquery.LoadJobConfig(
    write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE, # Crea o sobrescribe la tabla completa
    schema=[
        bigquery.SchemaField("Date", "DATE"),
        bigquery.SchemaField("Ticker", "STRING"),
        bigquery.SchemaField("Open", "FLOAT"),
        bigquery.SchemaField("High", "FLOAT"),
        bigquery.SchemaField("Low", "FLOAT"),
        bigquery.SchemaField("Close", "FLOAT"),
        bigquery.SchemaField("Volume", "INTEGER"),
        bigquery.SchemaField("Daily_Return_Pct", "FLOAT"),
    ]
)

print(f"🚀 Subiendo datos a BigQuery ({TABLE_ID})...")
job = client.load_table_from_dataframe(final_df, TABLE_ID, job_config=job_config)
job.result()  # Esperar a que termine la carga

print(f"🎉 ¡Éxito total! Tabla '{TABLE_ID}' creada y poblada con datos reales.")