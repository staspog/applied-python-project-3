"""
Нагрузочные тесты URL Shortener API (Locust).

Запуск (сервис должен быть поднят на host):
  locust -f locustfile.py --host=http://localhost:8000

Веб-интерфейс: http://localhost:8089 (по умолчанию).
Без UI (только консоль):
  locust -f locustfile.py --host=http://localhost:8000 --headless -u 10 -r 2 -t 30s
"""
from locust import HttpUser, task, between


class ShortenerUser(HttpUser):
    wait_time = between(0.5, 1.5)

    def on_start(self):
        """Создать одну ссылку при старте пользователя (гостем)."""
        r = self.client.post(
            "/links/shorten",
            json={"original_url": "https://example.com/load-test"},
        )
        if r.status_code == 201:
            self.short_code = r.json().get("short_code")
        else:
            self.short_code = None

    @task(3)
    def follow_redirect(self):
        """Переход по короткой ссылке (редирект)."""
        if self.short_code:
            self.client.get(
                f"/links/{self.short_code}",
                allow_redirects=False,
                name="/links/[short_code]",
            )

    @task(2)
    def get_stats(self):
        """Получение статистики по короткой ссылке."""
        if self.short_code:
            self.client.get(
                f"/links/{self.short_code}/stats",
                name="/links/[short_code]/stats",
            )

    @task(1)
    def create_link(self):
        """Создание новой короткой ссылки (гость)."""
        self.client.post(
            "/links/shorten",
            json={"original_url": "https://example.com/load"},
            name="/links/shorten",
        )
