document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('login-form');
  const button = document.getElementById('login-button');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const email = form.email.value;
    const password = form.password.value;

    clearFormErrors([
      { fieldId: 'email-field', errorId: 'email-error' },
      { fieldId: 'password-field', errorId: 'password-error' },
    ]);

    const errors = validateLoginForm(email, password);

    if (hasErrors(errors)) {
      if (errors.email) showFieldError('email-field', 'email-error', errors.email);
      if (errors.password) showFieldError('password-field', 'password-error', errors.password);
      return;
    }

    button.disabled = true;
    button.textContent = 'Signing in...';

    const { ok, data } = await apiPost('/api/auth/login', { email, password });

    if (!ok) {
      button.disabled = false;
      button.textContent = 'Sign in';
      const fieldErrors = data.errors || {};
      if (fieldErrors.email) showFieldError('email-field', 'email-error', fieldErrors.email);
      if (fieldErrors.password) showFieldError('password-field', 'password-error', fieldErrors.password);
      if (!fieldErrors.email && !fieldErrors.password) {
        showFieldError('password-field', 'password-error', data.message || 'Login failed');
      }
      return;
    }

    localStorage.setItem('queuesmart_token', data.token);
    localStorage.setItem('queuesmart_user', JSON.stringify(data.user));

    window.location.href = 'home.html';
  });

  ['email', 'password'].forEach((name) => {
    form[name].addEventListener('input', () => {
      const fieldId = `${name}-field`;
      const errorId = `${name}-error`;
      showFieldError(fieldId, errorId, '');
    });
  });
});
