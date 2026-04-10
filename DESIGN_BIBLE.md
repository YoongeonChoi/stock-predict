# Stock Predict Design Bible

이 문서는 `Stock Predict`의 프론트엔드 시각 규칙과 정보 구조 규칙을 정의하는 기준 문서입니다.
모든 UI 작업은 이 문서를 먼저 읽고, 여기서 정한 원칙을 공용 primitive와 실제 화면에 함께 반영합니다.

## 1. 제품 성격

`Stock Predict`는 홍보용 랜딩 페이지가 아니라 `시장 탐색, 종목 해석, 포트폴리오 운영, 예측 검증`을 한 흐름으로 묶는 작업형 워크스페이스입니다.

디자인의 목표는 세 가지입니다.

- 덜 지저분하게 보일 것
- 긴 한국어 문장과 숫자가 쉽게 읽힐 것
- 사용자가 지금 무엇을 봐야 하고 무엇을 눌러야 하는지 바로 이해할 것

우리가 지향하는 톤은 아래 문장으로 요약합니다.

- `브루탈한 구조감 + 절제된 타이포 + 한정된 포인트 컬러`

즉, 장식적인 글래스 UI가 아니라 `강한 면 분할`, `건조한 정보 정렬`, `작은 수의 시각 규칙`으로 질서를 만드는 방향입니다.

## 2. Visual Thesis

### 2.1 핵심 문장

- `Less is more`
- `한 블록 = 한 visible frame`
- `강조는 색보다 구조와 타이포로 만든다`

### 2.2 컬러

- 기준 테마는 `light mode`
- 기본 축은 `off-white / ink / cobalt blue`
- 다크 모드는 라이트 구조를 유지한 파생형으로만 만든다
- 상태색은 `warning / danger / positive`처럼 의미가 필요한 경우에만 보조적으로 사용한다

규칙:

- 한 화면의 강한 포인트 컬러는 기본적으로 1개만 쓴다
- routine UI에 장식용 gradient를 깔지 않는다
- 배경은 정보 전달을 방해하지 않는 평평한 면으로 유지한다

### 2.3 타이포

- 본문과 제목은 `IBM Plex Sans KR`
- 숫자, 티커, 시간, 버전, 감사 정보는 `IBM Plex Mono`

규칙:

- 제목은 구조를 세우는 용도, 본문은 설명 용도, mono는 정렬과 비교 용도로 역할을 분리한다
- uppercase eyebrow는 꼭 필요한 섹션에만 쓴다
- 긴 한국어 문장을 좁은 캡슐 안에 넣지 않는다
- line-height와 max-width를 먼저 조정하고, 그다음 프레임을 고민한다

### 2.4 Radius / Shadow / Border

- radius 기본값은 `8 / 12 / 14px`
- shadow는 아주 약하게만 쓴다
- 깊이감은 shadow보다 `spacing + contrast + typography`로 만든다

보더 규칙:

- 모든 블록에 보더를 기본 적용하지 않는다
- 아래 경우에만 보더를 허용한다
  - 입력 필드
  - 표와 차트 프레임
  - 경고/실패 상태
  - 실제 섹션 경계가 필요한 slab

금지:

- 카드 안 카드
- 카드 안 bordered list
- 카드 안 bordered metric
- 긴 문장을 담는 rounded pill
- glass panel 안에 또 glass panel

## 3. Primitive System

페이지는 임의 Tailwind 조합이 아니라 아래 semantic primitive를 기준으로 만든다.

### 3.1 Page Shell

- 화면 전체 리듬을 담당한다
- 페이지 최대 폭, 기본 세로 간격, top rhythm을 통일한다

### 3.2 Section Slab

- 큰 정보 덩어리를 담는 기본 단위
- 한 섹션은 한 slab를 기본으로 한다
- 섹션 내부는 heading, copy, metric strip, list, data frame으로 나눈다

원칙:

- slab 하나 안에서 너무 많은 내부 프레임을 만들지 않는다
- 섹션을 쪼개기 전에 텍스트 계층으로 해결한다

### 3.3 Metric Strip

- 숫자 요약, 작은 상태 요약 전용
- 짧은 라벨 + 큰 숫자 + 짧은 보조 설명 구조를 유지한다
- 카드처럼 보이기보다 조밀한 읽기 리듬을 제공해야 한다

### 3.4 Status Token

- 아주 짧은 상태만 담는다
- 예: `partial`, `오늘`, `한국`, `high`, `warning`

금지:

- 문장형 설명
- 운영 안내
- helper text
- 긴 날짜 범위나 설명 문구

### 3.5 Action Button

- 계층은 `primary / secondary / text` 세 단계만 쓴다
- 같은 row에서 primary는 1개만 강하게 보인다
- 실행 버튼과 상태 선택 토글을 섞지 않는다
- chip 계열은 `filter / segment / range / mode`처럼 상태를 고르는 토글에만 쓴다
- 페이지 이동, 저장, 삭제, 새로고침, 다운로드처럼 결과를 발생시키는 CTA는 button primitive를 사용한다

### 3.6 Field Shell

- 검색창, 입력창, 드롭다운, 텍스트 영역에 공통으로 쓴다
- 입력 계열은 시각 장식보다 label, helper, focus-visible을 우선한다

### 3.7 Data Frame

- 표, 차트, 코드형 데이터, dense list 전용 프레임
- 설명 카피와 데이터 프레임을 같은 박스 안에서 경쟁시키지 않는다

## 4. Layout Rules

### 4.1 한 블록 = 한 visible frame

이 문서의 가장 중요한 규칙입니다.

- 하나의 정보 블록은 화면에서 하나의 프레임만 가진다
- 프레임이 이미 있다면, 내부 정보는 타이포와 spacing으로 구분한다
- 또 다른 박스를 만들기 전에 정말 구조적 경계가 필요한지 먼저 확인한다

### 4.2 페이지 thread

모든 주요 화면은 아래 thread를 기본으로 한다.

1. `header`
2. `decision`
3. `evidence`
4. `action`

이 순서는 유지하되, thread마다 카드 하나씩 기계적으로 배정하지 않는다.

좋은 예:

- 큰 slab 안에서 `핵심 결론 -> 보조 설명 -> 관련 숫자`를 한 덩어리로 보여주는 화면

나쁜 예:

- 같은 의미의 정보를 카드 세 개로 쪼개고, 각 카드 안에 또 chip과 inner box를 넣는 화면

### 4.3 정렬

- 같은 row의 제목, 숫자, 보조문구는 baseline을 의식해 맞춘다
- 대칭보다 읽기 쉬운 정렬을 우선한다
- box height를 억지로 맞추기보다 정보 밀도와 제목 줄 수를 먼저 정리한다

## 5. Header / Navigation / Search

### 5.1 Page Header

페이지 헤더는 `큰 glass 카드`가 아니라 `타이포 중심 editorial header`로 구성한다.

기본 구성:

- eyebrow
- title
- 1~2줄 설명
- meta 1줄
- primary action 1개

규칙:

- meta는 짧은 상태 위주로만 둔다
- 설명문을 chip 여러 개로 나누지 않는다
- 모바일 first viewport에서 헤더가 콘텐츠를 과점유하지 않게 한다

### 5.2 Global Navigation

- 카드형 메뉴를 기본으로 하지 않는다
- 더 건조한 rail/list 구조를 사용한다
- 데스크톱 rail은 slim 폭을 유지하고, 브랜드 설명은 본문을 잠식하지 않을 정도로만 압축한다
- 그룹은 최대 3개
- 그룹당 메뉴는 보통 2~5개

메뉴 구조:

- 시장 탐색
  - 대시보드
  - 기회 레이더
  - 스크리너
  - 비교
- 운영
  - 포트폴리오
  - 관심종목
  - 캘린더
  - 아카이브
- 리서치
  - 예측 연구실
  - 설정

### 5.3 Search Bar

- flat brutal field를 기본으로 한다
- helper pill, inner card, decorative capsule을 넣지 않는다
- 결과 목록은 얇은 구분선과 정렬로 처리한다

## 6. Text Rules

### 6.1 Copy Style

- 한국어 우선
- 운영형 문장 우선
- 마케팅 문구 금지
- headline보다 utility copy가 더 중요할 때는 utility copy를 택한다

좋은 예:

- `최근 갱신`, `부분 응답`, `실측 평가 대기`, `선택한 날짜 일정`

피할 예:

- `혁신적인 분석`
- `AI가 자동으로 해결`
- `놀라운 인사이트`

### 6.2 긴 문장 처리

- 긴 문장을 pill 안에 넣지 않는다
- 경고/운영 안내는 제목, 이유, 다음 행동 구조로 분리한다
- 본문은 line-height를 확보하고 폭을 제어한다

## 7. Tables, Charts, Metrics

### 7.1 Table

- dense한 정보는 표로 정리한다
- 표 바깥 설명과 표 안 메타 정보를 중복하지 않는다
- 숫자열은 mono + right align을 기본으로 한다
- 모바일에서는 dense table을 바로 강요하지 않고, 핵심 수치 요약 카드나 summary block을 먼저 보여준 뒤 `md` 이상에서 표 상세를 확장한다
- 모바일에서 표 자체가 필요하면 viewport 전체 스크롤이 아니라 table frame 내부 스크롤만 허용한다

### 7.2 Chart

- 차트는 프레임을 허용한다
- 차트 주변 필터와 설명을 또 다른 카드에 나누지 않는다
- 범례와 컨트롤은 짧게 유지한다

### 7.3 Metric

- 숫자가 주인공인 영역은 타이포를 먼저 키운다
- 숫자마다 box를 두 겹으로 두지 않는다
- 4개 이상 metric이 모이면 strip/grid로 처리한다

## 8. State System

상태 표현은 아래 네 가지를 기준으로 통일한다.

- `loading skeleton`
- `partial warning`
- `empty guidance`
- `blocking failure`

구조:

- 제목
- 이유
- 다음 행동

규칙:

- raw error message를 먼저 던지지 않는다
- 사용자가 지금 볼 수 있는 것과 없는 것을 같이 설명한다
- retry는 있을 때만 primary action으로 준다

## 9. Mobile Rules

모바일에서는 시각 규칙을 더 강하게 적용한다.

- 상단 chrome은 single-plane처럼 보이게 한다
- 첫 viewport에서 header + search + account가 콘텐츠를 밀어내지 않게 한다
- box보다 텍스트 흐름을 우선한다
- pill 남발을 금지한다
- 한 row의 action 개수는 가능한 한 줄인다
- dense action row는 모바일에서 full-width stack이나 1열 흐름으로 먼저 정리하고, 좁은 화면에서 버튼 여러 개를 억지로 한 줄에 우겨 넣지 않는다
- helper text, pending email, 상태 설명은 잘림보다 자연스러운 줄바꿈을 우선한다
- audit/status chip과 metric value는 긴 티커, 경로, stale 메타가 들어와도 `max-width + wrap`으로 먼저 수용한다
- state card와 warning banner의 액션은 모바일에서 내용 오른쪽에 억지로 붙이지 않고, 본문 아래 stack으로 내려 읽기 순서를 유지한다

모바일 성공 기준:

- first screen에서 boxed clutter가 보이지 않을 것
- 긴 한국어 문장이 박스 밖으로 튀어나오지 않을 것
- 숫자와 보조문구가 줄바꿈돼도 리듬이 유지될 것

## 10. Route Notes

### `/`

- 한 화면의 핵심 결론은 1개
- 요약, 감사 정보, 오늘의 포커스를 먼저 본다
- 카드 모자이크보다 큰 slab 2~3개 구조를 우선한다

### `/radar`

- 숫자보다 지금 usable한 후보와 상태 설명이 먼저 보인다
- partial 상태에서도 0/0/0 카드보다 운영형 설명을 우선한다

### `/calendar`

- `월 제목 -> 월 이동 -> 범례 -> 월간 보드 -> 선택 날짜 agenda`
- 날짜 셀은 `날짜 번호 + 점/건수 + 선택 강조`
- 일정 상세는 아래 agenda에서 읽는다

### `/lab`

- `표본 수집 퍼널 -> horizon 커버리지 -> 막히는 지점 -> 검증 workspace`
- 성과 카드보다 파이프라인 상태를 먼저 보여준다

### `/stock/[ticker]`

- 종목 헤더, 요약, 차트, 실행 정보가 box soup처럼 보이지 않게 한다
- confidence note, data quality, summary bullets를 같은 리듬 안에서 읽히게 정리한다
- 모바일에서는 고정 폭 보조 패널을 두지 않고, 차트/재무는 summary-first 흐름으로 재배치한다

### `/auth`, `/settings`

- 폼은 border보다 label, helper, input rhythm이 중요하다
- 경고문과 상태문을 capsule로 감싸지 않는다
- 입력과 액션의 계층을 명확하게 나눈다

## 11. Do / Don't

### Do

- 큰 제목과 짧은 보조 설명으로 구조를 세운다
- 숫자와 텍스트의 역할을 분리한다
- 한 섹션에 한 가지 메시지만 강조한다
- chip을 정말 짧은 상태에만 쓴다
- border 대신 spacing과 contrast를 먼저 조정한다

### Don't

- 모든 블록에 border를 준다
- 긴 문장을 pill 안에 넣는다
- 카드 안에 카드 안에 카드를 넣는다
- 같은 의미를 chip, caption, box로 세 번 반복한다
- 모바일 화면에서 헤더와 메타를 박스 여러 개로 분절한다

## 12. Release Rule

새 UI primitive, 시각 규칙, header 규칙, 상태 카드 규칙을 추가하거나 바꿨다면 아래를 같이 맞춘다.

- 공용 CSS / component primitive
- 관련 페이지
- `README.md`
- `CHANGELOG.md`
- 이 문서

이 문서는 참고 문서가 아니라 현재 구현과 함께 움직이는 canonical spec이다.
