from app.services.ai.rag import CultureRagService
from app.db.session import SessionLocal
from app.db.models import VectorDocument

db = SessionLocal()
query = "외국인이 좋아하는 전통 도자기 체험"

tokens = CultureRagService._query_tokens(query)
print(f"질의 토큰: {tokens}\n")

doc = db.query(VectorDocument).filter_by(title="옹기장").first()
score = CultureRagService._lexical_score(doc, tokens)
print(f"옹기장 lexical_score: {score}")
print(f"옹기장 content 일부: {doc.content[:100]}")

db.close()
