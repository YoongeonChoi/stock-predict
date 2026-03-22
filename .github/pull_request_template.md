## 요약

- 이 변경으로 무엇이 달라졌는지 적어주세요.

## 사용자 영향

- 사용자 화면, API, 다운로드, 예측 결과에 어떤 변화가 있는지 적어주세요.

## 검증

- [ ] `cd backend && & ..\venv\Scripts\python.exe -m compileall app`
- [ ] `cd backend && & ..\venv\Scripts\python.exe -m unittest discover -s tests -v`
- [ ] `cd frontend && npm run build`
- [ ] `cd frontend && npx tsc --noEmit`

## 변경 체크리스트

- [ ] 사용자에게 보이는 변경을 `README.md`에 반영했다
- [ ] 주요 변경 사항을 `CHANGELOG.md`에 반영했다
- [ ] 새로운 실패 경로가 있다면 `backend/app/errors.py`와 `README.md`의 에러 코드 표를 함께 갱신했다
- [ ] 릴리즈 버전을 변경해야 한다면 `backend/app/version.py`, `frontend/package.json`, `frontend/package-lock.json`을 함께 맞췄다
- [ ] 백엔드 응답 변경이 있다면 `frontend/src/lib/api.ts`와 관련 UI를 함께 수정했다
- [ ] 사용자 설명 문구를 한국어 중심으로 점검했다
- [ ] 테스트 또는 회귀 검증을 추가하거나 갱신했다

## 비고

- 제한 사항이나 후속 작업이 있으면 적어주세요.
