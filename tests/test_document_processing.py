import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from document_processor import DocumentParser

parser = DocumentParser("data")
documents = parser.load_documents()

for i, doc in enumerate(documents[:3]):  # preview first 3 docs
    print(doc.page_content[:200])  # show first 200 chars
