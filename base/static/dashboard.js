// RoadPulse — dashboard.js
//
// Incidents (map markers, heatmap, table, active-incidents stat) are now
// live from GET /api/incidents/recent. Notifications, weather, predictions,
// and the analytics charts are still dummy data — each block below notes
// the Flask endpoint it should eventually be replaced by.

document.addEventListener('DOMContentLoaded', () => {

    function timeAgo(isoString) {
        const diffMs = Date.now() - new Date(isoString).getTime();
        const mins = Math.round(diffMs / 60000);
        if (mins < 1) return 'just now';
        if (mins < 60) return `${mins}m ago`;
        if (mins < 1440) return `${Math.round(mins / 60)}h ago`;
        return `${Math.round(mins / 1440)}d ago`;
    }

    // Real data — fetched below from GET /api/incidents/recent
    let incidents = [];

    // Real data — fetched below from GET /api/weather

    // Real data — fetched below from GET /api/predictions

    /* =================================================================
       NOTIFICATIONS DROPDOWN — real events from GET /api/notifications
       ================================================================= */
    const notifIcon = {
        approved: 'bi-check-circle text-success',
        rejected: 'bi-x-circle text-danger',
        alert: 'bi-exclamation-triangle text-danger'
    };

    async function loadNotifications() {
        const notifList = document.getElementById('notification-list');
        const badge = document.getElementById('notif-badge');
        let items = [];
        try {
            const res = await fetch('/api/notifications');
            if (!res.ok) throw new Error('Request failed');
            items = await res.json();
        } catch (err) {
            console.warn('Could not load notifications from the API — is the Flask server running?', err);
        }

        if (items.length === 0) {
            notifList.innerHTML = `<li class="px-3 py-3 RP-subtle text-center" style="font-size:0.85rem;">No notifications yet.</li>`;
            badge.hidden = true;
        } else {
            notifList.innerHTML = items.map((n) => `
                <li class="d-flex gap-2 px-3 py-2 RP-notif-item">
                    <i class="bi ${notifIcon[n.kind] || 'bi-info-circle text-info'}"></i>
                    <div>
                        <div style="font-size:0.85rem;">${n.text}</div>
                        <div class="RP-subtle" style="font-size:0.72rem;">${timeAgo(n.timestamp)}</div>
                    </div>
                </li>
            `).join('');
            badge.textContent = items.length;
            badge.hidden = false;
        }
    }

    loadNotifications();

    document.getElementById('mark-all-read').addEventListener('click', () => {
        document.getElementById('notif-badge').hidden = true;
    });

    /* =================================================================
       LEAFLET MAP — markers + toggleable heatmap
       ================================================================= */
    // Andheri, Mumbai Suburban — keep in sync with weather.py and report.js
    const CITY_CENTER = [19.1136, 72.8697];

    const map = L.map('trafficMap', { scrollWheelZoom: false }).setView(CITY_CENTER, 13);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);

    const typeColor = { Accident: '#e1543a', Pothole: '#f2a93b', Waterlogging: '#3fc1b0' };

    const markersLayer = L.layerGroup().addTo(map);
    const heatLayer = L.heatLayer([], { radius: 30, blur: 25, maxZoom: 15 });

    const btnMarkers = document.getElementById('btn-markers');
    const btnHeatmap = document.getElementById('btn-heatmap');

    function showMarkers() {
        map.removeLayer(heatLayer);
        markersLayer.addTo(map);
        btnMarkers.classList.add('active');
        btnHeatmap.classList.remove('active');
    }

    function showHeatmap() {
        map.removeLayer(markersLayer);
        heatLayer.addTo(map);
        btnHeatmap.classList.add('active');
        btnMarkers.classList.remove('active');
    }

    btnMarkers.addEventListener('click', showMarkers);
    btnHeatmap.addEventListener('click', showHeatmap);

    /* =================================================================
       RECENT INCIDENTS — fetched from GET /api/incidents/recent
       Feeds the map markers, the heatmap layer, and the table together
       so they never fall out of sync with each other.
       ================================================================= */
    const tbody = document.getElementById('incidents-table-body');

    function renderIncidents(list) {
        incidents = list;

        // Markers
        markersLayer.clearLayers();
        list.forEach((inc) => {
            const color = typeColor[inc.type] || '#8b97a3';
            const marker = L.circleMarker([inc.lat, inc.lng], {
                radius: 8,
                color: color,
                fillColor: color,
                fillOpacity: 0.85,
                weight: 2
            }).bindPopup(`
                <strong>${inc.type}</strong><br>
                ${inc.location}<br>
                <span style="color:#8b97a3;font-size:0.8em;">Reported ${timeAgo(inc.reported_at)} &middot; ${inc.status}</span>
                ${inc.photo_url ? `<br><img src="${inc.photo_url}" alt="Incident photo" style="margin-top:6px;max-width:180px;border-radius:6px;display:block;">` : ''}
            `);
            markersLayer.addLayer(marker);
        });

        // Heatmap — weighted by severity. Once /api/analytics/heatmap exists
        // with real density data, swap this derivation out for that.
        const heatPoints = list.flatMap((inc) => {
            const weight = inc.severity === 'high' ? 1 : inc.severity === 'medium' ? 0.6 : 0.3;
            return [
                [inc.lat, inc.lng, weight],
                [inc.lat + 0.003, inc.lng + 0.002, weight * 0.5],
                [inc.lat - 0.002, inc.lng - 0.003, weight * 0.4]
            ];
        });
        heatLayer.setLatLngs(heatPoints);

        // Table
        if (list.length === 0) {
            tbody.innerHTML = `
                <tr><td colspan="6" class="text-center RP-subtle py-4">
                    No incidents reported yet.
                </td></tr>`;
        } else {
            tbody.innerHTML = list.map((inc) => `
                <tr>
                    <td>${inc.photo_url
                        ? `<img src="${inc.photo_url}" alt="Photo of ${inc.type} incident" class="RP-thumb">`
                        : '<span class="RP-subtle">&mdash;</span>'}</td>
                    <td>${inc.type}</td>
                    <td>${inc.location}</td>
                    <td class="RP-subtle">${timeAgo(inc.reported_at)}</td>
                    <td><span class="badge-severity badge-${inc.severity}">${inc.severity}</span></td>
                    <td><span class="badge-status badge-${inc.status}">${inc.status}</span></td>
                </tr>
            `).join('');
        }
    }

    async function loadIncidents() {
        try {
            const res = await fetch('/api/incidents/recent');
            if (!res.ok) throw new Error('Request failed');
            renderIncidents(await res.json());
        } catch (err) {
            console.warn('Could not load incidents from the API — is the Flask server running?', err);
            renderIncidents([]);
        }
    }

    loadIncidents();

    /* =================================================================
       STAT CARDS — real counts from GET /api/dashboard/stats
       ================================================================= */
    const trendIcon = { up: 'bi-arrow-up-short', down: 'bi-arrow-down-short', flat: 'bi-dash' };

    async function loadStats() {
        try {
            const res = await fetch('/api/dashboard/stats');
            if (!res.ok) throw new Error('Request failed');
            const stats = await res.json();

            document.getElementById('stat-incidents').textContent = stats.active_incidents;
            document.getElementById('stat-reports').textContent = stats.reports_today;

            const trendEl = document.getElementById('reports-trend');
            trendEl.className = `stat-trend trend-${stats.reports_today_trend}`;
            const icon = trendIcon[stats.reports_today_trend] || 'bi-dash';
            trendEl.innerHTML = `<i class="bi ${icon}"></i>${stats.reports_today_trend_text}`;
        } catch (err) {
            console.warn('Could not load dashboard stats — is the Flask server running?', err);
        }
    }

    loadStats();

    /* =================================================================
       WEATHER WIDGET — real data from GET /api/weather (Open-Meteo)
       ================================================================= */
    const weatherIconMap = {
        sun: 'bi-sun', 'cloud-sun': 'bi-cloud-sun', clouds: 'bi-clouds',
        'cloud-fog': 'bi-cloud-fog2', 'cloud-drizzle': 'bi-cloud-drizzle',
        'cloud-rain': 'bi-cloud-rain', 'cloud-rain-heavy': 'bi-cloud-rain-heavy',
        'cloud-snow': 'bi-cloud-snow', 'cloud-lightning': 'bi-cloud-lightning',
        'cloud-lightning-rain': 'bi-cloud-lightning-rain'
    };

    async function loadWeather() {
        const widget = document.getElementById('weather-widget');
        try {
            const res = await fetch('/api/weather');
            if (!res.ok) throw new Error('Request failed');
            const weather = await res.json();
            const iconClass = weatherIconMap[weather.icon] || 'bi-cloud';

            widget.innerHTML = `
                <div class="weather-main">
                    <i class="bi ${iconClass} weather-icon"></i>
                    <div>
                        <div class="weather-temp">${weather.tempC}&deg;C</div>
                        <div class="weather-cond">${weather.condition}</div>
                    </div>
                </div>
                <div class="weather-grid">
                    <div><div class="w-val">${weather.humidity}%</div><div class="w-label">Humidity</div></div>
                    <div><div class="w-val">${weather.windKmh} km/h</div><div class="w-label">Wind</div></div>
                </div>
            `;
        } catch (err) {
            console.warn('Could not load weather from the API — is the Flask server running?', err);
            widget.innerHTML = `<p class="RP-subtle mb-0" style="font-size:0.85rem;">Weather unavailable right now.</p>`;
        }
    }

    loadWeather();

    /* =================================================================
       CONGESTION PREDICTION PANEL — real data from GET /api/predictions
       Heuristic forecast derived from recent incident density, not a
       live traffic-speed feed — see predictions.py for the reasoning.
       ================================================================= */
    async function loadPredictions() {
        const list = document.getElementById('prediction-list');
        let predictions = [];
        try {
            const res = await fetch('/api/predictions');
            if (!res.ok) throw new Error('Request failed');
            predictions = await res.json();
        } catch (err) {
            console.warn('Could not load predictions from the API — is the Flask server running?', err);
        }

        if (predictions.length === 0) {
            list.innerHTML = `<p class="RP-subtle mb-0" style="font-size:0.85rem;">Not enough recent activity to forecast congestion yet.</p>`;
            return;
        }

        list.innerHTML = predictions.map((p) => {
            const cls = p.level.toLowerCase();
            return `
                <div class="prediction-item">
                    <div class="p-row">
                        <span class="p-road">${p.road}</span>
                        <span class="p-level badge-severity badge-${cls}">${p.level}</span>
                    </div>
                    <div class="progress">
                        <div class="progress-bar progress-bar-${cls}" style="width:${p.pct}%"></div>
                    </div>
                </div>
            `;
        }).join('');
    }

    loadPredictions();

    /* =================================================================
       QUICK ACTIONS
       ================================================================= */
    document.getElementById('qa-refresh').addEventListener('click', (e) => {
        const btn = e.currentTarget;
        btn.classList.add('disabled');
        const icon = btn.querySelector('i');
        icon.style.animation = 'spin 0.6s linear infinite';

        loadIncidents().finally(() => {
            document.getElementById('last-updated').textContent =
                'Updated ' + new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            icon.style.animation = '';
            btn.classList.remove('disabled');
        });
        loadStats();
        loadPredictions();
    });

    document.getElementById('qa-report').addEventListener('click', () => {
        alert('This will generate a downloadable PDF/CSV report once the Analytics module is connected.');
    });

    document.getElementById('qa-heatmap').addEventListener('click', () => {
        showHeatmap();
        document.getElementById('map-section').scrollIntoView({ behavior: 'smooth', block: 'center' });
    });

    /* =================================================================
       CHARTS (Chart.js) — real data from GET /api/analytics/summary
       ================================================================= */
    Chart.defaults.color = '#8b97a3';
    Chart.defaults.font = { family: 'Inter', size: 11 };

    const chartTypeColor = {
        Accident: '#e1543a', Pothole: '#f2a93b', Waterlogging: '#3fc1b0',
        'Signal Fault': '#8b97a3', Roadblock: '#4caf7d', Other: '#c3cbd3'
    };

    async function loadAnalytics() {
        let summaryData = { by_type: [], by_hour: Array.from({ length: 24 }, (_, h) => ({ hour: h, count: 0 })) };
        try {
            const res = await fetch('/api/analytics/summary');
            if (!res.ok) throw new Error('Request failed');
            summaryData = await res.json();
        } catch (err) {
            console.warn('Could not load analytics from the API — is the Flask server running?', err);
        }

        // Pie — incidents by type
        new Chart(document.getElementById('chart-pie'), {
            type: 'doughnut',
            data: {
                labels: summaryData.by_type.map((d) => d.type),
                datasets: [{
                    data: summaryData.by_type.map((d) => d.count),
                    backgroundColor: summaryData.by_type.map((d) => chartTypeColor[d.type] || '#8b97a3'),
                    borderColor: '#10161d',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, padding: 12 } } }
            }
        });

        // Line — incidents reported by hour of day (proxy for activity, not a real congestion feed)
        new Chart(document.getElementById('chart-line'), {
            type: 'line',
            data: {
                labels: summaryData.by_hour.map((d) => `${d.hour}:00`),
                datasets: [{
                    label: 'Incidents Reported',
                    data: summaryData.by_hour.map((d) => d.count),
                    borderColor: '#f2a93b',
                    backgroundColor: 'rgba(242,169,59,0.12)',
                    fill: true,
                    tension: 0.35,
                    pointRadius: 0,
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { color: '#212b36' }, ticks: { maxTicksLimit: 6 } },
                    y: { grid: { color: '#212b36' }, beginAtZero: true, ticks: { precision: 0 } }
                }
            }
        });
    }

    loadAnalytics();

    /* =================================================================
       CITYWIDE STATUS BANNER — last updated time
       ================================================================= */
    document.getElementById('last-updated').textContent =
        'Updated ' + new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
});
