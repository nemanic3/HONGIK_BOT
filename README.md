# 홍익 졸업 봇

<p align="center">
  <img src="https://raw.githubusercontent.com/ROKSSAN/team4-frontend/refs/heads/main/team4-frontend-dev%20copy/public/main.png" 
       alt="프로젝트 대표 이미지" width="800"/>
</p>

---

## 프로젝트 소개

성적표 한 장으로 졸업 요건, 이수 현황, 누락 과목까지 자동으로 정리해주는 웹 대시보드 서비스입니다.

---

## 주요 기능

📸 성적표 이미지 업로드 (캡처 기준)

🔍 OCR로 교과목명, 학점, 학기 추출

📊 전공/교양 이수율 계산 + 졸업요건 자동 체크

🎯 현재는 25학번 컴퓨터공학과만 지원, 이후 확장 예정

---

## 🗓️ 프로젝트 일정

| 기간 | 내용 | 진행 상황 |
|------|------|------------|
| ~ 6/29 (일) | 개인 과제 제출 | ✅ 완료 |
| 6/30 (월) | 팀 및 멘토 배정 | ✅ 완료 |
| 7/3 (목) | OT (오리엔테이션) | ✅ 완료 |
| 7/4 (금) ~ 7/10 (목) | 주제 선정 및 기획 | ✅ 완료 |
| 7/8 (화) ~ 7/12 (토) | 기능 명세서 작성 + DB 설계 | ✅ 완료 |
| 7/11 (금) | 1주차 과제 발표 (비대면) | ✅ 완료 |
| 7/13 (일) ~ 7/19 (토) | 백엔드/프론트 기본 구조 구현 | 🛠️ 예정 |
| 7/18 (금) | 2주차 과제 제출 (README + 기능 명세서) | 🗓 예정 |
| 7/20 (일) ~ 7/26 (토) | OCR 연동 + 데이터 처리 로직 구현 | ⏳ 예정 |
| 7/27 (일) ~ 8/2 (토) | UI 완성 및 프론트/백 연동 테스트 | ⏳ 예정 |
| 8/3 (일) | 중간 발표 (비대면) | 🗓 예정 |
| 8/3 ~ 8/9 (토) | 코드 리팩토링 + 사용자 피드백 반영 | ⏳ 예정 |
| 8/10 ~ 8/15 (금) | 배포 준비 + 테스트 마무리 | ⏳ 예정 |
| 8/16 (토) | 최종 발표 (대면) | 🗓 예정 |

---

## 📁 시작 가이드

### Requirements

#### 🖥️ Backend
- [Python 3.10 이상](https://www.python.org/downloads/release/python-3100/)
- [Django 4.0](https://www.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [PostgreSQL](https://www.postgresql.org/)
- Kakao OCR API

#### 💻 Frontend
- [Node.js 14.19.3](https://nodejs.org/en)
- [Npm 9.2.0](https://docs.npmjs.com/cli/v9/commands/npm)  
- [React.js](https://react.dev/)
- [Axios](https://axios-http.com/)
- [Chart.js](https://www.chartjs.org/)

#### 🎨 Design
- [Figma](https://www.figma.com)
- [Notion](https://www.notion.com/) (플로우 차트 및 명세 관리용)

---


## 팀 구성

<table style="width:100%; border-collapse: collapse;">
  <tr>
    <th style"border:1px solid #ddd; padding:8px; text-align:center;">팀장 신성현</th>
    <th style"border:1px solid #ddd; padding:8px; text-align:center;">이나나</th>
    <th style"border:1px solid #ddd; padding:8px; text-align:center;">강 산</th>
    <th style"border:1px solid #ddd; padding:8px; text-align:center;">김의림</th>
    <th style"border:1px solid #ddd; padding:8px; text-align:center;">곽유나</th>
  </tr>
  <tr>
    <td style="border:1px solid #ddd; padding:8px; text-align:center;">
      <img width="160px" src="https://avatars.githubusercontent.com/u/188848771?v=4" />
    </td>
    <td style="border:1px solid #ddd; padding:8px; text-align:center;">
       <img width="160px" src="https://github.com/user-attachments/assets/3471d8d4-b25d-49b1-8980-a23f877fbbc8" />
    </td>
    <td style="border:1px solid #ddd; padding:8px; text-align:center;">
      <img width="160px" src="https://avatars.githubusercontent.com/u/139611910?s=400&u=c3c4a6eb05429b73e109293cac9ad11680365b1a&v=4" /> 
    </td>
    <td style="border:1px solid #ddd; padding:8px; text-align:center;">
      <img width="145px" height="145px" style="object-fit: cover;" src="https://github.com/Uirim/Uirim/blob/main/증명사진.jpg?raw=true" />
    </td>
    <td style="border:1px solid #ddd; padding:8px; text-align:center;">
      <img width="160px" src="https://avatars.githubusercontent.com/u/195542716?s=400&u=42372de0252734a071646c6136a851f9c088cf62&v=4" />
    </td>
  </tr>
  <tr>
    <td style="border:1px solid #ddd; padding:8px; text-align:center;"><strong>21학번 백엔드</strong></td>
    <td style="border:1px solid #ddd; padding:8px; text-align:center;"><strong>23학번 백엔드</strong></td>
    <td style="border:1px solid #ddd; padding:8px; text-align:center;"><strong>23학번 프론트엔드</strong></td>
    <td style="border:1px solid #ddd; padding:8px; text-align:center;"><strong>23학번 프론트엔드</strong></td>
    <td style="border:1px solid #ddd; padding:8px; text-align:center;"><strong>24학번 디자이너</strong></td>
  </tr>
</table>

---

## 기술 스택

### Frontend
<p align="left">
  <img src="https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white" alt="HTML5 Badge"/>
  <img src="https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white" alt="CSS3 Badge"/>
  <img src="https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black" alt="JavaScript Badge"/>
</p>


### Backend
![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)
![Django REST Framework](https://img.shields.io/badge/Django%20REST%20Framework-009688?style=for-the-badge&logo=django&logoColor=white)

### Database
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white)

### OCR 처리
![Kakao OCR](https://img.shields.io/badge/Kakao%20OCR-FEE500?style=for-the-badge&logo=kakaotalk&logoColor=black)
![Tesseract](https://img.shields.io/badge/Tesseract-0099FF?style=for-the-badge&logo=tesseract&logoColor=white)

### Visualization
![Chart.js](https://img.shields.io/badge/Chart.js-100000?style=for-the-badge&logo=chartdotjs&logoColor=F7931E)


---

## 💡 아키텍처

### 시스템 구성

- **Frontend**: React.js  
  사용자로부터 성적표 이미지 업로드 → 서버로 전송 → 결과 시각화  
- **Backend**: Django + DRF  
  이미지 처리, Kakao OCR API 연동, 과목/학점/학기 파싱, 졸업요건 계산  
- **Database**: PostgreSQL  
  과목, 학점, 이수 상태 저장 및 통계 관리  
- **OCR API**: Kakao OCR  
  이미지 → 텍스트 변환

---

### 🔧 디렉토리 구조

```bash
📦 project-root
├── backend               # Django 기반 백엔드
│   ├── api              # DB 모델, 시리얼라이저, API 뷰 등
│   ├── config           # 프로젝트 설정 (settings, urls 등)
│   └── public           # 업로드된 성적표 이미지 저장
│
├── frontend             # React 기반 프론트엔드
│   ├── components       # 재사용 가능한 UI 컴포넌트
│   ├── pages            # 페이지 단위 라우팅 구성
│   └── styles           # 전역 및 모듈 스타일 파일
│
└── README.md            # 프로젝트 설명 문서
```

---

### 📄 기능 명세서

👉 [기능 명세서 보기](https://github.com/HICC-2025-project-4team/team4/blob/main/GR%20%EB%B4%87%20%EC%B5%9C%EC%A2%85%20%EA%B8%B0%EB%8A%A5%20%EB%AA%85%EC%84%B8%EC%84%9C%20.xlsx)

본 문서에는 기능 설명, API 흐름, 예외 처리 조건 등이 포함되어 있으며  
백엔드/프론트 개발 시 이를 기준으로 구현이 진행됩니다.
