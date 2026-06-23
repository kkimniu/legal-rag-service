# AI Pipeline

법률 RAG 기능을 백엔드 API와 분리해 실험, 배치 처리, 재색인 작업을 관리하는 공간입니다.

- `preprocessing`: AI Hub 원천 데이터 정제, 개인정보 마스킹, 포맷 통일
- `embeddings`: 문서 임베딩 생성과 ChromaDB 색인
- `rag`: 검색 · 답변 품질 평가 스크립트
