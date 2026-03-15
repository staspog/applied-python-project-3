# URL Shortener API (FastAPI)

Сервис сокращения ссылок с CRUD, редиректом, статистикой, TTL ссылок, PostgreSQL как основным хранилищем и Redis-кэшем.

## Запуск (docker-compose)

```bash
docker compose up --build
```

Сервис будет доступен на `http://localhost:8000`.

OpenAPI/Swagger: `http://localhost:8000/docs`

Перед первым запуском создайте `.env` из `.env.example` и задайте как минимум `JWT_SECRET_KEY` и `SESSION_SECRET_KEY` (в docker-compose они не переопределяются из `environment`, но приложение читает их из `env_file`).

### Весь проект в Docker + нагрузочные тесты Locust

1. **Поднять** (из корня проекта, где лежит `docker-compose.yml`):

   ```bash
   cd /path/to/project3
   docker compose up --build -d
   ```

   Поднимутся контейнеры: `db` (Postgres), `redis`, `app` (FastAPI на порту 8000). Миграции выполняются при старте `app`.

2. **Проверить, что API отвечает:**

   ```bash
   curl -s http://localhost:8000/docs
   # или
   curl -s -X POST http://localhost:8000/links/shorten \
     -H "Content-Type: application/json" \
     -d '{"original_url":"https://example.com"}'
   ```

3. **Запустить Locust** на своей машине (не в контейнере), указав хост приложения:

   ```bash
   # из той же папки project3
   locust -f locustfile.py --host=http://localhost:8000
   ```

   Откроется веб-интерфейс по адресу **http://localhost:8089**. Укажите число пользователей и RPS, нажмите Start.

   Вариант без веб-интерфейса (только консоль):

   ```bash
   locust -f locustfile.py --host=http://localhost:8000 --headless -u 10 -r 2 -t 30s
   ```

4. **Остановить стек:**

   ```bash
   docker compose down
   ```

## Миграции

При старте контейнера `app` автоматически выполняется `alembic upgrade head`.

## Переменные окружения и генерация секретов

Файл `.env` можно собрать по образцу `.env.example`. Минимум, что нужно задать:

- `JWT_SECRET_KEY` — секрет для подписи JWT-токенов.
- `SESSION_SECRET_KEY` — секрет для подписи cookie-сессий гостей.

Примеры команд для генерации случайных значений (запускаются на сервере в шелле):

```bash
python - << 'EOF'
import secrets
print(secrets.token_urlsafe(32))
EOF
```

Сгенерированную строку можно подставить, например:

```env
JWT_SECRET_KEY="сюда_вставить_случайный_секрет"
SESSION_SECRET_KEY="сюда_другой_случайный_секрет"
```

Остальные переменные из `.env.example` можно оставить по умолчанию или подстроить под свою инфраструктуру.

## Авторизация

- Регистрация: `POST /auth/register`
- Получение токена: `POST /auth/token` (form-data, OAuth2 password flow)
- Текущий пользователь: `GET /auth/me` (Bearer token)

## API эндпоинты

- **Создать короткую ссылку**: `POST /links/shorten`
- **Редирект**: `GET /links/{short_code}`
- **Обновить**: `PUT /links/{short_code}` (только владелец-юзер)
- **Удалить**: `DELETE /links/{short_code}` (только владелец-юзер)
- **Статистика**: `GET /links/{short_code}/stats`
- **Поиск по original_url**: `GET /links/search?original_url=...`

## TTL (expires_at)

В `POST /links/shorten` можно передать `expires_at` (ISO datetime) с точностью до минуты (секунды должны быть `00`).

Если ссылка истекла — она возвращает 404 и переносится в архив (таблица `links_archive`).

Фоновая задача также периодически архивирует истёкшие записи.

## Доп. функциональность

- **История истёкших/удалённых**: `GET /links/expired` (для текущего пользователя или для гостя по cookie-сессии)
- **Гостевой режим (cookie-сессия)**:
  - При создании ссылки без авторизации выдаётся `guest_id` в signed cookie.
  - Можно управлять своими гостевыми ссылками:
    - `PUT /guest/links/{short_code}`
    - `DELETE /guest/links/{short_code}`
  - Ограничения для гостей (настраиваются env): rate-limit создания и max активных ссылок.

## Особенность `/links/{short_code}` в Swagger

Эндпоинт `GET /links/{short_code}` возвращает **редирект** (307) на внешний URL.  
В Swagger UI при нажатии “Try it out” и “Execute” вы можете увидеть сообщение вида:

> Undocumented  
> Failed to fetch.  
> Possible Reasons: CORS / Network Failure / URL scheme must be "http" or "https" for CORS request.

Это **ожидаемое поведение Swagger**, а не ошибка сервиса:

- браузер выполняет AJAX‑запрос к `/links/{short_code}`;
- сервер отвечает `307 Temporary Redirect` с заголовком `Location: <оригинальный URL>`;
- браузер пытается сходить уже на внешний домен (например, `https://example.com`),  
  но тот не даёт CORS‑заголовков для `http://localhost:8000/docs`, и Swagger не может “прочитать” этот ответ.

В логах приложения при этом видно, что редирект отрабатывает корректно, например:

```text
INFO:     146.75.54.132:22000 - "GET /links/project3_1 HTTP/1.1" 307 Temporary Redirect
```

**Как правильно тестировать редирект без фронта:**

- После создания ссылки (через Swagger или `curl`) возьмите `short_code` из ответа и:
  - либо откройте `http://<host>/links/{short_code}` прямо в адресной строке браузера  
    → браузер сам перейдёт на оригинальный URL;
  - либо используйте `curl`:

    ```bash
    curl -i http://localhost:8000/links/myalias
    ```

    В ответе вы увидите строку статуса `307 Temporary Redirect` и заголовок `Location` с полной ссылкой.

В тестовом режиме можно использовать Swagger как интерфейс для **создания**/изменения ссылок и просмотра статистики, а для проверки самого редиректа — просто открывать `GET /links/{short_code}` в браузере или через `curl`, как описано выше.

## Примеры запросов

### Регистрация

```bash
curl -X POST http://localhost:8000/auth/register \\
  -H 'Content-Type: application/json' \\
  -d '{"username":"alice","password":"secret123","email":"alice@example.com"}'
```

### Токен

```bash
curl -X POST http://localhost:8000/auth/token \\
  -H 'Content-Type: application/x-www-form-urlencoded' \\
  -d 'username=alice&password=secret123'
```

### Создание короткой ссылки (без авторизации)

```bash
curl -i -X POST http://localhost:8000/links/shorten \\
  -H 'Content-Type: application/json' \\
  -d '{"original_url":"https://example.com/some/very/long/url"}'
```

Важно: ответ включает `Set-Cookie` с guest-сессией. Сохрани cookie (через `-c cookies.txt` / `-b cookies.txt`), если хочешь управлять гостевыми ссылками.

### Создание кастомного alias + expires_at

```bash
curl -X POST http://localhost:8000/links/shorten \\
  -H 'Content-Type: application/json' \\
  -d '{"original_url":"https://example.com","custom_alias":"myalias","expires_at":"2030-01-01T10:30:00+00:00"}'
```

### Редирект

```bash
curl -i http://localhost:8000/links/myalias
```

### Статистика

```bash
curl http://localhost:8000/links/myalias/stats
```

### Поиск по original_url

```bash
curl 'http://localhost:8000/links/search?original_url=https://example.com'
```

### Обновление (только владелец-юзер)

```bash
TOKEN="paste_token_here"
curl -X PUT http://localhost:8000/links/myalias \\
  -H "Authorization: Bearer $TOKEN" \\
  -H 'Content-Type: application/json' \\
  -d '{"original_url":"https://example.com/new","custom_alias":"newalias"}'
```

### Удаление (только владелец-юзер)

```bash
TOKEN="paste_token_here"
curl -X DELETE http://localhost:8000/links/newalias \\
  -H "Authorization: Bearer $TOKEN"
```

### Гостевое обновление/удаление (по cookie)

```bash
curl -X PUT http://localhost:8000/guest/links/myalias \\
  -b cookies.txt -c cookies.txt \\
  -H 'Content-Type: application/json' \\
  -d '{"original_url":"https://example.com/guest-update"}'
```

```bash
curl -X DELETE http://localhost:8000/guest/links/myalias \\
  -b cookies.txt -c cookies.txt
```

### История истёкших/удалённых

```bash
curl 'http://localhost:8000/links/expired?limit=50&offset=0' -b cookies.txt -c cookies.txt
```

## Запуск тестов

### Юнит и функциональные тесты (pytest)

```bash
# все тесты
pytest tests/ -v

# с покрытием (терминал + HTML-отчёт)
coverage run -m pytest tests/
coverage report
coverage html
```

**Где смотреть отчёт о покрытии**

- **Процент покрытия: — 92%**.
- **HTML-отчёт** (файл, визуализирующий покрытие) в репозиторий не включён. Чтобы получить его после клонирования репозитория:
  ```bash
  pip install -r requirements.txt   # или активировать существующий venv
  coverage run -m pytest tests/
  coverage html
  ```
  После этого откройте в браузере **`htmlcov/index.html`** — там сводка по модулям и детализация по строкам. В каталоге `htmlcov/` появятся все нужные файлы отчёта.

### Нагрузочные тесты (Locust)

Сервис должен быть запущен и иметь доступ к **Redis** и БД. При локальном запуске (`uvicorn app.main:app`) без Docker Redis по умолчанию не поднят — запросы будут падать с 500 (`Connection refused` к localhost:6379). Варианты:

**Вариант 1 — всё в Docker (рекомендуется):**
```bash
docker compose up --build
# в другом терминале:
locust -f locustfile.py --host=http://localhost:8000
```

```bash
# веб-интерфейс Locust: http://localhost:8089
# только консоль:
locust -f locustfile.py --host=http://localhost:8000 --headless -u 10 -r 2 -t 30s
```

В сценарии: создание ссылки гостем, переход по короткой ссылке (редирект), запрос статистики.

## Схема БД

- `users`: пользователи
- `links`: активные ссылки
- `links_archive`: истёкшие/удалённые ссылки (история)
