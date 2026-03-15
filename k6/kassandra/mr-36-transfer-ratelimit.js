import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.2/index.js';

// Custom metrics
const transferDuration = new Trend('transfer_duration', true);
const rateLimitErrors = new Rate('rate_limit_errors');
const selfTransferErrors = new Rate('self_transfer_errors');

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export const options = {
  scenarios: {
    // Scenario 1: Normal transfer load (within rate limits)
    normal_transfers: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '10s', target: 5 },
        { duration: '20s', target: 5 },
        { duration: '10s', target: 0 },
      ],
      gracefulRampDown: '5s',
      exec: 'normalTransfers',
      tags: { scenario: 'normal_transfers' },
    },
    // Scenario 2: Rate limit testing (burst transfers)
    rate_limit_test: {
      executor: 'per-vu-iterations',
      vus: 3,
      iterations: 15, // 15 iterations per VU = 45 total transfers
      maxDuration: '30s',
      startTime: '45s', // Start after normal scenario
      exec: 'rateLimitTest',
      tags: { scenario: 'rate_limit_test' },
    },
  },
  thresholds: {
    'http_req_duration{scenario:normal_transfers}': ['p95<2000'], // SLO: p95 < 2000ms for transfers
    'http_req_failed{scenario:normal_transfers}': ['rate<0.01'], // SLO: error rate < 1%
    'transfer_duration': ['p95<2000'],
    'rate_limit_errors': ['rate>0'], // We EXPECT rate limit errors in the rate_limit_test scenario
  },
};

let authToken = null;
let accountIds = [];

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
      tags: { endpoint: 'login' },
    }
  );

  check(loginRes, {
    'login successful': (r) => r.status === 200,
    'token received': (r) => r.json('token') !== undefined,
  });

  const token = loginRes.json('token');

  // Get existing accounts
  const accountsRes = http.get(`${BASE_URL}/api/accounts`, {
    headers: { Authorization: `Bearer ${token}` },
    tags: { endpoint: 'list_accounts' },
  });

  const accounts = accountsRes.json('accounts') || [];
  const existingAccountIds = accounts.map((a) => a.id);

  // Create additional accounts if needed (we need at least 2 for transfers)
  const accountsToCreate = Math.max(0, 3 - accounts.length);
  const newAccountIds = [];

  for (let i = 0; i < accountsToCreate; i++) {
    const createRes = http.post(
      `${BASE_URL}/api/accounts`,
      JSON.stringify({
        name: `Test Account ${Date.now()}-${i}`,
        currency: 'USD',
      }),
      {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        tags: { endpoint: 'create_account' },
      }
    );

    if (createRes.status === 201) {
      newAccountIds.push(createRes.json('id'));
    }
  }

  const allAccountIds = [...existingAccountIds, ...newAccountIds];

  // Deposit funds into accounts to ensure sufficient balance
  for (const accountId of allAccountIds) {
    http.post(
      `${BASE_URL}/api/transactions/deposit`,
      JSON.stringify({
        account_id: accountId,
        amount: 10000,
        description: 'Initial deposit for testing',
      }),
      {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        tags: { endpoint: 'deposit' },
      }
    );
  }

  return { token, accountIds: allAccountIds };
}

// Scenario 1: Normal transfer operations (respecting rate limits)
export function normalTransfers(data) {
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${data.token}`,
  };

  // Randomly select two different accounts
  const fromIdx = Math.floor(Math.random() * data.accountIds.length);
  let toIdx = Math.floor(Math.random() * data.accountIds.length);
  while (toIdx === fromIdx) {
    toIdx = Math.floor(Math.random() * data.accountIds.length);
  }

  const transferPayload = {
    from_account_id: data.accountIds[fromIdx],
    to_account_id: data.accountIds[toIdx],
    amount: Math.floor(Math.random() * 100) + 10, // Random amount between 10-110
    description: 'Performance test transfer',
  };

  const res = http.post(
    `${BASE_URL}/api/transactions/transfer`,
    JSON.stringify(transferPayload),
    {
      headers,
      tags: { endpoint: 'transfer', test_type: 'normal' },
    }
  );

  const success = check(res, {
    'transfer status is 201': (r) => r.status === 201,
    'transfer has transaction id': (r) => r.json('id') !== undefined,
    'transfer response time < 2000ms': (r) => r.timings.duration < 2000,
  });

  if (res.status === 201) {
    transferDuration.add(res.timings.duration);
  }

  // Sleep to stay within rate limits (10 transfers/min = 1 transfer per 6 seconds)
  // Add some randomness to simulate realistic user behavior
  sleep(6 + Math.random() * 2);
}

// Scenario 2: Test rate limiting behavior
export function rateLimitTest(data) {
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${data.token}`,
  };

  // Use consistent accounts for this VU
  const fromIdx = __VU % data.accountIds.length;
  const toIdx = (fromIdx + 1) % data.accountIds.length;

  const transferPayload = {
    from_account_id: data.accountIds[fromIdx],
    to_account_id: data.accountIds[toIdx],
    amount: 10,
    description: 'Rate limit test transfer',
  };

  const res = http.post(
    `${BASE_URL}/api/transactions/transfer`,
    JSON.stringify(transferPayload),
    {
      headers,
      tags: { endpoint: 'transfer', test_type: 'rate_limit' },
    }
  );

  const isRateLimited = res.status === 429;
  rateLimitErrors.add(isRateLimited);

  check(res, {
    'transfer succeeds or rate limited': (r) => r.status === 201 || r.status === 429,
    'rate limit message correct': (r) =>
      r.status !== 429 || r.json('detail')?.includes('rate limit'),
  });

  // Test self-transfer validation (should fail with 400)
  if (__ITER === 0) {
    const selfTransferPayload = {
      from_account_id: data.accountIds[fromIdx],
      to_account_id: data.accountIds[fromIdx], // Same account
      amount: 10,
      description: 'Self-transfer test',
    };

    const selfRes = http.post(
      `${BASE_URL}/api/transactions/transfer`,
      JSON.stringify(selfTransferPayload),
      {
        headers,
        tags: { endpoint: 'transfer', test_type: 'self_transfer_validation' },
      }
    );

    const isSelfTransferError = selfRes.status === 400;
    selfTransferErrors.add(isSelfTransferError);

    check(selfRes, {
      'self-transfer rejected with 400': (r) => r.status === 400,
      'self-transfer error message correct': (r) =>
        r.json('detail')?.includes('same account'),
    });
  }

  // Rapid fire to trigger rate limit
  sleep(0.1);
}

export function handleSummary(data) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const resultsDir = 'k6/kassandra/results';
  const jsonFile = `${resultsDir}/mr-36-transfer-ratelimit-${timestamp}.json`;

  return {
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
    [jsonFile]: JSON.stringify(data, null, 2),
  };
}
