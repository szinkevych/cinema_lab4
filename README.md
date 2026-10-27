# Cinema: система бронювання та продажу квитків

Лабораторна робота №4 (3 рівень). Реляційна база даних у PostgreSQL із
консольним застосунком і вебзастосунком на Flask.

**Автор:** Зінькевич Олександра  
**Група:** ІПЗ-31  
**Звіт:** [docs/report.md](docs/report.md)

## Можливості

- 11 таблиць із первинними й зовнішніми ключами, обмеженнями цілісності та індексами
- 13 SQL-запитів: фільтрація, JOIN, підзапити, агрегація та віконні функції
- Функції та процедури PostgreSQL для продажу й скасування квитків і звітності
- Тригери перевірки бізнес-правил, аудит квитків і журнал дій
- Консольний застосунок для роботи з даними
- Вебзастосунок на Flask: розклад, квитки, ролі користувачів, звіти Excel/PDF
- Read-only JSON API та створення резервної копії PostgreSQL

## Структура репозиторію

```text
lab04-database/
├── README.md
├── docker-compose.yml
├── docs/
│   ├── report.md
│   ├── ER-діаграма.png
│   ├── api-and-backup.md
│   └── screenshots/              # скриншоти роботи застосунків і запитів
├── database/
│   ├── 01_create_tables.sql
│   ├── 02_insert_data.sql
│   ├── 03_create_procedures.sql
│   ├── 04_create_triggers.sql
│   ├── 05_create_views.sql
│   ├── 06_create_activity_log.sql
│   ├── 07_level3_completions.sql
│   ├── queries.sql
│   ├── backup.py
│   └── demo/
│       └── level2_demo.sql
├── console_app/
│   ├── main.py
│   ├── database.py
│   └── requirements.txt
└── web_app/
    ├── app.py
    ├── database.py
    ├── auth.py
    ├── validators.py
    ├── routes/
    ├── templates/
    ├── static/
    └── requirements.txt
```

## Вимоги

- Docker Desktop із Docker Compose
- Python 3.10+

## Запуск

### 1. База даних

Із кореневої папки репозиторію виконайте:

```powershell
docker compose up -d
docker compose ps
```

Скрипти з `database/` виконуються автоматично під час першого запуску на
порожньому томі. Параметри підключення: `localhost:5434`, база `cinema`,
користувач `postgres`, пароль `password`.

Щоб переглянути журнал запуску:

```powershell
docker compose logs -f postgres
```

Щоб видалити контейнер і том бази та ініціалізувати її заново:

```powershell
docker compose down -v
docker compose up -d
```

**Увага:** `docker compose down -v` видаляє збережені в томі дані бази.

### 2. Консольний застосунок

У корені репозиторію:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r console_app\requirements.txt
python console_app\main.py
```

### 3. Вебзастосунок

У корені репозиторію:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r web_app\requirements.txt
python web_app\app.py
```

Вебзастосунок доступний за адресою <http://127.0.0.1:5000>. Якщо потрібно,
параметри підключення можна змінити змінними середовища `DB_HOST`, `DB_PORT`,
`DB_NAME`, `DB_USER` і `DB_PASSWORD`.

## SQL-запити

13 запитів розміщені у [database/queries.sql](database/queries.sql). Їх можна
виконати з кореня репозиторію в PowerShell:

```powershell
Get-Content database\queries.sql -Raw |
    docker compose exec -T postgres psql -U postgres -d cinema
```

## Технології

PostgreSQL 17, Docker Compose, Python, psycopg2, Flask, openpyxl, ReportLab.

Деталі реалізації, опис запитів і ER-діаграма — у [звіті](docs/report.md).
