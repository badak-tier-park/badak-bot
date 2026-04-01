# 스타크래프트 종족 설정

종족은 T(테란), Z(저그), P(프로토스) 3가지만 있음. 랜덤(R) 없음.

종족 관련 코드, DB 제약, UI 선택지 모두 T/Z/P만 포함할 것.

---

# 환경 변수 및 배포 구성

## 로컬 개발

`.env` 파일은 **개발용 Supabase 프로젝트(`badak-dev`)** 를 바라보고 있다.

## 운영 배포

`main` 브랜치에 푸시되면 GitHub Actions(`deploy.yml`)가 자동 실행된다.  
EC2 접속 정보는 **GitHub Secrets** 으로 관리된다.

| Secret | 용도 |
|--------|------|
| `EC2_HOST` | EC2 서버 주소 |
| `EC2_USER` | SSH 접속 유저 |
| `EC2_KEY` | SSH 개인 키 |

운영 DB 연결 정보는 EC2 서버의 `/home/ubuntu/badak-bot/.env` 에 별도 보관되며, git에는 포함되지 않는다.
