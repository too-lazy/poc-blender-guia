# 🦷 IAppliances Alpha — Blender Dental Guide Pipeline

> Rails 8 + Blender headless pipeline for generating 3D dental surgical guides from STL scans.

![Ruby](https://img.shields.io/badge/Ruby-4.0.1-red)
![Rails](https://img.shields.io/badge/Rails-8.1.2-red)
![Blender](https://img.shields.io/badge/Blender-5.0+-orange)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-blue)
![Tailwind](https://img.shields.io/badge/Tailwind-4.2-cyan)

---

## Overview

IAppliances Alpha automates the generation of occlusal renders and (in future phases) 3D-printable surgical guides for orthodontic mini-screw placement. It combines a **Rails web interface** with a **Python/Blender headless pipeline** to process dental STL scans.

### How It Works

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐     ┌────────────┐
│  Upload STL  │ ──▶ │  Rails App   │ ──▶ │  Solid Queue Job │ ──▶ │  Blender   │
│  (Web UI)    │     │  (Case/Run)  │     │  (Background)    │     │  (Headless)│
└─────────────┘     └──────────────┘     └──────────────────┘     └─────┬──────┘
                                                                        │
                    ┌──────────────┐     ┌──────────────────┐           │
                    │  View Render │ ◀── │  Active Storage  │ ◀─────────┘
                    │  (Web UI)    │     │  (PNG output)    │     Render PNG
                    └──────────────┘     └──────────────────┘
```

### Key Features

- **Patient Management** — Create patients, attach cases with STL files
- **Quick Process** — Upload and process STL files without creating a patient
- **Blender Pipeline** — Automated occlusal camera + lighting + Cycles render
- **Live Status** — Monitor running workflows with real-time log output
- **Render Viewer** — In-page lightbox viewer for Blender output images
- **Neobrutalism UI** — Bold, distinctive interface with IAppliances branding

---

## Tech Stack

| Layer        | Technology                                    |
|-------------|-----------------------------------------------|
| **Backend**  | Ruby 4.0.1, Rails 8.1.2, PostgreSQL           |
| **Frontend** | Hotwire (Turbo + Stimulus), Tailwind CSS 4.2  |
| **Pipeline** | Python 3, Blender 5.0+ (headless/CLI)         |
| **Jobs**     | Solid Queue (database-backed)                 |
| **Storage**  | Active Storage (local disk or S3)             |
| **Deploy**   | Kamal 2 (Docker), Thruster                    |

---

## Project Structure

```
poc-blender-guia/
├── app/
│   ├── controllers/          # Rails controllers
│   │   ├── dashboard_controller.rb
│   │   ├── patients_controller.rb
│   │   ├── cases_controller.rb
│   │   ├── workflow_runs_controller.rb
│   │   ├── quick_processes_controller.rb
│   │   └── status_controller.rb
│   ├── jobs/
│   │   └── blender_workflow_job.rb   # Background Blender execution
│   ├── models/
│   │   ├── patient.rb                # has_many :cases
│   │   ├── case.rb                   # belongs_to :patient (optional)
│   │   └── workflow_run.rb           # belongs_to :case
│   ├── views/                        # ERB templates (neobrutalism)
│   └── javascript/controllers/       # Stimulus controllers
├── src/                              # Python Blender pipeline
│   ├── cli.py                        # CLI entrypoint
│   ├── loader.py                     # STL loading + scene setup
│   ├── camera.py                     # Occlusal camera positioning
│   └── render.py                     # Lighting, material, Cycles render
├── docs/
│   └── plan.md                       # Project roadmap
├── samples/                          # Example STL files
├── output/                           # Local render output
├── config/                           # Rails configuration
├── db/                               # Migrations and schema
└── Dockerfile                        # Production image (includes Blender)
```

---

## Setup

### Prerequisites

- **Ruby** 4.0.1 (via rbenv/asdf)
- **PostgreSQL** 16+
- **Blender** 5.0+ (must be on `PATH`)
- **Node.js** (not required — uses importmap)

### Installation

```bash
# Clone
git clone <repo-url> && cd poc-blender-guia

# Ruby dependencies
bundle install

# Database
bin/rails db:create db:migrate

# Verify Blender
blender --version   # Should show 5.x

# Start dev server (Rails + Tailwind watcher)
bin/dev
```

The app will be available at **http://localhost:3000**.

### Environment Variables

| Variable           | Description                          | Default         |
|-------------------|--------------------------------------|-----------------|
| `DATABASE_URL`     | PostgreSQL connection string         | See database.yml|
| `RAILS_MASTER_KEY` | Decrypts credentials (production)    | config/master.key|
| `RAILS_ENV`        | Environment (development/production) | development     |

---

## Usage

### Web Interface

| Route                | Description                          |
|---------------------|--------------------------------------|
| `/`                  | Dashboard — stats and recent runs    |
| `/patients`          | Patient list                         |
| `/patients/:id`      | Patient detail + cases               |
| `/patients/:id/cases/new` | Create case with STL upload     |
| `/quick_process/new` | Upload STL without a patient         |
| `/status`            | Live workflow status + logs          |

### Workflow

1. **Upload STL** — via Patient → Case, or Quick Process
2. **Execute Workflow** — triggers `BlenderWorkflowJob` in Solid Queue
3. **Blender runs headless** — loads STL, sets occlusal camera, renders PNG
4. **View result** — render appears on case page and status page

### CLI (Direct Blender)

Run the pipeline directly without Rails:

```bash
blender --background --python src/cli.py -- samples/dental.stl output/render.png
```

Arguments after `--` are passed to the Python script:
- `arg1` — Input STL file path (required)
- `arg2` — Output PNG path (default: `output/oclusal.png`)

---

## Blender Pipeline

The Python pipeline in `src/` runs inside Blender's embedded Python:

| Module      | Responsibility                                      |
|------------|------------------------------------------------------|
| `cli.py`    | Argument parsing, orchestration                     |
| `loader.py` | Scene clearing, STL import via `bpy.ops.wm.stl_import`, centering |
| `camera.py` | Orthographic camera positioned for occlusal view    |
| `render.py` | Sun lamp, bone-colored material, Cycles 64 samples, 1920×1080 |

> **Note:** Blender 5.0 uses `bpy.ops.wm.stl_import` / `bpy.ops.wm.stl_export` instead of the legacy `bpy.ops.import_mesh.stl`.

---

## Development

```bash
# Start Rails + Tailwind watcher
bin/dev

# Run only Rails
bin/rails server

# Build Tailwind once
bin/rails tailwindcss:build

# Rails console
bin/rails console

# Run background jobs (if not using async adapter)
bin/rails solid_queue:start
```

### Code Quality

```bash
bin/rubocop              # Ruby linting
bin/brakeman             # Security scanning
bundle audit check       # Dependency audit
```

---

## Deployment

Production uses **Kamal 2** with Docker:

```bash
# Setup (first time)
kamal setup

# Deploy
kamal deploy

# Rollback
kamal rollback
```

The Dockerfile installs Blender in the production image for headless rendering.

---

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| **1. Occlusal Render** | ✅ Done | Load STL → occlusal camera → Cycles render |
| **2. Web App** | ✅ Done | Rails UI, patient/case management, job queue |
| **3. Radiography** | 🔜 Planned | DICOM loading, image overlay, registration |
| **4. Guide Generation** | 🔜 Planned | Screw placement, guide geometry, STL export |
| **5. Validation** | 🔜 Planned | Clearance checks, thickness, batch processing |

---

## License

Proprietary — IAppliances. All rights reserved.
