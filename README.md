# IAppliances Alpha — Dental Guide Pipeline

Rails 8.1.2 + Ruby 4.0.1 + PostgreSQL frontend for generating 3D dental surgical guides using Blender.

## Setup

```bash
bin/setup        # Install gems, create DB, run migrations
bin/dev          # Start dev server (port 3000)
```

## Blender Pipeline (CLI)

```bash
blender --background --python src/cli.py -- samples/test_dental.stl output/oclusal.png
```

## Structure

```
app/                # Rails application (controllers, models, views, jobs)
src/                # Blender pipeline scripts (cli.py, loader.py, camera.py, render.py)
samples/            # Sample STL files for testing
config/deploy.yml   # Kamal deployment (iappliances.toolazy.to)
```

## Deploy

```bash
bin/kamal deploy
```
