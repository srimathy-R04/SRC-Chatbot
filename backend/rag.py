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
    "what", "is", "the", "a", "an",
    "of", "at", "in", "on", "for",
    "to", "and", "or", "are",
    "was", "were", "when",
    "where", "who", "how",
    "which", "can", "could",
    "do", "does", "did",
    "tell", "me", "please",
    "about", "give", "show",
    "i", "my", "your", "you",
    "there", "available"
}


# ==================================================
# LOAD KNOWLEDGE BASE
# ==================================================

def load_documents():
    documents = []

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
# SPLIT DOCUMENT
# ==================================================

def split_into_chunks(text):
    # First split the document into paragraphs
    sections = re.split(r"\n\s*\n", text)

    chunks = []
    current_chunk = ""

    for section in sections:
        section = section.strip()

        if not section:
            continue

        # If the section looks like a heading,
        # keep the next section together with it.
        if len(section.splitlines()) <= 2 and len(section) < 100:
            current_chunk = section
        else:
            if current_chunk:
                chunks.append(current_chunk + "\n\n" + section)
                current_chunk = ""
            else:
                chunks.append(section)

    # Add anything remaining
    if current_chunk:
        chunks.append(current_chunk)

    return chunks


# ==================================================
# SEARCH
# ==================================================

def search_knowledge(query, top_k=3):
    query_words = tokenize(query)
    results = []
    documents = load_documents()

    for document in documents:
        chunks = split_into_chunks(document["text"])

        for chunk in chunks:
            chunk_words = tokenize(chunk)
            score = 0

            # WORD MATCH
            for word in query_words:
                if word in chunk_words:
                    score += 5

            # EXACT PHRASE MATCH
            query_lower = query.lower()
            chunk_lower = chunk.lower()

            if query_lower in chunk_lower:
                score += 20

            # SPECIAL KEYWORD MATCHING
            important_keywords = [
                "phone", "number", "email", "fee", "fees",
                "programme", "programmes", "course", "courses",
                "cia", "exam", "admission", "address",
                "contact", "website"
            ]

            for keyword in important_keywords:
                if keyword in query_lower:
                    if keyword in chunk_lower:
                        score += 15

            # ONLY KEEP RELEVANT RESULTS
            if score > 0:
                results.append({
                    "source": document["source"],
                    "text": chunk,
                    "score": score
                })

    # Highest score first
    results.sort(key=lambda x: x["score"], reverse=True)

    return results[:top_k]


# ==================================================
# GET CONTEXT
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

    question = input("Enter your question: ")
    results = search_knowledge(question)

    if results:
        print("\nRelevant information found:\n")

        for result in results:
            print(f"[Score: {result['score']}] Source: {result['source']}")
            print(result["text"])
            print("\n---")

    else:
        print("\nNo relevant information found.")
