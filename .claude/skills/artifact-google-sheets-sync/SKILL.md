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

### 재동기화는 append-only가 아니라 upsert로 짜라
처음엔 "중복이면 skip"으로 짰는데, 실전에서 이게 계속 발목을 잡았다: 매칭 로직을 고치거나(날짜 허용범위 변경,
거래처 매핑 추가 등) 컬럼 인식을 바로잡은 뒤 다시 동기화하면, **날짜+거래처+금액 같은 키는 그대로인데 상태/사유만
바뀐 경우**가 대부분이다. skip 방식이면 이런 업데이트가 조용히 무시돼서, 매번 "시트에서 행을 다 지우고 다시
올려주세요"를 반복해야 했다. 해결: 고유키 컬럼 값을 읽을 때 **행 번호까지 같이 저장**해두고, 같은 키가 있으면
그 행을 `setValues`로 덮어쓰기(update), 없으면 append. 처음부터 이렇게 짜면 이후의 모든 재계산·재동기화가
"그냥 다시 보내면 알아서 갱신됨"이 된다.
```javascript
var keyToRowNum = {};
keyCol.forEach(function (r, i) { if (r[0]) keyToRowNum[r[0]] = i + 2; }); // 헤더가 1행이므로 +2
var existingRowNum = keyToRowNum[hash];
if (existingRowNum) sh.getRange(existingRowNum, 1, 1, HEADERS.length).setValues([values]); // update
else rowsToAppend.push(values); // append
```

### 브라우저 쪽 자동복구(localStorage)가 "고친 게 반영 안 됨"의 원인이 될 수 있다
Artifact에 새로고침 시 이전 작업을 자동 복구하는 기능을 넣어두면 (있으면 편함), **소스별로 저장해둔 컬럼 매핑도
그대로 복원된다.** 컬럼 자동인식 로직 자체를 고쳐도, 이미 업로드된 소스는 새로고침해봤자 옛날에 잘못 잡힌 매핑을
계속 쓴다 — 파일을 다시 끌어다 놓아야만 재인식이 실행되기 때문. 사용자 입장에서는 "코드를 고쳤다는데 왜 그대로냐"로
보인다. 대응: 파일을 다시 올리지 않고도 저장된 헤더로 컬럼 인식만 다시 돌리는 "자동 재인식" 버튼을 소스 카드마다
둘 것. (`guessCol(src.header, GUESS.xxx)`를 다시 호출해서 `src.mapping`을 덮어쓰기만 하면 됨.)

### 플랫폼 정산내역(쿠팡 등)은 건별 매칭이 아니라 "증빙 존재"로 처리
오픈마켓/플랫폼(쿠팡 등)은 개별 주문마다 세금계산서가 안 나오는 게 정상이라, 매입/매출세금계산서 기준으로
"미매칭 = X"를 걸면 대량의 정상 매출이 전부 오탐으로 걸린다. 이런 플랫폼의 정산내역 파일(결제수단별 정산내역 등)은
업로드는 받되, 건별 금액·날짜 매칭을 시도하지 말고 "이 거래처의 정산내역이 업로드되어 있다"는 사실 자체를
증빙으로 인정해서 상태를 O로 바꾸는 정도로만 쓰는 게 현실적이다 (거래상대방 텍스트에 플랫폼명이 포함되고, 해당
플랫폼 정산내역이 하나라도 업로드돼 있으면 통과).

### xlsx를 라이브러리 없이 손으로 파싱할 때는 inlineStr을 놓치기 쉽다
디버깅 목적으로 xlsx를 `zipfile`+`xml.etree`로 직접 열어볼 때, 텍스트 셀이 전부 빈 값으로 나오면 `t="s"`
(sharedStrings 참조)만 처리하고 `t="inlineStr"` (`<is><t>...</t></is>`로 셀 안에 문자열이 직접 들어있는 경우)를
빠뜨렸을 가능성이 크다. 실제로 쿠팡 정산내역 다운로드 파일은 inlineStr 방식이었다. Artifact 안에 인라인해둔
SheetJS는 두 방식 다 정상 처리하므로 이건 어디까지나 "터미널에서 사람이 미리보기할 때"만 해당하는 함정이다.

## Artifact 안에 외부 라이브러리(예: xlsx 파서) 넣기

Artifact CSP는 외부 스크립트 로딩도 막지만, **Claude Code의 Bash 도구는 인터넷이 되므로 라이브러리를
미리 다운로드해서 파일 안에 통째로 인라인**하면 된다.
- SheetJS(xlsx) 같은 라이브러리는 `xlsx.full.min.js`(전체판)를 쓰면 legacy 코드페이지 변환表에
  **의도적으로 U+FFFD(대체 문자)가 대량으로 들어있어서**, Artifact 퍼블리시 검증기가 "깨진 이스케이프
  시퀀스"로 오인해 거부한다 (`content contains invalid or unpaired escape sequences`).
  → `xlsx.core.min.js`(코어 빌드, BIFF/xls 지원은 유지하면서 코드페이지 표 제외)를 쓰면 해결된다.
- 인라인하기 전에 라이브러리 파일에 `</script`가 리터럴로 들어있는지 먼저 확인할 것 (있으면 스크립트
  태그가 조기 종료된다).
