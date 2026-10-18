"""Business-logic services.

Each module in this package wraps a single domain capability so that API
endpoints stay thin (parse request → call service → serialize response).

Planned layout:
    file_service.py      # hashing, de-duplication, saving uploads
    parsing_service.py   # PDF/PPTX → text extraction
    chunking_service.py  # text → DocumentChunk rows
    vector_service.py    # ChromaDB embedding + semantic search
    generation_service.py# lessons / questions / flashcards via an LLM
    quiz_service.py      # quiz assembly + grading
"""
