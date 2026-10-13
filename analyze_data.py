import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

# 1. Conexión con BigQuery
KEY_PATH = "gcp_key.json"
credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
client = bigquery.Client(credentials=credentials, project=credentials.project_id)

DATASET_ID = "ecommerce_data"
TABLE_ID = f"{credentials.project_id}.{DATASET_ID}.daily_stock_prices"

print("📊 Consultando BigQuery y calculando métricas de mercado...")

# 2. Query SQL analítica con Window Functions (calcula media móvil de 7 días)
QUERY = f"""
WITH recent_data AS (
    SELECT 
        Date,
        Ticker,
        Close,
        Daily_Return_Pct,
        Volume,
        AVG(Close) OVER(
            PARTITION BY Ticker 
            ORDER BY Date 
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS sma_7d
    FROM `{TABLE_ID}`
),
latest_date AS (
    SELECT MAX(Date) AS max_date FROM `{TABLE_ID}`
)
SELECT 
    r.Date,
    r.Ticker,
    ROUND(r.Close, 2) AS close_price,
    r.Daily_Return_Pct AS return_pct,
    ROUND(r.sma_7d, 2) AS sma_7d,
    r.Volume AS volume
FROM recent_data r
WHERE r.Date = (SELECT max_date FROM latest_date)
ORDER BY r.Daily_Return_Pct DESC;
"""

# Ejecutar la consulta en BigQuery y traerla como DataFrame
df = client.query(QUERY).to_dataframe()

print(f"\n📅 Fecha del último cierre: {df['Date'].iloc[0]}")
print("=" * 60)
print(f"{'TICKER':<8} | {'PRECIO':<10} | {'RETORNO 24H':<12} | {'SMA (7D)':<10} | {'ESTADO'}")
print("=" * 60)

alerts = []

for _, row in df.iterrows():
    ticker = row['Ticker']
    price = f"${row['close_price']:.2f}"
    ret = row['return_pct']
    sma = f"${row['sma_7d']:.2f}"
    
    # Lógica de detección de anomalías / alertas
    if ret >= 1.5:
        status = "🟢 Subida Fuerte"
        alerts.append(f"🚀 OPORTUNIDAD: {ticker} subió un {ret}% cerrando en {price}.")
    elif ret <= -1.5:
        status = "🔴 Caída Significativa"
        alerts.append(f"⚠️ RIESGO: {ticker} cayó un {ret}% cerrando en {price}.")
    else:
        status = "⚪ Estable"
        
    ret_str = f"{ret:+.2f}%"
    print(f"{ticker:<8} | {price:<10} | {ret_str:<12} | {sma:<10} | {status}")

print("=" * 60)

# Resumen de alertas detectadas
if alerts:
    print("\n🔔 ALERTAS DETECTADAS PARA LA GERENCIA:")
    for a in alerts:
        print(f" - {a}")
else:
    print("\n✅ Mercado tranquilo: No hubo movimientos bruscos hoy.")