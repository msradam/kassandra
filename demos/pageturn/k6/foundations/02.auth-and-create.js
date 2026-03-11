import http from "k6/http";
import { check, group, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export const options = {
  vus: 3,
  duration: "10s",
};

export function setup() {
  const loginRes = http.post(
    `${BASE_URL}/api/auth/login`,
    JSON.stringify({ username: "admin", password: "pageturn123" }),
    { headers: { "Content-Type": "application/json" } }
  );
  check(loginRes, { "login 200": (r) => r.status === 200 });
  return { token: loginRes.json().token };
}

export default function (data) {
  group("Create and verify book", function () {
    const book = {
      title: `Load Test Book ${Date.now()}`,
      author: "k6 Runner",
      genre: "technical",
      price: 19.99,
      year: 2024,
    };

    const createRes = http.post(
      `${BASE_URL}/api/books`,
      JSON.stringify(book),
      {
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${data.token}`,
        },
        tags: { endpoint: "/api/books", scenario: "create" },
      }
    );
    check(createRes, {
      "create 201": (r) => r.status === 201,
      "has id": (r) => r.json().id > 0,
    });

    if (createRes.status === 201) {
      const bookId = createRes.json().id;
      const getRes = http.get(`${BASE_URL}/api/books/${bookId}`, {
        tags: { endpoint: "/api/books/:id", scenario: "read" },
      });
      check(getRes, {
        "get 200": (r) => r.status === 200,
        "title matches": (r) => r.json().title === book.title,
      });
    }
  });
  sleep(1);
}
