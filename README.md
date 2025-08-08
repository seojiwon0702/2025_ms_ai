# 지니어스 학습 추천 챗봇

## 개요
    지니어스에서 뭘 학습해야할지 모르겠어요..라는 고민을 해결하기 위한 사용자 맞춤형 교육 추천 챗봇
<br>

## 환경 변수(.env)
    OPENAI_API_KEY = ****
    OPENAI_API_TYPE = azure
    OPENAI_API_VERSION = 2025-01-01-preview
    AZURE_OPENAI_ENDPOINT = https://support-openai-prj.openai.azure.com/

    AZURE_OPENAI_LLM = prj-gpt-4.1

    DB_HOST = support-postgresql.postgres.database.azure.com
    DB_PORT = 5432
    DB_NAME = support_genius
    DB_USER = support_admin
    DB_PASSWORD = **** 
<br>

## 설치 방법
### local(가상환경)
◎ 가상환경 생성
```cmd
python -m venv my-venv
```

◎ 가상환경 실행
```cmd
.\my-venv\Scripts\Activate.bat
```

◎ 필요 라이브러리 설치
```cmd
pip install streamlit openai psycopg2-binary python-dotenv
```

◎ streamlit 실행
```cmd
streamlit run genius_chat.py
```

<br>

### Azure Web App
◎ .deployment 파일 생성
```
[config]
SCM_DO_BUILD_DURING_DEPLOYMENT=false
```
◎ streamlit.sh 파일 생성
```shell
pip install streamlit openai psycopg2-binary python-dotenv 

python -m streamlit run ./genius_chat.py --server.port 8000 --server.address 0.0.0.0
```
※ 위 두개의 파일은 디렉토리 최상단에 위치한다.

◎ Azure WebApp 설정
    WebApp > 구성 > 시작명령에 다음과 같은 명령어를 입력 후 저장해준다.
```
bash /home/site/wwwroot/streamlit.sh
```

◎ 배포 이후 WebApp을 다시시작한다.