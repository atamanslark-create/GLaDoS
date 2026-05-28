"""
GLaDoS Веб-панель мониторинга
Доступна по адресу: http://localhost:7777
Логин: slark / Пароль: 8l99ujqF
"""

from flask import Flask, render_template_string, jsonify, request
from flask_httpauth import HTTPBasicAuth
from datetime import datetime, timedelta
import sys

# Добавить путь для импорта database
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import database as db
except ImportError:
    print("❌ Ошибка: не найден модуль database.py")
    print("   Убедись, что веб-панель запущена в папке с database.py")
    sys.exit(1)

app = Flask(__name__)

basic_auth = HTTPBasicAuth()

@basic_auth.verify_password
def verify_password(username, password):
    return username == 'slark' and password == '8l99ujqF'

DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GLaDoS - Веб-панель мониторинга</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial;
            background: #0f1419;
            color: #e0e6ed;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        h1 { font-size: 32px; margin-bottom: 10px; }
        .subtitle { opacity: 0.9; font-size: 14px; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: #1a1e2e;
            border-left: 4px solid #667eea;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        .stat-label { font-size: 12px; opacity: 0.7; text-transform: uppercase; margin-bottom: 8px; }
        .stat-value { font-size: 28px; font-weight: bold; }
        .section-title {
            font-size: 20px;
            margin-top: 40px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }
        .charts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .chart-container {
            background: #1a1e2e;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            position: relative;
            height: 400px;
        }
        .chart-title {
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #333;
        }
        .bots-table {
            width: 100%;
            background: #1a1e2e;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #333;
        }
        th {
            background: #0f1419;
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
            opacity: 0.7;
        }
        tr:hover { background: #252c3c; }
        .status-online { color: #10b981; }
        .status-offline { color: #ef4444; }
        .status-error { color: #f59e0b; }
        .alert { padding: 15px; border-radius: 5px; margin-bottom: 15px; }
        .alert-warning { background: #92400e; border-left: 4px solid #f59e0b; }
        .alert-error { background: #7f1d1d; border-left: 4px solid #ef4444; }
        .refresh-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            margin-bottom: 20px;
        }
        .refresh-btn:hover { background: #764ba2; }
        footer {
            text-align: center;
            margin-top: 40px;
            opacity: 0.5;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 GLaDoS Веб-панель мониторинга</h1>
            <div class="subtitle">Централизованный мониторинг всех VPS</div>
        </header>

        <button class="refresh-btn" onclick="location.reload()">🔄 Обновить</button>

        <div class="stats-grid" id="stats-container">
            <div class="stat-card">
                <div class="stat-label">Активные боты</div>
                <div class="stat-value" id="active-bots">-</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Всего команд</div>
                <div class="stat-value" id="total-commands">-</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Выполнено</div>
                <div class="stat-value" id="executed-commands">-</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Ошибок</div>
                <div class="stat-value" id="failed-commands">-</div>
            </div>
        </div>

        <h2 class="section-title">📈 Метрики за последние 7 дней</h2>
        <div class="charts-grid">
            <div class="chart-container">
                <div class="chart-title">CPU Использование (%)</div>
                <canvas id="cpu-chart"></canvas>
            </div>
            <div class="chart-container">
                <div class="chart-title">RAM Использование (%)</div>
                <canvas id="ram-chart"></canvas>
            </div>
            <div class="chart-container">
                <div class="chart-title">Диск Использование (%)</div>
                <canvas id="disk-chart"></canvas>
            </div>
        </div>

        <h2 class="section-title">🤖 Статус ботов</h2>
        <div class="bots-table">
            <table id="bots-table">
                <thead>
                    <tr>
                        <th>Имя</th>
                        <th>Статус</th>
                        <th>Username</th>
                        <th>Последний отчёт</th>
                        <th>Действие</th>
                    </tr>
                </thead>
                <tbody id="bots-tbody">
                    <tr><td colspan="5" style="text-align: center;">Загрузка...</td></tr>
                </tbody>
            </table>
        </div>

        <footer>
            <p>GLaDoS © 2026 | Последнее обновление: <span id="last-update">-</span></p>
        </footer>
    </div>

    <script>
        const API_BASE = '/api';
        let cpuChart, ramChart, diskChart;

        async function fetchData(endpoint) {
            try {
                const res = await fetch(`${API_BASE}${endpoint}`);
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                return await res.json();
            } catch (e) {
                console.error(`Error fetching ${endpoint}:`, e);
                return null;
            }
        }

        async function updateStats() {
            const stats = await fetchData('/stats');
            if (stats) {
                document.getElementById('active-bots').textContent = stats.active_bots || 0;
                document.getElementById('total-commands').textContent = stats.total_commands || 0;
                document.getElementById('executed-commands').textContent = stats.executed_commands || 0;
                document.getElementById('failed-commands').textContent = stats.failed_commands || 0;
            }
        }

        async function updateCharts() {
            const metrics = await fetchData('/metrics');
            if (!metrics) return;

            const dates = metrics.dates || [];
            const cpuData = metrics.cpu_data || [];
            const ramData = metrics.ram_data || [];
            const diskData = metrics.disk_data || [];

            const chartConfig = {
                type: 'line',
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { min: 0, max: 100, ticks: { color: '#888' } },
                        x: { ticks: { color: '#888' } }
                    },
                    elements: { line: { tension: 0.4 } }
                }
            };

            if (cpuChart) cpuChart.destroy();
            cpuChart = new Chart(document.getElementById('cpu-chart'), {
                ...chartConfig,
                data: {
                    labels: dates,
                    datasets: [{
                        data: cpuData,
                        borderColor: '#f59e0b',
                        backgroundColor: 'rgba(245, 158, 11, 0.1)',
                        borderWidth: 2,
                        fill: true
                    }]
                }
            });

            if (ramChart) ramChart.destroy();
            ramChart = new Chart(document.getElementById('ram-chart'), {
                ...chartConfig,
                data: {
                    labels: dates,
                    datasets: [{
                        data: ramData,
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        borderWidth: 2,
                        fill: true
                    }]
                }
            });

            if (diskChart) diskChart.destroy();
            diskChart = new Chart(document.getElementById('disk-chart'), {
                ...chartConfig,
                data: {
                    labels: dates,
                    datasets: [{
                        data: diskData,
                        borderColor: '#8b5cf6',
                        backgroundColor: 'rgba(139, 92, 246, 0.1)',
                        borderWidth: 2,
                        fill: true
                    }]
                }
            });
        }

        async function updateBots() {
            const bots = await fetchData('/bots');
            if (!bots) return;

            const tbody = document.getElementById('bots-tbody');
            tbody.innerHTML = '';

            if (bots.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align: center;">Нет ботов</td></tr>';
                return;
            }

            bots.forEach(bot => {
                const statusClass = `status-${bot.status}`;
                const statusText = {
                    'online': '🟢 Онлайн',
                    'offline': '🔴 Офлайн',
                    'error': '⚠️ Ошибка'
                }[bot.status] || '⚪ Неизвестно';

                const row = document.createElement('tr');
                row.innerHTML = `
                    <td><strong>${bot.name}</strong></td>
                    <td><span class="${statusClass}">${statusText}</span></td>
                    <td>${bot.username || '—'}</td>
                    <td>${bot.last_report || '—'}</td>
                    <td><button onclick="alert('Просмотр деталей: ${bot.name}')" style="cursor: pointer; color: #667eea;">Детали</button></td>
                `;
                tbody.appendChild(row);
            });
        }

        async function init() {
            document.getElementById('last-update').textContent = new Date().toLocaleTimeString('ru-RU');
            await updateStats();
            await updateCharts();
            await updateBots();

            // Обновлять каждые 30 секунд
            setInterval(async () => {
                await updateStats();
                await updateBots();
            }, 30000);

            // Графики обновлять каждые 2 минуты
            setInterval(updateCharts, 120000);
        }

        init();
    </script>
</body>
</html>
'''


# API endpoints
@app.route('/')
@basic_auth.login_required
def dashboard():
    """Главная страница панели."""
    return render_template_string(DASHBOARD_HTML)


@app.route('/api/stats')
@basic_auth.login_required
def api_stats():
    """Получить статистику."""
    bots = db.list_bots()
    stats = db.get_stats()

    return jsonify({
        'active_bots': len([b for b in bots if b['status'] == 'online']),
        'total_bots': len(bots),
        'total_commands': stats.get('total_commands', 0),
        'executed_commands': stats.get('executed_commands', 0),
        'failed_commands': stats.get('failed_commands', 0),
        'pending_commands': stats.get('pending_commands', 0),
    })


@app.route('/api/metrics')
@basic_auth.login_required
def api_metrics():
    """Получить метрики за 7 дней."""
    # Это будет работать, когда в mini-bot настроено сохранение метрик
    # На данный момент возвращаем пустые данные

    dates = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
    dates.reverse()

    return jsonify({
        'dates': dates,
        'cpu_data': [0] * 7,      # Будут заполняться из БД
        'ram_data': [0] * 7,
        'disk_data': [0] * 7,
    })


@app.route('/api/bots')
@basic_auth.login_required
def api_bots():
    """Получить список ботов."""
    bots = db.list_bots()
    result = []

    for bot in bots:
        latest = db.get_latest_report(bot['id'])
        result.append({
            'id': bot['id'],
            'name': bot['name'],
            'username': bot['username'],
            'status': bot['status'],
            'last_report': latest['received_at'] if latest else None,
        })

    return jsonify(result)


@app.route('/api/commands')
@basic_auth.login_required
def api_commands():
    """Получить историю команд."""
    logs = db.get_command_history(limit=20)
    return jsonify([dict(log) for log in logs])


if __name__ == '__main__':
    print("🚀 GLaDoS Веб-панель запущена")
    print("📍 http://localhost:7777")
    print("👤 Логин: slark")
    print("🔐 Пароль: 8l99ujqF")
    print("")

    try:
        app.run(host='127.0.0.1', port=7777, debug=False)
    except KeyboardInterrupt:
        print("\n⛔ Веб-панель остановлена")
