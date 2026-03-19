/**
 * Kassandra Performance Test
 * MR !41: feat: add promotions system to Hestia Eats
 * 
 * Tests new promotion endpoints:
 * - GET /api/promotions (list with restaurant enrichment - N+1 pattern)
 * - GET /api/promotions/{id} (detail with restaurant and menu items)
 * 
 * SLOs: Default p95 < 500ms
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Counter } from 'k6/metrics';

const BASE_URL = 'http://localhost:8080';
const BEARER_TOKEN = 'hestia-bearer-token-2026';

// Custom metrics
const promotionListDuration = new Trend('promotion_list_duration', true);
const promotionDetailDuration = new Trend('promotion_detail_duration', true);
const promotionListErrors = new Counter('promotion_list_errors');
const promotionDetailErrors = new Counter('promotion_detail_errors');

export const options = {
  scenarios: {
    warmup: {
      executor: 'constant-arrival-rate',
      rate: 5,
      timeUnit: '1s',
      duration: '5s',
      preAllocatedVUs: 5,
      maxVUs: 10,
      exec: 'warmupScenario',
    },
    steady_load: {
      executor: 'constant-arrival-rate',
      rate: 20,
      timeUnit: '1s',
      duration: '10s',
      preAllocatedVUs: 20,
      maxVUs: 40,
      startTime: '5s',
      exec: 'steadyLoadScenario',
    },
    spike_test: {
      executor: 'constant-arrival-rate',
      rate: 50,
      timeUnit: '1s',
      duration: '10s',
      preAllocatedVUs: 50,
      maxVUs: 100,
      startTime: '15s',
      exec: 'spikeScenario',
    },
  },
  thresholds: {
    'http_req_duration{endpoint:list_promotions}': ['p(95)<500'],
    'http_req_duration{endpoint:get_promotion_detail}': ['p(95)<500'],
    'http_req_failed{endpoint:list_promotions}': ['rate<0.01'],
    'http_req_failed{endpoint:get_promotion_detail}': ['rate<0.01'],
    'promotion_list_duration': ['p(95)<500', 'p(99)<800'],
    'promotion_detail_duration': ['p(95)<500', 'p(99)<800'],
  },
};

const headers = {
  'Authorization': `Bearer ${BEARER_TOKEN}`,
  'Content-Type': 'application/json',
};

// Test data - promotion IDs from seed data (1-7)
const PROMOTION_IDS = [1, 2, 3, 4, 6, 7]; // Excluding ID 5 (inactive)
const RESTAURANT_IDS = [1, 2, 3, 4, 6, 7, 8];

function testListPromotions() {
  const res = http.get(`${BASE_URL}/api/promotions`, {
    headers,
    tags: { endpoint: 'list_promotions' },
  });

  const success = check(res, {
    'list promotions: status 200': (r) => r.status === 200,
    'list promotions: has promotions array': (r) => {
      try {
        const body = JSON.parse(r.body);
        return Array.isArray(body.promotions);
      } catch {
        return false;
      }
    },
    'list promotions: has total field': (r) => {
      try {
        const body = JSON.parse(r.body);
        return typeof body.total === 'number';
      } catch {
        return false;
      }
    },
    'list promotions: enriched with restaurant data': (r) => {
      try {
        const body = JSON.parse(r.body);
        if (body.promotions.length > 0) {
          const promo = body.promotions[0];
          return promo.restaurant_name && promo.restaurant_cuisine && typeof promo.restaurant_rating === 'number';
        }
        return true;
      } catch {
        return false;
      }
    },
  });

  if (!success) {
    promotionListErrors.add(1);
  }

  promotionListDuration.add(res.timings.duration);
  return res;
}

function testListPromotionsWithFilters() {
  // Test filtering by restaurant_id
  const restaurantId = RESTAURANT_IDS[Math.floor(Math.random() * RESTAURANT_IDS.length)];
  const res = http.get(`${BASE_URL}/api/promotions?restaurant_id=${restaurantId}`, {
    headers,
    tags: { endpoint: 'list_promotions' },
  });

  check(res, {
    'list promotions (filtered): status 200': (r) => r.status === 200,
    'list promotions (filtered): correct restaurant_id': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.promotions.every(p => p.restaurant_id === restaurantId);
      } catch {
        return false;
      }
    },
  });

  promotionListDuration.add(res.timings.duration);
}

function testListPromotionsInactive() {
  // Test including inactive promotions
  const res = http.get(`${BASE_URL}/api/promotions?active=false`, {
    headers,
    tags: { endpoint: 'list_promotions' },
  });

  check(res, {
    'list promotions (all): status 200': (r) => r.status === 200,
    'list promotions (all): includes inactive': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.total >= 7; // Should include all 7 promotions
      } catch {
        return false;
      }
    },
  });

  promotionListDuration.add(res.timings.duration);
}

function testGetPromotionDetail() {
  const promotionId = PROMOTION_IDS[Math.floor(Math.random() * PROMOTION_IDS.length)];
  const res = http.get(`${BASE_URL}/api/promotions/${promotionId}`, {
    headers,
    tags: { endpoint: 'get_promotion_detail' },
  });

  const success = check(res, {
    'get promotion detail: status 200': (r) => r.status === 200,
    'get promotion detail: has promotion fields': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.id && body.title && body.discount_pct !== undefined;
      } catch {
        return false;
      }
    },
    'get promotion detail: has restaurant object': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.restaurant && body.restaurant.name && body.restaurant.cuisine;
      } catch {
        return false;
      }
    },
    'get promotion detail: has menu_items array': (r) => {
      try {
        const body = JSON.parse(r.body);
        return Array.isArray(body.menu_items);
      } catch {
        return false;
      }
    },
    'get promotion detail: has menu_item_count': (r) => {
      try {
        const body = JSON.parse(r.body);
        return typeof body.menu_item_count === 'number' && body.menu_item_count === body.menu_items.length;
      } catch {
        return false;
      }
    },
  });

  if (!success) {
    promotionDetailErrors.add(1);
  }

  promotionDetailDuration.add(res.timings.duration);
  return res;
}

function testGetPromotionNotFound() {
  const res = http.get(`${BASE_URL}/api/promotions/9999`, {
    headers,
    tags: { endpoint: 'get_promotion_not_found' },
  });

  check(res, {
    'get promotion (not found): status 404': (r) => r.status === 404,
    'get promotion (not found): has error message': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.error && body.error.toLowerCase().includes('not found');
      } catch {
        return false;
      }
    },
  });
}

// Warmup scenario - light load to initialize
export function warmupScenario() {
  testListPromotions();
  sleep(0.1);
}

// Steady load scenario - realistic mixed traffic
export function steadyLoadScenario() {
  const scenario = Math.random();
  
  if (scenario < 0.5) {
    // 50% - List all active promotions
    testListPromotions();
  } else if (scenario < 0.75) {
    // 25% - Get promotion detail
    testGetPromotionDetail();
  } else if (scenario < 0.9) {
    // 15% - List promotions filtered by restaurant
    testListPromotionsWithFilters();
  } else {
    // 10% - List all promotions including inactive
    testListPromotionsInactive();
  }
  
  sleep(0.1);
}

// Spike scenario - high load with edge cases
export function spikeScenario() {
  const scenario = Math.random();
  
  if (scenario < 0.4) {
    // 40% - List promotions (N+1 pattern under load)
    testListPromotions();
  } else if (scenario < 0.7) {
    // 30% - Get promotion detail (heavy payload)
    testGetPromotionDetail();
  } else if (scenario < 0.85) {
    // 15% - Filtered list
    testListPromotionsWithFilters();
  } else if (scenario < 0.95) {
    // 10% - All promotions
    testListPromotionsInactive();
  } else {
    // 5% - Not found case
    testGetPromotionNotFound();
  }
  
  sleep(0.05);
}
