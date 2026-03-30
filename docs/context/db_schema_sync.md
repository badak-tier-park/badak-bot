# DB 스키마 참조 규칙

SQL 스키마는 별도 레포에서 관리된다. 코딩 시 아래 위치를 참조할 것.

## 스키마 위치

- GitHub: https://github.com/badak-tier-park/badak-schema/blob/main/schema.sql
- Raw: https://raw.githubusercontent.com/badak-tier-park/badak-schema/main/schema.sql

> `docs/sql/init.sql`은 삭제됨 (2026-03-30). 로컬 파일 대신 위 레포를 단일 소스로 사용.

## 테이블 목록 (2026-03-30 기준)

- `users` — discord_id, nickname, race (T/Z/P), tier, is_admin
- `change_requests` — type (nickname/race), old_value, new_value, status (pending/approved/rejected), message_id, channel_id
- `games` — discord_id, played_at, map_name, game_duration_seconds, winner/loser name/race/apm, replay_file

## 스키마 변경 시

스키마 변경이 필요한 경우 `badak-schema` 레포의 `schema.sql`을 수정해야 한다.

- 테이블 추가 / 삭제
- 컬럼 추가 / 삭제 / 타입 변경
- CHECK 제약 조건 변경
- 기본값(DEFAULT) 변경
