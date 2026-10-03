import os
import gradio as gr

from dotenv import load_dotenv
from smolagents import CodeAgent, InferenceClientModel

from tools import (
    search_arxiv,
    download_arxiv_pdf,
    extract_pdf_text,
    downloaded_files,
    searched_papers
)


# ---------------------------------------------------------
# Environment
# ---------------------------------------------------------

load_dotenv(".env")

HF_TOKEN = os.getenv("HF_TOKEN")


# ---------------------------------------------------------
# Model
# ---------------------------------------------------------

model = InferenceClientModel(
    model_id="Qwen/Qwen2.5-Coder-32B-Instruct",
    token=HF_TOKEN
)


# ---------------------------------------------------------
# Agent
# ---------------------------------------------------------

agent = CodeAgent(
    tools=[
        search_arxiv,
        download_arxiv_pdf,
        extract_pdf_text
    ],
    model=model,
    add_base_tools=False,
    max_steps=5
)


# ---------------------------------------------------------
# Main Agent Function
# ---------------------------------------------------------

def agent_chat(
    topic,
    num_papers,
    read_paper,
    summarize_methodology,
    generate_bibtex,
    additional_instructions
):
    # Clear data left over from the previous request
    downloaded_files.clear()
    searched_papers.clear()

    # -----------------------------------------------------
    # Input guardrails
    # -----------------------------------------------------

    if not topic.strip():
        return (
            "Please enter a research topic.",
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False)
        )

    if len(topic) > 200:
        return (
            "Research topic is too long. Please keep it under 200 characters.",
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False)
        )

    if len(additional_instructions) > 1000:
        return (
            "Additional instructions are too long. Please keep them under 1000 characters.",
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False)
        )

    # -----------------------------------------------------
    # Build the research goal from the UI
    # -----------------------------------------------------

    user_goal = f"Research the topic: {topic}.\n"
    user_goal += f"Find {int(num_papers)} relevant arXiv paper(s).\n"

    if summarize_methodology:
        user_goal += (
            "Download and read the selected paper(s), then summarize "
            "the methodology or research approach used in the paper(s).\n"
        )

    elif read_paper:
        user_goal += (
            "Download and read the selected paper(s), then provide "
            "a concise overview of what the paper(s) discuss.\n"
        )

    else:
        user_goal += (
            "Search arXiv only. Do not download or read the PDF. "
            "Return the paper title, authors, year, URL, and a brief "
            "description based on the arXiv search result.\n"
        )

    if generate_bibtex:
        user_goal += (
            "Provide BibTeX citations for the selected paper(s).\n"
        )

    if additional_instructions.strip():
        user_goal += (
            f"Additional instructions: {additional_instructions}\n"
        )

    # -----------------------------------------------------
    # Agent instructions
    # -----------------------------------------------------

    formatted_prompt = f"""
{user_goal}

Research instructions:
- Use the available arXiv tools when the request requires paper research.
- When calling search_arxiv, set max_results exactly to {int(num_papers)}.
- Do not analyze more than {int(num_papers)} paper(s).
- If you download and read a paper, do not assume it has a section literally named "Methodology".
- Determine the methodology or research approach directly from the available extracted text.
- If the paper is a survey or review article, summarize how the authors organize, analyze, compare, or synthesize the literature instead of inventing an experimental methodology.
- After extracting the paper text, summarize it directly.
- Do not use regex or write additional parsing code to locate methodology sections.
- Do not request more than 5 PDF pages or 15000 extracted characters.
- Follow the requested research actions exactly.
- If the goal says "Search arXiv only", do not call download_arxiv_pdf or extract_pdf_text.

Formatting instructions:
- Answer in the same language as the user's request unless the user asks for another language.
- Make the final answer clean and easy to read.
- Only include BibTeX if it was requested.
- If BibTeX was requested, put all BibTeX entries inside a fenced ```bibtex code block.
- Do not include Python representations such as lists or tuples in the final answer.
- Do not include internal reasoning or execution details in the final answer.
- For every paper discussed, always include its title, authors, year, and arXiv URL before the analysis or summary.
"""

    # -----------------------------------------------------
    # Run Agent
    # -----------------------------------------------------

    try:
        result = agent.run(formatted_prompt)

        return (
            str(result),

            gr.update(
                visible=len(searched_papers) >= 1,
                label=(
                    f"⬇ Paper 1: {searched_papers[0]['title'][:25]}..."
                    if len(searched_papers) >= 1
                    else "Download Paper 1"
                )
            ),

            gr.update(
                visible=len(searched_papers) >= 2,
                label=(
                    f"⬇ Paper 2: {searched_papers[1]['title'][:25]}..."
                    if len(searched_papers) >= 2
                    else "Download Paper 2"
                )
            ),

            gr.update(
                visible=len(searched_papers) >= 3,
                label=(
                    f"⬇ Paper 3: {searched_papers[2]['title'][:25]}..."
                    if len(searched_papers) >= 3
                    else "Download Paper 3"
                )
            )
        )

    except Exception as e:
        return (
            f"### Agent Error\n\n```text\n{str(e)}\n```",
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False)
        )


# ---------------------------------------------------------
# PDF Download Function
# ---------------------------------------------------------

def download_paper(paper_index):
    """
    Downloads one of the papers returned by the most recent
    arXiv search.
    """

    if paper_index >= len(searched_papers):
        raise gr.Error(
            "No paper is available for this download."
        )

    arxiv_url = searched_papers[paper_index]["url"]
    paper_id = arxiv_url.split("/")[-1]
    file_path = os.path.join(
        "downloads",
        f"{paper_id}.pdf"
    )

    # If the agent already downloaded the PDF,
    # reuse the existing local file.
    if os.path.exists(file_path):
        return file_path

    # Otherwise download it now.

    return download_arxiv_pdf(arxiv_url)


# ---------------------------------------------------------
# Gradio Interface
# ---------------------------------------------------------

with gr.Blocks(
    title="Autonomous arXiv Research Agent"
) as demo:

    gr.Markdown(
        """
        # Autonomous arXiv Research Agent

        Search, read, and analyze academic papers from arXiv.
        """
    )

    # -----------------------------------------------------
    # Research topic
    # -----------------------------------------------------

    topic = gr.Textbox(
        label="Research Topic",
        placeholder=(
            "E.g., Agentic AI, Neural SDEs, Computer Vision"
        )
    )

    # -----------------------------------------------------
    # Number of papers
    # -----------------------------------------------------

    num_papers = gr.Slider(
        minimum=1,
        maximum=3,
        value=1,
        step=1,
        label="Number of Papers"
    )

    # -----------------------------------------------------
    # Research options
    # -----------------------------------------------------

    with gr.Row():

        read_paper = gr.Checkbox(
            label="Read Paper & Summarize",
            value=False
        )

        summarize_methodology = gr.Checkbox(
            label="Summarize Methodology",
            value=False
        )

        generate_bibtex = gr.Checkbox(
            label="Generate BibTeX",
            value=False
        )

    # -----------------------------------------------------
    # Additional instructions
    # -----------------------------------------------------

    additional_instructions = gr.Textbox(
        label="Additional Instructions (Optional)",
        placeholder=(
            "E.g., Explain the main findings in simple language."
        ),
        lines=2
    )

    # -----------------------------------------------------
    # Research button
    # -----------------------------------------------------

    research_button = gr.Button(
        "Research"
    )

    # -----------------------------------------------------
    # Agent result
    # -----------------------------------------------------

    output = gr.Markdown(
        label="Research Results"
    )

    # -----------------------------------------------------
    # Download controls
    # -----------------------------------------------------

    gr.Markdown("### Download Papers")

    with gr.Row():

        download_1 = gr.DownloadButton(
            "Download Paper 1",
            visible=False
        )

        download_2 = gr.DownloadButton(
            "Download Paper 2",
            visible=False
        )

        download_3 = gr.DownloadButton(
            "Download Paper 3",
            visible=False
        )

    # -----------------------------------------------------
    # Research button event
    # -----------------------------------------------------

    research_button.click(
        fn=agent_chat,
        inputs=[
            topic,
            num_papers,
            read_paper,
            summarize_methodology,
            generate_bibtex,
            additional_instructions
        ],
        outputs=[
            output,
            download_1,
            download_2,
            download_3
        ]
    )

    # -----------------------------------------------------
    # Download button events
    # -----------------------------------------------------

    download_1.click(
        fn=lambda: download_paper(0),
        outputs=download_1
    )

    download_2.click(
        fn=lambda: download_paper(1),
        outputs=download_2
    )

    download_3.click(
        fn=lambda: download_paper(2),
        outputs=download_3
    )


# ---------------------------------------------------------
# Launch
# ---------------------------------------------------------

demo.launch()