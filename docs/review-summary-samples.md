# Review Summary Quality Samples

## Positive

Input:

> 선생님이 친절했고 매듭 만드는 과정을 차근차근 알려주셔서 좋았습니다. 완성품도 예뻐서 다시 참여하고 싶어요.

Expected:

```json
{
  "summary": "강사의 친절한 설명과 단계적인 진행이 만족스러웠고, 완성품에 대한 만족도도 높았습니다.",
  "sentimentScore": 0.9,
  "keywords": ["친절", "매듭", "완성품"]
}
```

## Neutral

Input:

> 체험 내용은 괜찮았지만 시간이 조금 짧았습니다. 위치 안내는 더 자세하면 좋겠습니다.

Expected:

```json
{
  "summary": "체험 자체는 무난했지만 진행 시간이 짧고 위치 안내가 부족했다는 의견입니다.",
  "sentimentScore": 0.55,
  "keywords": ["시간", "위치 안내", "체험"]
}
```

## Negative

Input:

> 예약 시간보다 늦게 시작했고 재료 설명도 부족했습니다. 가격에 비해 만족도가 낮았습니다.

Expected:

```json
{
  "summary": "시작 지연과 부족한 재료 설명 때문에 가격 대비 만족도가 낮았다는 부정적인 후기입니다.",
  "sentimentScore": 0.2,
  "keywords": ["지연", "재료 설명", "가격"]
}
```

## Short Review

Input:

> 좋아요

Expected:

```json
{
  "summary": "좋아요",
  "sentimentScore": 0.5,
  "keywords": []
}
```
