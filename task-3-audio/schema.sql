

CREATE DATABASE IF NOT EXISTS consultbae
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE consultbae;

-- ---------------------------------------------------------------------
-- people — Task 1 clean/master table (deduped record per person)
-- If you already created this in Task 1's pipeline, this is a no-op
-- (IF NOT EXISTS) and won't touch your existing data.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS people (
    person_id           INT AUTO_INCREMENT PRIMARY KEY,
    full_name            VARCHAR(255) NOT NULL,
    canonical_phone       VARCHAR(20)  NULL,
    canonical_email        VARCHAR(255) NULL,
    city                  VARCHAR(100) NULL,
    source_flags           VARCHAR(255) NULL,
    skills                VARCHAR(500) NULL,
    experience_years        FLOAT        NULL,
    rate_or_ctc             VARCHAR(50)  NULL,
    status                VARCHAR(50)  NULL,
    verified              BOOLEAN      DEFAULT FALSE,
    projects_completed       INT          NULL,
    notes                 TEXT         NULL,
    created_at            TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_canonical_phone (canonical_phone)
);

-- ---------------------------------------------------------------------
-- submissions — Task 3 audio collection app
-- Same table backend.py's init_db() creates at runtime; kept here too
-- so the whole DB can be provisioned in one shot before first run.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS submissions (
    submission_id    INT AUTO_INCREMENT PRIMARY KEY,
    person_id        INT NULL,
    name             VARCHAR(255) NOT NULL,
    phone            VARCHAR(20)  NOT NULL,
    audio_path       VARCHAR(500) NOT NULL,
    duration_sec     FLOAT,
    sample_rate_hz   INT,
    bitrate_kbps     FLOAT,
    loudness_db      FLOAT,
    noise_estimate   VARCHAR(20),
    snr_db           FLOAT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (person_id) REFERENCES people(person_id)
        ON DELETE SET NULL
);
