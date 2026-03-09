# Links Shortener

Микросервис для сокращения ссылок, построенный на FastAPI. Позволяет пользователям создавать короткие ссылки из длинных URL, управлять ими, отслеживать статистику кликов и выполнять перенаправление.

## Функциональность

- **Создание коротких ссылок**: Генерация уникальных коротких URL из оригинальных ссылок.
- **Пользовательские алиасы**: Возможность указать собственный псевдоним для короткой ссылки.
- **Истечение срока действия**: Установка даты истечения для ссылок.
- **Аутентификация пользователей**: Регистрация, авторизация и управление пользователями.
- **Управление ссылками**: Обновление и удаление ссылок (только для владельцев).
- **Статистика**: Просмотр количества кликов и времени последнего доступа.
- **Перенаправление**: Автоматическое перенаправление на оригинальный URL при переходе по короткой ссылке.
- **Поиск ссылок**: Поиск короткой ссылки по оригинальному URL.
- **Кэширование**: Использование Redis для кэширования short_url → original_url для ускорения перенаправлений.
- **Фоновые задачи**: Celery для асинхронной обработки задач.

## API Описание

Сервис предоставляет REST API с следующими эндпоинтами:

### Ссылки (`/links`)

#### POST `/links/shorten`
Создает новую короткую ссылку.

**Тело запроса:**
```json
{
  "original_url": "https://example.com/very/long/url",
  "custom_alias": "my-link",  // опционально
  "expires_at": "2024-12-31T23:59:00"  // опционально
}
```

**Ответ (201):**
```json
{
  "id": "uuid",
  "user_id": "uuid",  // null для анонимных пользователей
  "original_url": "https://example.com/very/long/url",
  "short_url": "my-link",
  "created_at": "2024-01-01T00:00:00Z",
  "expires_at": "2024-12-31T23:59:00Z"
}
```

#### PUT `/links/{short_url}`
Обновляет существующую ссылку (доступно только владельцу этой ссылки).

**Тело запроса:**
```json
{
  "expires_at": "2025-12-31T23:59:00",
  "custom_alias": "new-alias"
}
```

#### DELETE `/links/{short_url}`
Удаляет ссылку (только владелец).

**Ответ (204):** Нет тела.

#### GET `/links/{short_url}/stats`
Получает статистику по ссылке.

**Ответ (200):**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "original_url": "https://example.com/very/long/url",
  "short_url": "my-link",
  "created_at": "2024-01-01T00:00:00Z",
  "expires_at": "2024-12-31T23:59:00Z",
  "click_count": 42,
  "last_accessed_at": "2024-01-15T10:30:00Z"
}
```

#### GET `/links/by-short/{short_url}`
Перенаправляет на оригинальный URL и увеличивает счетчик кликов.

**Ответ (302):** Редирект на оригинальный URL.

#### GET `/links/by-original/search?original_url=https://example.com/very/long/url`
Ищет короткую ссылку по оригинальному URL.

**Ответ (200):**
```json
{
  "short_url": "my-link",
  "original_url": "https://example.com/very/long/url"
}
```

### Аутентификация (`/auth`)

#### POST `/auth/jwt/login`
Вход в систему.

**Тело запроса:**
```json
{
  "username": "user@example.com",
  "password": "password"
}
```

#### POST `/auth/register`
Регистрация нового пользователя, в сервисе реализована проверка на уникальность email и сложность пароля.

**Тело запроса:**
```json
{
  "email": "user@example.com",
  "password": "password",
  "is_active": true,
  "is_superuser": false,
  "is_verified": false
}
```

#### POST `/auth/jwt/logout`
Выход из системы.

### Пользователи (`/users`)

#### GET `/users/me`
Получить информацию о текущем пользователе.

#### PATCH `/users/me`
Обновить информацию о текущем пользователе.

## Примеры запросов

### Создание ссылки (анонимно без авторизации)
```bash
curl -X POST "http://localhost:8000/links/shorten" \
  -H "Content-Type: application/json" \
  -d '{
    "original_url": "https://www.google.com/search?q=fastapi",
    "custom_alias": "google-search"
  }'
```

### Создание ссылки (авторизованно)
```bash
curl -X POST "http://localhost:8000/links/shorten" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "original_url": "https://github.com/tiangolo/fastapi",
    "expires_at": "2024-12-31T23:59:00"
  }'
```

### Получение статистики
```bash
curl -X GET "http://localhost:8000/links/google-search/stats"
```

### Перенаправление
```bash
curl -X GET "http://localhost:8000/links/by-short/google-search"
```

### Регистрация пользователя
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword"
  }'
```

### Вход в систему
```bash
curl -X POST "http://localhost:8000/auth/jwt/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=securepassword"
```

## Инструкция по запуску при помощи Docker Compose

### Предварительные требования

- Python 3.10
- PostgreSQL
- Redis
- Docker и Docker Compose (для контейнеризованного запуска)

### Локальный запуск

1. **Клонируйте репозиторий:**
   ```bash
   git clone <repository-url>
   cd LinksShortener
   ```

2. **Настройте переменные окружения:**
   Создайте файл `.env` в корне проекта:
   ```env
   DB_USER=your_db_user
   DB_PASS=your_db_password
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=links_shortener
   SECRET=your_secret_key
   REDIS_PORT=6379
   ```
3. **Запустите docker-compose контейнер**
    В контейнере уже содержится всё необходимое для запуска приложения, включая PostgreSQL и Redis. Просто выполните команду:
   ```bash
   docker-compose up --build
   ```
Приложение будет доступно по адресу: http://localhost:8000

Документация API: http://localhost:8000/docs

## Сервис deployed by Render: https://linksshortener.onrender.com/docs

## Описание базы данных

Сервис использует PostgreSQL в качестве основной базы данных.

### Таблица `users`

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID | Первичный ключ |
| email | String | Email пользователя (уникальный) |
| hashed_password | String | Хэшированный пароль |
| is_active | Boolean | Активен ли пользователь |
| is_superuser | Boolean | Является ли суперпользователем |
| is_verified | Boolean | Подтвержден ли email |
| created_at | DateTime | Дата создания |

### Таблица `links`

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID | Первичный ключ |
| original_url | String | Оригинальный URL |
| short_url | String | Короткий URL (уникальный) |
| user_id | UUID (FK) | ID пользователя (может быть NULL для анонимных ссылок) |
| created_at | DateTime | Дата создания |
| expires_at | DateTime | Дата истечения (может быть NULL) |
| click_count | Integer | Количество кликов |

### Связи

- `users.id` → `links.user_id` (один ко многим)

## Миграции

Для управления схемой базы данных используется Alembic.

- **Создание новой миграции:**
  ```bash
  alembic revision --autogenerate -m "Описание изменений"
  ```

- **Применение миграций:**
  ```bash
  alembic upgrade head
  ```

- **Откат миграции:**
  ```bash
  alembic downgrade -1
  ```

## Переменные окружения

| Переменная | Описание | Пример |
|------------|----------|--------|
| DB_USER | Пользователь базы данных | postgres |
| DB_PASS | Пароль базы данных | password |
| DB_HOST | Хост базы данных | localhost |
| DB_PORT | Порт базы данных | 5432 |
| DB_NAME | Имя базы данных | links_shortener |
| SECRET | Секретный ключ для JWT | your_secret_key |
| REDIS_PORT | Порт Redis | 6379 |

## Технологии

- **FastAPI**: Веб-фреймворк
- **SQLAlchemy**: ORM для работы с БД
- **PostgreSQL**: База данных
- **Redis**: Кэширование и брокер сообщений
- **Celery**: Очередь задач
- **Alembic**: Миграции БД
- **Pydantic**: Валидация данных
- **FastAPI Users**: Аутентификация пользователей
- **Docker**: Контейнеризация