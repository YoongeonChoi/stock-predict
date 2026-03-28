# Stock Predict Design Bible

이 문서는 `Stock Predict`의 UI/UX 아키텍처 기준서입니다.
사람과 AI 에이전트 모두 이 문서를 기준으로 화면을 설계하고 수정합니다.

목표는 하나입니다.

- 화면마다 분위기와 정보 구조가 달라지는 일을 막는다.
- 투자 판단에 필요한 정보를 빠르게 읽히게 만든다.
- 새 기능이 붙어도 기존 화면과 같은 언어로 확장되게 만든다.
- 과장된 AI 데모처럼 보이지 않고, 실제로 오래 써도 피로하지 않은 워크스페이스를 만든다.

---

## 1. 제품 성격

이 제품은 `콘텐츠 사이트`가 아니라 `투자 워크스페이스`입니다.
또한 `AI 쇼케이스`가 아니라 `판단과 운영을 돕는 업무 도구`입니다.

따라서 UI는 아래 4가지를 동시에 만족해야 합니다.

1. 차분해야 한다.
2. 정보 밀도를 견딜 수 있어야 한다.
3. 행동으로 이어져야 한다.
4. 신뢰감을 잃지 않아야 한다.

한 줄 톤으로 정리하면 아래와 같습니다.

- `분석적`
- `절제된 자신감`
- `현대적`
- `장난스럽지 않음`
- `결정 지원형`

피해야 하는 방향도 분명합니다.

- 마케팅 랜딩 페이지처럼 과장된 히어로
- 카드마다 다른 규칙을 가진 “잡탕형” 대시보드
- 장식용 색이 많은 UI
- 설명용 히어로와 운영용 패널이 한 화면 상단에서 경쟁하는 UI
- 버튼이 너무 많아서 어디를 눌러야 할지 모르는 상태
- 차트/표/요약이 같은 중요도로 섞여 있는 화면
- 네온 포인트 색, 과도한 glow, 강한 gradient로 “AI스러운 분위기”를 억지로 만드는 화면
- 카드마다 다른 채도와 그림자를 써서 시선이 산만해지는 화면

### 1.1 시각 톤 원칙

이 제품의 시각 톤은 아래 문장으로 기억합니다.

- `중립적인 바탕 + 단일 포인트 색 + 명확한 정렬`

규칙:

- 배경과 surface는 중립색 위주로 설계합니다.
- 포인트 색은 CTA, active state, focus, 핵심 수치 강조에만 제한적으로 사용합니다.
- 같은 화면에서 브랜드 포인트 색이 여러 톤으로 난무하지 않게 합니다.
- 그림자는 존재감보다 계층 구분을 위해 씁니다.
- gradient는 기본 배경 언어가 아니라 예외적 강조 수단입니다.
- 아이콘, 배지, 칩은 설명 보조용이지 장식용이 아닙니다.

### 1.2 사람 기준 읽기 원칙

좋은 화면은 “센터에 멋있게 놓인 화면”이 아니라 “사람이 왼쪽 위부터 편하게 읽는 화면”입니다.

규칙:

- dense-data 페이지는 기본적으로 좌측 정렬을 우선합니다.
- 헤더, 카드 제목, 표, 필터의 시작선이 가능한 한 맞도록 설계합니다.
- 같은 row에 놓인 요소는 top edge와 baseline이 맞아야 합니다.
- 카드 높이를 억지로 맞추기보다, 읽기 순서와 정보의 무게를 먼저 맞춥니다.
- 한 화면에서 가장 중요한 시각적 강조점은 1개, 많아도 2개를 넘기지 않습니다.

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

- 좌측 상단 브랜드는 작은 wordmark 수준으로 유지한다
- 브랜드 영역에 소개 카피, 상태 칩, 마케팅 문구를 넣지 않는다
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

추가 원칙:

- 내비게이션 이름은 제약보다 작업을 드러내야 합니다.
- 시장 범위가 제한적이더라도 메뉴 이름 앞에 매번 `한국장` 같은 수식어를 붙이지 않습니다.
- 범위 정보는 페이지 설명, helper text, validation에서 전달합니다.

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

- 포트폴리오는 항상 `총자산 -> 보유 종목 -> 리스크/리밸런싱 -> 추천` 순서를 따른다
- 대시보드는 항상 `선택 시장 현황 -> 히트맵/모멘텀 -> 뉴스/셋업` 순서를 따른다
- 각 페이지의 가장 중요한 카드/패널은 상단 첫 screen에 와야 한다
- “읽고 판단하는 정보”가 “탐색용 부가 정보”보다 먼저 온다
- 공개 first screen은 가능하면 server-first로 `decision thread + audit thread`를 함께 채운다
- `/`, `/radar`, `/calendar`, `/archive`, `/screener`는 첫 screen에서 최소 한 개의 실제 수치 카드와 한 개의 freshness/audit 정보가 동시에 보여야 한다
- 공개 first screen에 `blank card`, `skeleton-only`, raw `Failed to fetch`를 그대로 두지 않는다

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
- 로그아웃 상태의 private page는 빈 인증 벽보다 `demo cards + CTA`를 먼저 보여 준다
- 데모는 public data 기반 설명형 미리보기만 사용하고, 가짜 수익률이나 허구의 보유 자산을 만들지 않는다

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
- audit strip은 가능한 한 `generated_at`, `partial`, `fallback_reason`의 같은 규칙으로 읽히게 한다
- 정상 상태는 `마지막 갱신 시각`, partial 상태는 `일부 데이터 지연`, stale-but-usable 상태는 `전일 기준`, `기관 동기화 중` 같은 보조 문구로 통일한다

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

- data-heavy page는 화면 폭을 적극 사용하되, 한 줄에 같은 무게의 dense panel을 2개 이상 두지 않는다
- 2열 레이아웃을 쓰더라도 한쪽은 핵심 패널, 다른 한쪽은 보조 패널이어야 한다
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

### 5.5 정렬 규칙

정렬은 단순 미감이 아니라 이해 속도에 직접 영향을 줍니다.

규칙:

- page header, 주요 action, 첫 번째 decision card는 같은 left edge를 공유합니다.
- dense table과 filter bar는 가능한 한 같은 폭과 같은 시작선을 사용합니다.
- 카드 안 요소는 가운데 정렬보다 좌측 정렬을 기본으로 합니다.
- 숫자 카드도 label, value, helper의 기준선이 흐트러지지 않게 합니다.
- 비어 있는 공간은 “의미 없는 여백”이 아니라 섹션 전환 리듬을 만드는 데 사용합니다.

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

추가 규칙:

- 색이 primary를 대신하지 않게 합니다. primary는 위치, 크기, 여백, 대비를 함께 써서 드러나야 합니다.
- 모든 버튼을 칩처럼 작게 만들지 않습니다. 중요한 액션은 눌러도 될 것처럼 보여야 합니다.

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
- 필드가 많은 폼은 `한 덩어리의 긴 표`처럼 보이게 두지 않고, 의미가 가까운 입력끼리 묶어 section처럼 보이게 한다
- 계정/인증 폼은 모바일에서 항상 한 열 기준으로 읽히고, 태블릿 이상에서만 2열 확장을 허용한다
- 아이디 중복 확인, 비밀번호 강도, 에러 안내처럼 즉시 피드백이 필요한 요소는 입력창 아래나 옆의 고정된 자리에서 반복적으로 보이게 한다
- 전화번호, 생년월일 같은 개인 입력은 helper text와 validation 상태를 함께 보여 주되 과도한 경고색 남발을 피한다

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

### 6.8 로딩과 fallback

이 제품은 외부 데이터 의존도가 높기 때문에 로딩과 실패 상태를 평소 디자인의 일부로 다룹니다.

규칙:

- skeleton은 “곧 데이터가 들어올 자리”를 설명해야 합니다.
- skeleton은 큰 빈 박스만 남기지 말고, 무엇을 불러오는 중인지 제목과 한 줄 설명으로 함께 보여 줍니다.
- 한 패널이 실패해도 페이지 전체를 막지 않습니다.
- fallback 문구는 짧고 담담하게 씁니다.
- `Failed to fetch` 같은 raw 브라우저 에러 문구를 그대로 노출하지 않습니다.
- 사용자에게 재시도 경로가 있으면 버튼이나 링크로 바로 제공합니다.
- `불러오는 중` 상태가 길어질 수 있는 패널은 timeout 뒤 fallback 또는 구조화된 에러 상태로 전환합니다.
- 공개 읽기 페이지는 클라이언트 재호출 전에 서버에서 최소 결과를 먼저 보여 주는 구성을 우선합니다.

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
- 범위 제약을 headline처럼 반복하지 말고, 필요한 곳에서만 설명
- `AI` 자체를 강조하기보다 근거, 데이터, 해석, 액션을 강조

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
- 모바일에서는 상단 고정 바와 drawer, form CTA가 서로 겹치지 않게 spacing을 확보한다
- 최신 iPhone / Galaxy 계열 세로 비율에서도 헤더, 입력 폼, sticky 요소가 viewport를 과도하게 차지하지 않게 한다
- 가로 스크롤이 불가피한 표는 wrapper 안에서만 스크롤되게 하고, 페이지 전체가 옆으로 밀리지 않게 한다

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

---

## 13. 색상 기준

주요 포인트 색상은 아래 값을 기본으로 사용합니다.

- `Accent`: `#2563EB`
- `Accent soft`: `#DBEAFE`
- `Surface base`: neutral gray scale
- `Success` / `Warning` / `Danger`는 의미 전달용으로만 사용

규칙:

- 주요 CTA, 활성 상태, 포커스 강조는 이 accent를 우선 사용한다
- 성과 의미 색상은 유지할 수 있지만, 브랜드 포인트 색은 accent로 통일한다
- 초록색 계열은 수익/상승 의미에만 제한적으로 사용하고 브랜드 포인트 색으로 쓰지 않는다
- 보라/청록/핑크를 동시에 쓰는 식의 다색 포인트 전략을 금지한다
- 카드 배경 자체를 accent tint로 넓게 칠하지 않는다. 필요하면 border, badge, number, button에서만 accent를 쓴다
- 현행 코드에 legacy accent가 남아 있더라도, 신규 UI 작업은 이 기준으로 수렴시킨다
