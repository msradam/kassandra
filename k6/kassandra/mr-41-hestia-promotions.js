/**
 * Kassandra Performance Test — MR !41
 * Hestia Eats: Promotions system (GET /api/promotions, GET /api/promotions/{id})
 * SLOs: p95 < 500ms, error rate < 1%
 */

import http from 'k6/http';
import { check } from 'k6';
import { Trend, Counter } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';
const AUTH = { headers: { Authorization: 'Bearer hestia-bearer-token-2026' } };

const promotionListDuration = new Trend('promotion_list_duration', true);
const promotionDetailDuration = new Trend('promotion_detail_duration', true);
const promotionListErrors = new Counter('promotion_list_errors');
const promotionDetailErrors = new Counter('promotion_detail_errors');

export const options = {
  scenarios: {
    warmup: {
      executor: 'constant-arrival-rate',
      rate: 5, timeUnit: '1s', duration: '5s',
      preAllocatedVUs: 5, maxVUs: 10,
      exec: 'warmup',
    },
    steady: {
      executor: 'constant-arrival-rate',
      rate: 20, timeUnit: '1s', duration: '10s',
      preAllocatedVUs: 20, maxVUs: 40,
      startTime: '5s', exec: 'steady',
    },
    spike: {
      executor: 'constant-arrival-rate',
      rate: 50, timeUnit: '1s', duration: '10s',
      preAllocatedVUs: 50, maxVUs: 100,
      startTime: '15s', exec: 'spike',
    },
  },
  thresholds: {
    'promotion_list_duration': ['p(95)<500', 'p(99)<800'],
    'promotion_detail_duration': ['p(95)<500', 'p(99)<800'],
    'http_req_duration{endpoint:list_promotions}': ['p(95)<500'],
    'http_req_duration{endpoint:get_promotion}': ['p(95)<500'],
    'http_req_failed{endpoint:list_promotions}': ['rate<0.01'],
    'http_req_failed{endpoint:get_promotion}': ['rate<0.01'],
  },
};

const PROMO_IDS = [1, 2, 3, 4, 6, 7];
const RESTAURANT_IDS = [1, 2, 3, 4, 6, 7, 8];

function listPromotions(params) {
  const qs = params || '';
  const res = http.get(`${BASE_URL}/api/promotions${qs}`, {
    ...AUTH,
    tags: { endpoint: 'list_promotions' },
  });
  promotionListDuration.add(res.timings.duration);
  const ok = check(res, {
    'list promotions: status 200': (r) => r.status === 200,
    'list promotions: has promotions array': (r) => {
      const b = r.json(); return b && Array.isArray(b.promotions);
    },
    'list promotions: has total': (r) => {
      const b = r.json(); return b && typeof b.total === 'number';
    },
    'list promotions: enriched with restaurant data': (r) => {
      const b = r.json();
      if (!b || !b.promotions || b.promotions.length === 0) return true;
      const p = b.promotions[0];
      return p.restaurant_name && p.restaurant_cuisine && typeof p.restaurant_rating === 'number';
    },
  });
  if (!ok) promotionListErrors.add(1);
  return res;
}

function getPromotion(id) {
  const res = http.get(`${BASE_URL}/api/promotions/${id}`, {
    ...AUTH,
    tags: { endpoint: 'get_promotion' },
  });
  promotionDetailDuration.add(res.timings.duration);
  const ok = check(res, {
    'get promotion: status 200': (r) => r.status === 200,
    'get promotion: has title': (r) => {
      const b = r.json(); return b && b.title;
    },
    'get promotion: has restaurant object': (r) => {
      const b = r.json(); return b && b.restaurant && b.restaurant.name;
    },
    'get promotion: has menu_items array': (r) => {
      const b = r.json(); return b && Array.isArray(b.menu_items);
    },
    'get promotion: menu_item_count matches': (r) => {
      const b = r.json();
      return b && typeof b.menu_item_count === 'number' && b.menu_item_count === (b.menu_items || []).length;
    },
  });
  if (!ok) promotionDetailErrors.add(1);
  return res;
}

function getPromotion404() {
  const res = http.get(`${BASE_URL}/api/promotions/9999`, {
    ...AUTH,
    tags: { endpoint: 'get_promotion_404' },
  });
  check(res, {
    '404: correct status': (r) => r.status === 404,
    '404: has error message': (r) => {
      const b = r.json(); return b && b.error;
    },
  });
}

export function warmup() {
  listPromotions();
}

export function steady() {
  const r = Math.random();
  if (r < 0.50) listPromotions();
  else if (r < 0.75) getPromotion(PROMO_IDS[Math.floor(Math.random() * PROMO_IDS.length)]);
  else if (r < 0.90) {
    const rid = RESTAURANT_IDS[Math.floor(Math.random() * RESTAURANT_IDS.length)];
    listPromotions(`?restaurant_id=${rid}`);
  } else listPromotions('?active=false');
}

export function spike() {
  const r = Math.random();
  if (r < 0.40) listPromotions();
  else if (r < 0.70) getPromotion(PROMO_IDS[Math.floor(Math.random() * PROMO_IDS.length)]);
  else if (r < 0.85) {
    const rid = RESTAURANT_IDS[Math.floor(Math.random() * RESTAURANT_IDS.length)];
    listPromotions(`?restaurant_id=${rid}`);
  } else if (r < 0.95) listPromotions('?active=false');
  else getPromotion404();
}

export function handleSummary(data) {
  return {
    'k6/kassandra/results/mr-41-hestia-promotions.json': JSON.stringify(data, null, 2),
  };
}
