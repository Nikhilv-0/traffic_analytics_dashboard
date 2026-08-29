// RoadPulse — login.js
// Handles: password visibility toggle, register password strength/match
// feedback, and submit handlers that call the Flask Authentication module.
// Endpoints assumed: POST /api/auth/login, POST /api/auth/register
// Adjust the URLs/payload keys to match your actual Flask routes.

document.addEventListener('DOMContentLoaded', () => {

    /* ---------- password show/hide ---------- */
    document.querySelectorAll('.toggle-visibility').forEach((btn) => {
        btn.addEventListener('click', () => {
            const input = btn.previousElementSibling;
            const showing = input.type === 'text';
            input.type = showing ? 'password' : 'text';
            btn.setAttribute('aria-pressed', String(!showing));
            btn.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
        });
    });

    /* ---------- register: password strength meter ---------- */
    const regPassword = document.getElementById('register-password');
    const strengthMeter = document.querySelector('.strength-meter');
    const passwordHint = document.getElementById('password-hint');

    function scorePassword(value) {
        let score = 0;
        if (value.length >= 8) score++;
        if (/[A-Z]/.test(value) && /[a-z]/.test(value)) score++;
        if (/\d/.test(value)) score++;
        if (/[^A-Za-z0-9]/.test(value)) score++;
        return score;
    }

    if (regPassword) {
        regPassword.addEventListener('input', () => {
            const score = scorePassword(regPassword.value);
            const levels = ['', 'weak', 'fair', 'good', 'strong'];
            strengthMeter.className = 'strength-meter ' + (levels[score] || '');
            passwordHint.textContent = regPassword.value.length === 0
                ? 'At least 8 characters'
                : ['Too short', 'Weak', 'Fair', 'Good', 'Strong'][score];
        });
    }

    /* ---------- register: confirm password match ---------- */
    const confirmInput = document.getElementById('register-confirm');
    const confirmHint = document.getElementById('confirm-hint');

    function checkMatch() {
        if (!confirmInput.value) {
            confirmHint.hidden = true;
            return true;
        }
        const matches = confirmInput.value === regPassword.value;
        confirmHint.hidden = matches;
        return matches;
    }

    if (confirmInput) {
        confirmInput.addEventListener('input', checkMatch);
        regPassword.addEventListener('input', checkMatch);
    }

    /* ---------- shared helpers ---------- */
    const messageBox = document.getElementById('form-message');

    function showMessage(text, type) {
        messageBox.textContent = text;
        messageBox.className = 'form-message' + (type === 'success' ? ' success' : '');
        messageBox.hidden = false;
    }

    function hideMessage() {
        messageBox.hidden = true;
    }

    function setLoading(form, isLoading) {
        const btn = form.querySelector('.btn');
        btn.classList.toggle('loading', isLoading);
        btn.disabled = isLoading;
    }

    /* ---------- login submit ---------- */
    const loginForm = document.getElementById('login-form');
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideMessage();

        if (!loginForm.checkValidity()) {
            loginForm.reportValidity();
            return;
        }

        const payload = {
            email: document.getElementById('login-email').value.trim(),
            password: document.getElementById('login-password').value,
            remember: document.getElementById('remember-me').checked
        };

        setLoading(loginForm, true);
        try {
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json().catch(() => ({}));

            if (!res.ok) {
                showMessage(data.message || 'Invalid email or password.', 'error');
                return;
            }

            showMessage('Signed in — redirecting…', 'success');
            window.location.href = data.redirect || '/dashboard';
        } catch (err) {
            showMessage('Could not reach the server. Please try again.', 'error');
        } finally {
            setLoading(loginForm, false);
        }
    });

    /* ---------- register submit ---------- */
    const registerForm = document.getElementById('register-form');
    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hideMessage();

        if (!registerForm.checkValidity()) {
            registerForm.reportValidity();
            return;
        }
        if (!checkMatch()) {
            showMessage("Passwords don't match.", 'error');
            return;
        }

        const payload = {
            name: document.getElementById('register-name').value.trim(),
            email: document.getElementById('register-email').value.trim(),
            password: regPassword.value
        };

        setLoading(registerForm, true);
        try {
            const res = await fetch('/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json().catch(() => ({}));

            if (!res.ok) {
                showMessage(data.message || 'Registration failed. Try a different email.', 'error');
                return;
            }

            showMessage('Account created — you can log in now.', 'success');
            registerForm.reset();
            document.getElementById('login-tab').checked = true;
        } catch (err) {
            showMessage('Could not reach the server. Please try again.', 'error');
        } finally {
            setLoading(registerForm, false);
        }
    });
});
