// RoadPulse — incidents.js
// Populates the full active-incidents table from GET /api/incidents/active.
// This page is intentionally simple: just a list of every incident that's
// currently pending or verified — no filters, no map, no charts.

document.addEventListener('DOMContentLoaded', () => {

    function timeAgo(isoString) {
        const diffMs = Date.now() - new Date(isoString).getTime();
        const mins = Math.round(diffMs / 60000);
        if (mins < 1) return 'just now';
        if (mins < 60) return `${mins}m ago`;
        if (mins < 1440) return `${Math.round(mins / 60)}h ago`;
        return `${Math.round(mins / 1440)}d ago`;
    }

    const tbody = document.getElementById('incidents-table-body');

    function renderIncidents(list) {
        if (list.length === 0) {
            tbody.innerHTML = `
                <tr><td colspan="6" class="text-center RP-subtle py-4">
                    No active incidents right now.
                </td></tr>`;
            return;
        }

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

    async function loadIncidents() {
        try {
            const res = await fetch('/api/incidents/active');
            if (!res.ok) throw new Error('Request failed');
            renderIncidents(await res.json());
        } catch (err) {
            console.warn('Could not load incidents from the API — is the Flask server running?', err);
            tbody.innerHTML = `
                <tr><td colspan="6" class="text-center RP-subtle py-4">
                    Could not load incidents right now.
                </td></tr>`;
        }
    }

    loadIncidents();

    document.getElementById('refresh-incidents').addEventListener('click', loadIncidents);
});
