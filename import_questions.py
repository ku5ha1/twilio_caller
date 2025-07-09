import json
from app.db import SessionLocal
from app.models import Question

def import_questions(json_path="interview_questions.json"):
    session = SessionLocal()
    with open(json_path, "r", encoding="utf-8") as f:
        questions = json.load(f)
    added, skipped = 0, 0
    for q in questions:
        # Check if question already exists (by text and role)
        exists = session.query(Question).filter_by(text=q["text"], role=q["role"]).first()
        if not exists:
            question = Question(text=q["text"], role=q["role"], order=q["order"])
            session.add(question)
            added += 1
        else:
            skipped += 1
    session.commit()
    session.close()
    print(f"Added {added} questions. Skipped {skipped} (already present).")

if __name__ == "__main__":
    import_questions() 