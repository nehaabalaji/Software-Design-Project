const API_BASE_URL =
  window.location.port === '5000' ? '' : 'http://127.0.0.1:5000';

function authHeaders() {
  const token = localStorage.getItem('queuesmart_token');
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function apiRequest(method, path, body) {
  try {
    const options = { method, headers: authHeaders() };
    if (body !== undefined) options.body = JSON.stringify(body);
    const response = await fetch(`${API_BASE_URL}${path}`, options);
    const data = await response.json().catch(() => ({}));
    return { ok: response.ok, status: response.status, data };
  } catch (err) {
    return {
      ok: false,
      status: 0,
      data: { message: 'Could not reach the server. Is the backend running on port 5000?' },
    };
  }
}

async function apiPost(path, body) {
  return apiRequest('POST', path, body);
}

async function apiGet(path) {
  return apiRequest('GET', path);
}

async function apiPut(path, body) {
  return apiRequest('PUT', path, body);
}

async function apiDelete(path) {
  return apiRequest('DELETE', path);
}

// Downloads use a plain authenticated fetch (not JSON) so the browser never
// sees the token in the URL, then saves the response as a file via a
// throwaway <a download> link.
async function apiDownload(path, filename) {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, { headers: authHeaders() });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      return { ok: false, status: response.status, data };
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    return { ok: true, status: response.status };
  } catch (err) {
    return { ok: false, status: 0, data: { message: 'Could not reach the server.' } };
  }
}
