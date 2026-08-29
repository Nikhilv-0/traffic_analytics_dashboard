// RoadPulse — profile.js
// Populates the My Reports table from GET /api/incidents/mine.
// Account details (name/email/role/member-since/report-count) are
// rendered server-side in profile.html via current_user — no fetch
// needed for those.

document.addEventListener('DOMContentLoaded', () => {

    function timeAgo(isoString) {
        const diffMs = Date.now() - new Date(isoString).getTime();
        const mins = Math.round(diffMs / 60000);
        if (mins < 1) return 'just now';
        if (mins < 60) return `${mins}m ago`;
        if (mins < 1440) return `${Math.round(mins / 60)}h ago`;
        return `${Math.round(mins / 1440)}d ago`;
    }

    const tbody = document.getElementById('my-reports-table-body');

    function renderReports(list) {
        if (list.length === 0) {
            tbody.innerHTML = `
                <tr><td colspan="6" class="text-center RP-subtle py-4">
                    You haven't reported any incidents yet.
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

    async function loadMyReports() {
        try {
            const res = await fetch('/api/incidents/mine');
            if (!res.ok) throw new Error('Request failed');
            renderReports(await res.json());
        } catch (err) {
            console.warn('Could not load your reports from the API — is the Flask server running?', err);
            tbody.innerHTML = `
                <tr><td colspan="6" class="text-center RP-subtle py-4">
                    Could not load your reports right now.
                </td></tr>`;
        }
    }

    loadMyReports();

    document.getElementById('refresh-my-reports').addEventListener('click', loadMyReports);
});
