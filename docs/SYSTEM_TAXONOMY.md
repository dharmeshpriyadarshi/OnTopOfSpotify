# Spotify API Aggregator: System Taxonomy

## 1. Objective

This document outlines the strict directory architecture
for the Headless CMS extending the Spotify Web API.

## 2. Directory Responsibilities

- `api/`: FastAPI routers and HTTP endpoint definitions.
- `core/`: Global configurations, OAuth security state,
  and custom exception handling.
- `db/`: SQLAlchemy declarative bases, session management,
  and PostgreSQL schemas.
- `services/`: The API aggregation layer merging Spotify
  metadata with internal CMS BLOBs.
- `migrations/`: Alembic environment scripts for strict
  database schema versioning.