from pathlib import Path
from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader
from langchain_core.documents import Document
from src.utils.logger import get_logger

logger = get_logger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent


class DocumentParser:
    def __init__(self, folder_path: str = "data"):
        # Adapt folder path to always be relative to project root
        self.folder = ROOT_DIR / folder_path

        if not self.folder.exists():
            logger.error(f"Folder not found: {self.folder}")
            raise FileNotFoundError(f"Data folder '{self.folder}' does not exist.")

        # Collect all files in the folder
        self.filepaths = [p for p in self.folder.glob("*") if self._is_valid_file(p)]
        if not self.filepaths:
            logger.warning(
                f"No valid files found in {self.folder}. Supported: .txt, .pdf, .docx"
            )

    def _is_valid_file(self, path: Path) -> bool:
        return (
            path.exists()
            and path.is_file()
            and path.suffix.lower() in [".txt", ".pdf", ".docx"]
        )

    def _get_loader_for_file(self, path: Path):
        if not self._is_valid_file(path):
            logger.warning(f"Invalid file: {path}")
            return None

        if path.suffix.lower() == ".txt":
            return TextLoader(str(path))
        elif path.suffix.lower() == ".pdf":
            return PyPDFLoader(str(path))
        elif path.suffix.lower() == ".docx":
            return Docx2txtLoader(str(path))

    def load_documents(self):
        """Load and return all valid documents as LangChain Document objects with metadata."""
        all_docs = []
        for path in self.filepaths:
            loader = self._get_loader_for_file(path)
            if loader:
                try:
                    docs = loader.load()
                    for doc in docs:
                        # Wrap into LangChain Document with enriched metadata
                        enriched_doc = Document(
                            page_content=doc.page_content,
                            metadata={
                                "source": str(path),
                                "filename": path.name,
                                "file_type": path.suffix.lower(),
                                "folder": str(self.folder),
                                "doc_length": len(doc.page_content),
                            },
                        )
                        all_docs.append(enriched_doc)
                    logger.info(f"Loaded {len(docs)} document(s) from {path.name}")
                except Exception as e:
                    logger.error(f"Error loading {path.name}: {e}", exc_info=True)
        if not all_docs:
            logger.warning("No documents were loaded. Check input files.")
        return all_docs