# RAG Research Chatbot Template

A **citation-verified research assistant chatbot** that answers questions using your own documents -- PDFs, Word files, spreadsheets, datasets, and more. Every answer cites its sources with numbered references, and a 6-layer verification system ensures the chatbot never makes things up.

**Built for researchers.** No coding experience required. You provide your documents, choose an AI provider, and the chatbot does the rest.

---

## Table of Contents

- [What This Does](#what-this-does)
- [Prerequisites](#prerequisites)
- [Installation (Step by Step)](#installation-step-by-step)
- [Supported File Formats](#supported-file-formats)
- [Using the Chatbot](#using-the-chatbot)
  - [Terminal Interface (CLI)](#terminal-interface-cli)
  - [Web Interface](#web-interface)
- [How It Works](#how-it-works)
- [SQL Layer: Structured Data Queries](#sql-layer-structured-data-queries)
- [KB Self-Awareness: The Meta Overview](#kb-self-awareness-the-meta-overview)
- [Anti-Hallucination: How the Chatbot Stays Honest](#anti-hallucination-how-the-chatbot-stays-honest)
- [Configuration Reference](#configuration-reference)
- [Docker (Optional)](#docker-optional)
- [Advantages and Limitations](#advantages-and-limitations)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## What This Does

You give the chatbot a collection of research documents (journal articles, datasets, reports, codebooks). When you ask a question, it:

1. **Knows what it knows** -- during ingestion, the chatbot builds a meta-overview of its entire knowledge base so it can answer questions like "What data do you have?" and contextualize every answer within the bigger picture
2. **Searches your documents** for relevant passages using vector similarity
3. **Queries your datasets** directly using SQL for filtering, aggregation, and lookups
4. **Optionally searches the web** for supplementary academic papers (via Semantic Scholar)
5. **Generates an answer** grounded only in the retrieved sources
6. **Cites every claim** with numbered endnote references (e.g., `[1]`, `[2]`)
7. **Verifies the answer** against the sources before showing it to you

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

1. **Python 3.11--3.13** installed on your computer (Python 3.14+ is **not supported** due to dependency compatibility)
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
cd path/to/chatbotsample_api
```

### 2. Set up a Python environment

We recommend using a conda environment with **Python 3.12** (the most widely compatible version). Python 3.14+ is **not supported** due to dependency compatibility issues.

```bash
conda create -n chatbot python=3.12 -y
conda activate chatbot
```

If you don't use conda, any Python 3.11--3.13 installation will work.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

This installs all the libraries the chatbot needs (AI providers, document readers, the vector database, etc.). It may take a few minutes.

> **Tip:** If `pip` doesn't work, try `pip3` instead. On some systems, Python 3 uses `pip3`.

### 4. Run the setup wizard

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

### 5. Add your documents

Copy your research files into the `knowledge_base/` folder. You can organize them into subfolders:

```
knowledge_base/
  NAVCO 2.0/
    NAVCO2JPRcodebook2013.pdf
    navco2_dataset.csv
  Survey Data/
    responses.xlsx
    codebook.docx
  notes.txt
```

### 6. Ingest (index) your documents

```bash
python ingest.py
```

This reads all your files, splits them into searchable chunks, and stores them in a local vector database. Tabular files (CSV, Excel, Stata, SPSS, R data) are also loaded into a local SQLite database for structured queries. You only need to re-run this when you add, remove, or change documents.

```
Found 5 files across 2 dataset(s):

  NAVCO 2.0: 3 files (.csv, .pdf)
  Survey Data: 2 files (.docx, .xlsx)

Processing: NAVCO 2.0/Chenoweth_Stephan_2011.pdf
  -> 47 chunks
Processing: NAVCO 2.0/NAVCO2JPRcodebook2013.pdf
  -> 12 chunks
...

Ingesting 2 tabular file(s) into SQLite...
  SQL: navco_2_0__navco2_dataset_csv (15234 rows, 12 columns)
  SQL: survey_data__responses_xlsx (500 rows, 8 columns)
SQL ingestion complete: 2 table(s).

Generating knowledge base overview...
KB overview generated and indexed.

Ingestion complete: 89 chunks from 5 files.
```

### 7. Start the chatbot

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

> **Note on datasets:** Tabular files (`.csv`, `.tab`, `.tsv`, `.xlsx`, `.xls`, `.dta`, `.sav`, `.rds`, `.rda`) get **dual ingestion**: they are stored in both the vector database (for conceptual questions like "what does PTS measure?") and a local SQLite database (for structured queries like "PTS scores for China" or "how many countries are in the dataset?"). The SQL layer handles filtering, aggregation, and precise lookups that vector search cannot do. For very large datasets (100,000+ rows), ingestion will be slow. Consider using a representative subset.

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
 1. UNDERSTAND -- The AI reformulates your question for better search
                -- Has full awareness of the KB contents (via meta overview)
                -- Expands abbreviations, resolves follow-up references
                -- May ask a clarification question if genuinely ambiguous
                -- Routes to vector search, SQL, or both
        |
        v
 2. RETRIEVE -- route="vector": search your local vector database
              -- route="sql": run a SQL query against your datasets
              -- route="both": run both, merge results
              -- Fallback: if the chosen path returns nothing, try the other
              -- Optionally search Semantic Scholar for academic papers
        |
        v
 3. GENERATE -- Send the question + retrieved passages to the AI model
              -- System prompt includes KB overview for broader context
              -- System prompt enforces strict citation rules
        |
        v
 4. VERIFY  -- Scan for warning phrases ("based on my knowledge...")
             -- Check that cited claims overlap with source text
             -- Ask the AI to audit its own answer against the sources
             -- If errors found: correct and re-verify (up to 3 times)
             -- If still failing: refuse to answer
        |
        v
 5. DISPLAY -- Show the verified answer with numbered references
```

**Key design principles:**

- **Your documents always come first.** Local sources (both vector search results and SQL query results) are the primary authority. Web sources (if enabled) are supplementary and never override your documents.
- **No sources = no answer.** If the chatbot cannot find relevant passages in your documents or the web, it will say so rather than make something up.
- **Smart query routing.** The chatbot automatically decides how to search: conceptual questions go to vector search, data lookups go to SQL, and mixed questions use both. If one path returns nothing, it falls back to the other.
- **Smart query understanding.** Before searching, the chatbot reformulates your question to improve retrieval accuracy -- expanding abbreviations, resolving references from prior conversation, and adding relevant keywords. It shows you what it searched for, so you can see how your question was interpreted.
- **Self-aware.** The chatbot knows what's in its knowledge base. Ask "What data do you have?" and it will tell you, instead of refusing because it can't find a matching chunk.
- **Every claim gets a citation.** The answer format uses numbered endnotes (`[1]`, `[2]`, etc.) with a full reference list at the bottom.
- **Direct quotes are marked.** When the chatbot uses three or more consecutive words from a source, they appear in quotation marks.

---

## SQL Layer: Structured Data Queries

When you ingest tabular files (CSV, Excel, Stata, SPSS, R data), they are loaded into a local SQLite database alongside the vector database. This enables questions that vector search cannot handle:

| Question type | Example | Route |
|---------------|---------|-------|
| Specific data lookup | "What are the PTS scores for China along the years?" | SQL |
| Aggregation / counting | "How many countries are in the dataset?" | SQL |
| Data comparison | "Compare GDP of China and India in 2020" | SQL |
| Conceptual / definitional | "What does PTS measure?" | Vector |
| Mixed (concept + data) | "Explain the PTS methodology and show China's scores" | Both |

**How it works:**

1. During ingestion, the chatbot reads the table structure (column names, types, row counts) and saves a schema registry
2. When you ask a question, the AI sees the available table schemas and decides whether to use SQL, vector search, or both
3. For SQL queries, the AI generates a SQLite SELECT statement, which is validated (SELECT-only, no semicolons) and executed against a read-only database connection
4. SQL results are formatted as context and fed into the same verification pipeline as vector search results

**Safety:** SQL injection is prevented by two layers: (1) queries must be a single SELECT statement with no semicolons, and (2) the SQLite connection is opened in read-only mode.

**Graceful degradation:** If no tabular files are ingested, the SQL layer is silently skipped and the chatbot works identically to a vector-only system. If a SQL query fails or returns no results, the chatbot falls back to vector search.

---

## KB Self-Awareness: The Meta Overview

A common problem with RAG chatbots is that they don't know what they know. If you ask "What data do you have?" or "What datasets are available?", a typical vector-search chatbot returns nothing -- because abstract meta-questions don't match any specific document chunk.

This chatbot solves that problem with a **KB meta overview** -- an LLM-generated high-level summary of the entire knowledge base that is produced automatically during ingestion. The overview describes what documents and tables exist, what topics they cover, and how they connect.

**How the meta overview is used:**

1. **Answering meta-questions.** The overview is stored as a special chunk in the vector database, so questions like "What is in the knowledge base?" find it through normal vector search and get a real answer instead of a refusal.
2. **Smarter query routing.** The query understanding layer sees the full overview, so it knows what's available when deciding how to reformulate and route your question (vector, SQL, or both).
3. **Better-contextualized answers.** When generating any response, the AI has the "big picture" of the knowledge base alongside the specific retrieved passages. This helps it say things like "the PTS dataset, one of three datasets in the knowledge base, shows..." instead of answering in isolation.

**Graceful degradation:** If the LLM is unavailable during ingestion, the overview falls back to a structured file listing (deterministic, no LLM needed). If the overview file is missing entirely (e.g., first run before ingestion), the chatbot works identically to a system without the feature -- no errors, no impact. The overview regenerates automatically every time you run `python ingest.py`.

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
  top_k: 50                        # Candidate pool cap for vector search
  max_distance: 0.55               # Relevance threshold (0=identical, 1=unrelated)

web_search:
  enabled: true                    # true | false
  backend: "semantic_scholar"      # Search engine for academic papers
  max_results: 5                   # Papers to retrieve per query

query_understanding:
  enabled: true                    # Set to false to skip query reformulation
  max_history: 6                   # Conversation messages used for context
  max_clarifications: 1            # Max clarification rounds before forcing a search

verification:
  enabled: true                    # Set to false to skip verification (faster but riskier)
  max_iterations: 3                # Max correction attempts before refusing
  strict_mode: true                # true = refuse on failure; false = show with warning

sql:
  enabled: true                    # Set to false to disable SQL layer entirely
  max_rows: 200                    # Max rows returned per SQL query (prevents context overflow)

paths:
  knowledge_base: "knowledge_base" # Where your documents live
  vector_db: "chroma_db"           # Where the vector database is stored
  sql_db: "sql_db"                 # Where the SQLite database and schema registry are stored
```

### .env

Your API key. Never share this file or commit it to GitHub.

```
OPENAI_API_KEY=sk-...
```

You can also set API keys as environment variables in your terminal instead of using the `.env` file.

### Choosing a Model

Better models are more expensive!

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

The container mounts your `knowledge_base/`, `chroma_db/`, `sql_db/`, `config.yaml`, and `.env` as volumes, so your data stays on your computer. API keys can also be passed as environment variables.

---

## Advantages and Limitations

### Advantages

- **No hallucination by design.** The 6-layer verification stack catches unsupported claims before they reach you. If the chatbot can't verify an answer, it refuses rather than guessing. This is critical for research where accuracy matters.
- **Full citation trail.** Every factual claim is tied to a specific source with page numbers or URLs. You can trace any claim back to the original document and verify it yourself.
- **Works with your own documents.** Unlike general-purpose chatbots, this one answers from *your* knowledge base. Your PDFs, datasets, and codebooks are the primary authority.
- **Knows what it knows.** The chatbot builds a meta-overview of its entire knowledge base during ingestion. It can answer meta-questions like "What datasets do you have?" and contextualizes every answer within the broader picture. This is unlike typical RAG systems that are blind to their own contents.
- **Structured data queries.** Ask questions like "PTS scores for China along the years" or "how many countries are in the dataset?" and the chatbot queries your datasets directly using SQL -- no more imprecise vector search over tabular data.
- **Reads 15 file formats.** Handles the formats social scientists actually use: Stata `.dta`, SPSS `.sav`, R `.rds`/`.rda`, Excel, CSV, PDF, Word, and plain text. No file conversion needed.
- **No data leaves your computer (except to the AI provider).** Your documents are stored locally in a vector database and SQLite database on your own machine. They are not uploaded to any cloud storage. Only the relevant text chunks or query results are sent to the AI provider as part of each query.
- **Swappable AI providers.** Switch between OpenAI, Anthropic, and Google Gemini without changing your documents or setup. Use whatever provider your institution has access to.
- **Web search augmentation.** Optionally supplement your local documents with academic papers from Semantic Scholar. Local sources always take priority.
- **Two interfaces.** Use the terminal for quick queries or the web UI for a more visual experience. Both share the same backend.
- **Open source and extensible.** The registry pattern makes it straightforward to add new file formats, AI providers, or search backends by writing a single file and adding one line to the registry.

### Limitations

- **Requires an API key (costs money).** The chatbot relies on commercial AI providers. Each question costs a small amount (fractions of a cent to a few cents), and the verification loop multiplies this by 2--4x per question.
- **Not a replacement for reading your sources.** The chatbot summarizes and cites, but it cannot replace careful reading of original documents. Always verify critical findings by checking the cited pages yourself.
- **Quality depends on your documents.** The chatbot can only work with what you give it. If your knowledge base is incomplete, the answers will be incomplete. If a PDF has poor text extraction (e.g., scanned images without OCR), those pages will be missing.
- **Scanned PDFs are not supported.** The PDF reader extracts text from digitally-created PDFs. If your PDFs are scanned images (common with older journal articles), you will need to run OCR software (like Adobe Acrobat or the free tool `ocrmypdf`) on them first.
- **Large datasets are slow to ingest.** For datasets with 100,000+ rows, the ingestion step will be slow. The SQL layer handles structured queries efficiently once ingested, but the initial loading takes time. Consider using a representative sample for very large files.
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
