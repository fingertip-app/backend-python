import os
import sys
from openai import OpenAI
import psycopg
from dotenv import load_dotenv
load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def search(query: str, top_k: int = 20):
    resp = client.embeddings.create(model="text-embedding-3-small", input=query)
    qvec = resp.data[0].embedding
    qvec_str = "[" + ",".join(str(x) for x in qvec) + "]"
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, category,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM vector_documents
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (qvec_str, qvec_str, top_k),
            )
            rows = cur.fetchall()
    print(f"\n=== Query: {query} (top {top_k}) ===")
    for rank, (id_, title, category, sim) in enumerate(rows, 1):
        marker = " <-- 자수장" if "자수" in (title or "") else ""
        print(f"{rank:3d}. id={id_:4d} sim={sim:.4f} [{category}] {title}{marker}")

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "자수장"
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    search(query, top_k)
