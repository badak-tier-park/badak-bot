# DB 스키마 동기화 규칙

소스 작업 중 DB 스키마에 변경이 생기면 반드시 `docs/sql/init.sql`을 함께 갱신해야 한다.

## 해당되는 경우

- 테이블 추가 / 삭제
- 컬럼 추가 / 삭제 / 타입 변경
- CHECK 제약 조건 변경
- 기본값(DEFAULT) 변경

## 위치

`docs/sql/init.sql`
