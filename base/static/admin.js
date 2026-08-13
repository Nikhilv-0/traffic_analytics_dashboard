// RoadPulse — admin.js
//
// The Authentication + Incident modules aren't wired to a database yet,
// so both lists are intentionally empty right now. This file is written
// against the endpoints the Flask Admin module is expected to expose —
// once those exist, real data will flow in with no markup changes needed.
//
// Expected endpoints:
//   GET    /api/admin/incidents/pending   -> [{ id, type, description, location, reported_at }]
//   POST   /api/admin/incidents/:id/approve
//   POST   /api/admin/incidents/:id/reject
//   GET    /api/admin/sessions            -> [{ username, location, login_at }]

document.addEventListener('DOMContentLoaded', () => {

    const incidentsList = document.getElementById('incidents-list');
    const sessionsList = document.getElementById('sessions-list');
    const incidentTemplate = document.getElementById('incident-row-template');
    const sessionTemplate = document.getElementById('session-row-template');
    const statusDot = document.querySelector('.status-dot');
    const connectionLabel = document.getElementById('connection-label');

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
    function renderIncidents(incidents) {
        document.getElementById('count-pending').textContent = incidents.length;

        if (incidents.length === 0) {
            emptyState(
                incidentsList,
                'No incidents awaiting review',
                'Reports submitted by users will appear here once the Incident module is connected to the database.'
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

            const photo = row.querySelector('.row-photo');
            if (incident.photo_url) {
                photo.src = incident.photo_url;
                photo.hidden = false;
            }

            row.querySelector('.btn-approve').addEventListener('click', () => reviewIncident(incident.id, 'approve', row));
            row.querySelector('.btn-reject').addEventListener('click', () => reviewIncident(incident.id, 'reject', row));

            incidentsList.appendChild(node);
        });
    }

    async function reviewIncident(id, action, row) {
        row.style.opacity = '0.5';
        try {
            const res = await fetch(`/api/admin/incidents/${id}/${action}`, { method: 'POST' });
            if (!res.ok) throw new Error('Request failed');
            row.remove();
            const remaining = incidentsList.querySelectorAll('.row').length;
            document.getElementById('count-pending').textContent = remaining;
            if (action === 'approve') {
                const approvedEl = document.getElementById('count-approved');
                approvedEl.textContent = Number(approvedEl.textContent) + 1;
            }
            if (remaining === 0) {
                emptyState(incidentsList, 'No incidents awaiting review', 'You\u2019re all caught up.');
            }
        } catch (err) {
            row.style.opacity = '1';
            console.error(`Failed to ${action} incident ${id}`, err);
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
            const res = await fetch('/api/admin/incidents/pending');
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
        const [incidentsOk, sessionsOk] = await Promise.all([loadIncidents(), loadSessions()]);
        reflectConnection(incidentsOk && sessionsOk);
    }

    function reflectConnection(ok) {
        statusDot.dataset.state = ok ? 'online' : 'offline';
        connectionLabel.textContent = ok ? 'Connected' : 'Not connected to database';
    }

    document.getElementById('refresh-incidents').addEventListener('click', async () => {
        reflectConnection(await loadIncidents());
    });
    document.getElementById('refresh-sessions').addEventListener('click', async () => {
        reflectConnection(await loadSessions());
    });

    refreshAll();
});
