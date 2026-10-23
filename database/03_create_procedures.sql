-- =====================================================================
-- Збережені процедури (функції PL/pgSQL), рівень 2
-- Усі помилки подаються через RAISE EXCEPTION зі зрозумілим текстом.
-- =====================================================================

-- Процедура 1. Продаж квитка з усіма перевірками.
-- Тип квитка: regular (повна ціна), child (-50%), student (-20%).
-- Повертає номер створеного квитка.
CREATE OR REPLACE FUNCTION sell_ticket(
    p_screening_id INT,
    p_row          INT,
    p_seat         INT,
    p_customer_id  INT,
    p_ticket_type  VARCHAR DEFAULT 'regular'
) RETURNS INT AS $$
DECLARE
    v_start     TIMESTAMP;
    v_hall_id   INT;
    v_base      DECIMAL(8, 2);
    v_seat_id   INT;
    v_coef      DECIMAL(3, 2);
    v_ticket_id INT;
BEGIN
    SELECT start_time, hall_id, base_price
    INTO v_start, v_hall_id, v_base
    FROM screenings
    WHERE screening_id = p_screening_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Сеанс % не знайдено', p_screening_id;
    END IF;
    IF v_start <= CURRENT_TIMESTAMP THEN
        RAISE EXCEPTION 'Сеанс % уже розпочався, продаж неможливий', p_screening_id;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM customers WHERE customer_id = p_customer_id) THEN
        RAISE EXCEPTION 'Клієнта % не знайдено', p_customer_id;
    END IF;

    -- Місце шукаємо саме в залі цього сеансу
    SELECT seat_id INTO v_seat_id
    FROM seats
    WHERE hall_id = v_hall_id AND row_number = p_row AND seat_number = p_seat;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'У залі цього сеансу немає місця: ряд %, місце %', p_row, p_seat;
    END IF;

    v_coef := CASE p_ticket_type
                  WHEN 'regular' THEN 1.0
                  WHEN 'child'   THEN 0.5
                  WHEN 'student' THEN 0.8
              END;
    IF v_coef IS NULL THEN
        RAISE EXCEPTION 'Невідомий тип квитка "%" (дозволено: regular, child, student)', p_ticket_type;
    END IF;

    INSERT INTO tickets (screening_id, seat_id, customer_id, price)
    VALUES (p_screening_id, v_seat_id, p_customer_id, v_base * v_coef)
    RETURNING ticket_id INTO v_ticket_id;

    RETURN v_ticket_id;
EXCEPTION
    WHEN unique_violation THEN
        RAISE EXCEPTION 'Місце (ряд %, місце %) на сеанс % уже продано', p_row, p_seat, p_screening_id;
END;
$$ LANGUAGE plpgsql;


-- Процедура 2. Скасування квитка (не пізніше ніж за годину до початку).
CREATE OR REPLACE FUNCTION cancel_ticket(p_ticket_id INT) RETURNS VOID AS $$
DECLARE
    v_status VARCHAR;
    v_start  TIMESTAMP;
BEGIN
    SELECT t.status, s.start_time
    INTO v_status, v_start
    FROM tickets t
    JOIN screenings s ON s.screening_id = t.screening_id
    WHERE t.ticket_id = p_ticket_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Квиток % не знайдено', p_ticket_id;
    END IF;
    IF v_status = 'cancelled' THEN
        RAISE EXCEPTION 'Квиток % уже скасовано', p_ticket_id;
    END IF;
    IF v_start <= CURRENT_TIMESTAMP + INTERVAL '1 hour' THEN
        RAISE EXCEPTION 'Скасування можливе не пізніше ніж за годину до початку сеансу';
    END IF;

    UPDATE tickets
    SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP
    WHERE ticket_id = p_ticket_id;
END;
$$ LANGUAGE plpgsql;


-- Процедура 3. Звіт про виручку по залах за період (за датою сеансу).
CREATE OR REPLACE FUNCTION hall_revenue_report(p_from DATE, p_to DATE)
RETURNS TABLE (
    hall_name        VARCHAR,
    hall_kind        VARCHAR,
    screenings_count BIGINT,
    tickets_sold     BIGINT,
    revenue          NUMERIC
) AS $$
BEGIN
    IF p_from > p_to THEN
        RAISE EXCEPTION 'Початок періоду (%) пізніше за його кінець (%)', p_from, p_to;
    END IF;

    RETURN QUERY
    SELECT h.name::VARCHAR,
           h.hall_type::VARCHAR,
           COUNT(DISTINCT s.screening_id),
           COUNT(t.ticket_id),
           COALESCE(SUM(t.price), 0)::NUMERIC
    FROM halls h
    LEFT JOIN screenings s ON s.hall_id = h.hall_id
                          AND s.start_time::date BETWEEN p_from AND p_to
    LEFT JOIN tickets t    ON t.screening_id = s.screening_id AND t.status = 'sold'
    GROUP BY h.hall_id, h.name, h.hall_type
    ORDER BY 5 DESC, h.name;
END;
$$ LANGUAGE plpgsql;