-- =====================================================================
-- Тестові дані. Дати сеансів задані відносно CURRENT_DATE,
-- щоб запити "розклад на сьогодні" завжди повертали результат.
-- =====================================================================

INSERT INTO genres (name) VALUES
('Фантастика'), ('Драма'), ('Комедія'), ('Бойовик'), ('Анімація'), ('Фентезі'),
('Трилер'), ('Пригоди'), ('Біографія'), ('Кримінал'), ('Сімейний'), ('Мюзикл');

INSERT INTO movies (title, description, duration_min, release_year, age_rating) VALUES
('Дюна: Частина друга',          'Пол Атрейдес об''єднується з фрименами для помсти.',          166, 2024, 12),
('Опенгеймер',                   'Історія створення атомної бомби.',                            180, 2023, 16),
('Головоломка 2',                'Райлі підростає, і в її голові з''являються нові емоції.',      96, 2024,  6),
('Інтерстеллар',                 'Експедиція крізь червоточину в пошуках нового дому людства.', 169, 2014, 12),
('Барбі',                        'Барбі вирушає з Барбіленду у реальний світ.',                 114, 2023, 12),
('Володар перснів: Братство персня', 'Хоббіт Фродо вирушає знищити Перстень Всевладдя.',         178, 2001, 12),
('Паразити',                     'Бідна родина проникає в життя заможної.',                     132, 2019, 16),
('Мавка. Лісова пісня',          'Анімаційна адаптація драми-феєрії Лесі Українки.',             99, 2023,  6),
('Той, що біжить по лезу 2049',  'Новий мисливець за replicant розкриває давню таємницю.',      164, 2017, 16),
('Хрещений батько',              'Сага про сицилійську мафіозну родину Корлеоне.',              175, 1972, 18),
('Коко',                         'Хлопчик потрапляє у Країну мертвих, щоб стати музикантом.',   105, 2017,  6),
('Памфір',                       'Контрабандист на українсько-румунському кордоні.',            101, 2022, 16);

INSERT INTO movie_genres (movie_id, genre_id) VALUES
(1,1),(1,8),(1,2),
(2,9),(2,2),
(3,5),(3,3),(3,11),
(4,1),(4,2),
(5,3),(5,6),
(6,6),(6,8),
(7,7),(7,2),(7,3),
(8,5),(8,6),(8,12),(8,11),
(9,1),(9,7),
(10,10),(10,2),
(11,5),(11,11),(11,8),
(12,2),(12,7);

INSERT INTO halls (name, hall_type) VALUES
('Зал 1', '2D'), ('Зал 2', '2D'), ('Зал 3', '2D'),
('Зал 4', '3D'), ('Зал 5', '3D'),
('Зал 6', '2D'), ('Зал 7', '2D'),
('IMAX',  'IMAX'),
('VIP 1', 'VIP'), ('VIP 2', 'VIP');

-- Місця генеруються: кількість рядів x місць у ряду для кожного залу
INSERT INTO seats (hall_id, row_number, seat_number)
SELECT h.hall_id, r, s
FROM halls h
JOIN (VALUES
    ('Зал 1', 8, 12), ('Зал 2', 8, 12), ('Зал 3', 6, 10),
    ('Зал 4', 8, 10), ('Зал 5', 7, 10),
    ('Зал 6', 6, 8),  ('Зал 7', 6, 8),
    ('IMAX', 12, 16),
    ('VIP 1', 4, 6),  ('VIP 2', 4, 6)
) AS cfg(hall_name, rows_cnt, per_row) ON cfg.hall_name = h.name
CROSS JOIN LATERAL generate_series(1, cfg.rows_cnt) AS r
CROSS JOIN LATERAL generate_series(1, cfg.per_row)  AS s;

INSERT INTO customers (first_name, last_name, email, phone) VALUES
('Олена',    'Коваленко',  'olena.kovalenko@example.com',  '+380501234501'),
('Андрій',   'Шевчук',     'andriy.shevchuk@example.com',  '+380671234502'),
('Марія',    'Бондаренко', 'maria.bondarenko@example.com', '+380931234503'),
('Дмитро',   'Мельник',    'dmytro.melnyk@example.com',    '+380501234504'),
('Софія',    'Ткаченко',   'sofia.tkachenko@example.com',  '+380661234505'),
('Іван',     'Кравченко',  'ivan.kravchenko@example.com',  '+380971234506'),
('Анна',     'Олійник',    'anna.oliynyk@example.com',     '+380631234507'),
('Максим',   'Лисенко',    'maksym.lysenko@example.com',   '+380501234508'),
('Катерина', 'Мороз',      'kateryna.moroz@example.com',   '+380991234509'),
('Богдан',   'Савчук',     'bohdan.savchuk@example.com',   '+380671234510'),
('Юлія',     'Гончар',     'yulia.honchar@example.com',    NULL),
('Назар',    'Руденко',    'nazar.rudenko@example.com',    '+380931234512');

-- Сеанси: від учора до післязавтра
INSERT INTO screenings (movie_id, hall_id, start_time, base_price) VALUES
(1,  8, (CURRENT_DATE - 1) + TIME '18:00', 220),   -- 1  минулий
(2,  8, (CURRENT_DATE - 1) + TIME '21:30', 220),   -- 2  минулий
(3,  1, (CURRENT_DATE - 1) + TIME '12:00', 120),   -- 3  минулий
(8,  2, (CURRENT_DATE - 1) + TIME '14:00', 110),   -- 4  минулий
(1,  8,  CURRENT_DATE      + TIME '18:00', 220),   -- 5  сьогодні
(3,  1,  CURRENT_DATE      + TIME '12:30', 120),   -- 6  сьогодні
(8,  2,  CURRENT_DATE      + TIME '15:00', 110),   -- 7  сьогодні
(4,  4,  CURRENT_DATE      + TIME '19:00', 160),   -- 8  сьогодні
(9,  9,  CURRENT_DATE      + TIME '20:30', 300),   -- 9  сьогодні
(5,  5, (CURRENT_DATE + 1) + TIME '17:00', 150),   -- 10 завтра
(7,  3, (CURRENT_DATE + 1) + TIME '19:30', 140),   -- 11 завтра
(6,  6, (CURRENT_DATE + 1) + TIME '16:00', 130),   -- 12 завтра
(10, 7, (CURRENT_DATE + 1) + TIME '21:00', 140),   -- 13 завтра
(12, 3, (CURRENT_DATE + 2) + TIME '20:00', 130),   -- 14 післязавтра
(11, 2, (CURRENT_DATE + 2) + TIME '11:00', 110);   -- 15 післязавтра

-- Квитки: (сеанс, ряд, місце, клієнт, коефіцієнт ціни, статус, за скільки до початку куплено)
-- Місце шукається в залі саме цього сеансу.
INSERT INTO tickets (screening_id, seat_id, customer_id, price, status, purchased_at, cancelled_at)
SELECT screening_id, seat_id, customer_id, price, status, purchased_at,
       CASE WHEN status = 'cancelled' THEN purchased_at + INTERVAL '10 minutes' END
FROM (
    SELECT v.screening_id, st.seat_id, v.customer_id,
           sc.base_price * v.coef AS price,
           v.status,
           LEAST(sc.start_time - v.before, CURRENT_TIMESTAMP - INTERVAL '1 hour') AS purchased_at
    FROM (VALUES
        ( 1, 5,  7,  1, 1.0, 'sold',      INTERVAL '2 days'),
        ( 1, 5,  8,  2, 1.0, 'sold',      INTERVAL '2 days'),
        ( 1, 6, 10,  3, 0.8, 'sold',      INTERVAL '1 day'),
        ( 1, 8,  3,  4, 1.0, 'sold',      INTERVAL '5 hours'),
        ( 2, 7,  7,  1, 1.0, 'sold',      INTERVAL '1 day'),
        ( 2, 7,  8,  5, 1.0, 'sold',      INTERVAL '3 hours'),
        ( 2, 9, 12,  6, 1.0, 'cancelled', INTERVAL '1 day'),
        ( 3, 4,  5,  7, 0.5, 'sold',      INTERVAL '1 day'),
        ( 3, 4,  6,  7, 0.5, 'sold',      INTERVAL '1 day'),
        ( 3, 4,  7,  8, 0.5, 'sold',      INTERVAL '3 hours'),
        ( 4, 3,  3,  9, 0.5, 'sold',      INTERVAL '1 day'),
        ( 4, 3,  4,  9, 0.5, 'sold',      INTERVAL '1 day'),
        ( 5, 5,  7, 10, 1.0, 'sold',      INTERVAL '3 days'),
        ( 5, 5,  8, 11, 1.0, 'sold',      INTERVAL '3 days'),
        ( 5, 6,  9, 12, 1.0, 'sold',      INTERVAL '1 day'),
        ( 5, 10, 2,  2, 0.8, 'sold',      INTERVAL '2 hours'),
        ( 6, 2,  5,  3, 0.5, 'sold',      INTERVAL '1 day'),
        ( 6, 2,  6,  3, 0.5, 'sold',      INTERVAL '1 day'),
        ( 7, 5,  5,  4, 1.0, 'sold',      INTERVAL '1 day'),
        ( 8, 4,  5,  1, 1.0, 'sold',      INTERVAL '2 days'),
        ( 8, 4,  6,  5, 1.0, 'sold',      INTERVAL '2 days'),
        ( 9, 2,  3,  6, 1.0, 'sold',      INTERVAL '3 days'),
        ( 9, 2,  4,  7, 1.0, 'sold',      INTERVAL '3 days'),
        ( 9, 3,  1,  8, 1.0, 'cancelled', INTERVAL '2 days'),   -- скасоване...
        ( 9, 3,  1, 10, 1.0, 'sold',      INTERVAL '1 day'),    -- ...і те саме місце продане повторно
        (10, 3,  5,  9, 1.0, 'sold',      INTERVAL '1 day'),
        (10, 3,  6, 10, 1.0, 'sold',      INTERVAL '1 day'),
        (11, 2,  2, 11, 1.0, 'sold',      INTERVAL '1 day'),
        (12, 4,  4, 12, 0.8, 'sold',      INTERVAL '1 day'),
        (13, 3,  3,  2, 1.0, 'sold',      INTERVAL '1 day'),
        (13, 3,  4,  3, 1.0, 'sold',      INTERVAL '1 day'),
        (14, 6,  7,  4, 1.0, 'sold',      INTERVAL '1 day'),
        (15, 1,  1,  8, 0.5, 'sold',      INTERVAL '1 day')
    ) AS v(screening_id, r, s, customer_id, coef, status, before)
    JOIN screenings sc ON sc.screening_id = v.screening_id
    JOIN seats st ON st.hall_id = sc.hall_id AND st.row_number = v.r AND st.seat_number = v.s
) q;

-- =====================================================================
-- Користувачі системи (12). Паролі збережені хешами (werkzeug, pbkdf2:sha256).
-- Паролі для входу: admin -> admin123, касири -> cashier123, глядачі -> customer123
-- (хеш однаковий в межах ролі, це лише тестові дані)
-- =====================================================================
INSERT INTO users (username, password_hash, email, role, customer_id) VALUES
('admin',    'pbkdf2:sha256:1000000$6bnjXHfFuDMWdgJM$19bb4db0c8ac82e8209e0ef9d8d82c2d9855e113ae2a6cb161ee20ea0f6563e0', 'admin@cinema.ua',    'admin',   NULL),
('cashier1', 'pbkdf2:sha256:1000000$8kD6qoUoAA5TAaCx$2654306e80d091e758fe5da54125a938e91b7f2149dff761bdad886bf9ddc478', 'cashier1@cinema.ua', 'cashier', NULL),
('cashier2', 'pbkdf2:sha256:1000000$8kD6qoUoAA5TAaCx$2654306e80d091e758fe5da54125a938e91b7f2149dff761bdad886bf9ddc478', 'cashier2@cinema.ua', 'cashier', NULL),
('olena_k',    'pbkdf2:sha256:1000000$mm8wg34YXH7v9xbR$05b9c91a47a6b3a10e9711617e396a54c06b7279c37015ff27f7901d674dd601', 'olena.kovalenko@example.com',  'customer', 1),
('andriy_sh',  'pbkdf2:sha256:1000000$mm8wg34YXH7v9xbR$05b9c91a47a6b3a10e9711617e396a54c06b7279c37015ff27f7901d674dd601', 'andriy.shevchuk@example.com',  'customer', 2),
('maria_b',    'pbkdf2:sha256:1000000$mm8wg34YXH7v9xbR$05b9c91a47a6b3a10e9711617e396a54c06b7279c37015ff27f7901d674dd601', 'maria.bondarenko@example.com', 'customer', 3),
('dmytro_m',   'pbkdf2:sha256:1000000$mm8wg34YXH7v9xbR$05b9c91a47a6b3a10e9711617e396a54c06b7279c37015ff27f7901d674dd601', 'dmytro.melnyk@example.com',    'customer', 4),
('sofia_t',    'pbkdf2:sha256:1000000$mm8wg34YXH7v9xbR$05b9c91a47a6b3a10e9711617e396a54c06b7279c37015ff27f7901d674dd601', 'sofia.tkachenko@example.com',  'customer', 5),
('ivan_k',     'pbkdf2:sha256:1000000$mm8wg34YXH7v9xbR$05b9c91a47a6b3a10e9711617e396a54c06b7279c37015ff27f7901d674dd601', 'ivan.kravchenko@example.com',  'customer', 6),
('anna_o',     'pbkdf2:sha256:1000000$mm8wg34YXH7v9xbR$05b9c91a47a6b3a10e9711617e396a54c06b7279c37015ff27f7901d674dd601', 'anna.oliynyk@example.com',     'customer', 7),
('maksym_l',   'pbkdf2:sha256:1000000$mm8wg34YXH7v9xbR$05b9c91a47a6b3a10e9711617e396a54c06b7279c37015ff27f7901d674dd601', 'maksym.lysenko@example.com',   'customer', 8),
('kateryna_m', 'pbkdf2:sha256:1000000$mm8wg34YXH7v9xbR$05b9c91a47a6b3a10e9711617e396a54c06b7279c37015ff27f7901d674dd601', 'kateryna.moroz@example.com',   'customer', 9);

-- =====================================================================
-- Журнал дій (12 записів). Номери квитків беруться з реальних даних.
-- =====================================================================
INSERT INTO activity_log (user_id, action, table_name, record_id, details, created_at) VALUES
(1, 'LOGIN',  NULL, NULL, 'Вхід адміністратора', CURRENT_TIMESTAMP - INTERVAL '3 days'),
(1, 'INSERT', 'movies', 12, 'Додано фільм «Памфір»', CURRENT_TIMESTAMP - INTERVAL '3 days'),
(1, 'INSERT', 'screenings', 14, 'Створено сеанс на післязавтра, Зал 3', CURRENT_TIMESTAMP - INTERVAL '2 days 22 hours'),
(2, 'LOGIN',  NULL, NULL, 'Вхід касира', CURRENT_TIMESTAMP - INTERVAL '2 days'),
(2, 'SELL_TICKET', 'tickets',
    (SELECT MIN(ticket_id) FROM tickets WHERE screening_id = 5),
    'Продано квиток на сеанс 5', CURRENT_TIMESTAMP - INTERVAL '2 days'),
(2, 'SELL_TICKET', 'tickets',
    (SELECT MAX(ticket_id) FROM tickets WHERE screening_id = 5),
    'Продано квиток на сеанс 5', CURRENT_TIMESTAMP - INTERVAL '2 days'),
(3, 'LOGIN',  NULL, NULL, 'Вхід касира', CURRENT_TIMESTAMP - INTERVAL '1 day'),
(3, 'CANCEL_TICKET', 'tickets',
    (SELECT MIN(ticket_id) FROM tickets WHERE status = 'cancelled' AND screening_id = 9),
    'Квиток скасовано за проханням клієнта', CURRENT_TIMESTAMP - INTERVAL '1 day'),
(3, 'SELL_TICKET', 'tickets',
    (SELECT MIN(ticket_id) FROM tickets WHERE status = 'sold' AND screening_id = 9 AND customer_id = 10),
    'Скасоване місце продано повторно', CURRENT_TIMESTAMP - INTERVAL '1 day'),
(4, 'LOGIN',  NULL, NULL, 'Вхід глядача olena_k', CURRENT_TIMESTAMP - INTERVAL '5 hours'),
(1, 'UPDATE', 'screenings', 9, 'Змінено базову ціну сеансу 9', CURRENT_TIMESTAMP - INTERVAL '4 hours'),
(1, 'LOGOUT', NULL, NULL, 'Вихід адміністратора', CURRENT_TIMESTAMP - INTERVAL '3 hours');

-- =====================================================================
-- Аудит змін квитків. Знижкові квитки: ціна змінилась з базової на пільгову;
-- скасовані: ціна -> NULL. На рівні 2 такі записи додаватиме тригер.
-- =====================================================================
INSERT INTO ticket_audit (ticket_id, operation, old_price, new_price, changed_by, changed_at)
SELECT t.ticket_id, 'UPDATE', s.base_price, t.price,
       CASE WHEN t.ticket_id % 2 = 0 THEN 'cashier1' ELSE 'cashier2' END,
       t.purchased_at + INTERVAL '1 minute'
FROM tickets t
JOIN screenings s ON s.screening_id = t.screening_id
WHERE t.status = 'sold' AND t.price < s.base_price
UNION ALL
SELECT t.ticket_id, 'UPDATE', t.price, NULL, 'cashier2', t.cancelled_at
FROM tickets t
WHERE t.status = 'cancelled';