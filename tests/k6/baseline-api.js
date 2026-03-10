import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { loginAndGetToken } from './helpers/auth.js';

const BASE_URL = __ENV.BASE_URL || 'https://quickpizza.grafana.com';

export const options = {
  scenarios: {
    baseline: {
      executor: 'ramping-vus',
      stages: [
        { duration: '30s', target: 10 },
        { duration: '1m', target: 20 },
        { duration: '30s', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<2000'],
  },
};

export function setup() {
  const token = loginAndGetToken();
  return { token: token };
}

export default function (data) {
  group('API Health', function () {
    const res = http.get(`${BASE_URL}/api/status/200`);
    check(res, { 'health returns 200': (r) => r.status === 200 });
  });
  group('Get Ratings', function () {
    const res = http.get(`${BASE_URL}/api/ratings`, {
      headers: { 'Authorization': `Bearer ${data.token}` },
    });
    check(res, {
      'ratings 200': (r) => r.status === 200,
      'has ratings array': (r) => {
        try { return JSON.parse(r.body).ratings !== undefined; } catch { return false; }
      },
    });
  });
  group('Recommend Pizza', function () {
    const res = http.post(`${BASE_URL}/api/pizza`, JSON.stringify({}), {
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${data.token}` },
    });
    check(res, {
      'pizza 200': (r) => r.status === 200,
      'has pizza': (r) => {
        try { return JSON.parse(r.body).pizza !== undefined; } catch { return false; }
      },
    });
  });
  sleep(1);
}
