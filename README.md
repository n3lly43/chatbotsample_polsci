# RAG Research Chatbot Template

A **citation-verified research assistant chatbot** that answers questions using your own documents -- PDFs, Word files, spreadsheets, datasets, and more. Every answer cites its sources with numbered references, and a 7-layer verification system ensures the chatbot never makes things up.

**Built for social scientists.** Drop your documents in a folder, provide an API key, and get a research chatbot with strong anti-hallucination guardrails. No coding experience required.

---

## Why This Template

Most AI chatbots hallucinate freely -- they generate plausible-sounding answers with no source trail. That is unacceptable for research, grant deliverables, and public-facing tools where every claim must be traceable. This template solves that problem.

**What makes this different from ChatGPT, Perplexity, or off-the-shelf RAG tools:**

- **Your documents are the only authority.** The chatbot answers exclusively from your knowledge base. It cannot draw on its training data. If your documents don't cover the question, it refuses to answer.
- **Every claim is cited and verified.** A 7-layer verification stack audits every response before showing it to you. Unsupported claims get caught and corrected automatically.
- **It understands structured data.** Tabular files (Stata `.dta`, SPSS `.sav`, R `.rds`, CSV, Excel) are loaded into a SQL database. Ask "how many campaigns succeeded after 2000?" and the chatbot writes and executes a real SQL query against your data -- not a fuzzy text search.
- **It reads the formats social scientists actually use.** 15 file types including Stata, SPSS, R data, do-files, and codebooks.
- **It is a starting point, not a black box.** Every component is modular and documented. You can swap AI providers, add new file readers, change the verification logic, or extend the retrieval strategy. Fork it and make it yours.

### Who Is This For

| You are a... | You could use this for... |
|---|---|
| **Researcher** | A personal assistant that knows your entire literature collection and datasets. Ask it questions while writing, and every answer comes with page-level citations you can verify. |
| **PI or lab director** | A shared knowledge base chatbot for your research group. Load your lab's published papers, datasets, and codebooks so RAs and collaborators can query them conversationally. |
| **Grant applicant** | A deliverable for NSF, NIH, or foundation grants. "We will build an AI-powered research tool that..." -- this template gives you a working prototype with citation verification, dual retrieval, and a documented architecture you can describe in a proposal. |
| **Course instructor** | A teaching assistant chatbot grounded in your course readings. Students ask questions; the chatbot answers only from assigned materials with full citations. |
| **Policy organization** | A public-facing tool that lets stakeholders query your reports and data. The anti-hallucination stack ensures the chatbot never misrepresents your findings. |
| **Data repository maintainer** | A conversational interface to your datasets. Users can ask natural-language questions about variables, coverage, and summary statistics instead of reading codebooks. |

---

## Table of Contents

- [What This Does](#what-this-does)
- [Sample Design Logic](#sample-design-logic)
- [Prerequisites](#prerequisites)
- [Quick Start (Step by Step)](#quick-start-step-by-step)
- [Supported File Formats](#supported-file-formats)
- [Using the Chatbot](#using-the-chatbot)
  - [Terminal Interface (CLI)](#terminal-interface-cli)
  - [Web Interface](#web-interface)
- [How It Works: The Full Pipeline](#how-it-works-the-full-pipeline)
  - [Step 0: Ingestion](#step-0-ingestion--building-the-knowledge-base)
  - [Step 1: Query Understanding](#step-1-query-understanding)
  - [Step 2: Retrieval](#step-2-retrieval)
  - [Step 3: Response Generation](#step-3-response-generation)
  - [Step 4: Verification](#step-4-verification-7-layer-anti-hallucination-stack)
  - [Step 5: Display](#step-5-display)
- [Configuration Reference](#configuration-reference)
- [Docker (Optional)](#docker-optional)
- [Advantages and Limitations](#advantages-and-limitations)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## What This Does

You give the chatbot a collection of research documents (journal articles, datasets, codebooks). When you ask a question, it:

1. **Knows what it knows** -- during ingestion, the chatbot builds a meta-overview of its entire knowledge base so it can answer questions like "What datasets do you have?" and contextualize every answer within the bigger picture
2. **Understands your question** -- reformulates vague or follow-up queries for better search, asks for clarification when genuinely ambiguous, and routes to the right search strategy (vector search, SQL, or both)
3. **Searches your documents** for relevant passages using vector similarity
4. **Queries your datasets** directly using SQL for filtering, aggregation, and lookups
5. **Optionally searches the web** for supplementary academic papers (via Semantic Scholar)
6. **Generates an answer** grounded only in the retrieved sources
7. **Cites every claim** with numbered endnote references (e.g., `[1]`, `[2]`)
8. **Verifies the answer** against the sources before showing it to you

If the chatbot cannot find relevant information in your documents, it **refuses to answer** rather than guessing. This is by design -- an incomplete answer grounded in sources is always better than a fabricated one.

### Example

Suppose you have the **NAVCO 2.0** (Nonviolent and Violent Campaigns and Outcomes) dataset in your knowledge base -- the `.dta` file, its codebook PDF, and the original Chenoweth & Stephan (2011) publication. You ask:

> **You:** Why do nonviolent campaigns succeed more often than violent ones?

The chatbot searches your documents, verifies its answer, and responds:

```
Nonviolent campaigns succeeded approximately 53% of the time between
1900 and 2006, compared to 26% for violent insurgencies [1]. As stated
in [1]: "nonviolent resistance campaigns were nearly twice as likely to
achieve full or partial success."

The primary mechanism is participation advantage. Nonviolent campaigns
attract significantly larger and more diverse participation, which
increases the likelihood of security force defections -- a key
mediating factor in campaign success [1][2]. The NAVCO 2.0 dataset
codes campaigns along dimensions including primary resistance method,
peak membership, and security force defections [3].

**References**

**Local Sources (Primary):**
[1] Chenoweth_Stephan_2011.pdf, p. 23
    -- knowledge_base/NAVCO/Chenoweth_Stephan_2011.pdf
[2] Chenoweth_Stephan_2011.pdf, p. 46
    -- knowledge_base/NAVCO/Chenoweth_Stephan_2011.pdf
[3] NAVCO2JPRcodebook2013.pdf, p. 7
    -- knowledge_base/NAVCO/NAVCO2JPRcodebook2013.pdf
```

> **Note:** The 53% figure comes from Chenoweth & Stephan's publication, which draws on NAVCO 1.1 (covering 1900--2006). The NAVCO 2.0 dataset itself (1945--2006, 250 campaigns) uses a binary success coding (0/1) and shows a 62% nonviolent success rate. The chatbot cites the source it found -- the PDF -- so the number reflects the publication's analysis, not a live query.

You can also ask data questions directly:

> **You:** How many nonviolent campaigns succeeded after 2000?

```
Searching for: "nonviolent campaigns success prim_method year > 2000"
Using SQL query for structured data

According to the NAVCO 2.0 dataset, 8 nonviolent campaigns
(prim_method = 1) active after 2000 achieved success (success = 1)
out of 16 total nonviolent campaigns in that period [1].

**References**

**Local Sources (Primary):**
[1] SQL query on navco__navco_v2_0_dta
    -- knowledge_base/NAVCO/NAVCO v2.0.dta
```

---

## Sample Design Logic

> **This section is written as a design rationale** -- the kind of description you would include in a grant proposal, technical appendix, or project documentation to explain *why* the system is built the way it is. Feel free to adapt this language for your own proposals.

### The Problem

Large language models (LLMs) are powerful text generators, but they hallucinate: they produce fluent, confident statements that have no basis in fact. In a research context, this is not a minor inconvenience -- it is a disqualifying flaw. A chatbot that fabricates citations, invents statistics, or misrepresents findings is worse than useless; it actively undermines the scholarly record.

The core challenge is: **How do you harness the natural-language capabilities of LLMs while guaranteeing that every claim is grounded in verifiable source material?**

### Design Principle: Defense in Depth

This template treats anti-hallucination as a **systems problem**, not a prompt-engineering trick. No single technique reliably prevents hallucination. Instead, the system layers seven independent verification mechanisms so that a failure at any one layer is caught by another:

```
Layer 0  No-source gate         If retrieval finds nothing, the LLM is never called.
                                The user gets a refusal, not a guess. [FREE]

Layer 1  System prompt           Strict instructions: "Use ONLY the provided sources.
                                 Never draw on your training data." [FREE]

Layer 2  Response length cap     Shorter context → shorter answer → less room to
                                 hallucinate. Token limit scales with evidence. [FREE]

Layer 3  LLM self-verification   A second LLM call audits the response against the
                                 sources using a 10-point checklist. If it finds
                                 unsupported claims, the response is corrected and
                                 re-audited (up to 3 iterations). [1-3 LLM CALLS]

Layer 4  Term-overlap check      For each cited claim, measures what fraction of
                                 content words actually appear in the cited source.
                                 Flags claims with <40% overlap. [FREE]

Layer 4.5 Citation audit         Deterministic check: Do citation numbers exceed
                                  the number of available sources? Do References
                                  mention actual filenames from the knowledge base? [FREE]

Layer 5  Warning-phrase scanner  Scans for telltale phrases like "based on my
                                 knowledge" or "it is well known" that signal the
                                 LLM is drawing on training data. [FREE]
```

Layers 0, 1, 2, 4, 4.5, and 5 are **deterministic and free** -- they require no additional LLM calls. Layer 3 is the expensive layer (1--3 extra calls per query), but it is also the most powerful: it can catch subtle hallucinations that deterministic checks miss, and it can *correct* them in place.

This layered architecture means the system degrades gracefully. Even if Layer 3 (LLM verification) makes an error, Layers 4, 4.5, and 5 provide independent sanity checks. Even if all post-generation layers fail, Layer 0 guarantees the LLM was never called without evidence in the first place.

### Design Principle: Dual Retrieval for Mixed Questions

Social science research involves both **conceptual questions** ("What does the success variable mean?") and **data questions** ("How many campaigns succeeded after 2000?"). These require fundamentally different retrieval strategies:

| Question type | Retrieval strategy | Why |
|---|---|---|
| Conceptual | Vector similarity search against document chunks | Finds passages that are *semantically similar* to the question, even if they use different words |
| Data/quantitative | SQL query against structured tables | Exact filtering, aggregation, and counting -- things vector search cannot do |
| Mixed | Both, merged | "Explain the success coding and show success rates by decade" needs the codebook AND the data |

The query understanding layer uses the LLM to classify each question and route it to the right strategy. If the chosen strategy returns nothing, the system automatically falls back to the other. This dual path means a single chatbot can handle the full range of questions a researcher would ask about a dataset and its documentation.

### Design Principle: Schema Enrichment

Raw column names in datasets (e.g., `prim_method`, `sec_defect`, `success`) are meaningless to an LLM without context. During ingestion, the system:

1. **Detects codebook files** in the same directory as each dataset (files named "codebook", "dictionary", "readme", etc.)
2. **Reads the codebook** and passes it to the LLM along with column names, types, and sample values
3. **Generates human-readable descriptions** for each column (e.g., `success: Binary campaign outcome — 1 = success, 0 = failure`)
4. **Injects the enriched schema into every query understanding prompt** so the LLM writes correct SQL (using actual column names, valid value ranges, and proper data types)

This means the chatbot understands your data dictionary without you writing any configuration.

### Design Principle: Over-Refusal Prevention

A naive anti-hallucination system refuses to answer whenever it is not 100% certain. This makes it useless for exploratory research where partial answers are valuable. The system explicitly distinguishes between:

- **No relevant information found** → refuse (Layer 0)
- **Some relevant information found, but incomplete** → answer with what is available, cite it, and note the limitation

An incomplete answer grounded in three sources is more useful than a refusal when the user's documents *do* contain relevant information. The verification stack catches unsupported *claims*, not incomplete *coverage*.

### Adapting This Design for Your Project

This template is a **starting point**. Here are common ways to adapt it:

| Your goal | What to change |
|---|---|
| **Different domain** | Change `chatbot.domain` in config.yaml. The system prompt automatically adjusts. |
| **Stricter verification** | Increase `verification.max_iterations`, lower `retrieval.max_distance` (stricter relevance threshold) |
| **Faster responses** | Set `verification.strict_mode: false` (warn instead of refuse), use a faster model (GPT-4.1-mini, Gemini Flash) |
| **Larger datasets** | Increase `sql.max_rows`, switch to OpenAI embeddings for better retrieval quality |
| **New file format** | Add one reader function to `src/readers/`, add one line to the registry dict |
| **New AI provider** | Add one module to `src/llm/`, add one line to the registry dict |
| **Deploy to the web** | Use the Docker setup, or deploy `app_web.py` to Streamlit Cloud |
| **For a grant proposal** | Describe the 7-layer verification stack, dual retrieval, and schema enrichment as your technical approach. All three are implemented and tested. |

---

## Prerequisites

Before you begin, you will need:

1. **Python 3.11--3.13** installed on your computer (Python 3.14+ is **not supported** due to dependency compatibility)
   - **Mac**: Open Terminal and type `python3 --version`. If you don't have Python, download it from [python.org](https://www.python.org/downloads/)
   - **Windows**: Download from [python.org](https://www.python.org/downloads/). During installation, check the box that says "Add Python to PATH"
2. **An API key** from one of these AI providers (you only need one):
   - [OpenAI](https://platform.openai.com/api-keys) (GPT-4.1, GPT-4o)
   - [Anthropic](https://console.anthropic.com/) (Claude Sonnet 4.6, Claude Opus 4.6)
   - [Google](https://aistudio.google.com/apikey) (Gemini 2.5 Pro, Gemini 2.5 Flash)

> **Cost note:** These AI providers charge per query. A typical research session (50--100 questions) costs roughly $0.50--$5.00 depending on the model you choose. Smaller models (GPT-4.1-mini, Claude Haiku 4.5, Gemini Flash) are significantly cheaper.

---

## Quick Start (Step by Step)

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

| Step | What it asks | Example |
|------|-------------|---------|
| 1 | Bot name | "NAVCO Research Assistant" |
| 2 | Domain | "nonviolent and violent campaigns and outcomes" |
| 3 | LLM provider | Choose OpenAI, Anthropic, or Google Gemini |
| 3b | API key | Paste your API key (it will be hidden as you type) |
| 4 | Model | Pick from the list of available models |
| 5 | Web search | Whether to also search Semantic Scholar for papers |

The wizard creates two files:
- `config.yaml` -- your chatbot's settings
- `.env` -- your API key (kept private, never uploaded to GitHub)

If you run the wizard again, it will **merge** your new API key with any existing keys in `.env` rather than overwriting them, so you can safely add multiple providers over time.

### 5. Add your documents

Copy your research files into the `knowledge_base/` folder. You can organize them into subfolders:

```
knowledge_base/
  NAVCO/
    Chenoweth_Stephan_2011.pdf
    NAVCO2JPRcodebook2013.pdf
    NAVCO v2.0.dta
  notes.txt
```

### 6. Ingest (index) your documents

```bash
python ingest.py
```

This reads all your files, splits them into searchable chunks, and stores them in a local vector database. Tabular files (CSV, Excel, Stata, SPSS, R data) are also loaded into a local SQLite database for structured queries. You only need to re-run this when you add, remove, or change documents.

```
Found 3 files across 1 dataset(s):

  NAVCO: 3 files (.dta, .pdf)

Processing: NAVCO/Chenoweth_Stephan_2011.pdf
  -> 47 chunks
Processing: NAVCO/NAVCO2JPRcodebook2013.pdf
  -> 12 chunks
Processing: NAVCO/NAVCO v2.0.dta
  -> 681 chunks

Ingesting 1 tabular file(s) into SQLite...
  SQL: navco__navco_v2_0_dta (1726 rows, 57 columns)
SQL ingestion complete: 1 table(s).

Generating knowledge base overview...
KB overview generated and indexed.

Ingestion complete: 740 chunks from 3 files.
```

**What happens during ingestion:**

- **Document chunking**: PDFs, Word files, and text are split into overlapping chunks for vector search
- **Dual ingestion for tabular data**: CSV, Excel, Stata, SPSS, and R files are loaded into both the vector database (for conceptual questions like "what does success mean in NAVCO?") and a SQLite database (for structured queries like "how many campaigns succeeded?")
- **Schema enrichment**: The chatbot automatically detects codebooks (files named "codebook", "readme", "data dictionary", etc.) and uses them with LLM analysis to generate human-readable column descriptions for your datasets (e.g., `success: Binary campaign outcome — 1 = success, 0 = failure`)
- **KB meta overview**: An LLM-generated summary of the entire knowledge base, enabling the chatbot to answer meta-questions like "What data do you have?"

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

> **Note on datasets:** Tabular files (`.csv`, `.tab`, `.tsv`, `.xlsx`, `.xls`, `.dta`, `.sav`, `.rds`, `.rda`) get **dual ingestion**: they are stored in both the vector database (for conceptual questions) and a local SQLite database (for structured queries). The SQL layer handles filtering, aggregation, and precise lookups that vector search cannot do. Leading zeros in identifier columns (zip codes, FIPS codes) are automatically preserved as text. For very large datasets (100,000+ rows), ingestion will be slow -- consider using a representative subset.

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

## How It Works: The Full Pipeline

This section walks through what happens under the hood from the moment you add documents to the moment you see an answer. Every example uses the **NAVCO 2.0** project (the Nonviolent and Violent Campaigns and Outcomes dataset by Chenoweth & Stephan) as a running illustration.

```
  knowledge_base/                     chroma_db/         sql_db/
  ┌──────────────┐   python ingest.py  ┌──────────┐    ┌──────────┐
  │ PDFs, CSVs,  │ ──────────────────> │ Vector   │ +  │ SQLite   │
  │ codebooks... │     (Step 0)        │ Database │    │ Database │
  └──────────────┘                     └────┬─────┘    └────┬─────┘
                                            │               │
                                            v               v
  You ask a question ──> [UNDERSTAND] ──> [RETRIEVE] ──> [GENERATE] ──> [VERIFY] ──> Answer
                          (Step 1)        (Step 2)       (Step 3)      (Step 4)    (Step 5)
```

### Step 0: Ingestion — Building the Knowledge Base

Before you can ask questions, you run `python ingest.py` to build the knowledge base. Here is what happens:

| Phase | What happens | Example |
|-------|-------------|---------|
| **File reading** | Each file is read using a format-specific reader | `Chenoweth_Stephan_2011.pdf` → text from each page; `NAVCO v2.0.dta` → rows with headers |
| **Chunking** | Long documents are split into overlapping chunks (~1000 characters each) | The publication PDF becomes 47 searchable chunks |
| **Vector embedding** | Each chunk is converted to a numerical vector and stored in ChromaDB | Enables "find passages similar to my question" |
| **SQL loading** | Tabular files are loaded into SQLite with type detection and null handling | `NAVCO v2.0.dta` → table with 1726 rows, 57 columns, correct numeric types |
| **Schema enrichment** | Codebooks are detected; LLM generates column descriptions | `success` → "Binary campaign outcome — 1 = success, 0 = failure" |
| **KB meta overview** | An LLM-generated summary of everything in the knowledge base | "The knowledge base contains the NAVCO 2.0 dataset (250 campaigns, 1945–2006) with codebook and the Chenoweth & Stephan (2011) publication..." |

The meta overview is stored as a special chunk in the vector database AND injected into the system prompt, so the chatbot always knows what it has access to.

### Step 1: Query Understanding

Before searching, the chatbot uses the LLM to understand and optimize your question.

**What the QU layer does:**

| Capability | Example |
|------------|---------|
| **Reformulation** | "Why did it work?" → `"why do nonviolent campaigns succeed mechanisms participation"` (expands vague query into search-optimized keywords) |
| **Pronoun resolution** | After discussing NAVCO, "How many are in the dataset?" → `"how many campaigns are in the NAVCO 2.0 dataset"` (resolves "it" from conversation history) |
| **Clarification** | "Show me the data" → *"Do you mean the NAVCO 2.0 campaign data (NAVCO v2.0.dta) or the codebook (NAVCO2JPRcodebook2013.pdf)?"* (asks when genuinely ambiguous, using KB overview to offer specific options) |
| **SQL routing** | "How many campaigns succeeded after 2000?" → routes to SQL with query `SELECT COUNT(*) FROM navco__navco_v2_0_dta WHERE success = 1 AND year > 2000` |
| **Mixed routing** | "Explain what success means in NAVCO and count successful campaigns" → routes to BOTH vector (for the definition) and SQL (for the count) |

The QU layer produces two outputs:
- **`search_query`**: keyword-optimized for retrieval (sent to the vector database / SQL engine)
- **`display_query`**: a clear, well-formed question (sent to the response LLM)

If the reformulated query differs from your original, you will see: `Searching for: "nonviolent campaigns success mechanisms participation"`.

### Step 2: Retrieval

Based on the route chosen by Step 1, the chatbot searches for relevant information:

| Route | When used | How it works | Example |
|-------|-----------|-------------|---------|
| **Vector** | Conceptual questions, definitions, explanations | Finds the chunks most similar to your query in the vector database; keeps only chunks below a distance threshold (default 0.55) | "Why do nonviolent campaigns succeed?" → retrieves chunks from Chenoweth_Stephan_2011.pdf about participation and defection mechanisms |
| **SQL** | Data lookups, counts, filtering, aggregation | Executes a validated SELECT query against the SQLite database | "How many campaigns in NAVCO are coded as nonviolent?" → `SELECT COUNT(*) FROM ... WHERE camp_type = 1` |
| **Both** | Mixed questions needing both context and data | Runs vector search AND SQL, merges results | "Explain success coding and show success rates by decade" → codebook chunks + SQL aggregation |
| **Fallback** | When the chosen route returns nothing | Automatically tries the other route | SQL returns no rows → falls back to vector search |
| **Web** | When enabled, supplements local results | Queries Semantic Scholar for academic papers | Adds peer-reviewed papers when local sources are thin |

**Source priority:** Local documents = SQL results > Web sources. Web results never override your local documents.

### Step 3: Response Generation

The retrieved passages are assembled into a context block and sent to the LLM along with:

- A **system prompt** that enforces strict citation rules ("NEVER use your training data. ONLY use the provided sources.")
- The **KB meta overview** so the LLM knows the broader context of the knowledge base
- The **display query** (the clear, well-formed version of your question)

The system prompt tells the LLM to:
- Cite every factual claim with a numbered endnote `[1]`, `[2]`, etc.
- Put direct quotes (3+ consecutive words from a source) in quotation marks
- End with a References section listing all cited sources with file names, page numbers, or URLs
- Refuse to answer if the provided sources do not contain relevant information

A **soft token cap** limits response length proportionally to context size -- less context means shorter answers, reducing the surface area for hallucination.

### Step 4: Verification (7-Layer Anti-Hallucination Stack)

This is the core differentiator. Before showing you the answer, it passes through seven verification layers:

```
Layer 0: No-source gate
   │  If retrieval found nothing, the LLM is NEVER called.
   │  A fixed refusal message is returned. (Free)
   v
Layer 1: System prompt guardrails
   │  Strict instructions baked into every LLM call. (Free)
   v
Layer 2: Response length cap
   │  Short context → short answer → less room to hallucinate. (Free)
   v
Layer 3: LLM self-verification loop (up to 3 iterations)
   │  A second LLM call audits the response against the sources
   │  using a 10-point checklist. If errors are found, the response
   │  is corrected and re-verified. If it still fails after 3
   │  attempts, the chatbot refuses to answer. (1-3 extra LLM calls)
   v
Layer 4: Term-overlap check
   │  For every cited claim, checks what fraction of words actually
   │  appear in the source text. Flags claims with < 40% overlap
   │  as potentially ungrounded. (Free, no LLM call)
   v
Layer 4.5: Citation audit
   │  Checks that citation numbers [N] don't exceed actual source
   │  count and that the References section mentions filenames from
   │  retrieved sources. (Free, no LLM call)
   v
Layer 5: Warning-phrase scanner
      Scans for phrases like "based on my knowledge" or "it is well
      known" that suggest the LLM is using training data instead of
      your documents. (Free, no LLM call)
```

**Layers 4 and 5 produce advisory flags** -- they don't automatically reject the answer. Instead, their flags are passed to Layer 3 (the self-verification loop) so the LLM can pay extra attention to those sections.

**Strict mode** (default): The chatbot refuses to answer if verification fails after all correction attempts. **Non-strict mode**: Shows the answer with a warning instead.

### Step 5: Display

The verified answer is displayed with:
- The response text with numbered citations
- A **status indicator** (Verified / Verification failed / Refused)
- The **iteration count** (how many verification rounds it took)
- A **source summary** (e.g., "Sources: 3 local, 12 SQL rows -- type /sources for details")

**Example session with the NAVCO knowledge base:**

```
You> What datasets do you have?
  [Verified] (1 iteration)
  The knowledge base contains the NAVCO 2.0 dataset with 250 campaigns
  from 1945 to 2006, its codebook, and the Chenoweth & Stephan (2011)
  publication. [1]

You> What does the success variable mean?
  Searching for: "NAVCO 2.0 success variable coding definition"
  [Verified] (1 iteration)
  The success variable in NAVCO 2.0 is a binary indicator: 1 = the
  campaign achieved success, 0 = it did not. A campaign is coded as
  successful if it achieved its stated maximalist goals within a
  reasonable time frame of the campaign's peak [1][2].

You> How many succeeded?
  Searching for: "count campaigns by success outcome NAVCO 2.0"
  Using SQL query for structured data
  [Verified] (1 iteration)
  Of the 250 campaigns in the NAVCO 2.0 dataset: 111 succeeded
  (success = 1) and 138 did not (success = 0) [1].

You> What about nonviolent ones specifically?
  Searching for: "nonviolent campaigns success count NAVCO 2.0 prim_method = 1"
  Using SQL query for structured data
  [Verified] (1 iteration)
  Among the 109 nonviolent campaigns (prim_method = 1): 68 succeeded
  (62%) and 41 did not (38%) [1]. This is consistent with the finding
  in Chenoweth and Stephan (2011) that "nonviolent resistance campaigns
  were nearly twice as likely to achieve full or partial success" [2].
```

Notice how the chatbot:
- Resolves "How many succeeded?" using conversation history (knows you mean the success variable)
- Resolves "What about nonviolent ones?" as a follow-up to the previous count
- Routes data questions to SQL automatically
- Cites both the SQL query results and the PDF publication
- Shows you the reformulated search query for transparency

---

## Configuration Reference

### config.yaml

Generated by the setup wizard. You can also edit it by hand.

```yaml
chatbot:
  name: "NAVCO Research Assistant"   # Display name
  domain: "nonviolent and violent campaigns"  # Topic (used in system prompt)

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
  max_rows: 200                    # Max rows returned per SQL query

paths:
  knowledge_base: "knowledge_base" # Where your documents live
  vector_db: "chroma_db"           # Where the vector database is stored
  sql_db: "sql_db"                 # Where the SQLite database and schema registry live
```

### .env

Your API key. Never share this file or commit it to GitHub.

```
OPENAI_API_KEY="sk-..."
```

You can also set API keys as environment variables in your terminal instead of using the `.env` file.

### Choosing a Model

Better models produce more accurate answers but cost more per query. You can switch models at any time using `/model` in the CLI or the sidebar dropdown in the web UI -- no need to re-run the setup wizard.

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

**Anti-hallucination guardrails (the core differentiator):**

- **7-layer verification stack.** No single defense against hallucination is reliable. This system layers seven independent checks -- from a hard gate that prevents the LLM from being called without evidence, to deterministic citation audits, to an iterative LLM self-verification loop. A failure at any one layer is caught by another. See [Sample Design Logic](#sample-design-logic) for the full rationale.
- **Refuse rather than guess.** If retrieval finds zero relevant sources, the LLM is never called. The user gets a clear refusal, not a confident-sounding fabrication. This is Layer 0 and it is non-negotiable.
- **Iterative self-correction.** When the verification loop detects an unsupported claim, it doesn't just flag it -- it sends the response back to the LLM with specific instructions to fix the problem, then re-verifies. Up to 3 correction cycles ensure the final answer is grounded.
- **Full citation trail.** Every factual claim is tied to a specific source with page numbers or URLs. You can trace any claim back to the original document. Direct quotes are marked with quotation marks. The References section distinguishes local sources (primary) from web sources (supplementary).
- **Deterministic checks complement LLM checks.** Layers 4, 4.5, and 5 are purely algorithmic -- they cannot be fooled by fluent text. They catch citation number inflation, missing filenames in references, and telltale phrases that signal training-data leakage.

**Research capabilities:**

- **Works with your own documents.** Unlike general-purpose chatbots, this one answers from *your* knowledge base. Your PDFs, datasets, and codebooks are the primary authority.
- **Knows what it knows.** The chatbot builds a meta-overview during ingestion. Ask "What datasets do you have?" and it can answer, instead of refusing because no chunk matches.
- **Structured data queries.** Ask "how many nonviolent campaigns succeeded after 2000?" and the chatbot queries your dataset directly using SQL. Schema enrichment with automatic codebook detection means the AI understands what each column means.
- **Smart query understanding.** The chatbot reformulates questions for better search, resolves pronouns from conversation history, asks clarification when needed, and routes each query to the best search strategy.
- **Reads 15 file formats.** Handles the formats social scientists actually use: Stata `.dta`, SPSS `.sav`, R `.rds`/`.rda`, Excel, CSV, PDF, Word, and plain text.

**Practical benefits:**

- **No data leaves your computer (except to the AI provider).** Documents are stored locally. Only relevant text chunks are sent to the AI provider as part of each query.
- **Swappable AI providers.** Switch between OpenAI, Anthropic, and Google Gemini without changing your documents or setup.
- **Web search augmentation.** Optionally supplement local documents with academic papers from Semantic Scholar. Local sources always take priority.
- **Two interfaces.** Terminal for quick queries; web UI for a more visual experience. Both share the same backend.
- **Open source and extensible.** The registry pattern makes it easy to add new file formats, AI providers, or search backends. Fork it and adapt for your project.

### Limitations

- **Requires an API key (costs money).** Each question costs a small amount, and the verification loop multiplies this by 2--4x per question.
- **Not a replacement for reading your sources.** The chatbot summarizes and cites, but always verify critical findings by checking the cited pages yourself.
- **Quality depends on your documents.** If your knowledge base is incomplete, the answers will be incomplete. If a PDF has poor text extraction, those pages will be missing.
- **Scanned PDFs are not supported.** The PDF reader extracts text from digitally-created PDFs. For scanned images, run OCR software (like `ocrmypdf`) on them first.
- **Large datasets are slow to ingest.** For 100,000+ row datasets, consider using a representative sample.
- **Verification is not perfect.** The self-verification loop significantly reduces hallucination but cannot eliminate it entirely. Treat all AI-generated answers as drafts requiring human review.
- **Single-user, single-session.** Runs locally on one computer. No user authentication or multi-user support.
- **Internet required for AI calls.** Even though documents are stored locally, every question requires an internet connection to the AI provider.
- **No GPU required.** The local embedding model runs on CPU (free but lower quality). Upgrade to OpenAI embeddings in `config.yaml` for better retrieval accuracy at additional cost.

---

## Troubleshooting

### "No supported files found"

Make sure your files are in the `knowledge_base/` folder and that file extensions match one of the [supported formats](#supported-file-formats).

### "API key not set"

Run `python setup.py` again, or manually create a `.env` file in the project root:

```
OPENAI_API_KEY="sk-your-key-here"
```

### "Failed to load config"

Run `python setup.py` to generate `config.yaml`, or check that the file exists in the project root.

### The chatbot keeps refusing to answer

This means it cannot find relevant passages in your documents. Try:
- Rephrasing your question with keywords that appear in your documents
- Adding more relevant documents to `knowledge_base/` and re-running `python ingest.py`
- Enabling web search (`/websearch on`) to supplement with academic papers

### PDF reader

This project uses `pypdf` (successor to PyPDF2) for PDF extraction.

### Ingestion is very slow

Large datasets take time to process. Consider using a codebook instead of the full dataset, taking a random sample of rows, or splitting very large files.

---

## License

MIT -- see [LICENSE](LICENSE).
