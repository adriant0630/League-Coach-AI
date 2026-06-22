## League Coach AI

## Description
A retrieval-augmented generation (RAG) system that generates League of Legends champion strategy briefs 
which includes rune pages, gameplans, and matchup advice through real strategic content rather than 
relying purely on an LLM's parametric memory.

You give the system a champion, role, and matchup context, and instead of generating a strategy though
an LLM's memory, the system:
1. Retrieves real, relevant strategic content from a corpus scraped from the League of Legends Wiki
2. Passes that retrieved content to Claude as grounding context
3. Generates a structured strategy brief (gameplan, item path, rune suggestions, matchup notes)
   through real content

This project is a proof-of-concept for that architecture, demonstrated on a domain (League of Legends) 
where I could build, test, and iterate quickly, with real public data available. The goal was to build 
something I'd actually want to use, while making deliberate engineering choices that map onto the kind 
of system Larus builds: retrieval grounded in verified sources, structured generation, and visible data 
verifiability.

## Limitations
This corpus is built from the League Wiki's legacy /Strategy subpages. However, the strategy pages have
not been updated since 2019, so information may be outdated and it does not cover all the current 
champions. Addtionally, some champions have more info on the strategy page than others which affects the 
quality of the information generated.

## Setup

### 1. Clone and Install

```bash
git clone https://github.com/yourusername/LOL-Tool.git
cd LOL-Tool

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Set Up Supabase

1. Create a free Supabase project at https://supabase.com
2. In the **SQL Editor**, run [schemaInitialization.sql](schemaInitialization.sql) to:
   - Enable pgvector extension
   - Create `champion_chunks` table with 384-dim embedding column
   - Create HNSW index for fast similarity search
   - Create `match_chunks()` helper function

### 3. Populate the Database

Run the scraper and cleaner (if not already done):

```bash
python scraper/scrape.py           # Downloads raw wiki pages
python cleaner/clean.py             # Chunks and cleans the data
```

Then ingest the cleaned chunks with embeddings:

```bash
python ingest.py                   # Embeds and inserts into Supabase
```

### 4. Configure Environment

Create a `.env` file in the project root:

```env
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
ANTHROPIC_API_KEY=your-claude-api-key
```

Get these values from:
- **SUPABASE_URL**: Supabase dashboard → Settings → API → URL
- **SUPABASE_SERVICE_KEY**: Supabase dashboard → Settings → API → Service Role Key
- **ANTHROPIC_API_KEY**: https://console.anthropic.com/account/keys
