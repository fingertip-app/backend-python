from app.services.ai.rag import CultureRagService
from app.db.session import SessionLocal
from app.db.models import VectorDocument

db = SessionLocal()
CultureRagService.init_idf_cache(db)

query = "외국인이 좋아하는 전통 도자기 체험"
tokens = CultureRagService._query_tokens(query)
print(f"토큰: {tokens}\n")
for t in tokens:
    print(f"  idf({t}) = {CultureRagService._get_idf(t):.3f}")

print()
for title in ["옹기장", "전통어로방식-어살", "장 담그기"]:
    doc = db.query(VectorDocument).filter_by(title=title).first()
    score = CultureRagService._lexical_score(doc, tokens)
    print(f"{title}: lexical_score={score:.2f}, content_preview={doc.content[:60]}")

db.close()
