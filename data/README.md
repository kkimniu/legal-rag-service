# Data Directory

대용량 법률 데이터는 Git에 직접 커밋하지 않습니다. 폴더 구조만 유지하고 실제 데이터는 로컬, 오브젝트 스토리지, 또는 별도 데이터 파이프라인으로 관리합니다.

- `raw`: AI Hub에서 받은 원천 데이터
- `processed`: 전처리와 정규화가 끝난 데이터
- `chunks`: 임베딩과 검색에 사용할 청크 데이터

## Raw Data Layout

AI Hub 법률 원본 데이터는 아래 구조로 둡니다.

```text
raw/
  aihub_legal/
    01_civil_law/
    02_intellectual_property_law/
    03_administrative_law/
    04_criminal_law/
```

현재 데이터 구조 점검은 `ai/preprocessing/inspect_dataset.py`로 수행합니다. 결과 파일 `processed/dataset_profile.json`은 로컬 분석 산출물이므로 Git에 커밋하지 않습니다.
