import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export const options = {
  vus: 5,
  duration: "5s",
};

export default function () {
  let res = http.get(`${BASE_URL}/api/books?per_page=5`, {
    headers: { "Content-Type": "application/json" },
  });
  check(res, { "status is 200": (r) => r.status === 200 });
  console.log(`Found ${JSON.parse(res.body).length} books`);
  sleep(1);
}
