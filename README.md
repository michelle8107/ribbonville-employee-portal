# 리본빌 경영관리

직원들이 같이 쓰는 관리자 홈페이지입니다.

## 기능

1. **📊 스프레드시트 링크 모음** — 자주 쓰는 스프레드시트/외부 링크를 이름·설명·카테고리·담당자와 함께 등록
2. **📅 업무 달력** — 팀 업무 일정을 달력으로 확인하고 등록/삭제

(연차 신청/결재 시스템은 추후 추가 예정)

데이터는 구글 시트에 저장되어 여러 직원이 동시에 보고 입력할 수 있습니다.

## 구글 시트 연동 설정 (최초 1회, 관리자가 진행)

### 1. 구글 클라우드에서 서비스 계정 만들기

1. https://console.cloud.google.com 에서 새 프로젝트 생성 (또는 기존 프로젝트 사용)
2. "API 및 서비스 > 라이브러리"에서 **Google Sheets API**, **Google Drive API** 둘 다 사용 설정
3. "API 및 서비스 > 사용자 인증 정보 > 사용자 인증 정보 만들기 > 서비스 계정" 으로 서비스 계정 생성
4. 생성된 서비스 계정으로 들어가 "키 > 키 추가 > 새 키 만들기 > JSON" 선택 → JSON 키 파일 다운로드
   - 이 파일 안의 내용이 `secrets.toml`의 `[gcp_service_account]` 부분입니다. 절대 외부에 공유하거나 GitHub에 올리지 마세요.

### 2. 구글 시트 준비

1. 새 구글 시트를 만듭니다 (예: "리본빌 직원홈페이지 DB")
2. 시트 URL에서 ID를 복사합니다: `https://docs.google.com/spreadsheets/d/이_부분이_ID/edit`
3. 시트 우측 상단 "공유"에서, 다운로드한 JSON 파일 안의 `client_email` 값(예: `xxx@xxx.iam.gserviceaccount.com`)을 **편집자**로 공유합니다.
4. "링크", "달력" 워크시트는 앱이 처음 실행될 때 자동으로 만들어줍니다. 미리 만들 필요 없습니다.

### 3. Streamlit Cloud에 Secrets 입력

App settings > Secrets 에 아래처럼 입력 (`.streamlit/secrets.toml.example` 참고):

```toml
SPREADSHEET_ID = "복사한 시트 ID"

GCP_SERVICE_ACCOUNT_JSON = '''
(다운로드한 JSON 키 파일을 메모장으로 열어서 내용 전체를 그대로 여기에 붙여넣기)
'''
```

값을 하나씩 옮겨 적을 필요 없이, 다운로드한 JSON 파일 내용을 통째로 `'''` 사이에 붙여넣기만 하면 된다.

## 로컬 실행

```
pip install -r requirements.txt
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
# secrets.toml 값 채운 후
streamlit run app.py
```
