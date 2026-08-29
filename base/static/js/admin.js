// RoadPulse — admin.js
//
// Endpoints used:
//   GET    /api/admin/incidents?status=pending|verified|rejected|all
//   POST   /api/admin/incidents/:id/approve
//   POST   /api/admin/incidents/:id/reject
//   DELETE /api/admin/incidents/:id
//   GET    /api/admin/sessions            -> [{ username, location, login_at }]

document.addEventListener('DOMContentLoaded', () => {

    const incidentsList = document.getElementById('incidents-list');
    const sessionsList = document.getElementById('sessions-list');
    const incidentTemplate = document.getElementById('incident-row-template');
    const sessionTemplate = document.getElementById('session-row-template');
    const statusDot = document.querySelector('.status-dot');
    const connectionLabel = document.getElementById('connection-label');
    const incidentFilter = document.getElementById('incident-filter');

    /* ---------- user menu dropdown ---------- */
    const userMenuToggle = document.getElementById('user-menu-toggle');
    const userMenuDropdown = document.getElementById('user-menu-dropdown');

    function closeUserMenu() {
        userMenuDropdown.hidden = true;
        userMenuToggle.setAttribute('aria-expanded', 'false');
    }

    userMenuToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = !userMenuDropdown.hidden;
        if (isOpen) {
            closeUserMenu();
        } else {
            userMenuDropdown.hidden = false;
            userMenuToggle.setAttribute('aria-expanded', 'true');
        }
    });

    document.addEventListener('click', (e) => {
        if (!userMenuDropdown.hidden && !e.target.closest('.user-menu')) {
            closeUserMenu();
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeUserMenu();
    });

    /* ---------- empty state builder ---------- */
    function emptyState(container, title, body) {
        container.innerHTML = '';
        const el = document.createElement('div');
        el.className = 'empty-state';
        el.innerHTML = `
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.4"/>
                <path d="M9 12h6M12 9v6" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
            </svg>
            <h3>${title}</h3>
            <p>${body}</p>
        `;
        container.appendChild(el);
    }

    function timeAgo(isoString) {
        const diffMs = Date.now() - new Date(isoString).getTime();
        const mins = Math.round(diffMs / 60000);
        if (mins < 1) return 'just now';
        if (mins < 60) return `${mins}m ago`;
        return `${Math.round(mins / 60)}h ago`;
    }

    /* ---------- incidents ---------- */
    const STATUS_LABELS = {
        pending: 'Pending', verified: 'Verified', rejected: 'Rejected'
    };

    const EMPTY_MESSAGES = {
        pending: 'No incidents awaiting review',
        verified: 'No verified incidents',
        rejected: 'No rejected incidents',
        all: 'No incidents yet'
    };

    function renderIncidents(incidents) {
        if (incidents.length === 0) {
            emptyState(
                incidentsList,
                EMPTY_MESSAGES[incidentFilter.value] || 'No incidents found',
                'Reports matching this filter will appear here.'
            );
            return;
        }

        incidentsList.innerHTML = '';
        incidents.forEach((incident) => {
            const node = incidentTemplate.content.cloneNode(true);
            const row = node.querySelector('.row');
            row.dataset.id = incident.id;
            row.querySelector('.row-type').textContent = incident.type;
            row.querySelector('.row-time').textContent = timeAgo(incident.reported_at);
            row.querySelector('.row-desc').textContent = incident.description;
            row.querySelector('.row-location').textContent = incident.location;

            const statusEl = row.querySelector('.row-status');
            statusEl.textContent = STATUS_LABELS[incident.status] || incident.status;
            statusEl.classList.add(`row-status-${incident.status}`);

            const photo = row.querySelector('.row-photo');
            if (incident.photo_url) {
                photo.src = incident.photo_url;
                photo.hidden = false;
            }

            // Approve/Reject only make sense for incidents still pending
            // review — everything else (verified/rejected) only
            // gets Delete, so admins can still clean those up.
            const approveBtn = row.querySelector('.btn-approve');
            const rejectBtn = row.querySelector('.btn-reject');
            if (incident.status === 'pending') {
                approveBtn.addEventListener('click', () => reviewIncident(incident.id, 'approve', row));
                rejectBtn.addEventListener('click', () => reviewIncident(incident.id, 'reject', row));
            } else {
                approveBtn.remove();
                rejectBtn.remove();
            }

            row.querySelector('.btn-delete').addEventListener('click', () => deleteIncident(incident.id, row));

            incidentsList.appendChild(node);
        });
    }

    function afterRowRemoved(row) {
        row.remove();
        if (incidentsList.querySelectorAll('.row').length === 0) {
            emptyState(
                incidentsList,
                EMPTY_MESSAGES[incidentFilter.value] || 'No incidents found',
                'You\u2019re all caught up.'
            );
        }
        // Keep the "Pending review" summary card accurate no matter which
        // filter is currently on screen.
        loadPendingCount();
    }

    async function reviewIncident(id, action, row) {
        row.style.opacity = '0.5';
        try {
            const res = await fetch(`/api/admin/incidents/${id}/${action}`, { method: 'POST' });
            if (!res.ok) throw new Error('Request failed');
            afterRowRemoved(row);
            if (action === 'approve') {
                const approvedEl = document.getElementById('count-approved');
                approvedEl.textContent = Number(approvedEl.textContent) + 1;
            }
        } catch (err) {
            row.style.opacity = '1';
            console.error(`Failed to ${action} incident ${id}`, err);
        }
    }

    async function deleteIncident(id, row) {
        if (!confirm('Permanently delete this report? This cannot be undone.')) return;
        row.style.opacity = '0.5';
        try {
            const res = await fetch(`/api/admin/incidents/${id}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Request failed');
            afterRowRemoved(row);
        } catch (err) {
            row.style.opacity = '1';
            console.error(`Failed to delete incident ${id}`, err);
        }
    }

    /* ---------- sessions ---------- */
    function renderSessions(sessions) {
        document.getElementById('count-sessions').textContent = sessions.length;

        if (sessions.length === 0) {
            emptyState(
                sessionsList,
                'No users currently logged in',
                'Active sessions will show up here once Authentication is connected to the database.'
            );
            return;
        }

        sessionsList.innerHTML = '';
        sessions.forEach((session) => {
            const node = sessionTemplate.content.cloneNode(true);
            node.querySelector('.row-type').textContent = session.username;
            node.querySelector('.row-time').textContent = timeAgo(session.login_at);
            node.querySelector('.row-location').textContent = session.location || '';
            sessionsList.appendChild(node);
        });
    }

    /* ---------- data loading ---------- */
    async function loadIncidents() {
        try {
            const res = await fetch(`/api/admin/incidents?status=${encodeURIComponent(incidentFilter.value)}`);
            if (!res.ok) throw new Error('not ok');
            renderIncidents(await res.json());
            return true;
        } catch (err) {
            // Request failed — show the empty state, caller decides how to
            // reflect that in the connection indicator.
            renderIncidents([]);
            return false;
        }
    }

    async function loadPendingCount() {
        // Always reflects the true pending count, independent of whichever
        // status filter happens to be selected in the list above.
        try {
            const res = await fetch('/api/admin/incidents?status=pending');
            if (!res.ok) throw new Error('not ok');
            const pending = await res.json();
            document.getElementById('count-pending').textContent = pending.length;
        } catch (err) {
            // leave the last-known value on screen
        }
    }

    async function loadSessions() {
        try {
            const res = await fetch('/api/admin/sessions');
            if (!res.ok) throw new Error('not ok');
            renderSessions(await res.json());
            return true;
        } catch (err) {
            renderSessions([]);
            return false;
        }
    }

    async function refreshAll() {
        const [incidentsOk, sessionsOk] = await Promise.all([loadIncidents(), loadSessions(), loadPendingCount()]);
        reflectConnection(incidentsOk && sessionsOk);
    }

    function reflectConnection(ok) {
        statusDot.dataset.state = ok ? 'online' : 'offline';
        connectionLabel.textContent = ok ? 'Connected' : 'Not connected to database';
    }

    document.getElementById('refresh-incidents').addEventListener('click', async () => {
        reflectConnection(await loadIncidents());
        loadPendingCount();
    });
    document.getElementById('refresh-sessions').addEventListener('click', async () => {
        reflectConnection(await loadSessions());
    });

    incidentFilter.addEventListener('change', loadIncidents);

    refreshAll();
});
