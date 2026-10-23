-- =====================================================================
-- SQL-запити (різної складності)
-- =====================================================================

-- Запит 1 (проста фільтрація). Сучасні фільми для віку до 12 років, найдовші першими
SELECT title, release_year, duration_min, age_rating
FROM movies
WHERE release_year >= 2015 AND age_rating <= 12
ORDER BY duration_min DESC;

-- Запит 2 (JOIN). Розклад на сьогодні
SELECT to_char(s.start_time, 'HH24:MI') AS start,
       m.title, h.name AS hall, h.hall_type, s.base_price
FROM screenings s
JOIN movies m ON m.movie_id = s.movie_id
JOIN halls  h ON h.hall_id  = s.hall_id
WHERE s.start_time::date = CURRENT_DATE
ORDER BY s.start_time;

-- Запит 3 (JOIN + агрегація рядків). Фільми та їхні жанри
SELECT m.title, string_agg(g.name, ', ' ORDER BY g.name) AS genres
FROM movies m
JOIN movie_genres mg ON mg.movie_id = m.movie_id
JOIN genres g        ON g.genre_id  = mg.genre_id
GROUP BY m.movie_id, m.title
ORDER BY m.title;

-- Запит 4 (агрегація). Виручка і кількість проданих квитків по фільмах
SELECT m.title,
       COUNT(t.ticket_id)         AS tickets_sold,
       COALESCE(SUM(t.price), 0)  AS revenue
FROM movies m
LEFT JOIN screenings s ON s.movie_id = m.movie_id
LEFT JOIN tickets t    ON t.screening_id = s.screening_id AND t.status = 'sold'
GROUP BY m.movie_id, m.title
ORDER BY revenue DESC;

-- Запит 5 (агрегація + підзапит у FROM). Заповненість кожного сеансу, %
SELECT s.screening_id, m.title, h.name AS hall, s.start_time,
       COUNT(t.ticket_id) AS sold,
       hs.total_seats,
       ROUND(100.0 * COUNT(t.ticket_id) / hs.total_seats, 1) AS occupancy_pct
FROM screenings s
JOIN movies m ON m.movie_id = s.movie_id
JOIN halls  h ON h.hall_id  = s.hall_id
JOIN (SELECT hall_id, COUNT(*) AS total_seats FROM seats GROUP BY hall_id) hs
     ON hs.hall_id = s.hall_id
LEFT JOIN tickets t ON t.screening_id = s.screening_id AND t.status = 'sold'
GROUP BY s.screening_id, m.title, h.name, s.start_time, hs.total_seats
ORDER BY occupancy_pct DESC;

-- Запит 6 (підзапит NOT EXISTS). Вільні місця на сеанс №5 по рядах
SELECT st.row_number,
       string_agg(st.seat_number::text, ', ' ORDER BY st.seat_number) AS free_seats
FROM screenings sc
JOIN seats st ON st.hall_id = sc.hall_id
WHERE sc.screening_id = 5
  AND NOT EXISTS (SELECT 1 FROM tickets t
                  WHERE t.screening_id = sc.screening_id
                    AND t.seat_id = st.seat_id
                    AND t.status = 'sold')
GROUP BY st.row_number
ORDER BY st.row_number;

-- Запит 7 (HAVING + підзапит). Клієнти, які витратили більше за середнього покупця
SELECT c.first_name || ' ' || c.last_name AS customer,
       COUNT(*) AS tickets, SUM(t.price) AS total_spent
FROM customers c
JOIN tickets t ON t.customer_id = c.customer_id AND t.status = 'sold'
GROUP BY c.customer_id, c.first_name, c.last_name
HAVING SUM(t.price) > (SELECT AVG(total)
                       FROM (SELECT SUM(price) AS total
                             FROM tickets WHERE status = 'sold'
                             GROUP BY customer_id) x)
ORDER BY total_spent DESC;

-- Запит 8 (підзапит NOT EXISTS). Фільми, яких немає в майбутньому розкладі
SELECT m.title, m.release_year
FROM movies m
WHERE NOT EXISTS (SELECT 1 FROM screenings s
                  WHERE s.movie_id = m.movie_id AND s.start_time > CURRENT_TIMESTAMP)
ORDER BY m.title;

-- Запит 9 (кілька JOIN). Історія покупок клієнта №1
SELECT t.ticket_id, m.title, h.name AS hall, s.start_time,
       st.row_number, st.seat_number, t.price, t.status
FROM tickets t
JOIN screenings s ON s.screening_id = t.screening_id
JOIN movies m     ON m.movie_id = s.movie_id
JOIN halls h      ON h.hall_id = s.hall_id
JOIN seats st     ON st.seat_id = t.seat_id
WHERE t.customer_id = 1
ORDER BY s.start_time;

-- Запит 10 (агрегація). Виручка за типами залів
SELECT h.hall_type, COUNT(t.ticket_id) AS tickets_sold, SUM(t.price) AS revenue
FROM tickets t
JOIN screenings s ON s.screening_id = t.screening_id
JOIN halls h      ON h.hall_id = s.hall_id
WHERE t.status = 'sold'
GROUP BY h.hall_type
ORDER BY revenue DESC;

-- =====================================================================
-- Рівень 2: складні аналітичні запити з агрегацією та віконними функціями
-- =====================================================================

-- Запит 11. Виручка по днях з наростаючим підсумком (віконна функція SUM OVER)
SELECT s.start_time::date AS day,
       COUNT(t.ticket_id) AS tickets,
       SUM(t.price)       AS revenue,
       SUM(SUM(t.price)) OVER (ORDER BY s.start_time::date) AS running_total
FROM tickets t
JOIN screenings s ON s.screening_id = t.screening_id
WHERE t.status = 'sold'
GROUP BY s.start_time::date
ORDER BY day;

-- Запит 12. Два найприбутковіші фільми в кожному типі залу (RANK OVER PARTITION BY)
SELECT hall_type, title, revenue, rnk
FROM (
    SELECT h.hall_type, m.title, SUM(t.price) AS revenue,
           RANK() OVER (PARTITION BY h.hall_type ORDER BY SUM(t.price) DESC) AS rnk
    FROM tickets t
    JOIN screenings s ON s.screening_id = t.screening_id
    JOIN movies m     ON m.movie_id = s.movie_id
    JOIN halls h      ON h.hall_id = s.hall_id
    WHERE t.status = 'sold'
    GROUP BY h.hall_type, m.movie_id, m.title
) ranked
WHERE rnk <= 2
ORDER BY hall_type, rnk;

-- Запит 13. Виручка по жанрах і частка кожного жанру (фільм зараховується до кожного свого жанру)
SELECT g.name AS genre,
       COUNT(t.ticket_id) AS tickets,
       SUM(t.price)       AS revenue,
       ROUND(100.0 * SUM(t.price) / SUM(SUM(t.price)) OVER (), 1) AS share_pct
FROM genres g
JOIN movie_genres mg ON mg.genre_id = g.genre_id
JOIN screenings s    ON s.movie_id = mg.movie_id
JOIN tickets t       ON t.screening_id = s.screening_id AND t.status = 'sold'
GROUP BY g.genre_id, g.name
ORDER BY revenue DESC;