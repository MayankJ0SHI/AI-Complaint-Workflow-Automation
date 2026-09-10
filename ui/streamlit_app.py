import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    
import io
from typing import Any

import pandas as pd
import requests
import streamlit as st

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

from src.config.settings import settings
API_BASE_URL = settings.api_base_url
PROCESS_ENDPOINT = f"{API_BASE_URL}/api/v1/process"


# -------------------------------------------------------------------
# Page configuration
# -------------------------------------------------------------------

st.set_page_config(
    page_title="AI Document Processing",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -------------------------------------------------------------------
# API functions
# -------------------------------------------------------------------


def process_documents(
    uploaded_files: list[Any],
) -> dict[str, Any]:
    """Send uploaded documents to the FastAPI service."""

    files = [
        (
            "files",
            (
                uploaded_file.name,
                uploaded_file.getvalue(),
                uploaded_file.type or "application/octet-stream",
            ),
        )
        for uploaded_file in uploaded_files
    ]

    response = requests.post(
        PROCESS_ENDPOINT,
        files=files,
        timeout=600,
    )

    response.raise_for_status()

    return response.json()


def fetch_report(run_id: str) -> bytes:
    """Download the final CSV report for a processing run."""

    response = requests.get(
        f"{API_BASE_URL}/api/v1/report/{run_id}",
        timeout=60,
    )

    response.raise_for_status()

    return response.content


def check_api_health() -> bool:
    """Check whether the FastAPI service is available."""

    try:
        response = requests.get(
            f"{API_BASE_URL}/health",
            timeout=5,
        )

        return response.ok

    except requests.RequestException:
        return False


# -------------------------------------------------------------------
# Sidebar
# -------------------------------------------------------------------

with st.sidebar:
    st.header("⚙️ Configuration")

    st.write("**API Service**")

    st.code(
        API_BASE_URL,
        language="text",
    )

    if check_api_health():
        st.success("API Connected")
    else:
        st.error("API Unavailable")

    st.divider()

    st.markdown("""
        **Supported documents**

        - TXT
        - PDF
        - DOCX

        **AI workflow**

        1. Document parsing
        2. Complaint extraction
        3. Customer email generation
        4. Management summary generation
        5. Consolidated reporting
        """)


# -------------------------------------------------------------------
# Header
# -------------------------------------------------------------------

st.title("📄 AI Document Processing System")

st.markdown("""
    Upload customer complaint documents and let the AI workflow
    automatically extract structured case information, generate
    customer communication, and prepare management summaries.
    """)

st.divider()


# -------------------------------------------------------------------
# Upload section
# -------------------------------------------------------------------

st.subheader("📤 Upload Complaint Documents")

uploaded_files = st.file_uploader(
    "Drag and drop your complaint documents here",
    type=["txt", "pdf", "docx"],
    accept_multiple_files=True,
    help="Supported formats: TXT, PDF and DOCX.",
)


if uploaded_files:

    st.success(f"{len(uploaded_files)} document(s) ready for processing.")

    upload_data = [
        {
            "File": uploaded_file.name,
            "Type": uploaded_file.type or "Unknown",
            "Size": f"{uploaded_file.size / 1024:.2f} KB",
        }
        for uploaded_file in uploaded_files
    ]

    upload_df = pd.DataFrame(upload_data)

    st.dataframe(
        upload_df,
        use_container_width=True,
        hide_index=True,
    )


# -------------------------------------------------------------------
# Processing
# -------------------------------------------------------------------

st.divider()

process_button = st.button(
    "🚀 Process Documents",
    type="primary",
    disabled=not uploaded_files,
    use_container_width=True,
)


if process_button:

    if not check_api_health():
        st.error(
            "The FastAPI service is unavailable. "
            "Start the API using:\n\n"
            "`uvicorn api.main:app --reload`"
        )

        st.stop()

    progress_container = st.empty()

    with st.spinner("Running AI document processing workflow..."):

        try:

            progress_container.info("Uploading documents and starting processing...")

            result = process_documents(uploaded_files)

            progress_container.empty()

        except requests.exceptions.ConnectionError:

            progress_container.empty()

            st.error("Unable to connect to the FastAPI service.")

            st.stop()

        except requests.exceptions.Timeout:

            progress_container.empty()

            st.error("The processing request timed out. " "Please try again.")

            st.stop()

        except requests.exceptions.HTTPError as exc:

            progress_container.empty()

            error_detail = exc.response.text if exc.response is not None else str(exc)

            st.error(f"Document processing failed:\n\n" f"{error_detail}")

            st.stop()

        except requests.RequestException as exc:

            progress_container.empty()

            st.error(f"API request failed: {exc}")

            st.stop()

        except Exception as exc:

            progress_container.empty()

            st.error(f"Unexpected error: {exc}")

            st.stop()

    # ---------------------------------------------------------------
    # Processing result
    # ---------------------------------------------------------------

    status = result["status"]
    run_id = result["run_id"]

    if status == "completed":

        st.success("✅ All documents were processed successfully.")

    elif status == "completed_with_errors":

        st.warning("⚠️ Processing completed, but some documents failed.")

    else:

        st.error("❌ All documents failed processing.")

    st.subheader("📊 Processing Summary")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Total Documents",
        result["total"],
    )

    col2.metric(
        "Successful",
        result["successful"],
    )

    col3.metric(
        "Failed",
        result["failed"],
    )

    st.caption(f"Processing Run ID: `{run_id}`")

    # ---------------------------------------------------------------
    # Retrieve report
    # ---------------------------------------------------------------

    try:

        report_content = fetch_report(run_id)

        report_df = pd.read_csv(io.BytesIO(report_content))

        st.divider()

        st.subheader("📋 Final Processing Report")

        st.dataframe(
            report_df,
            use_container_width=True,
            hide_index=True,
        )

        # -----------------------------------------------------------
        # Failed documents
        # -----------------------------------------------------------

        if "processing_status" in report_df.columns:

            failed_df = report_df[report_df["processing_status"] == "failed"]

            if not failed_df.empty:

                with st.expander("⚠️ View Failed Documents"):

                    columns = [
                        column
                        for column in [
                            "source_file",
                            "error_message",
                        ]
                        if column in failed_df.columns
                    ]

                    st.dataframe(
                        failed_df[columns],
                        use_container_width=True,
                        hide_index=True,
                    )

        # -----------------------------------------------------------
        # Download
        # -----------------------------------------------------------

        st.download_button(
            label="⬇️ Download Final Report",
            data=report_content,
            file_name=f"final_report_{run_id}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    except requests.exceptions.HTTPError:

        st.warning(
            "Processing completed, but the final report " "could not be retrieved."
        )

    except requests.RequestException as exc:

        st.warning(f"Unable to retrieve the final report: {exc}")

    except Exception as exc:

        st.warning(f"Unable to display the final report: {exc}")


# -------------------------------------------------------------------
# Footer
# -------------------------------------------------------------------

st.divider()

st.caption("AI Document Processing System | " "FastAPI + Streamlit + LiteLLM")
