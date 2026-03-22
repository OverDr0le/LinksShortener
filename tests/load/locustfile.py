"""
Locust load-test scenarios for the URL Shortener service.
─────────────────────────────────────────────────────────
Run (from project root, while the app is up on port 8000):

    locust -f tests/load/locustfile.py \
           --host http://localhost:8000 \
           --users 50 \
           --spawn-rate 5 \
           --run-time 60s \
           --headless \
           --html tests/load/report.html

Scenarios
─────────────────────────────────────────────────────────
1. AnonymousUser   — creates short links without auth (heaviest traffic).
2. AuthenticatedUser — registers → logs in → full CRUD cycle.
3. RedirectHeavyUser — only hits the redirect endpoint (read-only hotspot).
4. CacheEfficiencyUser — hits the same short code repeatedly to measure
                          the cache hit benefit (response time should drop
                          significantly after the first miss).
"""

import random
import string
import uuid

from locust import HttpUser, between, task, events


# ── helpers ───────────────────────────────────────────────────────────────────

def _random_alias(length: int = 10) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def _random_url() -> str:
    slug = "".join(random.choices(string.ascii_lowercase, k=8))
    return f"https://{slug}.loadtest.example.com/{_random_alias(6)}"


# ── Scenario 1 — Anonymous mass link creation ─────────────────────────────────

class AnonymousUser(HttpUser):
    """
    Simulates anonymous users creating short links at high volume.
    This is the primary write-load scenario.

    Weight = 3  → 3× more frequent than other users in a mixed swarm.
    """
    wait_time = between(0.5, 2)
    weight = 3

    @task(5)
    def create_short_link(self):
        """POST /links/shorten — anonymous, no custom alias."""
        with self.client.post(
            "/links/shorten",
            json={"original_url": _random_url()},
            catch_response=True,
            name="POST /links/shorten [anon]",
        ) as resp:
            if resp.status_code == 201:
                resp.success()
                # Store the short_url for subsequent redirect tests in same user session
                data = resp.json()
                self.created_short_urls = getattr(self, "created_short_urls", [])
                self.created_short_urls.append(data.get("short_url"))
                # Keep list bounded
                if len(self.created_short_urls) > 50:
                    self.created_short_urls = self.created_short_urls[-50:]
            else:
                resp.failure(f"Unexpected status {resp.status_code}: {resp.text[:200]}")

    @task(2)
    def create_with_custom_alias(self):
        """POST /links/shorten — anonymous with a unique custom alias."""
        alias = f"load-{_random_alias(8)}"
        with self.client.post(
            "/links/shorten",
            json={"original_url": _random_url(), "custom_alias": alias},
            catch_response=True,
            name="POST /links/shorten [alias]",
        ) as resp:
            if resp.status_code in (201, 400):
                # 400 is acceptable (rare alias collision)
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}")

    @task(3)
    def redirect_own_link(self):
        """GET /links/by-short/{code} — redirect one of the previously created links."""
        created = getattr(self, "created_short_urls", [])
        if not created:
            return
        short_url = random.choice(created)
        with self.client.get(
            f"/links/by-short/{short_url}",
            allow_redirects=False,
            catch_response=True,
            name="GET /links/by-short/{code} [redirect]",
        ) as resp:
            if resp.status_code in (200, 302, 307, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}")


# ── Scenario 2 — Authenticated full CRUD ─────────────────────────────────────

class AuthenticatedUser(HttpUser):
    """
    Simulates a registered user who:
      • Creates links with custom aliases
      • Updates them
      • Checks stats
      • Deletes them

    Registers and logs in during on_start.
    Weight = 1
    """
    wait_time = between(1, 3)
    weight = 1

    def on_start(self):
        self.token = None
        self.owned_links: list[str] = []
        uid = _random_alias(12)
        self.email = f"load_{uid}@test.example.com"
        self.password = f"LoadTest1_{uid[:6]}"
        self._register()
        self._login()

    def _register(self):
        self.client.post(
            "/auth/register",
            json={"email": self.email, "password": self.password},
            name="POST /auth/register",
        )

    def _login(self):
        resp = self.client.post(
            "/auth/jwt/login",
            data={"username": self.email, "password": self.password},
            name="POST /auth/jwt/login",
        )
        if resp.status_code == 200:
            self.token = resp.json().get("access_token")

    def _auth_headers(self) -> dict:
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    @task(4)
    def create_link(self):
        alias = f"auth-{_random_alias(8)}"
        with self.client.post(
            "/links/shorten",
            json={"original_url": _random_url(), "custom_alias": alias},
            headers=self._auth_headers(),
            catch_response=True,
            name="POST /links/shorten [auth]",
        ) as resp:
            if resp.status_code == 201:
                resp.success()
                self.owned_links.append(alias)
                if len(self.owned_links) > 20:
                    self.owned_links = self.owned_links[-20:]
            elif resp.status_code == 400:
                resp.success()   # alias collision, acceptable
            else:
                resp.failure(f"Unexpected status {resp.status_code}")

    @task(2)
    def get_stats(self):
        if not self.owned_links:
            return
        alias = random.choice(self.owned_links)
        with self.client.get(
            f"/links/{alias}/stats",
            headers=self._auth_headers(),
            catch_response=True,
            name="GET /links/{code}/stats",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}")

    @task(1)
    def update_link(self):
        if not self.owned_links:
            return
        old_alias = self.owned_links.pop()
        new_alias = f"upd-{_random_alias(7)}"
        with self.client.put(
            f"/links/{old_alias}",
            json={"custom_alias": new_alias},
            headers=self._auth_headers(),
            catch_response=True,
            name="PUT /links/{code}",
        ) as resp:
            if resp.status_code in (200, 404, 400):
                resp.success()
                if resp.status_code == 200:
                    self.owned_links.append(new_alias)
            else:
                resp.failure(f"Unexpected status {resp.status_code}")

    @task(1)
    def delete_link(self):
        if not self.owned_links:
            return
        alias = self.owned_links.pop()
        with self.client.delete(
            f"/links/{alias}",
            headers=self._auth_headers(),
            catch_response=True,
            name="DELETE /links/{code}",
        ) as resp:
            if resp.status_code in (204, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}")


# ── Scenario 3 — Redirect heavy (read-only hotspot) ──────────────────────────

# A small pool of well-known short codes that must be pre-seeded in the DB
# before running this scenario (see README section in this file).
_KNOWN_SHORT_CODES: list[str] = []   # populated at runtime via on_start


class RedirectHeavyUser(HttpUser):
    """
    Models the most common real-world pattern: many users clicking
    the same viral short link.  Demonstrates Redis cache efficiency:
    after the first DB miss the subsequent requests should be served
    entirely from cache (much lower latency).

    Weight = 5 — the dominant read traffic shape.
    """
    wait_time = between(0.1, 0.5)
    weight = 5

    def on_start(self):
        # Seed one link per virtual user so the pool grows with concurrency
        resp = self.client.post(
            "/links/shorten",
            json={"original_url": _random_url()},
            name="[setup] seed redirect link",
        )
        if resp.status_code == 201:
            code = resp.json().get("short_url")
            _KNOWN_SHORT_CODES.append(code)
        self._my_codes: list[str] = [resp.json().get("short_url")] if resp.status_code == 201 else []

    @task(10)
    def hit_redirect(self):
        """Repeatedly click the same short URL to warm / exercise the cache."""
        pool = _KNOWN_SHORT_CODES or self._my_codes
        if not pool:
            return
        code = random.choice(pool)
        with self.client.get(
            f"/links/by-short/{code}",
            allow_redirects=False,
            catch_response=True,
            name="GET /links/by-short/{code} [cache-hit]",
        ) as resp:
            if resp.status_code in (200, 302, 307, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected {resp.status_code}")

    @task(1)
    def check_stats(self):
        pool = _KNOWN_SHORT_CODES or self._my_codes
        if not pool:
            return
        code = random.choice(pool)
        with self.client.get(
            f"/links/{code}/stats",
            catch_response=True,
            name="GET /links/{code}/stats [read]",
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected {resp.status_code}")


# ── Scenario 4 — Cache efficiency measurement ─────────────────────────────────

class CacheEfficiencyUser(HttpUser):
    """
    Hits a single fixed short URL back-to-back to measure
    the Redis cache effect on response time.

    First request  → DB query + cache write  (expect ~50-200 ms)
    Subsequent     → cache read only          (expect  <10 ms)

    The Locust HTML report percentile chart will clearly show
    the latency drop after the first request per short code.

    Weight = 2
    """
    wait_time = between(0.05, 0.2)
    weight = 2

    _shared_warm_code: str | None = None   # class-level shared code

    def on_start(self):
        if CacheEfficiencyUser._shared_warm_code is None:
            resp = self.client.post(
                "/links/shorten",
                json={
                    "original_url": "https://cache-efficiency-test.locust.example.com/page",
                    "custom_alias": f"cache-eff-{_random_alias(5)}",
                },
                name="[setup] seed cache-efficiency link",
            )
            if resp.status_code == 201:
                CacheEfficiencyUser._shared_warm_code = resp.json().get("short_url")

    @task
    def hit_same_link(self):
        code = CacheEfficiencyUser._shared_warm_code
        if not code:
            return
        with self.client.get(
            f"/links/by-short/{code}",
            allow_redirects=False,
            catch_response=True,
            name="GET /links/by-short/{code} [cache-eff]",
        ) as resp:
            if resp.status_code in (200, 302, 307):
                resp.success()
            else:
                resp.failure(f"Unexpected {resp.status_code}")


# ── Event hooks (summary logging) ─────────────────────────────────────────────

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print a concise performance summary when the test finishes."""
    stats = environment.stats
    print("\n" + "=" * 60)
    print("LOAD TEST SUMMARY")
    print("=" * 60)
    for name, entry in stats.entries.items():
        print(
            f"  {entry.name:<45s} "
            f"reqs={entry.num_requests:>6d}  "
            f"fails={entry.num_failures:>4d}  "
            f"p50={entry.get_response_time_percentile(0.50):>6.0f}ms  "
            f"p95={entry.get_response_time_percentile(0.95):>6.0f}ms  "
            f"p99={entry.get_response_time_percentile(0.99):>6.0f}ms"
        )
    total = stats.total
    fail_rate = (total.num_failures / total.num_requests * 100) if total.num_requests else 0
    print("-" * 60)
    print(
        f"  TOTAL  reqs={total.num_requests}  "
        f"fails={total.num_failures} ({fail_rate:.1f}%)  "
        f"RPS={total.current_rps:.1f}"
    )
    print("=" * 60)
