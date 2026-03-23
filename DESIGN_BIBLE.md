# Stock Predict Design Bible

이 문서는 `Stock Predict`의 UI/UX 아키텍처 기준서입니다.
사람과 AI 에이전트 모두 이 문서를 기준으로 화면을 설계하고 수정합니다.

목표는 하나입니다.

- 화면마다 분위기와 정보 구조가 달라지는 일을 막는다.
- 투자 판단에 필요한 정보를 빠르게 읽히게 만든다.
- 새 기능이 붙어도 기존 화면과 같은 언어로 확장되게 만든다.

---

## 1. 제품 성격

이 제품은 `콘텐츠 사이트`가 아니라 `투자 워크스페이스`입니다.

따라서 UI는 아래 4가지를 동시에 만족해야 합니다.

1. 차분해야 한다.
2. 정보 밀도를 견딜 수 있어야 한다.
3. 행동으로 이어져야 한다.
4. 신뢰감을 잃지 않아야 한다.

한 줄 톤으로 정리하면 아래와 같습니다.

- `분석적`
- `차분한 긴장감`
- `현대적`
- `장난스럽지 않음`
- `결정 지원형`

피해야 하는 방향도 분명합니다.

- 마케팅 랜딩 페이지처럼 과장된 히어로
- 카드마다 다른 규칙을 가진 “잡탕형” 대시보드
- 장식용 색이 많은 UI
- 버튼이 너무 많아서 어디를 눌러야 할지 모르는 상태
- 차트/표/요약이 같은 중요도로 섞여 있는 화면

---

## 2. 레퍼런스 베이스

이 프로젝트는 아래 공식 디자인 시스템을 참고하되, 그대로 복제하지 않고 `주식 분석 워크스페이스`에 맞게 조합합니다.

- Atlassian Design
  - 토큰, spacing, grid, layout primitives, navigation 구조 참고
  - [Foundations](https://atlassian.design/foundations/)
  - [Spacing](https://atlassian.design/foundations/spacing)
  - [Grid](https://atlassian.design/foundations/grid-beta/applying-grid)
- Shopify Polaris
  - 페이지 헤더와 액션 수 제한, aside 구조 참고
  - [Page](https://shopify.dev/docs/api/app-home/web-components/layout-and-structure/page)
- Primer
  - 버튼 우선순위, 버튼 라벨, 문장형 케이스, 아이콘 사용법 참고
  - [Button](https://primer.style/brand/components/Button/)
  - [Button accessibility](https://primer.style/product/components/button/accessibility/)
- Carbon
  - 데이터 테이블 구조, 툴바, 검색, dense-data 읽기 흐름 참고
  - [Data table usage](https://carbondesignsystem.com/components/data-table/usage/)

참고 원칙 요약:

- Atlassian처럼 `토큰과 grid를 먼저` 정한다.
- Shopify처럼 `페이지 헤더의 액션 수를 제한`한다.
- Primer처럼 `버튼 hierarchy를 강하게` 둔다.
- Carbon처럼 `표는 제목, 설명, 툴바, 본문`의 구조를 갖춘다.

---

## 3. 정보 구조 아키텍처

### 3.1 글로벌 메뉴 원칙

글로벌 메뉴는 `업무 흐름` 기준으로 나눕니다. 기능 이름만 모아두지 않습니다.

- `시장 탐색`
  - 대시보드
  - 기회 레이더
  - 스크리너
  - 비교
- `운영`
  - 포트폴리오
  - 관심종목
  - 캘린더
  - 아카이브
- `리서치`
  - 예측 연구실
  - 설정 및 시스템

규칙:

- 글로벌 메뉴 그룹은 최대 `3개`
- 그룹당 메뉴는 권장 `2~4개`, 최대 `5개`
- 각 메뉴에는 `한 줄 설명`이 붙어야 한다
- 글로벌 메뉴에 `상세 페이지`를 직접 넣지 않는다
- 상세 페이지는 breadcrumb, local tabs, in-page links로 연결한다

### 3.2 Thread 깊이 규칙

이 문서에서 `thread`는 사용자가 따라가는 탐색 흐름과 페이지 깊이를 뜻합니다.

- `Depth 0`: 글로벌 메뉴 그룹
- `Depth 1`: 글로벌 메뉴로 직접 접근하는 주요 작업 화면
- `Depth 2`: 주요 화면 안의 상세 흐름
  - 예: 국가 상세, 종목 상세, 섹터 상세
- `Depth 3`: 부가 흐름
  - 예: export hub, archive detail, 특정 설정 패널

규칙:

- `Depth 1`은 항상 글로벌 메뉴에서 접근 가능해야 한다
- `Depth 2`부터는 breadcrumb나 local action으로 진입한다
- `Depth 3`는 global nav에 넣지 않는다
- 한 화면에서 local tabs는 최대 `5개`
- 같은 목적의 정보는 탭보다 `section`으로 먼저 해결한다

### 3.3 탐색 우선순위

메뉴는 아래 질문에 답하는 순서로 설계합니다.

1. 지금 시장에서 뭐가 중요한가
2. 내 포트폴리오에서 뭘 해야 하는가
3. 이 판단이 실제로 맞고 있는가

즉, 메뉴와 페이지 흐름은 항상 아래 순서를 우선합니다.

- `탐색`
- `행동`
- `검증`

---

## 4. 페이지 아키텍처

모든 페이지는 아래 5개 thread로 설계합니다.

### 4.1 Header thread

화면의 목적과 액션을 가장 먼저 알려주는 영역입니다.

구성:

- eyebrow
- page title
- one-line or two-line description
- meta chips
- primary action 1개
- secondary actions 0~3개

규칙:

- 헤더만 보고도 이 화면의 목적이 드러나야 한다
- 액션은 header에 몰아넣지 않는다
- header에 들어가는 secondary action은 최대 `3개`
- 페이지 전체 primary action은 최대 `1개`

### 4.2 Decision thread

사용자가 가장 먼저 봐야 하는 추천, 상태, 결론입니다.

예:

- 내일의 이상적 포트폴리오
- 지금 가장 강한 셋업
- 포트폴리오 리스크 코치 요약
- 예측 적중률 핵심 요약

규칙:

- 각 페이지의 가장 중요한 카드/패널은 상단 첫 screen에 와야 한다
- “읽고 판단하는 정보”가 “탐색용 부가 정보”보다 먼저 온다

### 4.3 Evidence thread

결론을 뒷받침하는 차트, 테이블, 브레이크다운입니다.

예:

- 시장 스냅샷
- 차트
- 히트맵
- allocation table
- score breakdown

규칙:

- 근거는 결론 뒤에 온다
- 증거의 종류가 여러 개여도 시선 흐름은 유지해야 한다
- 차트와 표는 같은 카드 안에 과도하게 섞지 않는다

### 4.4 Action thread

사용자가 실제 입력하거나 조정하는 흐름입니다.

예:

- 보유 종목 추가
- 필터
- 국가 선택
- 레이더 시장 전환

규칙:

- action thread는 독립된 덩어리처럼 보여야 한다
- 입력 폼과 분석 결과는 시각적으로 분리한다
- 액션 버튼은 한 곳에서만 확실하게 강조한다

### 4.5 Audit thread

신뢰성, freshness, 시스템 상태, 가정, 리스크를 보여주는 영역입니다.

예:

- 마지막 갱신 시각
- fallback 상태
- 리스크 플래그
- 시스템 상태
- diagnostics

규칙:

- 투자 판단에 영향을 주는 신뢰성 정보는 숨기지 않는다
- audit 정보는 중요하지만, decision thread보다 먼저 오면 안 된다

---

## 5. 레이아웃 시스템

### 5.1 폭 규칙

- 워크스페이스 전체 최대폭: `1500px`
- 정보 밀도가 높은 페이지:
  - `fluid`에 가깝게 사용
  - 예: 포트폴리오, 레이더, 스크리너
- 읽기 중심 페이지:
  - 더 좁은 content band 허용
  - 예: 설정 설명, 문서형 패널

규칙:

- data-heavy page는 화면 폭을 적극 사용한다
- content-heavy page는 줄 길이를 제한한다
- 본문과 aside는 arbitrary width를 매번 새로 만들지 않는다

### 5.2 8px 스케일

간격은 `8px` 기준으로 설계합니다.

권장 단위:

- `4`
- `8`
- `12`
- `16`
- `24`
- `32`
- `40`
- `48`
- `64`

규칙:

- raw pixel 남발 금지
- spacing은 되도록 token 또는 공용 class로 해결한다
- 컴포넌트 간격과 페이지 간격을 섞지 않는다

### 5.3 카드 사용 규칙

카드는 이 프로젝트의 기본 surface입니다.

카드 타입:

- `summary card`
- `detail card`
- `table shell`
- `action card`
- `status card`

규칙:

- 카드마다 border, radius, shadow 규칙이 달라지면 안 된다
- 중요도는 크기와 위치로 나누고, 장식으로 나누지 않는다
- 카드 안에서만 또 다른 카드 체계를 새로 만들지 않는다

### 5.4 Aside 사용 규칙

aside는 선택 사항입니다. 항상 넣지 않습니다.

aside에 적합한 내용:

- 빠른 요약
- 상태
- 저장/실행 버튼
- audit 정보

aside에 부적합한 내용:

- 긴 표
- 주력 차트
- 상세 본문

---

## 6. 컴포넌트 바이블

### 6.1 버튼

버튼은 아래 4단계로 나눕니다.

- `Primary`
- `Secondary`
- `Subtle`
- `Danger`

규칙:

- 페이지 전체에서 primary는 `1개`가 원칙
- 한 버튼 그룹에 primary는 최대 `1개`
- destructive action은 danger로 분리
- disabled button은 남발하지 않는다
- 가능하면 enabled 상태로 두고 validation/message로 막는다
- 라벨은 `sentence case`
- 라벨 줄바꿈 금지
- 아이콘은 라벨 보조용이다
- dropdown, select, filter 같은 선택형 버튼만 trailing cue를 허용한다

라벨 규칙:

- 좋은 예
  - `포트폴리오 열기`
  - `보유 종목 추가`
  - `PDF 내보내기`
- 나쁜 예
  - `확인`
  - `실행`
  - `Submit`

### 6.2 메뉴

메뉴는 `경로 안내`와 `작업 전환` 역할을 합니다.

규칙:

- 메뉴는 명사형보다 `기능이 드러나는 이름`을 우선한다
- 그룹명은 작업 의미를 가져야 한다
- 메뉴 설명은 모바일에서 숨겨도 되지만 데스크톱에선 유지한다
- hover와 active 상태 차이는 명확해야 한다
- active는 색만이 아니라 배경/아이콘/텍스트 weight로도 구분한다

### 6.3 테이블

테이블은 dense-data의 핵심 컴포넌트입니다.

구성:

- title
- optional description
- toolbar
- body
- optional pagination

규칙:

- 테이블에는 제목이 있어야 한다
- 필요한 경우 설명으로 데이터 의미를 적는다
- search/filter/action은 toolbar에 모은다
- 숫자 컬럼은 우측 정렬
- 긴 컬럼명은 최대 2줄, 필요 시 tooltip
- 컬럼명은 1~2단어 위주
- 한 행에서 액션은 과도하게 늘리지 않는다
- 스캔성이 필요하면 zebra stripe 또는 hover state를 사용한다

### 6.4 검색과 필터

규칙:

- 글로벌 검색은 항상 상단 고정 영역에서 접근 가능해야 한다
- 필터는 결과와 가까운 곳에 둔다
- 검색 결과가 없을 때는 빈 상태 설명을 보여준다
- 키보드로 첫 결과 진입이 가능해야 한다

### 6.5 폼

규칙:

- 라벨은 입력창 위
- placeholder는 보조 용도일 뿐, 라벨 대체 금지
- helper text는 입력창 아래
- 필수 입력의 강조는 색만으로 처리하지 않는다
- 한 form에는 primary submit 1개만 둔다

### 6.6 칩과 배지

칩은 meta, state, filter, tag를 짧게 표현할 때 씁니다.

규칙:

- 칩은 설명을 보조하는 용도
- 중요한 결정은 칩으로만 전달하지 않는다
- 칩 색은 상태 semantics와 연결돼야 한다

### 6.7 빈 상태

빈 상태는 “데이터 없음”이 아니라 “다음 행동 안내”까지 포함합니다.

구성:

- 현재 상태 설명
- 왜 비어 있는지
- 다음 액션

---

## 7. 화면 타입별 템플릿

### 7.1 Dashboard

순서:

1. page header
2. decision thread
3. market snapshot
4. exploration shortcuts
5. evidence blocks

### 7.2 Analysis page

예:

- radar
- country
- stock

순서:

1. page header
2. top recommendation or regime
3. evidence cards
4. table/chart details
5. audit/fallback notes

### 7.3 Operations page

예:

- portfolio
- watchlist

순서:

1. page header
2. add/edit action thread
3. summary metrics
4. risk/model tables
5. secondary evidence

### 7.4 Research page

예:

- prediction lab
- diagnostics

순서:

1. page header
2. top metrics
3. breakdowns
4. logs or audit detail

---

## 8. 콘텐츠 규칙

### 8.1 언어

- 한국어 우선
- 티커, 고유명사, API 이름은 영어 유지 가능
- 의미 없는 영문 라벨 금지

### 8.2 문장 스타일

- 짧고 단정하게
- 문어체보다 운영형 문장
- 과장 금지
- “놀라운”, “강력한”, “혁신적” 같은 마케팅 형용사 지양

### 8.3 수치 표현

- 수치는 정렬과 단위를 함께 설계한다
- 통화는 국가 기준으로 자동 표기
- 퍼센트, 점수, 신뢰도는 시각 규칙을 고정한다

---

## 9. 접근성 및 인터랙션 규칙

- 키보드 focus ring을 지우지 않는다
- 버튼, 메뉴, 토글은 색만으로 상태를 구분하지 않는다
- target size는 작게 만들지 않는다
- hover 없는 환경에서도 의미가 유지돼야 한다
- skeleton, loading, empty, error 상태를 설계한다
- toast는 결과 피드백용, 핵심 의사결정 전달용이 아니다

---

## 10. 구현 규칙

프론트 수정 시 아래 순서를 지킵니다.

1. `AGENTS.md` 확인
2. `DESIGN_BIBLE.md` 확인
3. 기존 공용 primitives 재사용 가능 여부 확인
4. 새 primitive가 필요하면 공용화 먼저 검토
5. 문구는 한국어 우선으로 정리
6. 모바일과 데스크톱 둘 다 확인

현재 공용 기준 파일:

- `frontend/src/app/globals.css`
- `frontend/src/app/layout.tsx`
- `frontend/src/components/Navigation.tsx`
- `frontend/src/components/PageHeader.tsx`
- `frontend/src/components/SearchBar.tsx`

규칙:

- 새 페이지를 만들면 먼저 `PageHeader`와 공용 spacing 규칙에 맞춘다
- 새 카드 스타일을 만들기 전에 기존 `.card`, `.metric-card`, `.info-chip` 재사용을 검토한다
- 버튼 스타일을 페이지마다 따로 만들지 않는다
- 메뉴 구조를 바꾸면 이 문서와 `Navigation.tsx`를 함께 갱신한다

---

## 11. AI 에이전트 체크리스트

UI 작업 전에 아래를 스스로 체크합니다.

- 이 화면의 primary user question이 무엇인가
- decision thread가 evidence보다 먼저 오는가
- primary action이 하나로 보이는가
- global nav와 local thread가 충돌하지 않는가
- 카드, 표, 폼이 기존 규칙과 같은 tone을 가지는가
- 모바일에서 위계가 유지되는가
- fallback, freshness, risk를 숨기지 않았는가
- 새 규칙을 만들었다면 이 문서에 반영했는가

---

## 12. 이 프로젝트의 최종 기준 문장

`Stock Predict`의 UI는 “예쁜 대시보드”가 아니라
`빠르게 읽히고, 신뢰할 수 있고, 바로 행동할 수 있는 투자 워크스페이스`여야 합니다.
