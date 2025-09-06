실행 방법

<AI 서버>
==========================================================
[conda modules]
fastapi
pydantic
pydantic_settings
sqlalchemy
torch
transformers
uvicorn
accelerate


(위 환경을 설치한 가상환경에 접속하여 server folder에서 아래 명령어를 입력하면 됩니다.)

uvicorn AI_app.main:app --host 0.0.0.0 --port 8002
==========================================================



<DB 서버>
==========================================================
1. postgresql을 설치합니다.

2. (모든 설정을 Default로 한 상태에서)
CREATE DATABASE dalgona_db; CREATE ROLE dalgona_user WITH LOGIN PASSWORD '0000';
CREATE SCHEMA IF NOT EXISTS dalgona_game AUTHORIZATION dalgona_user;
GRANT USAGE, CREATE ON SCHEMA dalgona_game TO dalgona_user;

3. psql -U postgres -d dalgona_db -f setup.sql
(위 명령어를 통해 DB 테이블을 생성합니다.)

4. Chocolatey 설치
(server\certs 폴더에서)
choco install mkcert -y
mkcert -install
mkcert <서버IP>

uvicorn DB_app.main:app --host 0.0.0.0 --port 8001 --ssl-certfile "certs\192.168.179.56.pem" --ssl-keyfile "certs\192.168.179.56-key.pem
==========================================================

클라이언트에서 서버 접속 ip를 192.168.178.134로 설정해 놓았기에,
서버 환경 구축에 어려움이 있을 수 있는 점 사과 말씀 드립니다.