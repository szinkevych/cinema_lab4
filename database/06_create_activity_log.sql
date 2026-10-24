-- =====================================================================
-- Журнал дій (рівень 3): логування ВСІХ змін даних на рівні бази
-- =====================================================================
-- Тригери записують у activity_log кожну вставку, зміну й видалення в основних таблицях,
-- хто б їх не виконував (вебзастосунок, консоль, psql). Користувача тригер бере зі змінної
-- сесії app.user_id, яку вебзастосунок виставляє на початку кожної транзакції.

-- Універсальна функція запису події (її викликає і застосунок: вхід, вихід, реєстрація)
CREATE OR REPLACE FUNCTION log_activity(
    p_user_id    INT,
    p_action     VARCHAR,
    p_table_name VARCHAR DEFAULT NULL,
    p_record_id  INT     DEFAULT NULL,
    p_details    TEXT    DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO activity_log (user_id, action, table_name, record_id, details)
    VALUES (p_user_id, p_action, p_table_name, p_record_id, p_details);
END;
$$ LANGUAGE plpgsql;


-- Тригерна функція: назву стовпця первинного ключа передають аргументом тригера.
-- INSERT: записується новий рядок; UPDATE: лише змінені поля {"поле": {"old": .., "new": ..}};
-- DELETE: видалений рядок. Хеш пароля в журнал не потрапляє.
CREATE OR REPLACE FUNCTION log_data_change() RETURNS TRIGGER AS $$
DECLARE
    v_pk   TEXT  := TG_ARGV[0];
    v_user INT   := NULLIF(current_setting('app.user_id', true), '')::INT;
    v_old  JSONB;
    v_new  JSONB;
    v_diff JSONB;
BEGIN
    IF TG_OP = 'INSERT' THEN
        v_new := to_jsonb(NEW) - 'password_hash';
        PERFORM log_activity(v_user, 'INSERT', TG_TABLE_NAME::VARCHAR, (v_new ->> v_pk)::INT, v_new::TEXT);

    ELSIF TG_OP = 'UPDATE' THEN
        v_old := to_jsonb(OLD) - 'password_hash';
        v_new := to_jsonb(NEW) - 'password_hash';
        SELECT jsonb_object_agg(n.key, jsonb_build_object('old', v_old -> n.key, 'new', n.value))
        INTO v_diff
        FROM jsonb_each(v_new) n
        WHERE (v_old -> n.key) IS DISTINCT FROM n.value;
        IF v_diff IS NOT NULL THEN                       -- нічого не змінилось - не логуємо
            PERFORM log_activity(v_user, 'UPDATE', TG_TABLE_NAME::VARCHAR, (v_new ->> v_pk)::INT, v_diff::TEXT);
        END IF;

    ELSE  -- DELETE
        v_old := to_jsonb(OLD) - 'password_hash';
        PERFORM log_activity(v_user, 'DELETE', TG_TABLE_NAME::VARCHAR, (v_old ->> v_pk)::INT, v_old::TEXT);
    END IF;
    RETURN NULL;   -- AFTER-тригер
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_log_movies       AFTER INSERT OR UPDATE OR DELETE ON movies
    FOR EACH ROW EXECUTE FUNCTION log_data_change('movie_id');
CREATE TRIGGER trg_log_movie_genres AFTER INSERT OR UPDATE OR DELETE ON movie_genres
    FOR EACH ROW EXECUTE FUNCTION log_data_change('movie_id');
CREATE TRIGGER trg_log_screenings   AFTER INSERT OR UPDATE OR DELETE ON screenings
    FOR EACH ROW EXECUTE FUNCTION log_data_change('screening_id');
CREATE TRIGGER trg_log_customers    AFTER INSERT OR UPDATE OR DELETE ON customers
    FOR EACH ROW EXECUTE FUNCTION log_data_change('customer_id');
CREATE TRIGGER trg_log_tickets      AFTER INSERT OR UPDATE OR DELETE ON tickets
    FOR EACH ROW EXECUTE FUNCTION log_data_change('ticket_id');
CREATE TRIGGER trg_log_users        AFTER INSERT OR UPDATE OR DELETE ON users
    FOR EACH ROW EXECUTE FUNCTION log_data_change('user_id');

-- Індекс для фільтрації журналу за таблицею та дією
CREATE INDEX idx_activity_log_table_action ON activity_log(table_name, action);