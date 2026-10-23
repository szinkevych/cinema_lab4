-- =====================================================================
-- База даних кінотеатру. Фізична структура (PostgreSQL)
-- 11 таблиць, 3НФ
-- =====================================================================

-- Часовий пояс бази: за замовчуванням Docker використовує UTC, а сеанси задаються за київським часом.
-- Налаштування діє для всіх НОВИХ підключень до бази (наступні скрипти, застосунки, psql).
ALTER DATABASE cinema SET timezone TO 'Europe/Kyiv';

-- Жанри
CREATE TABLE genres (
    genre_id SERIAL PRIMARY KEY,
    name     VARCHAR(50) NOT NULL UNIQUE
);

-- Фільми
CREATE TABLE movies (
    movie_id     SERIAL PRIMARY KEY,
    title        VARCHAR(200) NOT NULL,
    description  TEXT,
    duration_min INT NOT NULL CHECK (duration_min > 0 AND duration_min <= 600),
    release_year INT NOT NULL CHECK (release_year > 1880 AND release_year <= 2100),
    age_rating   INT NOT NULL DEFAULT 0 CHECK (age_rating IN (0, 6, 12, 16, 18)),
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (title, release_year)
);

-- Зв'язок фільм-жанр (M:N), складений первинний ключ з двох зовнішніх
CREATE TABLE movie_genres (
    movie_id INT NOT NULL REFERENCES movies(movie_id) ON DELETE CASCADE,
    genre_id INT NOT NULL REFERENCES genres(genre_id) ON DELETE CASCADE,
    PRIMARY KEY (movie_id, genre_id)
);

-- Зали
CREATE TABLE halls (
    hall_id   SERIAL PRIMARY KEY,
    name      VARCHAR(50) NOT NULL UNIQUE,
    hall_type VARCHAR(10) NOT NULL DEFAULT '2D'
              CHECK (hall_type IN ('2D', '3D', 'IMAX', 'VIP'))
);

-- Місця в залах
CREATE TABLE seats (
    seat_id     SERIAL PRIMARY KEY,
    hall_id     INT NOT NULL REFERENCES halls(hall_id) ON DELETE CASCADE,
    row_number  INT NOT NULL CHECK (row_number > 0),
    seat_number INT NOT NULL CHECK (seat_number > 0),
    UNIQUE (hall_id, row_number, seat_number)
);

-- Сеанси
CREATE TABLE screenings (
    screening_id SERIAL PRIMARY KEY,
    movie_id     INT NOT NULL REFERENCES movies(movie_id) ON DELETE RESTRICT,
    hall_id      INT NOT NULL REFERENCES halls(hall_id)   ON DELETE RESTRICT,
    start_time   TIMESTAMP NOT NULL,
    base_price   DECIMAL(8, 2) NOT NULL CHECK (base_price >= 0),
    UNIQUE (hall_id, start_time)   -- у залі не може бути двох сеансів з однаковим початком
);

-- Клієнти
CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    first_name  VARCHAR(50)  NOT NULL,
    last_name   VARCHAR(50)  NOT NULL,
    email       VARCHAR(100) NOT NULL UNIQUE CHECK (email LIKE '%_@_%._%'),
    phone       VARCHAR(20)  UNIQUE CHECK (phone ~ '^\+?[0-9]{10,15}$'),
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Квитки. Скасування зберігається статусом, історія не втрачається
CREATE TABLE tickets (
    ticket_id    SERIAL PRIMARY KEY,
    screening_id INT NOT NULL REFERENCES screenings(screening_id) ON DELETE RESTRICT,
    seat_id      INT NOT NULL REFERENCES seats(seat_id)           ON DELETE RESTRICT,
    customer_id  INT NOT NULL REFERENCES customers(customer_id)   ON DELETE RESTRICT,
    price        DECIMAL(8, 2) NOT NULL CHECK (price >= 0),
    status       VARCHAR(10) NOT NULL DEFAULT 'sold' CHECK (status IN ('sold', 'cancelled')),
    purchased_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cancelled_at TIMESTAMP,
    CHECK ((status = 'sold'      AND cancelled_at IS NULL) OR
           (status = 'cancelled' AND cancelled_at IS NOT NULL))
);

-- Одне місце не можна продати двічі на один сеанс,
-- але скасоване місце можна продати повторно
CREATE UNIQUE INDEX uq_tickets_active_seat
    ON tickets (screening_id, seat_id) WHERE status = 'sold';

-- =====================================================================
-- Індекси на зовнішніх ключах та полях, що часто використовуються
-- (seats(hall_id) покривається складеним UNIQUE)
-- =====================================================================
CREATE INDEX idx_movie_genres_genre ON movie_genres(genre_id);
CREATE INDEX idx_screenings_movie   ON screenings(movie_id);
CREATE INDEX idx_screenings_start   ON screenings(start_time);
CREATE INDEX idx_tickets_screening  ON tickets(screening_id);
CREATE INDEX idx_tickets_seat       ON tickets(seat_id);
CREATE INDEX idx_tickets_customer   ON tickets(customer_id);
CREATE INDEX idx_tickets_purchased  ON tickets(purchased_at);

-- =====================================================================
-- Таблиці для рівнів 2 і 3 (є на ER-діаграмі)
-- =====================================================================

-- Користувачі системи (рівень 3: аутентифікація і ролі).
-- customer_id необов'язковий: у касира або адміна може не бути профілю клієнта.
CREATE TABLE users (
    user_id       SERIAL PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email         VARCHAR(100) NOT NULL UNIQUE CHECK (email LIKE '%_@_%._%'),
    role          VARCHAR(20)  NOT NULL DEFAULT 'customer'
                  CHECK (role IN ('admin', 'cashier', 'customer')),
    customer_id   INT UNIQUE REFERENCES customers(customer_id) ON DELETE SET NULL
);

-- Журнал дій користувачів (рівень 3: логування операцій)
CREATE TABLE activity_log (
    log_id     SERIAL PRIMARY KEY,
    user_id    INT REFERENCES users(user_id) ON DELETE SET NULL,
    action     VARCHAR(50) NOT NULL,
    table_name VARCHAR(50),
    record_id  INT,
    details    TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Аудит змін квитків (рівень 2: заповнюватиметься тригером)
CREATE TABLE ticket_audit (
    audit_id   SERIAL PRIMARY KEY,
    ticket_id  INT NOT NULL REFERENCES tickets(ticket_id) ON DELETE RESTRICT,
    operation  VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    old_price  DECIMAL(8, 2),
    new_price  DECIMAL(8, 2),
    changed_by VARCHAR(50) NOT NULL DEFAULT current_user,
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_activity_log_user    ON activity_log(user_id);
CREATE INDEX idx_activity_log_created ON activity_log(created_at);
CREATE INDEX idx_ticket_audit_ticket  ON ticket_audit(ticket_id);