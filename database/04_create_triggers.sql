-- =====================================================================
-- Тригери, рівень 2
-- =====================================================================

-- Тригер 1. Місце квитка має належати залу, у якому йде сеанс.
-- Закриває правило, яке не можна виразити звичайними обмеженнями (воно зачіпає 3 таблиці).
CREATE OR REPLACE FUNCTION check_ticket_seat_hall() RETURNS TRIGGER AS $$
DECLARE
    v_seat_hall      INT;
    v_screening_hall INT;
BEGIN
    SELECT hall_id INTO v_seat_hall      FROM seats      WHERE seat_id      = NEW.seat_id;
    SELECT hall_id INTO v_screening_hall FROM screenings WHERE screening_id = NEW.screening_id;

    IF v_seat_hall IS DISTINCT FROM v_screening_hall THEN
        RAISE EXCEPTION 'Місце (ID %) належить іншому залу, ніж сеанс (ID %)',
                        NEW.seat_id, NEW.screening_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ticket_seat_hall
BEFORE INSERT OR UPDATE OF screening_id, seat_id ON tickets
FOR EACH ROW EXECUTE FUNCTION check_ticket_seat_hall();


-- Тригер 2. Сеанси в одному залі не можуть перетинатися в часі.
-- Враховується тривалість фільму та 15 хвилин на прибирання між сеансами.
CREATE OR REPLACE FUNCTION check_screening_overlap() RETURNS TRIGGER AS $$
DECLARE
    v_break    CONSTANT INT := 15;   -- хвилин на прибирання залу
    v_duration INT;
    v_conflict RECORD;
BEGIN
    SELECT duration_min INTO v_duration FROM movies WHERE movie_id = NEW.movie_id;
    IF v_duration IS NULL THEN
        RETURN NEW;   -- фільму немає: помилку видасть зовнішній ключ
    END IF;

    SELECT s.screening_id, s.start_time, m.title
    INTO v_conflict
    FROM screenings s
    JOIN movies m ON m.movie_id = s.movie_id
    WHERE s.hall_id = NEW.hall_id
      AND s.screening_id IS DISTINCT FROM NEW.screening_id
      AND NEW.start_time < s.start_time + (m.duration_min + v_break) * INTERVAL '1 minute'
      AND s.start_time   < NEW.start_time + (v_duration + v_break)   * INTERVAL '1 minute'
    LIMIT 1;

    IF FOUND THEN
        RAISE EXCEPTION 'У цьому залі вже є сеанс «%» о %, час перетинається',
                        v_conflict.title, to_char(v_conflict.start_time, 'YYYY-MM-DD HH24:MI');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_screening_overlap
BEFORE INSERT OR UPDATE OF hall_id, start_time, movie_id ON screenings
FOR EACH ROW EXECUTE FUNCTION check_screening_overlap();


-- Тригер 3. Аудит квитків: запис у ticket_audit при продажу, зміні ціни та скасуванні.
-- Ім'я користувача береться зі змінної сесії app.current_user (її виставить вебзастосунок),
-- а якщо її немає, то це поточний користувач бази.
CREATE OR REPLACE FUNCTION log_ticket_changes() RETURNS TRIGGER AS $$
DECLARE
    v_user VARCHAR := COALESCE(NULLIF(current_setting('app.current_user', true), ''), current_user);
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO ticket_audit (ticket_id, operation, old_price, new_price, changed_by)
        VALUES (NEW.ticket_id, 'INSERT', NULL, NEW.price, v_user);

    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.status = 'sold' AND NEW.status = 'cancelled' THEN
            INSERT INTO ticket_audit (ticket_id, operation, old_price, new_price, changed_by)
            VALUES (NEW.ticket_id, 'UPDATE', OLD.price, NULL, v_user);
        ELSIF NEW.price IS DISTINCT FROM OLD.price THEN
            INSERT INTO ticket_audit (ticket_id, operation, old_price, new_price, changed_by)
            VALUES (NEW.ticket_id, 'UPDATE', OLD.price, NEW.price, v_user);
        END IF;
    END IF;
    RETURN NULL;   -- AFTER-тригер: значення, що повертається, ігнорується
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ticket_audit
AFTER INSERT OR UPDATE ON tickets
FOR EACH ROW EXECUTE FUNCTION log_ticket_changes();