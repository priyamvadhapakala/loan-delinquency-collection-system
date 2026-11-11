def apply_additive_migrations(connection):
    """Apply backward-compatible schema additions without altering existing rows."""
    preference_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(ContactPreference)")
    }
    additions = {
        "timezone": "TEXT",
        "allowed_contact_start": "TEXT",
        "allowed_contact_end": "TEXT",
        "weekend_contact_allowed": "INTEGER NOT NULL DEFAULT 0",
        "holiday_contact_allowed": "INTEGER NOT NULL DEFAULT 0",
        "allowed_channels_json": "TEXT",
    }
    for column, definition in additions.items():
        if column not in preference_columns:
            connection.execute(
                f"ALTER TABLE ContactPreference ADD COLUMN {column} {definition}"
            )

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS LoanAccountStatus (
            loan_id TEXT PRIMARY KEY REFERENCES Loan(loan_id) ON DELETE RESTRICT,
            dispute_status TEXT NOT NULL DEFAULT 'clear'
                CHECK (dispute_status IN ('clear', 'disputed', 'resolved')),
            hardship_status TEXT NOT NULL DEFAULT 'none'
                CHECK (hardship_status IN ('none', 'active', 'resolved')),
            debt_status TEXT NOT NULL DEFAULT 'unverified'
                CHECK (debt_status IN ('unverified', 'confirmed')),
            updated_at TEXT NOT NULL
                CHECK (strftime('%Y-%m-%dT%H:%M:%SZ', updated_at) = updated_at)
        );

        CREATE TABLE IF NOT EXISTS ComplianceAuditEvent (
            audit_id TEXT PRIMARY KEY
                CHECK (audit_id GLOB 'AUD-[0-9][0-9][0-9][0-9][0-9][0-9]'),
            event_at TEXT NOT NULL
                CHECK (strftime('%Y-%m-%dT%H:%M:%SZ', event_at) = event_at),
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            outcome TEXT NOT NULL CHECK (outcome IN ('permitted', 'denied', 'success')),
            reason TEXT NOT NULL,
            details_json TEXT NOT NULL DEFAULT '{}'
                CHECK (json_valid(details_json))
        );

        CREATE TABLE IF NOT EXISTS ContactHoliday (
            holiday_date TEXT PRIMARY KEY CHECK (date(holiday_date) = holiday_date),
            label TEXT NOT NULL CHECK (length(trim(label)) > 0),
            configured_at TEXT NOT NULL
                CHECK (strftime('%Y-%m-%dT%H:%M:%SZ', configured_at) = configured_at)
        );

        CREATE TABLE IF NOT EXISTS AnomalyRecord (
            anomaly_id TEXT PRIMARY KEY
                CHECK (anomaly_id GLOB 'ANM-[0-9][0-9][0-9][0-9][0-9][0-9]'),
            anomaly_type TEXT NOT NULL CHECK (anomaly_type IN (
                'paid_account_in_collection',
                'contact_outside_allowed_window',
                'payment_wrong_installment',
                'promise_exceeds_arrears',
                'disputed_debt_confirmed'
            )),
            record_reference TEXT NOT NULL,
            reason TEXT NOT NULL,
            detection_status TEXT NOT NULL CHECK (detection_status IN ('active', 'resolved')),
            first_detected_at TEXT NOT NULL,
            last_detected_at TEXT NOT NULL,
            UNIQUE (anomaly_type, record_reference)
        );

        CREATE TABLE IF NOT EXISTS AnomalyGroundTruth (
            label_id TEXT PRIMARY KEY,
            anomaly_type TEXT NOT NULL,
            record_reference TEXT NOT NULL,
            is_anomaly INTEGER NOT NULL CHECK (is_anomaly IN (0, 1)),
            label_source TEXT NOT NULL,
            labeled_at TEXT NOT NULL,
            UNIQUE (anomaly_type, record_reference)
        );

        CREATE INDEX IF NOT EXISTS ix_audit_entity_time
            ON ComplianceAuditEvent(entity_type, entity_id, event_at);
        CREATE INDEX IF NOT EXISTS ix_anomaly_status_type
            ON AnomalyRecord(detection_status, anomaly_type);

        CREATE TRIGGER IF NOT EXISTS trg_audit_event_no_update
        BEFORE UPDATE ON ComplianceAuditEvent
        BEGIN
            SELECT RAISE(ABORT, 'Compliance audit events are immutable');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_audit_event_no_delete
        BEFORE DELETE ON ComplianceAuditEvent
        BEGIN
            SELECT RAISE(ABORT, 'Compliance audit events are immutable');
        END;
        """
    )
    connection.commit()
