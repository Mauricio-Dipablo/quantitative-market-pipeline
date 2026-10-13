import json
import numpy as np
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

# 1. Conexión con BigQuery
KEY_PATH = "gcp_key.json"
credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
client = bigquery.Client(credentials=credentials, project=credentials.project_id)

DATASET_ID = "ecommerce_data"
TABLE_ID = f"{credentials.project_id}.{DATASET_ID}.daily_stock_prices"

print("Fetching 1-year historical data from BigQuery...")

# 2. Traer el último año de datos
QUERY = f"""
SELECT 
    CAST(Date AS STRING) as date_str,
    Ticker,
    ROUND(Close, 2) AS close_price,
    Daily_Return_Pct AS return_pct,
    Volume
FROM `{TABLE_ID}`
ORDER BY Date ASC;
"""

df = client.query(QUERY).to_dataframe()

tickers = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN']
dates = sorted(df['date_str'].unique().tolist())

stock_data = {}

for t in tickers:
    t_df = df[df['Ticker'] == t].sort_values('date_str').copy()
    latest = t_df.iloc[-1]
    
    # Cálculos estadísticos objetivos
    sma_7d = round(t_df['close_price'].tail(7).mean(), 2)
    
    # Calcular RSI (14 días)
    delta = t_df['close_price'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    t_df['rsi'] = 100 - (100 / (1 + rs))
    current_rsi = round(t_df['rsi'].iloc[-1], 2)
    
    # Volumen en comparación con la media de 30 días
    avg_volume_30d = t_df['Volume'].tail(30).mean()
    current_volume = latest['Volume']
    vol_pct = int((current_volume / avg_volume_30d) * 100) if avg_volume_30d > 0 else 100

    # Insight puramente basado en hechos reales (Sin predicciones)
    if current_rsi >= 70:
        insight = f"FACT: RSI is at {current_rsi} (Above standard 70 threshold). Volume is {vol_pct}% of the 30-day average."
        insight_color = "text-amber-400"
    elif current_rsi <= 30:
        insight = f"FACT: RSI is at {current_rsi} (Below standard 30 threshold). Volume is {vol_pct}% of the 30-day average."
        insight_color = "text-blue-400"
    elif vol_pct > 150:
        insight = f"FACT: Trading volume is unusually high ({vol_pct}% of the 30-day average). RSI is at {current_rsi}."
        insight_color = "text-emerald-400"
    else:
        insight = f"FACT: Metrics within standard deviations. RSI: {current_rsi} | Volume: {vol_pct}% of 30-day avg."
        insight_color = "text-slate-400"

    stock_data[t] = {
        "prices": t_df['close_price'].tolist(),
        "dates": t_df['date_str'].tolist(),
        "current_price": float(latest['close_price']),
        "return_pct": float(latest['return_pct']),
        "sma_7d": float(sma_7d),
        "rsi": float(current_rsi),
        "volume": int(current_volume),
        "insight": insight,
        "insight_color": insight_color
    }

latest_date = dates[-1]

# 3. Plantilla HTML (Con UI de Alertas de Precio)
html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quantitative Market Intelligence</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        body {{ font-family: 'Inter', sans-serif; }}
        /* Animación suave para el modal */
        #alert-modal {{ transition: opacity 0.2s ease-in-out; }}
    </style>
</head>
<body class="bg-[#0B0F19] text-slate-200 min-h-screen flex flex-col relative">

    <!-- Navbar -->
    <header class="border-b border-slate-800 bg-[#0F172A] px-8 py-5 flex items-center justify-between">
        <div class="flex items-center gap-4">
            <h1 class="text-xl font-bold tracking-wide text-white uppercase">Quantitative Market Intelligence</h1>
            <span class="text-[10px] bg-slate-800 text-slate-300 border border-slate-700 px-2.5 py-1 rounded tracking-widest font-mono">AUTOMATED PIPELINE</span>
        </div>
        <p class="text-xs text-slate-400 font-mono tracking-wide">LATEST DATA: <span class="text-slate-200 font-semibold">{latest_date}</span></p>
    </header>

    <!-- Main Container -->
    <div class="flex-1 flex overflow-hidden p-6 gap-6 max-w-[1400px] mx-auto w-full">
        
        <!-- Sidebar Navigation -->
        <aside class="w-64 bg-[#0F172A] border border-slate-800 rounded-xl p-4 flex flex-col gap-2 shrink-0">
            <span class="text-[10px] font-bold text-slate-500 uppercase tracking-widest px-3 mb-2">Views</span>
            <button onclick="switchTab('overview')" id="btn-overview" class="tab-btn w-full text-left px-4 py-3 rounded-lg text-sm font-medium transition flex items-center justify-between bg-blue-600/20 text-blue-400 border border-blue-500/30">
                <span>System Overview</span>
            </button>
            
            <span class="text-[10px] font-bold text-slate-500 uppercase tracking-widest px-3 my-2 mt-4">Asset Analytics</span>
            {"".join([f'''
            <button onclick="switchTab('{t}')" id="btn-{t}" class="tab-btn w-full text-left px-4 py-3 rounded-lg text-sm font-medium transition flex items-center justify-between text-slate-400 hover:bg-slate-800 border border-transparent">
                <span>{t}</span>
                <span class="text-xs font-mono {'text-emerald-400' if stock_data[t]['return_pct'] >= 0 else 'text-rose-400'}">{stock_data[t]['return_pct']:+.2f}%</span>
            </button>
            ''' for t in tickers])}
        </aside>

        <!-- Content Area -->
        <main class="flex-1 bg-[#0F172A] border border-slate-800 rounded-xl p-8 flex flex-col">
            
            <!-- OVERVIEW TAB -->
            <div id="tab-overview" class="tab-content flex-1 flex flex-col gap-8">
                <div>
                    <h2 class="text-2xl font-semibold text-white mb-2">Market Aggregation & Performance</h2>
                    <p class="text-sm text-slate-400">Automated BigQuery ELT pipeline processing 1-year historical pricing and technical indicators.</p>
                </div>

                <!-- KPI Cards -->
                <div class="grid grid-cols-5 gap-4">
                    {"".join([f'''
                    <div class="bg-[#151E32] border border-slate-800/60 rounded-lg p-5 flex flex-col gap-2 relative group cursor-pointer" onclick="switchTab('{t}')">
                        <div class="absolute inset-0 bg-blue-500/5 rounded-lg opacity-0 group-hover:opacity-100 transition"></div>
                        <span class="text-xs text-slate-500 font-bold uppercase tracking-wider">{t}</span>
                        <span class="text-2xl font-medium text-white">${stock_data[t]['current_price']:.2f}</span>
                        <span class="text-sm font-semibold {'text-emerald-400' if stock_data[t]['return_pct'] >= 0 else 'text-rose-400'}">{stock_data[t]['return_pct']:+.2f}%</span>
                    </div>
                    ''' for t in tickers])}
                </div>

                <!-- Comparative Chart -->
                <div class="flex-1 flex flex-col min-h-0 pt-4 border-t border-slate-800">
                    <span class="text-xs font-bold text-slate-500 uppercase tracking-widest mb-4">1-Year Normalized Performance (%)</span>
                    <div class="flex-1 min-h-0">
                        <canvas id="overviewChart"></canvas>
                    </div>
                </div>
            </div>

            <!-- ASSET TABS -->
            {"".join([f'''
            <div id="tab-{t}" class="tab-content hidden flex-1 flex flex-col gap-8">
                
                <div class="flex justify-between items-start">
                    <div>
                        <div class="flex items-center gap-4">
                            <h2 class="text-3xl font-semibold text-white tracking-tight">{t} Quantitative Profile</h2>
                            <!-- Botón de Notificación -->
                            <button onclick="openAlertModal('{t}', {stock_data[t]['current_price']})" class="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition shadow-lg shadow-blue-900/20">
                                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>
                                Set Price Alert
                            </button>
                        </div>
                        <div class="mt-4 inline-flex items-center gap-2 bg-[#151E32] border border-slate-800 px-4 py-2.5 rounded-lg">
                            <span class="text-[10px] font-bold text-slate-500 uppercase tracking-widest border-r border-slate-700 pr-3 mr-1">Data Insight</span>
                            <span class="text-sm font-medium {stock_data[t]['insight_color']}">{stock_data[t]['insight']}</span>
                        </div>
                    </div>
                    <div class="text-right">
                        <span class="text-4xl font-semibold text-white">${stock_data[t]['current_price']:.2f}</span>
                        <div class="text-sm font-medium mt-1 {'text-emerald-400' if stock_data[t]['return_pct'] >= 0 else 'text-rose-400'}">{stock_data[t]['return_pct']:+.2f}% (24h)</div>
                    </div>
                </div>

                <!-- Technical Stats Grid -->
                <div class="grid grid-cols-3 gap-4">
                    <div class="bg-[#151E32] border border-slate-800/60 rounded-lg p-5">
                        <span class="text-xs text-slate-500 font-bold uppercase tracking-wider">14-Day RSI</span>
                        <div class="text-2xl font-medium text-slate-200 mt-2">{stock_data[t]['rsi']}</div>
                    </div>
                    <div class="bg-[#151E32] border border-slate-800/60 rounded-lg p-5">
                        <span class="text-xs text-slate-500 font-bold uppercase tracking-wider">7-Day Moving Average</span>
                        <div class="text-2xl font-medium text-slate-200 mt-2">${stock_data[t]['sma_7d']:.2f}</div>
                    </div>
                    <div class="bg-[#151E32] border border-slate-800/60 rounded-lg p-5">
                        <span class="text-xs text-slate-500 font-bold uppercase tracking-wider">24h Trading Volume</span>
                        <div class="text-2xl font-medium text-slate-200 mt-2">{stock_data[t]['volume']:,}</div>
                    </div>
                </div>

                <!-- Asset Chart -->
                <div class="flex-1 flex flex-col min-h-0 pt-4 border-t border-slate-800">
                    <span class="text-xs font-bold text-slate-500 uppercase tracking-widest mb-4">1-Year Price Evolution (USD)</span>
                    <div class="flex-1 min-h-0">
                        <canvas id="chart-{t}"></canvas>
                    </div>
                </div>
            </div>
            ''' for t in tickers])}

        </main>
    </div>

    <!-- MODAL DE NOTIFICACIÓN -->
    <div id="alert-modal" class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 hidden flex items-center justify-center opacity-0 pointer-events-none transition-opacity duration-300">
        <div class="bg-[#0F172A] border border-slate-700 rounded-2xl w-full max-w-md p-6 shadow-2xl transform scale-95 transition-transform duration-300" id="alert-box">
            
            <div class="flex justify-between items-center mb-6">
                <h3 class="text-lg font-bold text-white flex items-center gap-2">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" class="text-blue-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>
                    Create Price Alert
                </h3>
                <button onclick="closeAlertModal()" class="text-slate-400 hover:text-white transition">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
            </div>

            <form id="alert-form" onsubmit="submitAlert(event)">
                <div class="mb-4">
                    <label class="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">Asset</label>
                    <div class="bg-[#151E32] border border-slate-700 rounded-lg px-4 py-3 text-white font-medium flex justify-between items-center">
                        <span id="modal-ticker">AAPL</span>
                        <span class="text-sm text-slate-400">Current: $<span id="modal-current-price">0.00</span></span>
                    </div>
                </div>

                <div class="mb-4">
                    <label class="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">Notify me when price crosses</label>
                    <div class="relative">
                        <span class="absolute left-4 top-3 text-slate-400">$</span>
                        <input type="number" step="0.01" id="modal-target-price" required class="w-full bg-[#151E32] border border-slate-700 rounded-lg pl-8 pr-4 py-3 text-white focus:outline-none focus:border-blue-500 transition" placeholder="e.g. 150.00">
                    </div>
                </div>

                <div class="mb-6">
                    <label class="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">Email Address</label>
                    <input type="email" required class="w-full bg-[#151E32] border border-slate-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-blue-500 transition" placeholder="you@company.com">
                </div>

                <button type="submit" class="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-3 rounded-lg transition flex justify-center items-center gap-2">
                    Set Automated Alert
                </button>
            </form>

            <!-- Success Message (Hidden by default) -->
            <div id="alert-success" class="hidden flex flex-col items-center justify-center py-6">
                <div class="w-12 h-12 bg-emerald-500/20 rounded-full flex items-center justify-center mb-4 border border-emerald-500/50">
                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" class="text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                </div>
                <h4 class="text-lg font-bold text-white mb-1">Alert Registered</h4>
                <p class="text-sm text-slate-400 text-center">You will receive an email notification when the target price is reached.</p>
                <button onclick="closeAlertModal()" class="mt-6 w-full bg-slate-800 hover:bg-slate-700 text-white font-semibold py-2 rounded-lg transition">Close</button>
            </div>
        </div>
    </div>

    <script>
        const rawData = {json.dumps(stock_data)};
        const chartDates = {json.dumps(dates)};

        // Lógica de Pestañas
        function switchTab(tabId) {{
            document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
            document.querySelectorAll('.tab-btn').forEach(btn => {{
                btn.classList.remove('bg-blue-600/20', 'text-blue-400', 'border-blue-500/30');
                btn.classList.add('text-slate-400', 'border-transparent');
            }});

            document.getElementById('tab-' + tabId).classList.remove('hidden');
            const activeBtn = document.getElementById('btn-' + tabId);
            activeBtn.classList.add('bg-blue-600/20', 'text-blue-400', 'border-blue-500/30');
            activeBtn.classList.remove('text-slate-400', 'border-transparent');
        }}

        // Lógica del Modal de Alertas
        const modal = document.getElementById('alert-modal');
        const modalBox = document.getElementById('alert-box');
        const form = document.getElementById('alert-form');
        const successMsg = document.getElementById('alert-success');

        function openAlertModal(ticker, currentPrice) {{
            document.getElementById('modal-ticker').innerText = ticker;
            document.getElementById('modal-current-price').innerText = currentPrice.toFixed(2);
            document.getElementById('modal-target-price').value = currentPrice.toFixed(2);
            
            // Reset form state
            form.classList.remove('hidden');
            successMsg.classList.add('hidden');
            form.reset();

            // Show modal
            modal.classList.remove('hidden', 'pointer-events-none');
            // Trigger animation
            setTimeout(() => {{
                modal.classList.remove('opacity-0');
                modalBox.classList.remove('scale-95');
            }}, 10);
        }}

        function closeAlertModal() {{
            modal.classList.add('opacity-0');
            modalBox.classList.add('scale-95');
            setTimeout(() => {{
                modal.classList.add('hidden', 'pointer-events-none');
            }}, 300);
        }}

        function submitAlert(e) {{
            e.preventDefault();
            // Aquí en la vida real se enviaría el POST a la base de datos
            form.classList.add('hidden');
            successMsg.classList.remove('hidden');
        }}

        // Setup Chart Defaults
        Chart.defaults.color = '#64748b';
        Chart.defaults.font.family = "'Inter', sans-serif";
        const gridOptions = {{ color: '#1e293b', drawBorder: false }};
        const pointOptions = {{ pointRadius: 0, hitRadius: 10, hoverRadius: 4 }};

        // Render Overview Chart
        const ctxOverview = document.getElementById('overviewChart').getContext('2d');
        const colors = {{'AAPL': '#38bdf8', 'MSFT': '#818cf8', 'NVDA': '#34d399', 'GOOGL': '#f472b6', 'AMZN': '#fbbf24'}};
        
        const overviewDatasets = Object.keys(rawData).map(ticker => {{
            const basePrice = rawData[ticker].prices[0];
            return {{
                label: ticker,
                data: rawData[ticker].prices.map(p => ((p - basePrice) / basePrice * 100).toFixed(2)),
                borderColor: colors[ticker],
                borderWidth: 1.5,
                tension: 0.1,
                ...pointOptions
            }};
        }});

        new Chart(ctxOverview, {{
            type: 'line',
            data: {{ labels: chartDates, datasets: overviewDatasets }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{ mode: 'index', intersect: false }},
                plugins: {{ tooltip: {{ padding: 12 }} }},
                scales: {{
                    x: {{ grid: gridOptions, ticks: {{ maxTicksLimit: 12 }} }},
                    y: {{ grid: gridOptions, ticks: {{ callback: v => v + '%' }} }}
                }}
            }}
        }});

        // Render Individual Charts
        Object.keys(rawData).forEach(ticker => {{
            const ctx = document.getElementById('chart-' + ticker).getContext('2d');
            let gradient = ctx.createLinearGradient(0, 0, 0, 400);
            gradient.addColorStop(0, colors[ticker] + '33');
            gradient.addColorStop(1, colors[ticker] + '00');

            new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: rawData[ticker].dates,
                    datasets: [{{
                        label: 'Close Price',
                        data: rawData[ticker].prices,
                        borderColor: colors[ticker],
                        backgroundColor: gradient,
                        borderWidth: 2,
                        fill: true,
                        tension: 0.1,
                        ...pointOptions
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {{ mode: 'index', intersect: false }},
                    plugins: {{ legend: {{ display: false }}, tooltip: {{ padding: 12 }} }},
                    scales: {{
                        x: {{ grid: gridOptions, ticks: {{ maxTicksLimit: 12 }} }},
                        y: {{ grid: gridOptions, ticks: {{ callback: v => '$' + v }} }}
                    }}
                }}
            }});
        }});
    </script>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("Dashboard with Notification UI successfully generated.")