const API_BASE_URL = 'http://127.0.0.1:5000';

async function apiPost(path, body) {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    return { ok: response.ok, status: response.status, data };
  } catch (err) {
    return {
      ok: false,
      status: 0,
      data: { message: 'Could not reach the server. Is the backend running?' },
    };
  }
}
