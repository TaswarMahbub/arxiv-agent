import os
import gradio as gr

from dotenv import load_dotenv
from smolagents import CodeAgent, InferenceClientModel

from tools import (
    search_arxiv,
    search_arxiv_research,
    download_arxiv_pdf,
    extract_pdf_text,
    search_web,
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
# Deep Research Agent (extension)
# ---------------------------------------------------------
# A separate agent with academic + web search only.
# It does not download or read PDFs.

deep_research_agent = CodeAgent(
    tools=[
        search_arxiv_research,
        search_web
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
# Deep Research Function (extension)
# ---------------------------------------------------------

def deep_research(
    question,
    num_papers,
    num_web_results,
    depth,
    additional_instructions
):
    # -----------------------------------------------------
    # Input guardrails
    # -----------------------------------------------------

    # Validate user input before any agent task is built or run.
    # (search_web keeps its own 300-character limit as defense-in-depth.)
    question = (question or "").strip()
    additional_instructions = (additional_instructions or "").strip()

    if not question:
        raise gr.Error("Please enter a research question.")

    if len(question) > 300:
        raise gr.Error("Research question must be 300 characters or fewer.")

    if len(additional_instructions) > 1000:
        raise gr.Error("Additional instructions must be 1000 characters or fewer.")

    if not os.getenv("SERPAPI_API_KEY"):
        return (
            "Deep Research requires a SerpAPI key. Please add "
            "`SERPAPI_API_KEY` to your `.env` file and restart the app."
        )

    # Hard limits, independent of the UI sliders
    num_papers = max(1, min(int(num_papers), 3))
    num_web_results = max(1, min(int(num_web_results), 5))

    if depth == "Detailed":
        depth_instructions = (
            "Write a detailed report: discuss each source individually "
            "and give a thorough synthesis."
        )
    else:
        depth_instructions = (
            "Write a concise report: keep each section short and focused."
        )

    formatted_prompt = f"""
Research question: {question}

Research instructions:
- Call search_arxiv_research exactly once with max_results set exactly to {num_papers}.
- Call search_web exactly once with max_results set exactly to {num_web_results}.
- search_arxiv_research returns a list of dicts with keys exactly: 'title', 'authors', 'year', 'url', 'abstract'.
- search_web returns a list of dicts with keys exactly: 'title', 'url', 'snippet'.
- Use only these keys. Print the search results first, read them, then write the report.
- Do not download or read PDFs. Use only the returned arXiv metadata/abstracts and web snippets.
- Never claim a source says something that is not supported by its returned abstract or snippet.
- Never invent sources, titles, authors, or URLs. Only cite sources returned by the tools.
- If a search returns no results, or the evidence is insufficient to answer the question, say so explicitly.
- Clearly distinguish academic (arXiv) evidence from web evidence.
- {depth_instructions}
"""

    if additional_instructions.strip():
        formatted_prompt += f"- Additional instructions: {additional_instructions}\n"

    formatted_prompt += """
Formatting instructions:
- Answer in the same language as the research question unless asked otherwise.
- Only call final_answer in a later step, after the search results have been printed and read.
- The final answer must be a Markdown string that starts with the heading "# Deep Research Report"
  followed by these "##" sections in this order. The text after each colon DESCRIBES the
  required content; it is NOT text to copy and MUST NOT be reproduced literally:
  - "## Overview": a synthesis that directly answers the research question.
  - "## Academic Evidence": the findings from each returned arXiv paper, with its title, authors, and year.
  - "## Web Evidence": the findings from each returned web result, with its page title.
  - "## Synthesis": agreements, differences, or complementary information across the two source types, and any gaps in the evidence.
  - "## Sources": a "### Academic Sources" numbered list (title and arXiv URL) and a "### Web Sources" numbered list (title and URL).
- Do not repeat, quote, or reproduce the report template or placeholder instructions. Replace every section with substantive content derived from the retrieved sources.
- Do not include Python representations such as lists or dictionaries in the final answer.
- Do not include internal reasoning or execution details in the final answer.
"""

    try:
        result = deep_research_agent.run(formatted_prompt)
        result_text = str(result)
        api_key = os.getenv("SERPAPI_API_KEY")
        if api_key:
            result_text = result_text.replace(api_key, "[REDACTED]")
        return result_text

    except Exception as e:
        error_text = str(e)
        api_key = os.getenv("SERPAPI_API_KEY")

        # Never show the API key in the UI
        if api_key:
            error_text = error_text.replace(api_key, "[REDACTED]")

        return f"### Deep Research Error\n\n```text\n{error_text}\n```"

# ---------------------------------------------------------
# Gradio Interface
# ---------------------------------------------------------

with gr.Blocks(
    title="Autonomous arXiv Research Agent"
) as demo:

    gr.Markdown(
        """
        # Autonomous arXiv Research Agent

        Search, read, and analyze academic papers from arXiv,
        or run multi-source Deep Research across arXiv and the web.
        """
    )

    with gr.Tab("arXiv Research — Original Lab"):

        gr.Markdown(
            "Search, read, and analyze academic papers from arXiv."
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


    # -----------------------------------------------------
    # Deep Research tab (extension)
    # -----------------------------------------------------

    with gr.Tab("Deep Research — Extended Multi-Source Research"):

        gr.Markdown(
            "Combine **arXiv academic papers** with **web search results** "
            "(via SerpAPI) into a single synthesized research report."
        )

        dr_question = gr.Textbox(
            label="Research Question",
            placeholder=(
                "E.g., How are AI agents being used in scientific research?"
            )
        )

        with gr.Row():

            dr_num_papers = gr.Slider(
                minimum=1,
                maximum=3,
                value=2,
                step=1,
                label="Number of Academic Papers"
            )

            dr_num_web = gr.Slider(
                minimum=1,
                maximum=5,
                value=3,
                step=1,
                label="Number of Web Results"
            )

        dr_depth = gr.Radio(
            choices=["Quick", "Detailed"],
            value="Quick",
            label="Research Depth"
        )

        dr_instructions = gr.Textbox(
            label="Additional Instructions (Optional)",
            placeholder=(
                "E.g., Focus on practical applications."
            ),
            lines=2
        )

        dr_button = gr.Button(
            "Deep Research"
        )

        dr_output = gr.Markdown(
            label="Deep Research Report"
        )

        dr_button.click(
            fn=deep_research,
            inputs=[
                dr_question,
                dr_num_papers,
                dr_num_web,
                dr_depth,
                dr_instructions
            ],
            outputs=dr_output
        )


# ---------------------------------------------------------
# Launch
# ---------------------------------------------------------

demo.launch()
