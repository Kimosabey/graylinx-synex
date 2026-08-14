-- Q42. The back end must not connect to the plant as root.
--
-- Measured on 2026-08-13: the sibling connects as `root` holding SUPER, DROP, FILE and
-- GRANT OPTION on *.* — and all three databases share the server, so those credentials reach
-- `shiva`, the customer's snapshot. The SQL validator in front of generated queries is
-- genuinely thorough (AST class check, a token deny-list blocking the file-write forms, a
-- table allow-list), so there is no live vulnerability. The objection is structural: that is
-- one application-layer guard in front of a credential that can drop the snapshot.
--
-- These two statements turn "Synex never writes to the plant" from a promise in a document
-- into a property of the database.
--
-- Run as an administrator, once:
--     mysql -h 127.0.0.1 -P 3307 -u root -p < 01-mysql-grants.sql

CREATE USER IF NOT EXISTS 'synex_plant_ro'@'%' IDENTIFIED BY 'CHANGE_ME';

-- SELECT only, on our own clone only. No grant on shiva, none on graylinx_v2, none on *.*
GRANT SELECT ON `graylinx_synex`.* TO 'synex_plant_ro'@'%';

FLUSH PRIVILEGES;

-- Verify:
--     SHOW GRANTS FOR 'synex_plant_ro'@'%';
-- Expect exactly two lines: USAGE ON *.*, and SELECT ON `graylinx_synex`.*
