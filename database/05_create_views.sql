-- =====================================================================
-- Представлення (VIEW), рівень 2
-- =====================================================================

-- Представлення 1. Квиток з повною інформацією (фільм, зал, час, місце, клієнт)
CREATE VIEW tickets_full AS
SELECT t.ticket_id,
       m.title                              AS movie,
       h.name                               AS hall,
       s.start_time,
       st.row_number,
       st.seat_number,
       c.first_name || ' ' || c.last_name   AS customer,
       t.price,
       t.status,
       t.purchased_at
FROM tickets t
JOIN screenings s ON s.screening_id = t.screening_id
JOIN movies m     ON m.movie_id     = s.movie_id
JOIN halls h      ON h.hall_id      = s.hall_id
JOIN seats st     ON st.seat_id     = t.seat_id
JOIN customers c  ON c.customer_id  = t.customer_id;

-- Представлення 2. Заповненість кожного сеансу
CREATE VIEW screening_occupancy AS
SELECT s.screening_id,
       m.title,
       h.name AS hall,
       s.start_time,
       hs.total_seats,
       COUNT(t.ticket_id)                                  AS sold_seats,
       hs.total_seats - COUNT(t.ticket_id)                 AS free_seats,
       ROUND(100.0 * COUNT(t.ticket_id) / hs.total_seats, 1) AS occupancy_pct
FROM screenings s
JOIN movies m ON m.movie_id = s.movie_id
JOIN halls  h ON h.hall_id  = s.hall_id
JOIN (SELECT hall_id, COUNT(*) AS total_seats FROM seats GROUP BY hall_id) hs
     ON hs.hall_id = s.hall_id
LEFT JOIN tickets t ON t.screening_id = s.screening_id AND t.status = 'sold'
GROUP BY s.screening_id, m.title, h.name, s.start_time, hs.total_seats;

-- Представлення 3. Виручка по фільмах
CREATE VIEW movie_revenue AS
SELECT m.movie_id,
       m.title,
       COUNT(t.ticket_id)        AS tickets_sold,
       COALESCE(SUM(t.price), 0) AS revenue
FROM movies m
LEFT JOIN screenings s ON s.movie_id = m.movie_id
LEFT JOIN tickets t    ON t.screening_id = s.screening_id AND t.status = 'sold'
GROUP BY m.movie_id, m.title;