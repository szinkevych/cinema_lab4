-- =====================================================================
-- Completion of level 3: explicit procedures and complete domain auditing
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_movies_title_trgm
    ON movies USING GIN (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_customers_first_name_trgm
    ON customers USING GIN (first_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_customers_last_name_trgm
    ON customers USING GIN (last_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_customers_full_name_trgm
    ON customers USING GIN ((first_name || ' ' || last_name) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_customers_email_trgm
    ON customers USING GIN (email gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_customers_phone_trgm
    ON customers USING GIN (phone gin_trgm_ops);

CREATE OR REPLACE PROCEDURE sell_ticket_proc(
    IN p_screening_id INT,
    IN p_row          INT,
    IN p_seat         INT,
    IN p_customer_id  INT,
    IN p_ticket_type  VARCHAR,
    INOUT p_ticket_id INT
) LANGUAGE plpgsql AS $$
BEGIN
    p_ticket_id := sell_ticket(p_screening_id, p_row, p_seat, p_customer_id, p_ticket_type);
END;
$$;

CREATE OR REPLACE PROCEDURE cancel_ticket_proc(IN p_ticket_id INT)
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM cancel_ticket(p_ticket_id);
END;
$$;

CREATE OR REPLACE PROCEDURE hall_revenue_report_proc(
    IN p_from DATE,
    IN p_to DATE,
    INOUT p_report JSONB
) LANGUAGE plpgsql AS $$
BEGIN
    SELECT COALESCE(
        jsonb_agg(to_jsonb(report) ORDER BY report.revenue DESC, report.hall_name),
        '[]'::JSONB
    )
    INTO p_report
    FROM hall_revenue_report(p_from, p_to) AS report;
END;
$$;

DROP TRIGGER IF EXISTS trg_log_genres ON genres;
CREATE TRIGGER trg_log_genres AFTER INSERT OR UPDATE OR DELETE ON genres
    FOR EACH ROW EXECUTE FUNCTION log_data_change('genre_id');
DROP TRIGGER IF EXISTS trg_log_halls ON halls;
CREATE TRIGGER trg_log_halls AFTER INSERT OR UPDATE OR DELETE ON halls
    FOR EACH ROW EXECUTE FUNCTION log_data_change('hall_id');
DROP TRIGGER IF EXISTS trg_log_seats ON seats;
CREATE TRIGGER trg_log_seats AFTER INSERT OR UPDATE OR DELETE ON seats
    FOR EACH ROW EXECUTE FUNCTION log_data_change('seat_id');
