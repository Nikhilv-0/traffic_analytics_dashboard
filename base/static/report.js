// RoadPulse — report.js
// Submits to the Flask Incident Module. Endpoint assumed:
//   POST /api/incidents  (multipart/form-data: type, severity, description,
//                          location_desc, lat, lng, reporter_name, photo)
// Adjust the URL/field names once the actual Flask route exists.

document.addEventListener('DOMContentLoaded', () => {

    /* =================================================================
       LOCATION PICKER MAP
       ================================================================= */
    // Andheri, Mumbai Suburban — keep in sync with weather.py and dashboard.js
    const CITY_CENTER = [19.1136, 72.8697];

    const map = L.map('pickerMap').setView(CITY_CENTER, 13);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);

    let marker = null;
    let selectedLat = null;
    let selectedLng = null;
    const coordText = document.getElementById('coord-text');

    function setLocation(lat, lng) {
        selectedLat = lat;
        selectedLng = lng;

        if (marker) {
            marker.setLatLng([lat, lng]);
        } else {
            marker = L.marker([lat, lng], { draggable: true }).addTo(map);
            marker.on('dragend', () => {
                const pos = marker.getLatLng();
                setLocation(pos.lat, pos.lng);
            });
        }

        coordText.textContent = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
    }

    map.on('click', (e) => setLocation(e.latlng.lat, e.latlng.lng));

    document.getElementById('use-my-location').addEventListener('click', () => {
        if (!navigator.geolocation) {
            alert('Location access is not available in this browser.');
            return;
        }
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const { latitude, longitude } = pos.coords;
                map.setView([latitude, longitude], 15);
                setLocation(latitude, longitude);
            },
            () => alert('Could not access your location. You can still click the map to drop a pin.')
        );
    });

    /* =================================================================
       PHOTO UPLOAD PREVIEW
       ================================================================= */
    const photoInput = document.getElementById('photo-input');
    const dropzone = document.getElementById('dropzone');
    const previewWrap = document.getElementById('photo-preview');
    const previewImg = document.getElementById('photo-preview-img');

    photoInput.addEventListener('change', () => {
        const file = photoInput.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            previewImg.src = e.target.result;
            previewWrap.hidden = false;
            dropzone.hidden = true;
        };
        reader.readAsDataURL(file);
    });

    document.getElementById('remove-photo').addEventListener('click', () => {
        photoInput.value = '';
        previewWrap.hidden = true;
        dropzone.hidden = false;
    });

    /* =================================================================
       DESCRIPTION CHARACTER COUNTER
       ================================================================= */
    const descField = document.getElementById('incident-desc');
    const charCount = document.getElementById('char-count');
    descField.addEventListener('input', () => {
        charCount.textContent = `${descField.value.length} / 500`;
    });

    /* =================================================================
       FORM SUBMIT
       ================================================================= */
    const form = document.getElementById('report-form');
    const messageBox = document.getElementById('report-message');
    const submitBtn = document.getElementById('submit-btn');

    function showMessage(text, type) {
        messageBox.textContent = text;
        messageBox.className = 'form-message' + (type === 'success' ? ' success' : '');
        messageBox.hidden = false;
        messageBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        messageBox.hidden = true;

        const type = document.getElementById('incident-type').value;
        const severity = form.querySelector('input[name="severity"]:checked')?.value;
        const description = descField.value.trim();
        const locationDesc = document.getElementById('location-desc').value.trim();

        if (!type || !severity || !description || !locationDesc) {
            form.reportValidity();
            return;
        }
        if (selectedLat === null || selectedLng === null) {
            showMessage('Please pin the incident location on the map.', 'error');
            return;
        }

        const payload = new FormData();
        payload.append('type', type);
        payload.append('severity', severity);
        payload.append('description', description);
        payload.append('location_desc', locationDesc);
        payload.append('lat', selectedLat);
        payload.append('lng', selectedLng);
        payload.append('reporter_name', document.getElementById('reporter-name').value.trim() || 'Guest');
        if (photoInput.files[0]) payload.append('photo', photoInput.files[0]);

        submitBtn.classList.add('loading');
        submitBtn.disabled = true;

        try {
            const res = await fetch('/api/incidents', { method: 'POST', body: payload });
            const data = await res.json().catch(() => ({}));

            if (!res.ok) {
                showMessage(data.message || 'Could not submit the report. Please try again.', 'error');
                return;
            }

            showMessage('Thanks — your report has been submitted for review.', 'success');
            form.reset();
            charCount.textContent = '0 / 500';
            previewWrap.hidden = true;
            dropzone.hidden = false;
            if (marker) { map.removeLayer(marker); marker = null; }
            selectedLat = null;
            selectedLng = null;
            coordText.textContent = 'Click on the map to drop a pin';
            document.getElementById('sev-medium').checked = true;
        } catch (err) {
            showMessage('Could not reach the server. Your report has not been submitted yet.', 'error');
        } finally {
            submitBtn.classList.remove('loading');
            submitBtn.disabled = false;
        }
    });
});
