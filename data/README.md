# Data Directory

대용량 법률/판례 데이터는 Git에 직접 커밋하지 않습니다. 이 폴더는 원본 데이터 위치와 전처리 산출물 위치만 고정하기 위해 사용합니다.

## 구조

```text
data/
  raw/
    aihub_legal/      AI Hub 법률 QA/조문 원본 데이터
    precedents/       판례 원본 데이터
  processed/          정규화된 문서 JSONL, 통계, 평가 산출물
  chunks/             임베딩/검색용 chunk JSONL
```

## 원칙

- `raw`의 원본 데이터는 수정하거나 삭제하지 않고 보관합니다.
- 필요한 데이터만 전처리 스크립트에서 선별하여 `processed`에 저장합니다.
- 검색용으로 나눈 chunk는 `chunks`에 저장합니다.
- `processed`, `chunks`, `chroma_db`는 재생성 가능한 산출물이므로 Git에 올리지 않습니다.

## 판례 데이터

판례 원본은 아래 위치에 넣습니다.

```text
data/raw/precedents/incoming/
```

현재 지원하는 입력 폴더는 다음과 같습니다.

- `Sublabel`: 판례/행정심판 재결례 원문 메타데이터
- `Training`: AI Hub 판결문 라벨링 학습 데이터
- `Validation`: AI Hub 판결문 라벨링 검증 데이터
- `Other`: 판례 관련 QA 보조 데이터

판례 전처리 명령은 `ai/preprocessing/README.md`를 참고합니다.
