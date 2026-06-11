# Future Web Migration Plan

## Overview

This document outlines the migration path from README-only publishing to a full web platform. The system is designed so that when the README exceeds size thresholds, the JSON API can seamlessly power a web frontend.

## Thresholds for Migration

| Stage | README Size | Ideas Count | Action |
|-------|------------|-------------|--------|
| Green | < 500 KB | < 1,500 | README-only (MVP) |
| Yellow | 500 KB - 1 MB | 1,500 - 3,000 | Generate JSON + README |
| Red | > 1 MB | > 3,000 | Switch to web platform |

## Architecture After Migration

```
┌──────────────────┐     ┌──────────────────┐
│   Pipeline       │ ──► │  data/ideas.json  │
│   (unchanged)    │     │  (static API)     │
└──────────────────┘     └────────┬─────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
           ┌─────────────────┐       ┌──────────────────┐
           │  GitHub Pages    │       │  Next.js / Astro  │
           │  (Static Site)   │       │  (Full App)       │
           └─────────────────┘       └──────────────────┘
```

## Phase 1: Static JSON API (Immediate)

Already implemented. `data/ideas.json` is generated daily and published to the repo.

### API Schema (data/ideas.json)
```json
[
  {
    "id": "uuid",
    "title": "Project Name",
    "category": ["Web Development", "Python"],
    "difficulty": "Intermediate",
    "tech_stack": ["Python", "Django"],
    "description": "Short description",
    "source": "github",
    "url": "https://...",
    "language": "Python",
    "stars": 150,
    "score": 150,
    "author": "username",
    "created_at": "2024-01-01T00:00:00"
  }
]
```

## Phase 2: GitHub Pages Frontend (Weeks 1-2)

### Tech Stack
- Astro (static site generation)
- Tailwind CSS
- GitHub Pages deployment

### Features
- Browse ideas by category
- Search by title/description/tech
- Filter by difficulty, source, language
- Sort by stars, date, quality score
- Responsive design
- Dark mode

### Implementation
```bash
# In the same repo or a new repo
npm create astro@latest -- --template basics
npm install @astrojs/tailwind
```

## Phase 3: Full Web Application (Weeks 3-4)

### Tech Stack
- Next.js or Astro
- SQLite → PostgreSQL migration
- Full-text search (MeiliSearch or pg_search)
- API rate limiting
- User accounts (optional)
- Admin dashboard

### Required Changes

#### Backend
1. Replace SQLite with PostgreSQL
2. Add REST API endpoints:
   - `GET /api/ideas` - List with pagination
   - `GET /api/ideas/:id` - Single idea
   - `GET /api/categories` - Category list
   - `GET /api/search?q=...` - Full-text search
3. Add API authentication for write operations

#### Frontend
1. Server-side rendering for SEO
2. Dynamic search with debouncing
3. Category pages with pagination
4. Weekly newsletter subscription
5. Contribution/submission form

## Data Flow After Migration

```
Collectors → Filters → AI → Categorize → Database
                                              │
                                              ▼
                             ┌────────────────┴────────────────┐
                             │                                 │
                             ▼                                 ▼
                       PostgreSQL DB                      data/ideas.json
                             │                                 │
                             ▼                                 ▼
                      REST API (FastAPI)                  GitHub Pages
                             │                                 │
                             ▼                                 ▼
                      Next.js Frontend                    Static Site
```

## Zero-Downtime Migration Steps

1. **Add PostgreSQL support** to `Database` class (abstract storage)
2. **Run dual-write** for one week (both SQLite and PostgreSQL)
3. **Deploy REST API** behind the existing JSON file
4. **Deploy new frontend** pointing to the API
5. **Monitor** for issues
6. **Switch** DNS/CNAME to new frontend
7. **Remove** old README publishing

## Cost Estimates

| Service | Estimated Monthly Cost |
|---------|----------------------|
| PostgreSQL (Railway/Render) | $5-20 |
| API hosting (Fly.io/Railway) | $5-10 |
| AI API calls | $10-50 (varies by volume) |
| Domain | $10-15/year |
| **Total** | **$20-80/month** |

## Migration Triggers (Automated)

When the monitoring system detects:
- README > 1 MB → Create GitHub issue "Migrate to Web Platform"
- Ideas > 3,000 → Auto-generate full ideas.json, suggest migration
- Growth rate > 20 ideas/day → Alert for migration planning
