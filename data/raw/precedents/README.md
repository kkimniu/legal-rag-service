# Precedent Raw Data

판례 원본 데이터 보관 위치입니다. 원본은 Git에 올리지 않고, 전처리 스크립트가 필요한 JSON만 읽어서 `data/processed/precedents`와 `data/chunks/precedents`에 산출물을 만듭니다.

## 현재 입력 위치

```text
data/raw/precedents/
  incoming/
    Other/       판례 관련 QA 보조 데이터
    Sublabel/    판례/행정심판 재결례 원문 메타데이터
    Training/    AI Hub 판결문 라벨링 학습 데이터
    Validation/  AI Hub 판결문 라벨링 검증 데이터
```

## 처리 원칙

- 원본 JSON은 삭제하지 않습니다.
- RAG 검색에 필요한 필드만 표준 JSONL로 정규화합니다.
- `Sublabel`과 `Training/Validation`은 판례 검색의 주 데이터로 사용합니다.
- `Other`는 질문/답변 보조 데이터로 분류하여 필요할 때 별도 컬렉션이나 보강 데이터로 사용할 수 있습니다.
