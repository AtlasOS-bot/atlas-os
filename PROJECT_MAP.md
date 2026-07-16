# Atlas Project Map

## Overview

Atlas is organized into independent modules. Each folder has a single responsibility.

---

## Folder Responsibilities

### atlas/
Core application entry point.

### brain/
Coordinates communication between Atlas modules.

### config/
Configuration, settings, constants and environment loading.

### dashboard/
Displays reports, alerts and user-facing information.

### decision/
Ranks opportunities and makes final recommendations.

### docs/
Project documentation.

### knowledge/
Reference information used by Atlas.

### learning/
Learns from historical data and improves future decisions.

### market/
Market pricing, trends and resale analysis.

### memory/
Persistent application memory and stored state.

### patterns/
Pattern recognition and historical analysis.

### popularity/
Measures demand and product popularity.

### reasoning/
Business logic used to evaluate opportunities.

### scouts/
Collects information from external websites and APIs.

### signals/
Generates signals from collected data.

### tests/
Automated project tests.

---

## Runtime Data

.atlas_data/

Stores generated JSON data including:

- alerts
- histories
- product states
- release calendars
- reports
- learned information

Atlas generates these automatically while running.

---

## Automation

.github/workflows/

Contains GitHub Actions that automate:

- product scouting
- market research
- opportunity scoring
- morning briefs
- alert generation
- ROI tracking
- pattern learning

---

## Data Flow

Scouts
↓
Signals
↓
Market Analysis
↓
Decision Engine
↓
Brain
↓
Memory (.atlas_data)
↓
Dashboard