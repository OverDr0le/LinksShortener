Структура проекта:
app/
 ├── main.py
 ├── config.py
 ├── database.py
 ├── models/
 │    ├── user.py
 │    └── link.py
 ├── schemas/
 │    ├── user.py
 │    └── link.py
 ├── services/
 │    └── link_service.py
 ├── routers/
 │    ├── auth.py
 │    └── links.py
 ├── utils/
 │    └── short_code.py
 └── cache/
      └── redis_client.py

app/
│
├── main.py
│
├── api/
│     ├── deps.py
│     └── links_router.py
│
├── services/
│     └── link_service.py
│
├── repositories/
│     └── link_repository.py
│
├── models/
│     ├── user.py
│     └── link.py
│
├── schemas/
│     └── link.py
│
├── core/
│     ├── config.py
│     └── security.py
│
├── database.py