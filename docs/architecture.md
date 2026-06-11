# Architecture Overview

## System Design

Open Source Radar is a modular, event-driven pipeline that collects, filters, categorizes, and publishes open-source project ideas automatically.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Data Sources                             │
│  ┌─────────┐  ┌──────────┐  ┌──────────────┐  ┌─────────┐ │
│  │  GitHub  │  │  Reddit   │  │ Hacker News  │  │ Future  │ │
│  └────┬────┘  └────┬─────┘  └──────┬───────┘  └────┬────┘ │
└───────┼────────────┼───────────────┼───────────────┼──────┘
        │            │               │               │
        ▼            ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│                   Collector Layer                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  BaseCollector (abstract)                            │   │
│  │  ├─ GitHubCollector                                  │   │
│  │  ├─ RedditCollector                                  │   │
│  │  ├─ HackerNewsCollector                              │   │
│  │  └─ Extensible for new sources                       │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────┘
                          │ RawIdea[]
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Filter Layer                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Layer 1: HardRulesFilter                           │   │
│  │  ├─ Score thresholds (viral / minimum)               │   │
│  │  ├─ Quality score calculation                       │   │
│  │  └─ Bypasses AI for viral projects                   │   │
│  │                                                      │   │
│  │  Layer 2: AIEvaluator (for borderline ideas)         │   │
│  │  ├─ GeminiProvider (default)                         │   │
│  │  ├─ OpenAIProvider (configurable)                    │   │
│  │  ├─ AnthropicProvider (configurable)                 │   │
│  │  └─ Abstract AIProvider interface                   │   │
│  │                                                      │   │
│  │  Layer 3: Deduplicator                              │   │
│  │  ├─ Exact title matching                             │   │
│  │  ├─ Fuzzy title matching (thefuzz)                   │   │
│  │  ├─ URL matching                                     │   │
│  │  ├─ Source ID matching                               │   │
│  │  └─ Semantic similarity (sentence-transformers)      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────┘
                          │ ProcessedIdea[]
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  Categorization Layer                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  CategorizationEngine                                │   │
│  │  ├─ Technology matching (Python, JS, Rust, Go, etc)  │   │
│  │  ├─ Topic matching (Web, CLI, AI, DevOps, etc)       │   │
│  │  ├─ Difficulty inference (Beginner/Int/Advanced)      │   │
│  │  └─ Tech stack extraction                             │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Storage Layer                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  SQLite (via Database class)                         │   │
│  │  ├─ raw_ideas                                       │   │
│  │  ├─ processed_ideas                                 │   │
│  │  ├─ fingerprints (for dedup)                        │   │
│  │  ├─ alerts                                          │   │
│  │  └─ metrics                                         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  Publishing Layer                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  READMEGenerator                                    │   │
│  │  ├─ Generates structured README                      │   │
│  │  ├─ Organized by sections (AI, Web, Python, etc)     │   │
│  │  └─ Consistent entry formatting                      │   │
│  │                                                      │   │
│  │  GitHubPublisher                                     │   │
│  │  ├─ Publishes README.md via API                      │   │
│  │  ├─ Publishes data/ideas.json                        │   │
│  │  ├─ Creates GitHub issues for alerts                 │   │
│  │  └─ Dry-run mode for testing                         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Monitoring Layer                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  GrowthTracker                                       │   │
│  │  ├─ Computes total/daily metrics                     │   │
│  │  ├─ Category distribution tracking                   │   │
│  │  └─ Growth rate calculation                          │   │
│  │                                                      │   │
│  │  AlertManager                                        │   │
│  │  ├─ README size thresholds (warning/critical)        │   │
│  │  ├─ Total ideas thresholds                           │   │
│  │  ├─ GitHub issue creation                            │   │
│  │  └─ Email alerts (configurable)                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Design Decisions

### 1. Modular Architecture
Each component is independently testable, replaceable, and extensible. New data sources implement `BaseCollector`. New AI providers implement `AIProvider`. The pipeline orchestrator wires everything together.

### 2. SQLite for Storage
Chosen for zero-dependency operation. The schema supports full CRUD with indexes for efficient dedup lookups. Migration to PostgreSQL or similar is straightforward (the Database class is the only file that needs modification).

### 3. Three-Layer Filtering
- **Layer 1 (Hard Rules)**: Zero-cost filtering for obvious cases
- **Layer 2 (AI)**: Selective AI evaluation only for borderline ideas (saves API costs)
- **Layer 3 (Dedup)**: Multi-strategy deduplication prevents content repetition

### 4. AI Provider Abstraction
The `AIProvider` abstract base class allows swapping between Gemini (default), OpenAI, Anthropic, or local models without changing pipeline code.

### 5. Future-Proof Data Format
`data/ideas.json` is designed to power any frontend (Next.js, Astro, GitHub Pages) without architectural changes.

## Scaling Considerations

| Component | Scaling Strategy |
|-----------|-----------------|
| Collectors | Add async batching, pagination, parallel source collection |
| AI Evaluation | Batch API calls, implement caching, use cheaper models for low-confidence items |
| Storage | Migrate from SQLite to PostgreSQL for concurrent access |
| Publishing | Use webhooks instead of scheduled commits for real-time updates |
| Frontend | Add Full-Text Search, filtering, pagination via data/ideas.json |
