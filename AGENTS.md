# Agent Guide

이 문서는 이 저장소에서 작업하는 AI 에이전트를 위한 기본 규칙입니다. 범위는 저장소 전체입니다.

## 목표

- 기능 추가 속도보다 신뢰성과 일관성을 우선합니다.
- 사용자에게 보이는 변경은 코드, 문서, 버전, 에러 코드까지 함께 반영합니다.
- 프론트와 백엔드 계약이 어긋나지 않도록 항상 함께 확인합니다.

## 필수 규칙

1. 사용자에게 보이는 동작이 바뀌면 `README.md`를 업데이트합니다.
2. 새로운 실패 경로나 예외 응답을 추가하면 `backend/app/errors.py`에 에러 코드를 등록하고, `README.md`의 에러 코드 표도 함께 갱신합니다.
3. 릴리즈 가치가 있는 기능 추가나 예측 엔진 개선을 반영하면 다음 파일의 버전을 함께 점검합니다.
   - `backend/app/version.py`
   - `frontend/package.json`
   - `frontend/package-lock.json`
   - `CHANGELOG.md`
4. 백엔드 API 응답이나 스키마가 바뀌면 프론트 타입과 호출부를 함께 수정합니다.
   - `frontend/src/lib/api.ts`
   - 관련 페이지/컴포넌트
5. 예측 엔진을 수정하면 모델 버전과 설명도 함께 맞춥니다.
   - `backend/app/analysis/next_day_forecast.py`
   - `backend/app/models/forecast.py`
   - `backend/app/services/system_service.py`
   - `README.md`
   - `CHANGELOG.md`
   - 관련 회귀 테스트
6. 사용자 설명, 상세 패널, 운영 안내 문구는 한국어 우선으로 작성합니다.
   - 고유명사, 티커, API 이름처럼 영어가 더 명확한 부분은 유지해도 됩니다.
7. 다운로드, 내보내기, 파일 생성 흐름을 바꾸면 브라우저 fallback까지 같이 확인합니다.
   - 필요 시 CORS 헤더와 파일명 처리도 점검합니다.
8. 비즈니스 로직이나 API를 바꾸면 최소 1개 이상의 검증 코드를 추가하거나 기존 테스트를 갱신합니다.
9. 사용자가 만든 기존 변경 사항은 절대 되돌리지 않습니다. 예상치 못한 수정이 보이면 먼저 멈추고 확인합니다.
10. 프론트엔드나 UI/UX를 수정할 때는 반드시 `DESIGN_BIBLE.md`를 먼저 읽고, 그 안의 메뉴 구조, page thread, button hierarchy, table, spacing 규칙을 따릅니다.
11. 새로운 UI primitive나 시각 규칙을 추가했다면 `DESIGN_BIBLE.md` 또는 관련 공용 파일에 기준을 함께 반영합니다.

## 작업 순서

1. 변경 범위를 파악하고 기존 계약을 읽습니다.
2. UI 작업이면 `DESIGN_BIBLE.md`를 먼저 확인합니다.
3. 기능 코드를 수정합니다.
4. 아래 동기화 항목을 빠짐없이 반영합니다.
5. 테스트와 빌드를 실행합니다.
6. 최종 보고에서 변경 파일, 검증 결과, 남은 리스크를 설명합니다.

## 동기화 체크리스트

- [ ] 사용자 동작 변경이 `README.md`에 반영되었는가
- [ ] 새 에러 코드가 `backend/app/errors.py`와 `README.md`에 반영되었는가
- [ ] 릴리즈 버전이 백엔드/프론트/체인지로그에 동기화되었는가
- [ ] 백엔드 응답 변경이 프론트 타입과 UI에 반영되었는가
- [ ] 한국어 사용자 문구가 자연스럽게 정리되었는가
- [ ] UI 변경이 `DESIGN_BIBLE.md`와 일관된가
- [ ] 테스트 또는 회귀 검증이 추가되었는가
- [ ] 아래 검증 명령을 실행했는가

## 기본 검증 명령

가장 먼저 아래 원클릭 검증을 권장합니다.

```powershell
.\verify.ps1
```

프론트 수정이 없거나 백엔드만 빠르게 볼 때는 아래처럼 실행합니다.

```powershell
.\verify.ps1 -SkipFrontend
```

### Backend

```powershell
cd backend
& ..\venv\Scripts\python.exe -m compileall app
& ..\venv\Scripts\python.exe -m unittest discover -s tests -v
```

### Frontend

```powershell
cd frontend
npm run build
npx tsc --noEmit
```

## Git 주의사항

- 파괴적인 git 명령은 사용하지 않습니다.
- 사용자가 요청하지 않은 리셋, 강제 체크아웃, 히스토리 재작성은 금지합니다.
- 커밋 메시지는 기능 범위가 드러나게 작성합니다.
- 브랜치 머지는 fast-forward로 처리하지 않고 항상 명시적 merge commit을 남깁니다.
- 머지 시 기본 원칙은 `git merge --no-ff <branch>` 이며, 가능하면 `Merge branch '<branch>'` 형태의 메시지를 사용합니다.
