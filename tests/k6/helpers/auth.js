import http from 'k6/http';

const BASE_URL = __ENV.BASE_URL || 'https://quickpizza.grafana.com';

export function getAuthHeaders() {
  const res = http.post(`${BASE_URL}/api/users/token/login`, JSON.stringify({
    username: 'default', password: '1234',
  }), { headers: { 'Content-Type': 'application/json' } });
  return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${res.json('token')}` };
}

export function loginAndGetToken() {
  const res = http.post(`${BASE_URL}/api/users/token/login`, JSON.stringify({
    username: 'default', password: '1234',
  }), { headers: { 'Content-Type': 'application/json' } });
  return res.json('token');
}
