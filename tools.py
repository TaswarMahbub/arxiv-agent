import arxiv
import os
import requests
import re
from urllib.parse import urlparse
from PyPDF2 import PdfReader
from smolagents import tool

downloaded_files = []
searched_papers = []

@tool
def search_arxiv(query: str, max_results: int = 3) -> list:
    """
    Searches arXiv for academic papers based on a query.
    
    Args:
        query: The search terms (e.g., 'Neural SDEs time series').
        max_results: The maximum number of papers to return. Defaults to 3.
        
    Returns:
        A list of dictionaries. Each dict contains 'title', 'authors', 'year', 'url', and 'abstract'.
    """
    # Hard safety limit
    max_results = max(1, min(max_results, 3))
    client = arxiv.Client()
    search = arxiv.Search(
        query=query, 
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance # Ensures accurate semantic matching
    )
    
    results = []
    for paper in client.results(search):
        # Extract authors into a comma-separated string
        # authors = ", ".join([author.name for author in paper.authors])
        authors = [author.name for author in paper.authors]
        
        # Append as a structured dictionary rather than a raw string
        results.append({
            "title": paper.title,
            "authors": authors,
            "year": paper.published.year,
            "url": paper.entry_id,
            "abstract": paper.summary
        })

    searched_papers.clear()
    searched_papers.extend(results)    
    return results
@tool
def download_arxiv_pdf(arxiv_url: str) -> str:
    """
    Downloads an arXiv paper PDF from its arXiv URL.

    Args:
        arxiv_url: The arXiv paper URL, such as
            'http://arxiv.org/abs/2605.23989v1'.

    Returns:
        The local file path of the downloaded PDF.
    """
    parsed_url = urlparse(arxiv_url)

    if parsed_url.hostname not in ["arxiv.org", "www.arxiv.org"]:
        raise ValueError("Only arXiv URLs are allowed.")
    
    pdf_url = arxiv_url.replace("/abs/", "/pdf/")

    if not pdf_url.endswith(".pdf"):
        pdf_url += ".pdf"

    os.makedirs("downloads", exist_ok=True)

    paper_id = pdf_url.split("/")[-1].replace(".pdf", "")
    file_path = os.path.join("downloads", f"{paper_id}.pdf")

    response = requests.get(pdf_url, timeout=30)
    response.raise_for_status()

    # Guardrail: verify that the downloaded content is actually a PDF
    if not response.content.startswith(b"%PDF-"):
        raise ValueError("Downloaded content is not a valid PDF.")

    # Guardrail: limit PDF downloads to 20 MB
    max_size = 20 * 1024 * 1024

    if len(response.content) > max_size:
        raise ValueError("PDF is too large. Maximum allowed size is 20 MB.")

    with open(file_path, "wb") as file:
        file.write(response.content)

    # Remember this file so the Gradio UI can offer it to the user
    if file_path not in downloaded_files:
        downloaded_files.append(file_path)

    return file_path

# @tool
# def extract_pdf_text(file_path: str, max_pages: int = 5) -> str:
#     """
#     Extracts text from the first pages of a downloaded PDF.

#     Args:
#         file_path: The local path to the PDF file.
#         max_pages: The maximum number of pages to extract. Defaults to 5.

#     Returns:
#         The extracted text from the PDF.
#     """

#     reader = PdfReader(file_path)

#     text = ""

#     pages_to_read = min(max_pages, len(reader.pages))

#     for i in range(pages_to_read):
#         page_text = reader.pages[i].extract_text()

#         if page_text:
#             text += page_text + "\n"

#     return text


@tool
def extract_pdf_text(
    file_path: str,
    max_pages: int = 5,
    max_chars: int = 15000
) -> str:
    """
    Extracts and cleans text from the first pages of a downloaded PDF.

    Args:
        file_path: The local path to the PDF file.
        max_pages: The maximum number of pages to extract. Defaults to 5.
        max_chars: The maximum number of characters to return. Defaults to 15000.

    Returns:
        Cleaned text extracted from the PDF.
    """
    # Hard safety limits
    max_pages = min(max_pages, 5)
    max_chars = min(max_chars, 15000)
    reader = PdfReader(file_path)

    text_parts = []

    pages_to_read = min(max_pages, len(reader.pages))

    for i in range(pages_to_read):
        page_text = reader.pages[i].extract_text()

        if page_text:
            text_parts.append(page_text)

    text = "\n".join(text_parts)

    # Remove PDF font/encoding artifacts such as /C8 /C12 /C3
    text = re.sub(r"/C\d+", " ", text)

    # Replace repeated spaces and tabs with one space
    text = re.sub(r"[ \t]+", " ", text)

    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    text = text.strip()

    # Guardrail: stop if the PDF contains no extractable text
    if not text:
        raise ValueError(
            "No readable text could be extracted from this PDF."
        )
    # Guardrail: do not return an unlimited amount of PDF text
    if len(text) > max_chars:
        text = text[:max_chars]
        text += "\n\n[Text truncated due to extraction limit.]"

    return text