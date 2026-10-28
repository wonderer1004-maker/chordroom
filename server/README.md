# 음원 추출 서버

GitHub Pages는 정적 호스팅이므로 이 서버는 별도로 실행합니다. `server/Dockerfile`에 yt-dlp, ffmpeg, Node.js 22와 Python을 묶었습니다. 로그인·쿠키·접근 제한 우회는 지원하지 않습니다.

## Docker 실행

저장소 루트에서:

```sh
docker build -f server/Dockerfile -t chordroom-audio .
docker run --rm -p 8787:10000 chordroom-audio
```

웹앱의 ‘유튜브 음원 · 다운로드 → 서버 연결 설정’에 `http://localhost:8787`을 입력합니다. 공개 서버는 HTTPS가 필요합니다. 기본 허용 웹앱은 `https://wonderer1004-maker.github.io`, `http://localhost:4173`, `http://127.0.0.1:4173`입니다. 다른 웹앱을 사용할 경우 `ALLOWED_ORIGINS`를 쉼표로 구분해 지정하세요.

Render에서는 저장소 `main`, Docker runtime, Dockerfile `server/Dockerfile`, context `.`, 무료 플랜으로 배포할 수 있습니다. 배포한 서비스의 실제 URL을 웹앱 설정이나 `dist/config.js`에 넣습니다. 서버 주소만 공개 설정에 넣고 토큰은 넣지 마세요.

## 동작과 제한

- `GET /health`: 상태 확인
- `POST /api/extractions`: `{ "url": "https://www.youtube.com/watch?v=..." }`, 202 작업 ID 반환
- `GET /api/extractions/{id}`: 진행 상태·결과 조회
- `GET /api/extractions/{id}/file`: MP3 다운로드
- 10분 이하, 단일 공개 영상. 재생목록·라이브·연령 제한 영상은 제외.
- 한 번에 한 작업. 주소별 10분에 5회, 임시 작업 최대 20개.
- 파일은 완료 후 약 10분 보관하고 정리합니다. 재시작·무료 서버 절전 시 사라질 수 있습니다.
- YouTube 정책·로그인 요구·서버 IP 차단·포맷 변경 등에 따라 공개 영상도 추출에 실패할 수 있습니다. 실패 시 원인을 UI에 표시하며 성공으로 위장하지 않습니다.
- 쿠키, 로그인 정보, 프록시, 비공개 영상 인증을 받거나 저장하지 않습니다.
- 파일명·경로는 서버에서 생성하며 외부 명령에 사용자 쉘 문자열을 넘기지 않습니다. 사용자 입력 URL은 YouTube 도메인과 11자리 ID만 허용하고 정규 URL로 변환합니다.

서버는 개인·소규모 실험용 단일 인스턴스입니다. 다중 사용자 상용 배포에는 인증, 공유 작업 저장소, 작업 큐, 프록시 단계의 요청 제한, 모니터링이 추가로 필요합니다. CORS 자체는 인증이 아니며 공개 API를 보호하는 수단으로 보지 않습니다.

## 검증

```sh
python -B server/test_app.py
```

URL 검증, 10분 제한, 시간 초과 처리, MP3 결과 메타데이터, 임시 파일 정리를 테스트합니다. 모의 추출 테스트가 YouTube의 실제 다운로드 성공을 보장하지는 않습니다.
