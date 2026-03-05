# RAG Research Chatbot Template

A **citation-verified research assistant chatbot** that answers questions using your own documents -- PDFs, Word files, spreadsheets, datasets, and more. Every answer cites its sources with numbered references, and a 6-layer verification system ensures the chatbot never makes things up.

**Built for researchers.** No coding experience required. You provide your documents, choose an AI provider, and the chatbot does the rest.

---

## Table of Contents

- [What This Does](#what-this-does)
- [Prerequisites](#prerequisites)
- [Installation (Step by Step)](#installation-step-by-step)
- [Quick Start Guide](#quick-start-guide)
- [Supported File Formats](#supported-file-formats)
- [Using the Chatbot](#using-the-chatbot)
  - [Terminal Interface (CLI)](#terminal-interface-cli)
  - [Web Interface](#web-interface)
- [How It Works](#how-it-works)
- [Anti-Hallucination: How the Chatbot Stays Honest](#anti-hallucination-how-the-chatbot-stays-honest)
- [Configuration Reference](#configuration-reference)
- [Docker (Optional)](#docker-optional)
- [Advantages and Limitations](#advantages-and-limitations)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## What This Does

You give the chatbot a collection of research documents (journal articles, datasets, reports, codebooks). When you ask a question, it:

1. **Searches your documents** for relevant passages using vector similarity
2. **Optionally searches the web** for supplementary academic papers (via Semantic Scholar)
3. **Generates an answer** grounded only in the retrieved sources
4. **Cites every claim** with numbered endnote references (e.g., `[1]`, `[2]`)
5. **Verifies the answer** against the sources before showing it to you

If the chatbot cannot find relevant information in your documents, it **refuses to answer** rather than guessing. This is by design -- an incomplete answer is always better than a fabricated one.

### Example Output

```
Nonviolent campaigns succeeded approximately 53% of the time between
1900 and 2006, compared to 26% for violent insurgencies. [1] As stated
in [1]: "nonviolent resistance campaigns were nearly twice as likely
to achieve full or partial success."

Campaigns that achieved large-scale, diverse participation were
significantly more likely to succeed. [1][2] The NAVCO 2.0 codebook
classifies primary resistance methods including protests, strikes,
boycotts, and other forms of noncooperation. [2] Security force
defections were also identified as a key mechanism linking mass
participation to campaign success. [3]

**References**

**Local Sources (Primary):**
[1] Chenoweth_Stephan_2011.pdf (p. 23)
    -- knowledge_base/NAVCO 2.0/Chenoweth_Stephan_2011.pdf
[2] NAVCO2JPRcodebook2013.pdf (p. 7)
    -- knowledge_base/NAVCO 2.0/NAVCO2JPRcodebook2013.pdf

**Web Sources (Supplementary):**
[3] Nepstad, S.E. (2011). "Nonviolent Revolutions: Civil Resistance
    in the Late 20th Century."
    DOI: https://doi.org/10.1093/acprof:oso/9780199778201.001.0001
```

---

## Prerequisites

Before you begin, you will need:

1. **Python 3.11 or later** installed on your computer
   - **Mac**: Open Terminal and type `python3 --version`. If you don't have Python, download it from [python.org](https://www.python.org/downloads/)
   - **Windows**: Download from [python.org](https://www.python.org/downloads/). During installation, check the box that says "Add Python to PATH"
2. **An API key** from one of these AI providers (you only need one):
   - [OpenAI](https://platform.openai.com/api-keys) (GPT-4o, GPT-4.1)
   - [Anthropic](https://console.anthropic.com/) (Claude Sonnet, Claude Opus)
   - [Google](https://aistudio.google.com/apikey) (Gemini 2.5 Pro, Gemini 2.5 Flash)

> **Cost note:** These AI providers charge per query. A typical research session (50--100 questions) costs roughly $0.50--$5.00 depending on the model you choose. Smaller models (GPT-4o-mini, Claude Haiku, Gemini Flash) are significantly cheaper.

---

## Installation (Step by Step)

### 1. Download the project

If you have `git` installed:

```bash
git clone https://github.com/LIANJie-Jason/chatbotsample_api.git
cd chatbotsample_api
```

If you don't have `git`, download the ZIP file from GitHub and unzip it. Then open a terminal and navigate to the unzipped folder:

```bash
cd path/to/rag-research-chatbot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

This installs all the libraries the chatbot needs (AI providers, document readers, the vector database, etc.). It may take a few minutes.

> **Tip:** If `pip` doesn't work, try `pip3` instead. On some systems, Python 3 uses `pip3`.

### 3. Run the setup wizard

```bash
python setup.py
```

The wizard walks you through five questions:

| Step | What it asks | What to enter |
|------|-------------|---------------|
| 1 | Bot name | Whatever you like (e.g., "My Research Assistant") |
| 2 | Domain | A short description of your topic (e.g., "political science") |
| 3 | LLM provider | Choose OpenAI, Anthropic, or Google Gemini |
| 3b | API key | Paste your API key (it will be hidden as you type) |
| 4 | Model | Pick from the list of available models |
| 5 | Web search | Whether to also search Semantic Scholar for papers |

The wizard creates two files:
- `config.yaml` -- your chatbot's settings
- `.env` -- your API key (kept private, never uploaded to GitHub)

### 4. Add your documents

Copy your research files into the `knowledge_base/` folder. You can organize them into subfolders:

```
knowledge_base/
  NAVCO 2.0/
    Chenoweth_Stephan_2011.pdf
    NAVCO2JPRcodebook2013.pdf
    navco2_dataset.csv
  Survey Data/
    responses.xlsx
    codebook.docx
  notes.txt
```

### 5. Ingest (index) your documents

```bash
python ingest.py
```

This reads all your files, splits them into searchable chunks, and stores them in a local vector database. You only need to re-run this when you add, remove, or change documents.

```
Found 5 files across 2 dataset(s):

  NAVCO 2.0: 3 files (.csv, .pdf)
  Survey Data: 2 files (.docx, .xlsx)

Processing: NAVCO 2.0/Chenoweth_Stephan_2011.pdf
  -> 47 chunks
Processing: NAVCO 2.0/NAVCO2JPRcodebook2013.pdf
  -> 12 chunks
...

Ingestion complete: 89 chunks from 5 files.
```

### 6. Start the chatbot

**Terminal interface** (recommended for getting started):

```bash
python app_cli.py
```

**Web interface** (browser-based, with a sidebar for settings):

```bash
streamlit run app_web.py
```

---

## Supported File Formats

The chatbot can read **15 file types** commonly used in social science research:

| Extension | Format | What it reads |
|-----------|--------|---------------|
| `.pdf` | PDF documents | Full text from each page |
| `.docx` | Word documents | All paragraphs |
| `.xlsx` | Excel (modern) | All sheets, row by row with column headers |
| `.xls` | Excel (legacy) | Same as .xlsx |
| `.csv` | Comma-separated | Row by row with column headers |
| `.tab` | Tab-separated | Row by row with column headers |
| `.tsv` | Tab-separated | Same as .tab |
| `.dta` | Stata data files | Variable labels + data rows |
| `.sav` | SPSS data files | Variable labels + data rows |
| `.rds` | R single-object files | Data frame contents |
| `.rda` | R workspace files | All data frames in the workspace |
| `.txt` | Plain text | Full file contents |
| `.md` | Markdown | Full file contents |
| `.json` | JSON | Full file contents |
| `.do` | Stata do-files | Full script contents (treated as text) |

> **Note on datasets:** For `.dta`, `.sav`, `.rds`, `.rda`, `.xlsx`, and `.csv` files, the chatbot reads the actual data values row by row. This means you can ask questions like "How many observations have country = India?" and the chatbot will look through the data to answer. For very large datasets (100,000+ rows), ingestion will be slow and the vector database will be large. Consider using a representative subset.

---

## Using the Chatbot

### Terminal Interface (CLI)

```bash
python app_cli.py
```

Type your question at the `You>` prompt. The chatbot searches your documents, generates a verified answer, and displays it with citations.

**Available commands:**

| Command | What it does |
|---------|-------------|
| `/help` | Show all commands |
| `/sources` | Show detailed source list from the last answer |
| `/ingest` | Re-index your documents (after adding new files) |
| `/model` | Switch to a different AI model |
| `/websearch on` | Turn on web search (Semantic Scholar) |
| `/websearch off` | Turn off web search |
| `/quit` | Exit the chatbot (also: `/exit`, `/q`) |

**Response status indicators:**

| Status | Meaning |
|--------|---------|
| Verified | The answer passed all verification checks |
| Verification failed | The answer could not be fully verified -- read with caution |
| Refused | The chatbot could not find relevant sources and declined to guess |

### Web Interface

```bash
streamlit run app_web.py
```

This opens a browser window with:

- **Sidebar** (left): Change AI provider, switch models, toggle web search, see how many document chunks are indexed, and re-ingest documents
- **Chat area** (center): Type questions and see answers with full citations
- **Footer**: Reminder that all answers are sourced from your knowledge base

Changes you make in the sidebar (switching models, toggling web search) apply only to the current session. They do not overwrite your `config.yaml`.

---

## How It Works

```
You ask a question
        |
        v
 1. RETRIEVE -- Search your local vector database for relevant passages
              -- Optionally search Semantic Scholar for academic papers
        |
        v
 2. GENERATE -- Send the question + retrieved passages to the AI model
              -- System prompt enforces strict citation rules
        |
        v
 3. VERIFY  -- Scan for warning phrases ("based on my knowledge...")
             -- Check that cited claims overlap with source text
             -- Ask the AI to audit its own answer against the sources
             -- If errors found: correct and re-verify (up to 3 times)
             -- If still failing: refuse to answer
        |
        v
 4. DISPLAY -- Show the verified answer with numbered references
```

**Key design principles:**

- **Your documents always come first.** Local sources are the primary authority. Web sources (if enabled) are supplementary and never override your documents.
- **No sources = no answer.** If the chatbot cannot find relevant passages in your documents or the web, it will say so rather than make something up.
- **Every claim gets a citation.** The answer format uses numbered endnotes (`[1]`, `[2]`, etc.) with a full reference list at the bottom.
- **Direct quotes are marked.** When the chatbot uses three or more consecutive words from a source, they appear in quotation marks.

---

## Anti-Hallucination: How the Chatbot Stays Honest

Large language models (like GPT-4 or Claude) sometimes generate plausible-sounding information that isn't true -- a problem researchers call "hallucination." This chatbot uses a **6-layer verification stack** to minimize that risk:

| Layer | Name | What it does | Cost |
|-------|------|-------------|------|
| **0** | No-source gate | If no relevant documents are found, the AI is **never called**. A fixed refusal message is returned instead. | Free |
| **1** | System prompt | The AI receives strict instructions: "NEVER use your training data. ONLY use the provided sources. If you can't find the answer, REFUSE." | Free |
| **2** | Response length cap | Short context = short answer. The AI is given a smaller token budget when few sources are found, reducing the opportunity to hallucinate. | Free |
| **3** | Self-verification loop | After generating an answer, a second AI call audits the response against the sources using a 9-point checklist. If errors are found, the answer is corrected and re-verified (up to 3 times). If it still fails, the chatbot refuses to answer. | 1--3 extra AI calls |
| **4** | Term-overlap check | For every cited claim, the system checks what fraction of words actually appear in the source text. Claims with less than 40% overlap are flagged. | Free (no AI call) |
| **5** | Warning-phrase scanner | Scans for phrases like "based on my knowledge" or "it is well known" that suggest the AI is drawing on its training data instead of your documents. | Free (no AI call) |

**Layers 4 and 5 produce advisory flags** -- they don't automatically reject the answer. Instead, their flags are passed to Layer 3 (the self-verification loop) so the AI can pay extra attention to those sections.

**What "strict mode" means:** When `strict_mode: true` (the default), the chatbot will refuse to answer if verification fails after all correction attempts. When `strict_mode: false`, it will show the answer with a warning instead.

---

## Configuration Reference

### config.yaml

Generated by the setup wizard. You can also edit it by hand.

```yaml
chatbot:
  name: "My Research Assistant"    # Display name
  domain: "political science"      # Topic description (used in system prompt)

llm:
  provider: "openai"               # openai | anthropic | gemini
  model: "gpt-4o"                  # Model name (from provider's catalog)
  temperature: 0.0                 # 0.0 = deterministic; higher = more creative
  max_tokens: 2048                 # Maximum response length

embeddings:
  provider: "local"                # local (free) | openai (better but costs money)
  openai_model: "text-embedding-3-small"   # Only used if provider is "openai"

retrieval:
  chunk_size: 1000                 # Characters per chunk (when splitting documents)
  chunk_overlap: 100               # Overlap between chunks (preserves context)
  top_k: 5                         # Number of chunks to retrieve per query

web_search:
  enabled: true                    # true | false
  backend: "semantic_scholar"      # Search engine for academic papers
  max_results: 5                   # Papers to retrieve per query

verification:
  enabled: true                    # Set to false to skip verification (faster but riskier)
  max_iterations: 3                # Max correction attempts before refusing
  strict_mode: true                # true = refuse on failure; false = show with warning

paths:
  knowledge_base: "knowledge_base" # Where your documents live
  vector_db: "chroma_db"           # Where the vector database is stored
```

### .env

Your API key. Never share this file or commit it to GitHub.

```
OPENAI_API_KEY=sk-...
```

You can also set API keys as environment variables in your terminal instead of using the `.env` file.

### Choosing a Model

| If you want... | Choose |
|----------------|--------|
| Best accuracy | GPT-4o, Claude Opus 4.6, Gemini 2.5 Pro |
| Lower cost | GPT-4o-mini, Claude Haiku 4.5, Gemini 2.5 Flash |
| Balance of both | GPT-4.1-mini, Claude Sonnet 4.6, Gemini 2.0 Flash |

You can switch models at any time using `/model` in the CLI or the sidebar dropdown in the web UI. No need to re-run the setup wizard.

---

## Docker (Optional)

If you prefer to run the chatbot in a container (useful for deployment or avoiding dependency conflicts):

```bash
# Build and start
docker-compose up --build

# Open the web UI
open http://localhost:8501
```

The container mounts your `knowledge_base/`, `chroma_db/`, `config.yaml`, and `.env` as volumes, so your data stays on your computer. API keys can also be passed as environment variables.

---

## Advantages and Limitations

### Advantages

- **No hallucination by design.** The 6-layer verification stack catches unsupported claims before they reach you. If the chatbot can't verify an answer, it refuses rather than guessing. This is critical for research where accuracy matters.
- **Full citation trail.** Every factual claim is tied to a specific source with page numbers or URLs. You can trace any claim back to the original document and verify it yourself.
- **Works with your own documents.** Unlike general-purpose chatbots, this one answers from *your* knowledge base. Your PDFs, datasets, and codebooks are the primary authority.
- **Reads 15 file formats.** Handles the formats social scientists actually use: Stata `.dta`, SPSS `.sav`, R `.rds`/`.rda`, Excel, CSV, PDF, Word, and plain text. No file conversion needed.
- **No data leaves your computer (except to the AI provider).** Your documents are stored locally in a vector database on your own machine. They are not uploaded to any cloud storage. Only the relevant text chunks are sent to the AI provider as part of each query.
- **Swappable AI providers.** Switch between OpenAI, Anthropic, and Google Gemini without changing your documents or setup. Use whatever provider your institution has access to.
- **Web search augmentation.** Optionally supplement your local documents with academic papers from Semantic Scholar. Local sources always take priority.
- **Two interfaces.** Use the terminal for quick queries or the web UI for a more visual experience. Both share the same backend.
- **Open source and extensible.** The registry pattern makes it straightforward to add new file formats, AI providers, or search backends by writing a single file and adding one line to the registry.

### Limitations

- **Requires an API key (costs money).** The chatbot relies on commercial AI providers. Each question costs a small amount (fractions of a cent to a few cents), and the verification loop multiplies this by 2--4x per question.
- **Not a replacement for reading your sources.** The chatbot summarizes and cites, but it cannot replace careful reading of original documents. Always verify critical findings by checking the cited pages yourself.
- **Quality depends on your documents.** The chatbot can only work with what you give it. If your knowledge base is incomplete, the answers will be incomplete. If a PDF has poor text extraction (e.g., scanned images without OCR), those pages will be missing.
- **Scanned PDFs are not supported.** The PDF reader extracts text from digitally-created PDFs. If your PDFs are scanned images (common with older journal articles), you will need to run OCR software (like Adobe Acrobat or the free tool `ocrmypdf`) on them first.
- **Large datasets are slow to ingest.** For datasets with 100,000+ rows, the ingestion step and the resulting vector database will be large. Consider using a representative sample or the codebook instead of the full dataset.
- **Verification is not perfect.** The self-verification loop significantly reduces hallucination but cannot eliminate it entirely. The term-overlap check (Layer 4) is a simple heuristic, not a semantic understanding check. Treat all AI-generated answers as drafts that require human review.
- **Single-user, single-session.** The chatbot runs locally on one computer. Chat history in the web UI is lost when you close the browser tab. There is no user authentication or multi-user support.
- **Internet required for AI calls.** Even though your documents are stored locally, every question requires an internet connection to reach the AI provider's API. The web search feature also requires internet access.
- **No GPU required.** The local embedding model (ChromaDB's default) runs on CPU. This is free but produces lower-quality embeddings than OpenAI's embedding models. You can upgrade to OpenAI embeddings in `config.yaml` if you want better retrieval accuracy (at additional cost).

---

## Troubleshooting

### "No supported files found"

Make sure your files are in the `knowledge_base/` folder (not a subfolder of a subfolder with no supported files). Check that your file extensions match one of the [supported formats](#supported-file-formats).

### "API key not set"

Run `python setup.py` again, or manually create a `.env` file in the project root:

```
OPENAI_API_KEY=sk-your-key-here
```

### "Failed to load config"

Run `python setup.py` to generate `config.yaml`, or check that the file exists in the project root.

### The chatbot keeps refusing to answer

This means it cannot find relevant passages in your documents. Try:
- Rephrasing your question with keywords that appear in your documents
- Adding more relevant documents to `knowledge_base/` and re-running `python ingest.py`
- Enabling web search (`/websearch on`) to supplement with academic papers

### PyPDF2 deprecation warning

You may see a warning about PyPDF2 being deprecated. This is cosmetic and does not affect functionality. A future update will replace it with the `pypdf` library.

### Ingestion is very slow

Large datasets (`.dta`, `.sav`, `.csv` with many rows) take time to process. Consider:
- Using a codebook or data dictionary instead of the full dataset
- Taking a random sample of rows
- Splitting very large files into smaller ones

---

## License

MIT -- see [LICENSE](LICENSE).
