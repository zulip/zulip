# Agent Notes for Tulip Development

## Development Environment Setup

This is a Zulip fork. The development environment runs inside a Docker container managed by Vagrant.

### Prerequisites
- Docker Desktop
- Vagrant (`brew install vagrant` or similar)
- For macOS: In Docker Desktop settings, use "osxfs (legacy)" file sharing (not VirtioFS) during provisioning

### First-Time Setup

```bash
# Start the Docker container
vagrant up --provider=docker

# SSH into the container
vagrant ssh

# Inside container: run provisioning (takes ~10-15 minutes)
cd /srv/zulip
./tools/provision
```

### Daily Development Workflow

```bash
# Start the environment (if stopped)
vagrant up --provider=docker

# SSH in
vagrant ssh

# Start the dev server
cd /srv/zulip
./tools/run-dev
```

Access the dev server at: http://localhost:9991/devlogin

### Running Tests & Linting

All commands run inside `vagrant ssh`:

```bash
# Run backend tests
./tools/test-backend

# Run specific test
./tools/test-backend zerver.tests.test_markdown

# Run linter
./tools/lint

# Run type checker
./tools/run-mypy
```

### Important Notes

1. **Django Setup Required**: When running Python imports directly, Django must be configured first:
   ```python
   import os
   os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zproject.settings")
   import django
   django.setup()
   # Now you can import from zerver.*
   ```

2. **File Sync**: Edit files on your host machine - they sync automatically to `/srv/zulip` in the container.

3. **Stopping the Environment**:
   ```bash
   vagrant halt  # Stops the container
   vagrant destroy  # Removes the container entirely
   ```

4. **Re-provisioning**: After pulling new changes that modify dependencies:
   ```bash
   vagrant ssh -c "cd /srv/zulip && ./tools/provision"
   ```

## Project Structure

- `zerver/` - Main Django app
  - `actions/` - Business logic functions
  - `views/` - HTTP endpoint handlers
  - `models/` - Database models
  - `worker/` - Background queue workers
  - `lib/` - Utility libraries
- `web/src/` - Frontend TypeScript code
- `zproject/urls.py` - URL routing
- `tools/` - Development scripts

## Current Work: Bot Interactions Feature

Adding Discord-style interactive bot components. See `/Users/ember/.claude/plans/kind-dazzling-dewdrop.md` for the full plan.

### New Files Created
- `zerver/views/bot_interactions.py` - API endpoint for widget interactions
- `zerver/actions/bot_interactions.py` - Business logic for routing interactions to bots
- `zerver/worker/bot_interactions.py` - Queue worker to deliver interactions to bots
