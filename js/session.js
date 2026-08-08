/** Shared session helpers for QueueSmart pages. */

function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem('queuesmart_user') || 'null');
  } catch {
    return null;
  }
}

function getStoredToken() {
  return localStorage.getItem('queuesmart_token');
}

function requireAuth(options = {}) {
  const token = getStoredToken();
  const user = getStoredUser();
  if (!token || !user) {
    window.location.href = 'login.html';
    return null;
  }
  if (options.adminOnly && user.role !== 'Administrator') {
    window.location.href = 'homescreen.html';
    return null;
  }
  if (options.userOnly && user.role === 'Administrator') {
    window.location.href = 'admin.html';
    return null;
  }
  return user;
}

async function logout() {
  const token = getStoredToken();
  if (token) {
    try {
      await apiPost('/api/auth/logout', {});
    } catch (_) {
      /* ignore network errors on logout */
    }
  }
  localStorage.removeItem('queuesmart_token');
  localStorage.removeItem('queuesmart_user');
  window.location.href = 'login.html';
}

function displayName(user) {
  if (!user) return 'User';
  const full = `${user.first_name || ''} ${user.last_name || ''}`.trim();
  return full || user.email || 'User';
}
