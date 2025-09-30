현재 가동중인 서버
uvicorn Merge_app.main:app --host 0.0.0.0 --port 25800
ngrok http 25800 --domain=unvintaged-dakota-folksier.ngrok-free.app

<<서버 실행 방법>>
※ 클라이언트의 서버 연결 IP주소 또한 바꿔줘야 합니다.

<공통>
==========================================================
1. Chocolatey를 설치합니다.

2. certs 폴더에서 아래 명령어 3줄을 차례로 입력합니다.
choco install mkcert -y
mkcert -install
mkcert <내 서버 IP>
==========================================================


<AI 서버>
==========================================================
1. miniconda를 설치합니다.

2. Anaconda Prompt를 실행하고 가상환경을 생성한 다음, 아래 모듈들을 설치합니다.
[conda modules]
fastapi
pydantic
pydantic_settings
sqlalchemy
torch
transformers
uvicorn
accelerate

3. 위 환경을 설치한 가상환경에 접속하여 server folder에서 아래 명령어를 입력하면 됩니다.

uvicorn AI_app.main:app --host 0.0.0.0 --port 8002 --ssl-certfile "certs\<내 서버 IP>.pem" --ssl-keyfile "certs\<내 서버 IP>-key.pem"
==========================================================


<DB 서버>
==========================================================
1. postgresql을 설치합니다.

2. (모든 설정을 Default로 한 상태에서)
SQL Shell (psql) 터미널을 열고 아래 명령어 3줄을 차례로 입력합니다.
CREATE DATABASE dalgona_db; CREATE ROLE dalgona_user WITH LOGIN PASSWORD '0000';
CREATE SCHEMA IF NOT EXISTS dalgona_game AUTHORIZATION dalgona_user;
GRANT USAGE, CREATE ON SCHEMA dalgona_game TO dalgona_user;

3. psql -U postgres -d dalgona_db -f setup.sql
(위 명령어를 통해 DB 테이블을 생성합니다.)

4. 위 파이썬 가상환경에 접속하여 server folder에서 아래 명령어를 입력하면 됩니다.

uvicorn DB_app.main:app --host 0.0.0.0 --port 8001 --ssl-certfile "certs\<내 서버 IP>.pem" --ssl-keyfile "certs\<내 서버 IP>-key.pem"
==========================================================