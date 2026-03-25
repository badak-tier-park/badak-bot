-- -----------------------------------------------
-- badak-bot 초기 테이블 생성
-- -----------------------------------------------

CREATE TABLE IF NOT EXISTS users (
    id          BIGSERIAL    PRIMARY KEY,
    discord_id  BIGINT       UNIQUE NOT NULL,
    nickname    VARCHAR(50)  NOT NULL,
    race        VARCHAR(1)   NOT NULL CHECK (race IN ('T', 'Z', 'P')),
    tier        VARCHAR(5)   NOT NULL,
    created_at  TIMESTAMP    DEFAULT NOW(),
    updated_at  TIMESTAMP    DEFAULT NOW()
);
