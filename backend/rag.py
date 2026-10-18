
from pathlib import Path
import re

# ==================================================
# KNOWLEDGE BASE LOCATION
# ==================================================

BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"


# ==================================================
# WORDS TO IGNORE
# ==================================================

STOP_WORDS = {
    "what", "is", "the", "a", "an", "of", "at", "in",
    "on", "for", "to", "and", "or", "are", "was", "were",
    "when", "where", "who", "how", "which", "can", "could",
    "do", "does", "did", "tell", "me", "please", "about",
    "give", "show", "i", "my", "your", "you", "there",
    "available", "begin", "start"
}


# ==================================================
# LOAD KNOWLEDGE BASE
# ==================================================

def load_documents():
    documents = []

    if not KNOWLEDGE_BASE_DIR.exists():
        print(f"Knowledge base folder not found: {KNOWLEDGE_BASE_DIR}")
        return documents

    for file_path in KNOWLEDGE_BASE_DIR.glob("*.txt"):
        with open(file_path, "r", encoding="utf-8") as file:
            text = file.read()

        documents.append({
            "source": file_path.name,
            "text": text
        })

    return documents


# ==================================================
# TOKENIZE
# ==================================================

def tokenize(text):
    words = re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())
    return [word for word in words if word not in STOP_WORDS]


# ==================================================
# SPLIT DOCUMENT INTO CHUNKS
# ==================================================

def split_into_chunks(text):
    sections = re.split(r"\n\s*\n", text)
    return [
        section.strip()
        for section in sections
        if section.strip()
    ]



# ==================================================
# INTENT-BASED SOURCE PRIORITY
# ==================================================

def get_source_bonus(query, source):
    query_words = set(tokenize(query))
    query_lower = query.lower()
    source = source.lower()

    bonus = 0

    # Contact questions
    contact_words = {
        "phone", "number", "email", "contact",
        "address", "website", "telephone"
    }

    if query_words & contact_words:
        if source == "contacts.txt":
            bonus += 40

    # Programme/course questions
    programme_words = {
        "programme", "programmes", "program",
        "programs", "course", "courses", "degree"
    }

    if query_words & programme_words:
        if source == "programmes.txt":
            bonus += 40

    # Fee questions
    fee_words = {"fee", "fees", "tuition", "cost", "payment"}

    if query_words & fee_words:
        if source == "fees.txt":
            bonus += 40

    # Academic calendar and examination questions
    calendar_words = {
        "academic", "calendar", "year", "semester",
        "exam", "examination", "cia", "date", "dates",
        "schedule", "timetable", "term"
    }

    if query_words & calendar_words:
        if "calendar" in source:
            bonus += 40

    # Admission questions
    admission_words = {"admission", "admissions", "application"}

    if query_words & admission_words:
        if "admission" in source or "contact" in source:
            bonus += 20

    # SRC background questions
    about_words = {"history", "founded", "inaugurated", "museum"}

    if query_words & about_words:
        if source == "about_src.txt":
            bonus += 30

    return bonus


# ==================================================
# SEARCH KNOWLEDGE BASE
# ==================================================


def search_knowledge(query, top_k=3):
    query_words = tokenize(query)
    query_lower = query.lower().strip()
    results = []

    documents = load_documents()

    if not documents:
        return results

    for document in documents:
        chunks = split_into_chunks(document["text"])

        for chunk in chunks:
            chunk_words = tokenize(chunk)
            chunk_lower = chunk.lower().strip()

            score = 0

            # Ignore chunks that simply repeat the complete question.
            normalized_chunk = re.sub(r"\s+", " ", chunk_lower)
            normalized_query = re.sub(r"\s+", " ", query_lower)

            if normalized_chunk == normalized_query:
                continue

            # Score meaningful query-word matches.
            matched_words = set(query_words) & set(chunk_words)
            score += len(matched_words) * 5

            # Prefer chunks that contain useful information
            # beyond the words already present in the question.
            extra_words = set(chunk_words) - set(query_words) - STOP_WORDS
            if matched_words and extra_words:
                score += min(len(extra_words), 5) * 2

            # Give a small bonus for an exact phrase match,
            # without letting a repeated question dominate.
            if query_lower in chunk_lower:
                score += 3

            # Prioritize the appropriate knowledge-base file.
            score += get_source_bonus(query, document["source"])

            if score > 0:
                results.append({
                    "source": document["source"],
                    "text": chunk,
                    "score": score
                })

    # Highest score first.
    results.sort(key=lambda item: item["score"], reverse=True)

    return results[:top_k]

# ==================================================
# GET CONTEXT FOR THE CHATBOT
# ==================================================

def get_context(query, top_k=3):
    results = search_knowledge(query, top_k)

    if not results:
        return ""

    context_parts = []

    for result in results:
        context_parts.append(
            f"Source: {result['source']}\n"
            f"{result['text']}"
        )

    return "\n\n---\n\n".join(context_parts)


# ==================================================
# TEST
# ==================================================

if __name__ == "__main__":
    print("SRC SmartBot - Knowledge Base Test")
    print("-----------------------------------")

    while True:
        question = input("\nEnter your question (or type exit): ").strip()

        if question.lower() == "exit":
            print("Testing completed.")
            break

        if not question:
            print("Please enter a question.")
            continue

        results = search_knowledge(question)

        if results:
            print("\nRelevant information found:\n")

            for result in results:
                print(
                    f"[Score: {result['score']}] "
                    f"Source: {result['source']}"
                )
                print(result["text"])
                print("\n---")
        else:
            print("\nNo relevant information found.")
