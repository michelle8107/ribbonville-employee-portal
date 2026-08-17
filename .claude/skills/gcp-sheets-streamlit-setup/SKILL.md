---
name: gcp-sheets-streamlit-setup
description: Connect a new Streamlit Cloud app to Google Sheets via a service account in the "Ribbonvill Content Automation" GCP project (focal-equinox-505111-v4). Use when adding a new Streamlit app that needs to read/write a Google Sheet, or when the current service account key stops working (invalid_grant / PEM errors).
---

# Google Sheets 서비스 계정 + Streamlit Secrets 연동

리본빌 직원 홈페이지(ribbonville-employee-portal)를 만들 때 겪었던 시행착오를 정리한 절차.
같은 패턴이 필요한 새 Streamlit 앱에도 그대로 재사용한다.

## 사전 정보

- GCP 프로젝트: **Ribbonvill Content Automation** (project id: `focal-equinox-505111-v4`)
- 이 프로젝트는 이미 Google Sheets API / Google Drive API가 활성화되어 있음 — 새로 만들 필요 없음
- 서비스 계정 콘솔: `https://console.cloud.google.com/iam-admin/serviceaccounts?project=focal-equinox-505111-v4`

## 절차

### 1. 서비스 계정 만들기 (앱마다 새로 만드는 걸 권장)

앱별로 별도 서비스 계정을 쓰면 어떤 앱이 어떤 시트에 접근하는지 명확하다.

1. 서비스 계정 콘솔 → "서비스 계정 만들기"
2. 이름: `<app-name>` 형식 (예: `ribbonvill-employee-portal`)
3. 권한(2단계)은 건너뛰어도 된다 — 프로젝트 전체 권한이 아니라 "시트 개별 공유"로 접근을 준다

### 2. 키 발급

1. 방금 만든 서비스 계정 → "키" 탭 → "키 추가" → "새 키 만들기" → JSON
2. 브라우저가 자동으로 JSON 파일을 다운로드한다

**함정**: 다운로드 폴더에 예전에 받은 다른 서비스 계정 키 파일들이 섞여 있으면 사용자가 헷갈려서 엉뚱한 파일을 붙여넣는 일이 잦다.
막 발급한 키가 아니라 예전 키(특히 삭제된 키)를 쓰면 `invalid_grant: Invalid JWT Signature` 에러가 난다.
혼동을 막으려면: **키를 새로 하나 만들고, 기존에 쓰던 낡은 키는 그 자리에서 바로 삭제**해서 "지금 다운로드 폴더에서 가장 최근 파일 = 유일하게 유효한 키"가 되게 만드는 게 가장 안전하다.

### 3. 구글 시트를 서비스 계정과 공유

1. 앱에서 쓸 새 구글 시트를 만든다 (`sheets.new`)
2. 시트 우측 상단 "공유" → 방금 받은 JSON 안의 `client_email` 값(예: `xxx@focal-equinox-505111-v4.iam.gserviceaccount.com`)을 **편집자**로 추가
3. 시트 URL에서 ID 복사: `https://docs.google.com/spreadsheets/d/<이 부분>/edit`

### 4. 앱 코드 쪽 — JSON을 통째로 받는 방식을 쓸 것

필드별로(`private_key_id`, `private_key`, `client_id` ...) TOML에 하나씩 옮겨 적게 하면 값 하나만 빠지거나 깨져도
`Unable to load PEM file` / `invalid_grant` 에러가 나고, 어떤 필드가 잘못됐는지 사용자가 알아내기 어렵다.

대신 앱 코드에서 **JSON 파일 내용을 통째로 받는 시크릿 하나**를 지원하게 만든다 (예: `ribbonville-employee-portal`의 `sheets_client.py` 참고):

```python
def _service_account_info() -> dict:
    table = st.secrets.get("gcp_service_account")  # 필드별 입력도 계속 지원(선택)
    if table:
        return dict(table)
    raw_json = st.secrets["GCP_SERVICE_ACCOUNT_JSON"]
    return json.loads(raw_json)
```

Streamlit Secrets에는 TOML **리터럴** 멀티라인 문자열(`'''...'''`, 작은따옴표)을 쓴다. 큰따옴표 버전(`"""..."""`)을
쓰면 `\n` 이스케이프가 실제 줄바꿈으로 바뀌어버려서, private_key 안의 `\n`이 진짜 개행문자가 되고
`json.loads()`가 "제어문자가 있다"며 실패한다.

```toml
SPREADSHEET_ID = "복사한 시트 ID"

GCP_SERVICE_ACCOUNT_JSON = '''
(다운로드한 JSON 파일 내용을 그대로 붙여넣기)
'''
```

### 5. Streamlit Cloud에 Secrets 입력할 때 (Claude가 직접 못 하는 부분)

**API 키/비밀키를 Claude가 대신 입력하는 것은 금지 규칙이라 항상 사용자가 직접 해야 한다.**
사용자가 헷갈리지 않게 붙여넣기를 최대한 쉽게 만들어줄 것:

1. Secrets 텍스트박스를 Claude가 미리 정리해서, 딱 하나의 영어 placeholder 토큰만 남겨둔다 (예: `PASTE_HERE`).
   한글 placeholder는 더블클릭으로 단어 전체가 안 잡힐 수 있어서 피한다.
2. 사용자에게: "메모장으로 JSON 파일 열기 → Ctrl+A, Ctrl+C → 여기서 `PASTE_HERE` 더블클릭 → Ctrl+V → Save changes" 순서로 안내한다.
3. 저장 후 앱을 확인했을 때 에러 메시지로 원인을 특정한다:
   - `AttributeError: module 'sheets_client' has no attribute ...` → 코드 배포가 아직 최신이 아님. "Manage app" 메뉴에서 Reboot app.
   - `Unable to load PEM file` → private_key 값 자체가 비어있거나 깨짐 (필드별 입력 방식에서 특히 잘 발생)
   - `invalid_grant: Invalid JWT Signature` → 키는 잘 붙여넣었지만, 그 키가 이미 삭제된(revoke된) 키다. 최신 키 파일을 다시 확인.

### 6. Streamlit Community Cloud의 private 앱 제한

무료 Community Cloud 워크스페이스는 **private 앱을 1개만** 허용한다. 두 번째 앱을 배포하려는데
"You can only have one private app per workspace" 에러가 나면, 그 앱의 GitHub 저장소를 public으로
바꿔야 한다 (`gh repo edit <repo> --visibility public --accept-visibility-change-consequences`).
민감한 코드/데이터가 없는지 먼저 확인할 것 — 시크릿(Secrets)은 저장소가 public이어도 노출되지 않는다.
