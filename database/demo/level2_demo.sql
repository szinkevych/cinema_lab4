-- Демонстрація рівня 2 (для скріншотів у звіт).
-- Файл лежить у підпапці demo, тому Docker його сам НЕ виконує (тут навмисні помилки).
-- Запуск: docker cp database/demo/level2_demo.sql cinema_db:/tmp/demo.sql
--         docker exec -it cinema_db psql -U postgres -d cinema -f /tmp/demo.sql

\echo '=== ПРОЦЕДУРА 1: продаж квитка (успіх) ==='
SELECT sell_ticket(10, 3, 3, 1, 'student') AS new_ticket \gset
SELECT :new_ticket AS ticket_id;

\echo '=== ПРОЦЕДУРА 1: те саме місце вдруге (помилка) ==='
SELECT sell_ticket(10, 3, 3, 2);

\echo '=== ПРОЦЕДУРА 1: сеанс, що вже минув (помилка) ==='
SELECT sell_ticket(1, 1, 1, 1);

\echo '=== ПРОЦЕДУРА 1: неіснуюче місце (помилка) ==='
SELECT sell_ticket(10, 99, 1, 1);

\echo '=== ТРИГЕР 3 (аудит): що записалось при продажу ==='
SELECT audit_id, ticket_id, operation, old_price, new_price, changed_by
FROM ticket_audit WHERE ticket_id = :new_ticket;

\echo '=== ТРИГЕР 3 (аудит): зміна ціни ==='
UPDATE tickets SET price = price - 10 WHERE ticket_id = :new_ticket;
SELECT audit_id, ticket_id, operation, old_price, new_price, changed_by
FROM ticket_audit WHERE ticket_id = :new_ticket ORDER BY audit_id;

\echo '=== ПРОЦЕДУРА 2: скасування квитка ==='
SELECT cancel_ticket(:new_ticket);
SELECT ticket_id, status, cancelled_at IS NOT NULL AS has_cancel_time FROM tickets WHERE ticket_id = :new_ticket;

\echo '=== ПРОЦЕДУРА 2: повторне скасування (помилка) ==='
SELECT cancel_ticket(:new_ticket);

\echo '=== ТРИГЕР 1: місце з іншого залу (помилка) ==='
INSERT INTO tickets (screening_id, seat_id, customer_id, price)
SELECT 10, seat_id, 1, 100 FROM seats WHERE hall_id = 8 LIMIT 1;

\echo '=== ТРИГЕР 2: сеанс, що перетинається з іншим у залі 5 (помилка) ==='
INSERT INTO screenings (movie_id, hall_id, start_time, base_price)
VALUES (2, 5, (CURRENT_DATE + 1) + TIME '18:00', 100);

\echo '=== ТРИГЕР 2: сеанс без перетину (успіх, потім відкочуємо) ==='
BEGIN;
INSERT INTO screenings (movie_id, hall_id, start_time, base_price)
VALUES (2, 5, (CURRENT_DATE + 1) + TIME '20:00', 100) RETURNING screening_id, start_time;
ROLLBACK;

\echo '=== ПРОЦЕДУРА 3: виручка по залах ==='
SELECT * FROM hall_revenue_report(CURRENT_DATE - 1, CURRENT_DATE + 2);

\echo '=== ПРОЦЕДУРА 3: неправильний період (помилка) ==='
SELECT * FROM hall_revenue_report(CURRENT_DATE + 5, CURRENT_DATE);

\echo '=== ПРЕДСТАВЛЕННЯ 1: tickets_full ==='
SELECT * FROM tickets_full ORDER BY ticket_id DESC LIMIT 5;

\echo '=== ПРЕДСТАВЛЕННЯ 2: screening_occupancy ==='
SELECT * FROM screening_occupancy ORDER BY occupancy_pct DESC LIMIT 5;

\echo '=== ПРЕДСТАВЛЕННЯ 3: movie_revenue ==='
SELECT * FROM movie_revenue ORDER BY revenue DESC LIMIT 5;