# 바닥티어 디스코드 봇 (badak-bot) — Claude 작업 지침

바닥티어 디스코드 서버의 봇(Python, discord.py). 사용자 등록(`/유저등록`), 경기 등록, 일정, 대기열 등.
**이 문서에는 코드에서 확인할 수 없는 내용만 적는다.**

## 놓치면 버그가 되는 것
- **봇은 DB에 직접 접속한다(asyncpg). Supabase RLS가 적용되지 않는다.** 권한 확인은 봇 코드(디스코드
  `운영진` 역할·명령어 권한 설정, `DISCORD.md`)에서만 이뤄진다 — 명령을 추가할 때 권한을 빼먹으면 누구나 실행된다
- `users`는 웹(badak-web)의 로그인 판정 기준이다. 웹은 여기서 등록된 `discord_id`만 들여보내고 `is_admin`으로
  관리자를 가른다. 컬럼 의미를 바꾸면 웹 로그인이 깨진다
- `games.map_name`은 웹에서 `maps.name`/`aliases`와 **텍스트로** 매칭된다. 맵 이름을 임의로 만들어 넣지 않는다
- 종족은 T(테란), Z(저그), P(프로토스) 3가지만. 랜덤(R) 없음 — 코드, DB 제약, UI 선택지 모두 T/Z/P만

## 조직 저장소 지도
바닥티어는 저장소 여러 개가 **같은 Supabase 프로젝트를 함께 쓴다**(운영 `badak`, 개발 `badak-dev`).
한 저장소에서 테이블·정책을 바꾸면 다른 저장소가 깨질 수 있으니, DB를 건드릴 땐 아래 사용처를 먼저 본다.
공개 저장소이므로 project ID는 문서에 쓰지 않고 Supabase MCP의 `list_projects`로 조회한다.

| 저장소 | 역할 | 배포 | DB와의 관계 |
|--------|------|------|-------------|
| `badak-web` | 웹앱(리그·팀배틀·토너먼트·대시보드·관리) | Vercel (`main`=운영) | 대부분의 테이블을 읽고 쓴다 |
| `badak-bot` | 디스코드 봇(`/유저등록` 등) | EC2 (`main` 푸시 시) | `users` 등록 — 웹은 여기 등록된 사용자만 로그인 가능 |
| `gg-tracker` | 리플레이 감시 데스크톱 앱(Go) | GitHub Release (`main` 푸시 시) | `record-game` 함수로 `games`에 전적 기록 |
| `badak-tier-park-api` | Supabase Edge Functions | `supabase functions deploy` | `record-game`·`get-games`(gg-tracker), `notify-entry`(웹의 엔트리 제출 → 디스코드) |
| `.github` | 조직 프로필·공통 이슈/PR 템플릿 | — | — |

로컬에서는 `~/dev/badak-tier-park/<저장소>`에 나란히 둔다.

## 환경 변수 및 배포 구성

### 로컬 개발

`.env` 파일은 **개발용 Supabase 프로젝트(`badak-dev`)** 를 바라보고 있다.

### 운영 배포

`main` 브랜치에 푸시되면 GitHub Actions(`deploy.yml`)가 자동 실행된다.  
EC2 접속 정보는 **GitHub Secrets** 으로 관리된다.

| Secret | 용도 |
|--------|------|
| `EC2_HOST` | EC2 서버 주소 |
| `EC2_USER` | SSH 접속 유저 |
| `EC2_KEY` | SSH 개인 키 |

운영 DB 연결 정보는 EC2 서버의 `/home/ubuntu/badak-bot/.env` 에 별도 보관되며, git에는 포함되지 않는다.

## 커밋 전 검증
테스트는 없다. 최소한 문법 검사가 통과해야 커밋한다:
```
python3 -m compileall -q bot.py cogs config.py database.py logger.py
```
명령·권한을 바꿨다면 개발 서버(`badak-dev`를 바라보는 로컬 `.env`)에서 실제로 실행해 확인한다.

## GitHub 작업 규칙
조직 공통 규칙의 원본은 `badak-web/CLAUDE.md`의 "Git" 섹션이다. 이 저장소에 해당하는 것만 추린다.

- 브랜치: `feat/`·`fix/`·`refactor/`·`style/`·`docs/`·`chore/` → `dev`로 PR → 모아서 `dev` → `main` 배포 PR.
  **`main` 병합 = 운영 배포**이므로 작업 PR을 `main`으로 열지 않는다
- PR 제목은 커밋과 같은 형식(`feat: …`). 템플릿은 조직 공통(`badak-tier-park/.github`)
- Assignees = 작성자, Reviewers = 작성자 외 쓰기 권한자 전원
  (`gh api repos/badak-tier-park/<저장소>/collaborators --jq '.[].login'`), 종류 Labels,
  관련 이슈는 본문 `Closes #n`. 이 저장소에는 badak-web 같은 PR 자동 설정 워크플로가 없어 직접 채운다
- 보호 규칙: `dev`·`main` 모두 승인 1명 필요, 삭제·강제 푸시 금지

- Projects: 조직 프로젝트 `badak-bot`(#1)
  (`gh project item-add 1 --owner badak-tier-park --url <PR/이슈 URL>`)

---

## 전역 개발 규칙 (사용자 전역 CLAUDE.md 복사본)
`~/.claude/CLAUDE.md`는 특정 PC에만 있어 다른 기기에서는 보이지 않으므로 여기에 복사해 둔다.
프로젝트에 국한되지 않는 새 규칙이 생기면 여기와 전역 파일 **양쪽에** 반영한다.
위 프로젝트 규칙과 겹치면 위(프로젝트) 서술이 우선한다.

### 커밋 컨벤션
**Conventional Commits**: `<type>(<scope>): <subject>` — scope는 선택.
- type: `feat` · `fix` · `docs` · `test` · `refactor` · `chore` · `style` · `perf`
- subject는 명령형 한 줄, 끝에 마침표 없음
- 본문은 "무엇"이 아니라 **"왜"**를 설명할 때만 쓴다

### 커밋 전 검증
typecheck·lint·test가 통과하는 상태에서 커밋한다. 명령은 프로젝트마다 다르니
CLAUDE.md·package.json scripts·CI에서 확인한다(이 저장소의 명령은 위 "커밋 전 검증").

### 이슈 정리
이슈를 닫기 전에 하위 이슈(sub-issue) 상태를 확인한다. 하위가 하나라도 열려 있으면
상위는 닫지 않는다. 해결 근거를 코드·커밋에서 확인하지 못한 이슈는 닫지 말고 사용자에게 묻는다.

### PR 작성
- Assignees에 작성자, Reviewers에 작성자를 뺀 팀원 전원, 종류·영역 Labels, 관련 이슈는 본문 `Closes #n`으로
  Development에 연결, 프로젝트를 쓰면 Projects에도 넣는다. 저장소에 자동화가 있어도 `gh pr create`로
  직접 올릴 때는 `--assignee @me --reviewer … --label …`로 채운다(자동화가 안 도는 경우가 있다)
- PR 템플릿이 있으면 그 섹션 구조를 따른다. 하지 않은 테스트는 체크하지 않고, 확인하지 못한 것은 적는다

### 문서 계층
- 루트 CLAUDE.md는 매 세션 로드되므로 전역 규칙과 "놓치면 버그가 되는" 요약만 둔다
- 기능별 상세는 그 디렉토리의 CLAUDE.md에 두고, 루트에 **문서 지도**로 위치를 적는다
- 하위 문서는 그 디렉토리 파일을 열 때만 로드된다 — 다른 디렉토리에서 그 기능을 건드릴 땐
  직접 읽어야 하므로 루트에 요약과 경로를 남긴다
- 코드·git 이력으로 알 수 있는 것은 적지 않는다. 코드로 알 수 없는 "왜"와 도메인 룰만 적는다
