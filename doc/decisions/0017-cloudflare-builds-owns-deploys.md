# 결정 0017 — 배포는 Cloudflare Workers Builds 가 갖는다

- 날짜: 2026-09-15
- 상태: **적용됨**
- 관련 결정: [결정 0002](0002-convert-in-browser.md),
  [결정 0010](0010-retire-the-server-conversion-path.md)

## 결론

배포하는 곳은 **Cloudflare Workers Builds** 한 곳이다. 대시보드에 연결한 저장소를
보고 `cf_build.sh` 로 짓고 `cf_deploy.sh` 로 올린다.

GitHub Actions 는 **검사만 한다.** 거기 있던 배포 잡(`deploy-staging`)을 지웠다.
조건(`vars.CLOUDFLARE_DEPLOY`)이 켜진 적이 없어 한 번도 돈 적 없는 길이었고,
두 경로를 함께 켜면 같은 Worker 에 두 번 배포되며 서로를 덮어쓴다.

```text
푸시 ─┬─ GitHub Actions : 검사 6잡 (배포하지 않는다)
      └─ Workers Builds : cf_build.sh → cf_deploy.sh → quotation
```

## 왜 이쪽인가

운영을 클라우드플레어에서 하고 있다. 배포만 GitHub 으로 떼어 놓으면 보는 곳이
둘로 갈리고, 저장소 비밀값·환경·브랜치 보호까지 새로 얽어야 한다. 지금 규모에서
그 값이 얻는 것보다 크다.

## 무엇을 잃는가 — 테스트가 배포를 막지 못한다

Workers Builds 는 푸시된 것을 그대로 짓고 **프로덕션**에 올린다. 검사 6잡이 붉어도
배포는 나간다. 이 저장소는 경계도 동일성도 테스트로 지키는데(결정 0009, 0012)
정작 사용자가 보는 것을 내보내는 길만 그 검사를 지나치지 않는다.

막는 방법은 하나다 — **`main` 브랜치 보호.** 검사 잡들을 필수 상태 검사로 걸고
직접 푸시를 막으면, 통과한 커밋만 `main` 에 들어오므로 Workers Builds 는 그것만
보게 된다. 이 설정 없이는 "푸시한 것이 곧 프로덕션"이다. 그 사실을 알고 쓴다.

## 토큰 — 사람에 매이지 않게

이 결정을 부른 사고가 그것이다. 조직을 떠난 사람의 빌드 토큰이 무효가 되면서
배포가 통째로 멈췄다.

```
Your build is configured with a build token that belongs to a user who has left
your organization. This token is no longer valid and cannot be managed by other
members.
```

빌드 토큰을 새로 만들 때 **계정 소유 토큰**으로 만든다. 같은 모양으로 다시 만들면
다음에 누가 나갈 때 또 멈춘다. 빌드 토큰(Settings → Build)과 `wrangler` 가 쓰는
API 토큰은 서로 다른 것이다.

## 바뀌지 않는 것

- 빌드·배포 **순서는 저장소가 갖는다** — `web/scripts/cf_build.sh`,
  `web/scripts/cf_deploy.sh`. 대시보드에는 그 두 줄만 넣는다. 설정과 코드가
  어긋나면 "여기서는 되는데 배포에서는 안 되는" 일이 생긴다.
- 올라가는 것은 정적 자산뿐이다. Worker 스크립트도 pywrangler 도 없다
  (결정 0002, 0010). CI 의 `bundle` 잡이 매 푸시마다 그것만은 확인한다.
- 데스크톱 EXE 담기(`fetch_desktop_app.sh`)도 그대로 `cf_build.sh` 안에 있다.
