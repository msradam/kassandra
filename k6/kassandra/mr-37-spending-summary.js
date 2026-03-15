import http from 'k6/http';
import { check, group } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

const BASE_URL = 'http://localhost:8000';

// Custom metrics
const spendingSummaryLatency = new Trend('spending_summary_latency', true);
const spendingSummaryErrors = new Rate('spending_summary_errors');
const spendingSummarySuccess = new Counter('spending_summary_success');
const healthCheckLatency = new Trend('health_check_latency', true);

export const options = {
  scenarios: {
    warmup: {
      executor: 'constant-arrival-rate',
      exec: 'healthCheck',
      rate: 5,
      timeUnit: '1s',
      duration: '10s',
      preAllocatedVUs: 10,
      maxVUs: 20,
      startTime: '0s',
    },
    steady_load: {
      executor: 'constant-arrival-rate',
      exec: 'spendingSummaryFlow',
      rate: 10,
      timeUnit: '1s',
      duration: '30s',
      preAllocatedVUs: 20,
      maxVUs: 40,
      startTime: '10s',
      gracefulStop: '5s',
    },
    spike: {
      executor: 'ramping-arrival-rate',
      exec: 'spendingSummaryFlow',
      startRate: 10,
      timeUnit: '1s',
      stages: [
        { target: 40, duration: '10s' },
        { target: 10, duration: '10s' },
      ],
      preAllocatedVUs: 30,
      maxVUs: 60,
      startTime: '40s',
      gracefulStop: '5s',
    },
  },
  thresholds: {
    // Global error rate threshold with abort
    'http_req_failed': [
      { threshold: 'rate<0.01', abortOnFail: true, delayAbortEval: '10s' },
    ],
    // Per-endpoint thresholds
    'http_req_duration{endpoint:spending_summary}': ['p(95)<1500'],
    'http_req_duration{endpoint:health}': ['p(95)<800'],
    'http_req_duration{scenario:steady_load}': ['p(95)<1500'],
    'http_req_duration{scenario:spike}': ['p(95)<2000'],
    // Custom metric thresholds
    'spending_summary_latency': ['p(95)<1500', 'p(99)<2000'],
    'spending_summary_errors': ['rate<0.01'],
  },
};

// Setup: authenticate and create test data
export function setup() {
  // Login to get auth token
  const loginRes = http.post(
    `${BASE_URL}/api/auth/login`,
    JSON.stringify({
      email: 'banker@midas.dev',
      password: 'midas123',
    }),
    {
      headers: { 'Content-Type': 'application/json' },
    }
  );

  if (loginRes.status !== 200) {
    throw new Error(`Login failed: ${loginRes.status} ${loginRes.body}`);
  }

  const authData = loginRes.json();
  const token = authData.token;

  // Get existing accounts
  const accountsRes = http.get(`${BASE_URL}/api/accounts`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  let accountId;
  if (accountsRes.status === 200) {
    const accounts = accountsRes.json().accounts;
    if (accounts && accounts.length > 0) {
      accountId = accounts[0].id;
    }
  }

  // Create account if none exists
  if (!accountId) {
    const createAcctRes = http.post(
      `${BASE_URL}/api/accounts`,
      JSON.stringify({
        name: 'Test Spending Account',
        currency: 'USD',
      }),
      {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
      }
    );

    if (createAcctRes.status === 201) {
      accountId = createAcctRes.json().id;
    } else {
      throw new Error(`Failed to create account: ${createAcctRes.status}`);
    }
  }

  // Create some transactions for testing
  for (let i = 0; i < 10; i++) {
    http.post(
      `${BASE_URL}/api/transactions/deposit`,
      JSON.stringify({
        account_id: accountId,
        amount: Math.random() * 100 + 10,
        description: `Test deposit ${i}`,
      }),
      {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
      }
    );
  }

  return { token, accountId };
}

// Health check scenario
export function healthCheck() {
  group('Health Check', () => {
    const res = http.get(`${BASE_URL}/api/health`, {
      tags: { endpoint: 'health' },
    });

    const success = check(res, {
      'health status is 200': (r) => r.status === 200,
      'health response has status field': (r) => {
        try {
          const body = r.json();
          return body.status !== undefined;
        } catch {
          return false;
        }
      },
      'health content-type is JSON': (r) =>
        r.headers['Content-Type']?.includes('application/json'),
      'health response time < 500ms': (r) => r.timings.duration < 500,
    });

    healthCheckLatency.add(res.timings.duration);
  });
}

// Main spending summary flow
export function spendingSummaryFlow(data) {
  const { token, accountId } = data;

  group('Spending Summary', () => {
    const res = http.get(
      `${BASE_URL}/api/accounts/${accountId}/spending`,
      {
        headers: { Authorization: `Bearer ${token}` },
        tags: { endpoint: 'spending_summary' },
      }
    );

    const success = check(res, {
      'spending summary status is 200': (r) => r.status === 200,
      'spending summary content-type is JSON': (r) =>
        r.headers['Content-Type']?.includes('application/json'),
      'spending summary response time < 1500ms': (r) => r.timings.duration < 1500,
      'spending summary has account_id': (r) => {
        try {
          const body = r.json();
          return body.account_id === accountId;
        } catch {
          return false;
        }
      },
      'spending summary has total_spent': (r) => {
        try {
          const body = r.json();
          return typeof body.total_spent === 'number';
        } catch {
          return false;
        }
      },
      'spending summary has transaction_count': (r) => {
        try {
          const body = r.json();
          return typeof body.transaction_count === 'number';
        } catch {
          return false;
        }
      },
      'spending summary has transactions array': (r) => {
        try {
          const body = r.json();
          return Array.isArray(body.transactions);
        } catch {
          return false;
        }
      },
      'spending summary transactions have required fields': (r) => {
        try {
          const body = r.json();
          if (!Array.isArray(body.transactions) || body.transactions.length === 0) {
            return true; // Empty array is valid
          }
          const tx = body.transactions[0];
          return (
            typeof tx.id === 'number' &&
            typeof tx.amount === 'number' &&
            typeof tx.description === 'string' &&
            tx.created_at !== undefined
          );
        } catch {
          return false;
        }
      },
    });

    spendingSummaryLatency.add(res.timings.duration);
    
    if (res.status === 200) {
      spendingSummarySuccess.add(1);
      spendingSummaryErrors.add(0);
    } else {
      spendingSummaryErrors.add(1);
    }
  });
}

export function handleSummary(data) {
  return {
    'k6/kassandra/results/mr-37-spending-summary.json': JSON.stringify(data, null, 2),
    stdout: JSON.stringify({ status: 'complete', metrics_count: Object.keys(data.metrics).length }),
  };
}
