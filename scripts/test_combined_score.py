from app.services.ai.rag import CultureRagService
from app.db.session import SessionLocal
from app.db.models import VectorDocument

db = SessionLocal()
query = "외국인이 좋아하는 전통 도자기 체험"
tokens = CultureRagService._query_tokens(query)

# top 200 후보 전체에 대해 lexical score 계산해서 max값 구해야 정확함
docs_with_scores = [
    ("옹기장", 0.2383),
    ("장 담그기", 0.3205),
]

for title, vector_score in docs_with_scores:
    doc = db.query(VectorDocument).filter_by(title=title).first()
    lexical_score = CultureRagService._lexical_score(doc, tokens)
    print(f"{title}: vector={vector_score}, lexical_raw={lexical_score}")

db.close()
