-- QueueSmart: Service + Queue schema (MySQL)
-- Integrates with the existing Flask backend (services use UUID ids
-- to stay consistent with UserCredentials / queue_entries FKs).

-- ---------------------------------------------------------------------------
-- Service table
-- ---------------------------------------------------------------------------
-- Already exists as `services` in this project. Constraints enforced below
-- match the assignment: non-empty name, expected_duration (duration) > 0.

ALTER TABLE services
  MODIFY COLUMN name VARCHAR(100) NOT NULL,
  MODIFY COLUMN description TEXT NULL,
  MODIFY COLUMN duration INT NOT NULL,
  ADD COLUMN IF NOT EXISTS priority_level INT NOT NULL DEFAULT 0;

-- MySQL 8+ CHECK constraints
ALTER TABLE services
  ADD CONSTRAINT chk_services_name_not_empty CHECK (CHAR_LENGTH(TRIM(name)) > 0),
  ADD CONSTRAINT chk_services_duration_positive CHECK (duration > 0);

-- ---------------------------------------------------------------------------
-- Queue table (one managed queue per service; open / closed)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS queues (
  queue_id INT NOT NULL AUTO_INCREMENT,
  service_id VARCHAR(36) NOT NULL,
  status ENUM('open', 'closed') NOT NULL DEFAULT 'open',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (queue_id),
  CONSTRAINT fk_queues_service
    FOREIGN KEY (service_id) REFERENCES services (id)
    ON DELETE CASCADE,
  CONSTRAINT uq_queues_service UNIQUE (service_id)
);

-- Example seed (optional):
-- INSERT INTO services (id, name, description, duration, priority, priority_level, created_at, updated_at)
-- VALUES (UUID(), 'Advising', 'Academic advising walk-in', 15, 'medium', 1, NOW(), NOW());
