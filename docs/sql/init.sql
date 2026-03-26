-- -----------------------------------------------
-- badak-bot 초기 테이블 생성
-- -----------------------------------------------

CREATE TABLE IF NOT EXISTS users (
    id          BIGSERIAL    PRIMARY KEY,
    discord_id  BIGINT       UNIQUE NOT NULL,
    nickname    VARCHAR(50)  NOT NULL,
    race        VARCHAR(1)   NOT NULL CHECK (race IN ('T', 'Z', 'P')),
    tier        VARCHAR(5)   NOT NULL,
    is_admin    BOOLEAN      DEFAULT FALSE,
    created_at  TIMESTAMP    DEFAULT NOW(),
    updated_at  TIMESTAMP    DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS change_requests (
    id          BIGSERIAL    PRIMARY KEY,
    type        VARCHAR(10)  NOT NULL CHECK (type IN ('nickname', 'race')),
    discord_id  BIGINT       NOT NULL,
    old_value   VARCHAR(50)  NOT NULL,
    new_value   VARCHAR(50)  NOT NULL,
    status      VARCHAR(10)  DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    message_id  BIGINT       UNIQUE,
    channel_id  BIGINT,
    created_at  TIMESTAMP    DEFAULT NOW()
);
