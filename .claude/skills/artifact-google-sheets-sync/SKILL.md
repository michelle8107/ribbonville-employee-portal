---
name: artifact-google-sheets-sync
description: Build a browser-only Claude Artifact tool (e.g. a data-reconciliation or upload UI) that needs its results to accumulate into a specific Google Sheet over time. Use when the natural approach ("just fetch/write the Sheet from the page") won't work because Artifacts can't call external URLs, and Drive-connector tools can create files but cannot edit the content of an existing one.
---

# Artifact → Google Sheets 동기화 (Apps Script 릴레이 패턴)

"증빙 크로스체크" (마이크래프트/엠와이피 재무 대사 도구)를 만들면서 겪은 시행착오 정리.
브라우저에서만 도는 Claude Artifact의 결과를 사용자의 실제 구글시트에 누적 저장하고 싶을 때 재사용.

## 왜 "그냥 연동"이 안 되는가

1. **Artifact 페이지는 CSP로 외부 요청이 막혀 있다.** `fetch`/`XHR`이 되는 곳은 Google Fonts뿐이다.
   시트 링크를 붙여넣게 해도 브라우저 쪽 JS가 `docs.google.com`에 요청을 못 보낸다.
2. **Google Drive MCP 커넥터에는 "기존 파일 내용 수정" 도구가 없다.** `create_file`(신규 생성)과
   `update_file`(제목/위치 변경만)만 있고, 이미 있는 스프레드시트에 행을 추가/수정하는 기능 자체가 없다.
   Sheets API(`spreadsheets.values.append` 등)를 쓰는 별도 커넥터가 없다면 이 경로는 막혀 있다고 보면 된다.
3. 따라서 "링크만 주면 자동으로 계속 반영"은 불가능하고, 현실적인 선택지는 아래 두 가지뿐이다.
   - **A. 이 스킬의 방법 (Apps Script 릴레이)** — 설정은 한 번, 이후엔 Claude가 대화 중에 릴레이
   - **B. 완전 수동** — 매번 CSV 내려받아 사용자가 직접 시트에 붙여넣기

## 방법 A: Apps Script 웹앱을 다리로 쓰기

### 구조
```
Artifact(브라우저, CSP로 외부요청 불가)
   → "동기화용 JSON 저장" 버튼으로 downloads capability 사용해 로컬 파일로 내려받음
   → 사용자가 파일 경로를 Claude(대화창)에 알려줌
   → Claude가 Bash/curl로 그 JSON을 Apps Script 웹앱 URL에 POST
   → Apps Script가 스프레드시트에 실제로 씀 (여긴 Google 앱스 스크립트 런타임이라 시트 직접 조작 가능)
```
핵심: **Claude Code의 Bash 도구는 실제 인터넷에 나갈 수 있다** (curl로 외부 API 호출 가능).
Artifact만 못 나가는 것이지 Claude 자체는 문제없다. 그래서 "브라우저(막힘) → Claude(뚫림) → Apps Script(시트 직접 조작)"
3단 릴레이가 성립한다.

### Apps Script 웹앱 배포 (사용자가 1회 진행)
1. 대상 스프레드시트 → 확장 프로그램 → Apps Script
2. `doPost(e)` / `doGet(e)`가 있는 코드 작성 (토큰 검사 후 데이터 반영)
3. 배포 → 새 배포 → 유형: 웹 앱, 실행: 나, 액세스: 전체 허용 → URL 확보
4. **코드를 수정한 뒤에는 "저장"만으로는 배포된 웹앱에 반영 안 됨.** 배포 관리 → 연필 아이콘 →
   "새 버전"으로 다시 배포해야 실제 `/exec` URL이 최신 코드로 바뀐다. (이걸 안 해서 옛날 코드가
   계속 응답하는 삽질을 함 — 매번 `doGet`으로 살아있는지, 응답 내용이 최신 로직인지 확인할 것)
5. "새 배포"를 누르면 완전히 다른 URL이 생긴다. 기존 URL을 유지하려면 반드시
   "배포 관리 → 기존 배포 편집 → 새 버전"이어야 한다.

### curl로 호출할 때 반드시 걸리는 함정: 302 리다이렉트
`script.google.com/.../exec`는 실행 결과를 바로 안 주고 `script.googleusercontent.com/macros/echo?...`로
302 리다이렉트한다.
- `curl -L`로 리다이렉트를 자동으로 따라가면, **POST가 GET으로 바뀌면서 예전 Content-Length 헤더가
  같이 남아** `411 Length Required` 에러가 난다.
- 해결: 리다이렉트를 자동으로 따라가지 말고 **두 단계로 분리**한다.
```bash
RESP=$(curl -sS -D - -o /dev/null -X POST "$URL" \
  -H "Content-Type: text/plain;charset=utf-8" \
  --data-binary @payload.json)
LOC=$(echo "$RESP" | grep -i '^Location:' | sed 's/Location: //I' | tr -d '\r')
curl -sS "$LOC"   # 진짜 응답(JSON)은 여기서 나온다
```
- 페이로드가 크면(수백 KB) 절대 쉘 인자로 넣지 말고 `--data-binary @파일경로`로 디스크에서 바로 읽게 한다
  (Claude의 컨텍스트에 큰 JSON을 통째로 띄우지 않아도 됨).

### 스키마를 나중에 확장할 때: 컬럼 위치를 고정하라
시트에 이미 데이터가 쌓인 뒤에 컬럼을 추가해야 하는 상황이 반드시 온다 (예: "원본상세" 컬럼을 나중에 추가).
- **새 컬럼은 항상 끝에 추가**하고, 중복 판정에 쓰는 "고유키" 같은 컬럼은 **고정된 열 번호 상수**로 관리한다
  (`HEADERS.length`처럼 배열 길이로 계산하면, 컬럼을 중간에 끼워넣는 순간 기존 행의 키 위치와 새 코드가
  읽는 위치가 어긋나서 중복 삽입되거나 데이터가 밀린다).
- 이미 있는 시트는 헤더 행이 자동으로 안 바뀐다 (헤더는 시트가 비어있을 때만 씀). 새 컬럼을 추가했으면
  기존 시트의 헤더 셀도 코드에서 한 번 보정해주는 게 안전하다.
```javascript
var KEY_COL = 10; // 배열 길이 대신 고정 상수
if (!sh.getRange(1, 11).getValue()) sh.getRange(1, 11).setValue('원본상세'); // 헤더 보정
```

### 중복 제거 키
- 국세청 전자세금계산서처럼 **승인번호 같은 진짜 고유값이 있으면 그걸 그대로 키로 쓴다** (해시 불필요).
- 은행 거래내역처럼 고유 ID가 없으면 `(날짜+거래처+금액+구분)`을 MD5 해시해서 키로 쓴다.
  `Utilities.computeDigest(Utilities.DigestAlgorithm.MD5, keySrc)` + `Utilities.base64Encode(...)`.

## 방법 A 대신 "진짜" 연동이 필요하면

이 저장소는 이미 GCP 서비스 계정으로 Google Sheets API를 직접 쓰는 Streamlit 앱 패턴을 갖고 있다
([[gcp-sheets-streamlit-setup]] 스킬 참고, `sheets_client.py`). Artifact + Apps Script 릴레이는
"설정 부담을 최소화한 임시 다리"이고, 사용 빈도가 잦아지거나 여러 사람이 실시간으로 같이 봐야 하면
차라리 이 포털에 페이지를 하나 추가해서 서비스 계정으로 직접 읽고 쓰는 쪽이 훨씬 안정적이다.
(단, 이 경우 새 서비스 계정 발급·시트 공유·Streamlit Secrets 입력은 사용자가 직접 해야 하는 부분이
있으니 `gcp-sheets-streamlit-setup` 스킬의 5번 항목을 같이 참고할 것.)

## Artifact 안에 외부 라이브러리(예: xlsx 파서) 넣기

Artifact CSP는 외부 스크립트 로딩도 막지만, **Claude Code의 Bash 도구는 인터넷이 되므로 라이브러리를
미리 다운로드해서 파일 안에 통째로 인라인**하면 된다.
- SheetJS(xlsx) 같은 라이브러리는 `xlsx.full.min.js`(전체판)를 쓰면 legacy 코드페이지 변환表에
  **의도적으로 U+FFFD(대체 문자)가 대량으로 들어있어서**, Artifact 퍼블리시 검증기가 "깨진 이스케이프
  시퀀스"로 오인해 거부한다 (`content contains invalid or unpaired escape sequences`).
  → `xlsx.core.min.js`(코어 빌드, BIFF/xls 지원은 유지하면서 코드페이지 표 제외)를 쓰면 해결된다.
- 인라인하기 전에 라이브러리 파일에 `</script`가 리터럴로 들어있는지 먼저 확인할 것 (있으면 스크립트
  태그가 조기 종료된다).
