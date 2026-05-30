# Preprocessing

AI Hub 법률 원본 데이터를 RAG에 넣기 전 구조를 점검하고 표준 포맷으로 변환하는 영역입니다.

권장 흐름:

1. `inspect_dataset.py`로 원본 데이터의 파일 수, 확장자, JSON 키, CSV 헤더를 확인합니다.
2. 원본은 `data/raw/aihub_legal` 아래에 그대로 둡니다.
3. 정제된 문서는 `data/processed`에 JSONL로 저장합니다.
4. 검색용 청크는 `data/chunks`에 저장합니다.

원본 데이터는 Git에 커밋하지 않습니다.
