import http from 'k6/http';
import { check } from 'k6';

export const options = { vus: 1, iterations: 1 };

interface SetupData { token: string; user: { id: number } }

function buildUrl(base: string, token: string): string {
  const url = `${base}/ping?t=${token}`;
  return url;
}

export function setup(): SetupData {
  return { token: 'abc123', user: { id: 7 } };
}

export default function (data: SetupData) {
  const base: string = __ENV.BASE_URL || 'http://127.0.0.1:8765';
  const url = buildUrl(base, data.token);
  const res = http.get(url);
  check(res, { 'status is 200': (r) => r.status === 200 });
}
