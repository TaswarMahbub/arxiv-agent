---
title: Arxiv Agent Lab
emoji: 🔥
colorFrom: pink
colorTo: yellow
sdk: gradio
sdk_version: 6.27.0
python_version: '3.12'
app_file: app.py
pinned: false
license: mit
short_description: Agentic AI Lab
---

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference


# Autonomous arXiv Research Agent

An AI research agent that searches arXiv for academic papers and can optionally read, analyze, and summarize the papers.

The application uses Hugging Face `smolagents`, the Qwen 2.5 Coder model, the arXiv API, PyPDF2, and Gradio.

## Features

- Search arXiv by research topic
- Select 1–3 papers
- Display paper titles, authors, publication years, and arXiv links
- Download paper PDFs directly from the interface
- Read and summarize papers
- Summarize the methodology or research approach of papers
- Generate BibTeX citations
- Compare multiple papers using additional instructions
- Guardrails for agent steps, input size, search results, PDF downloads, and PDF extraction
- **Deep Research** tab combining arXiv papers with web search results (see below)

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/TaswarMahbub/arxiv-agent.git
cd arxiv-agent
```

### 2. Create a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the Hugging Face Token

Create a local `.env` file from the provided example:

```bash
cp .env.example .env
```

Open `.env` and replace the placeholder with your own Hugging Face token:

```text
HF_TOKEN=your_huggingface_token_here
SERPAPI_API_KEY=your_serpapi_key_here
```

`SERPAPI_API_KEY` is only required for the Deep Research tab. The arXiv Research tab works with `HF_TOKEN` alone.

The real `.env` file is excluded from Git and should not be committed.

### 5. Run the Application

```bash
python3 app.py
```

Gradio will display a local URL in the terminal, typically:

```text
http://127.0.0.1:7860
```

Open this URL in a web browser to use the application.

## Using the Agent

1. Enter a research topic in the **Research Topic** field.
2. Select the number of papers to find using the **Number of Papers** slider.
3. Optionally select one or more research features:
   - **Read Paper & Summarize**
   - **Summarize Methodology**
   - **Generate BibTeX**
4. Optionally provide additional research instructions.
5. Click **Research**.
6. Review the generated research results.
7. Use the download controls below the results to download individual paper PDFs.

## How It Works

The application uses a `CodeAgent` from Hugging Face `smolagents` with custom tools for interacting with arXiv.

The agent can use the following tools:

- `search_arxiv` — searches arXiv and returns structured paper metadata.
- `download_arxiv_pdf` — downloads a selected arXiv paper as a PDF.
- `extract_pdf_text` — extracts bounded text from a downloaded PDF for analysis.

Depending on the options selected in the interface, the agent determines which tools are required.

For a basic search, the agent only searches arXiv:

```text
User Query
    ↓
CodeAgent
    ↓
search_arxiv
    ↓
Research Results
```

When paper reading or methodology analysis is requested, the workflow becomes:

```text
User Query
    ↓
CodeAgent
    ↓
search_arxiv
    ↓
download_arxiv_pdf
    ↓
extract_pdf_text
    ↓
Paper Analysis
```

PDF downloads exposed through the user interface are separate from the agent's decision to read a paper. A user can therefore search for papers and download a result without requiring the agent to analyze the PDF.

## Guardrails

The application includes several guardrails to keep agent behavior bounded and reduce unnecessary or unsafe operations.

These include:

- Maximum agent step limit
- Maximum number of arXiv search results
- Research-topic length limit
- Additional-instruction length limit
- arXiv-only PDF downloads
- HTTP request timeout
- PDF validation
- PDF download-size limit
- Maximum number of PDF pages extracted
- Maximum extracted-text length
- Empty PDF-text extraction handling

These safeguards help prevent runaway agent execution, excessive resource usage, invalid downloads, and attempts to summarize PDFs from which no usable text could be extracted.

## Deep Research Extension

The interface has two tabs:

- **arXiv Research — Original Lab**: the original lab workflow, preserved unchanged (search, Read Paper & Summarize, Summarize Methodology, BibTeX, PDF downloads, and all existing guardrails).
- **Deep Research — Extended Multi-Source Research**: an extension that researches beyond a single academic source.

Deep Research uses a **separate** `CodeAgent` with two tools:

- `search_arxiv` — academic evidence from arXiv (1–3 papers)
- `search_web` — complementary/current web evidence from Google via SerpAPI (1–5 results)

The agent synthesizes both source types into a structured report (Overview, Academic Evidence, Web Evidence, Synthesis, Sources), keeps academic and web sources clearly separated, and only cites sources actually returned by the tools. It does not download or read PDFs.

```text
Research Question
    ↓
Deep Research CodeAgent
    ↓            ↓
search_arxiv   search_web (SerpAPI)
    ↓            ↓
   Multi-source synthesis report
```

**`SERPAPI_API_KEY` is required for Deep Research.** If it is missing, the tab shows a clear message and the arXiv tab keeps working.

Additional Deep Research guardrails:

- Maximum 5 agent steps
- Maximum 3 arXiv papers and 5 web results (enforced in the tool and the app)
- Research question limited to 300 characters; additional instructions to 1000 characters
- Empty web queries rejected; web queries limited to 300 characters
- Explicit handling of a missing API key, SerpAPI errors, and empty results
- Request errors are not shown verbatim, so the API key can never leak into the UI
- Prompt instructions forbid fabricated sources or unsupported claims

## Project Files

```text
arxiv-agent/
├── app.py
├── tools.py
├── requirements.txt
├── README.md
├── .env.example
└── .gitignore
```

### `app.py`

Contains:

- Hugging Face model configuration
- `CodeAgent` configuration
- Agent prompting and orchestration
- Input guardrails
- Gradio user interface
- Research controls
- PDF download controls

### `tools.py`

Contains the custom agent tools for:

- Searching arXiv
- Downloading arXiv PDFs
- Extracting PDF text
- PDF and download guardrails

### `requirements.txt`

Contains the Python dependencies required to run the project.

### `.env.example`

Provides the expected environment-variable format without exposing a real API token.

### `.gitignore`

Prevents local or sensitive files such as `.env`, the virtual environment, downloaded PDFs, caches, and other generated files from being committed.

## Environment Variables

The application requires:

```text
HF_TOKEN
SERPAPI_API_KEY   (Deep Research tab only)
```

This token is used by the Hugging Face inference client.

For security, the real token must be stored in `.env` and should never be committed to the repository.

## Downloaded Papers

PDFs downloaded by the application are stored locally in:

```text
downloads/
```

The `downloads/` directory is excluded from Git.

When a user selects a paper's download control in the Gradio interface, the application provides the corresponding PDF for download.

## Notes

The application requires a Hugging Face token with permission to use the configured inference provider/model.

The current model configured by the application is:

```text
Qwen/Qwen2.5-Coder-32B-Instruct
```

The application is designed to run locally through Gradio.