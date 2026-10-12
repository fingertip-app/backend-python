# Initial synthetic evaluation seeds

이 자료는 실행기와 계약의 초기 검증용 합성 seed다. live DB/API, 실제 문화유산 snapshot, 실제 모델 실행 결과를 포함하지 않는다. 문화 heritageId/documentId는 모두 synthetic 접두어이며 사람이 실제 정답 문서를 검수했다고 주장하지 않는다. `humanReviewed=false`와 `kind=synthetic`을 명시한다. 실제 heritage snapshot 수집·사람 정답 검수는 Task 6 전에 필요하다. 현재 통과율을 실제 AI 품질·문화 사실성·정확도로 보고하면 안 된다.

- culture.json:20개, exact_name/natural_expression/ambiguous/unrelated 각5개. 기존 scripts/rag_api_smoke_test.py의6개 질의를 그대로 포함한다.
- recommendation.json:20개, normal/price_boundary/region_headcount/empty_inactive_ambiguous 각5개. allowedIds는 추천 가능한 후보 집합, forbiddenIds는 반드시 제외할 항목이며 모두 추천해야 한다는 뜻은 아니다.
- 각 dataset은 dev10/test10. culture의 정확명/자연어 표현은 같은 topic groupId와 split을 사용해 표현 변형 유출을 막는다. 추천 조건별 질의는 서로 독립된 group이다.
- catalog.json:ID101–112, SEOUL/GYEONGGI/BUSAN3지역, 빈 주소/null region, active/inactive, 50000/50000.01/49999.99 경계와0원, 정원2/3/4 포함. synthetic 주소는 지역 접두어 매핑 fixture이며 실제 위치가 아니다.
- culture-corpus.json:5개 synthetic document. 간단한 설명은 retrieval fixture일 뿐 신뢰할 수 있는 실제 국가유산 자료를 대체하지 않는다.

snapshotHash는 참조한 corpusFile 원본 bytes의 SHA-256이다. loader는 schema/unknown fields, 중복 case ID, dev/test group 유출, allowed/forbidden 겹침, 기대 source/catalog ID의 존재, corpus 해시와 provenance를 검사한다. 파일 수정 시 해시를 의도적으로 새로 고정해야 한다. seed expectedStatus의 conflict/unsupported는 clarification_required이며 culture 검색에 headCount는 사용되지 않는다.

금액은 1인당 KRW, 정원은 프로그램 최대 인원이다. 예약 가능 좌석·주말·시간·접근성·고령자 적합성은 검증하지 않는다. v1 추천 검색은 lexical catalog 검색이며 실험 결과에서 이 한계를 밝혀야 한다. 일정/접근성 및 자연어·구조화 지역 충돌 사례는 확인 질문 기대값을 고정한다. 총액 예산 문구는 단위가 확인될 때까지 추천하지 않는다.

기대 ID는 fixture 표의 active/지역/가격/정원을 기준으로 작성자가 수동 도출했다. 자동 ID 검색 로직으로 기대값을 생성하지 않았다. 실제 heritage 정답 검수 또는 AI 응답 검수와는 다르다. 이 파일의 합성 문구는 사용자 대화 원문을 수집한 데이터가 아니다.
