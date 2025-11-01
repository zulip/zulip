# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Development Commands

### Starting the Development Server
```bash
./tools/run-dev
```
Access at <http://localhost:9991/>. The server auto-reloads for most changes (Python, JS, CSS). For backend templates (Jinja2), manually reload the browser.

### Testing

**Run all tests:**
```bash
./tools/test-all
```

**Backend (Django/Python) tests:**
```bash
./tools/test-backend                           # All backend tests
./tools/test-backend zerver.tests.test_markdown.MarkdownEmbedsTest.test_inline_youtube  # Single test
./tools/test-backend MarkdownEmbedsTest        # Test class
./tools/test-backend zerver/tests/test_markdown.py  # Test file
./tools/test-backend --rerun                   # Rerun failed tests
./tools/test-backend --help                    # See all options
```

**Frontend (JavaScript/TypeScript) tests:**
```bash
./tools/test-js-with-node                      # All frontend unit tests
./tools/test-js-with-node util                 # Specific module
./tools/test-js-with-puppeteer                 # E2E integration tests
```

**Other test suites:**
```bash
./tools/test-migrations                        # Database migration tests
./tools/test-api                              # API documentation tests
./tools/test-help-documentation               # Help center link tests
```

### Linting

**Run all linters:**
```bash
./tools/lint                                  # All files
./tools/lint web/src/compose.ts              # Specific file
./tools/lint web/src/                        # Directory
./tools/lint --fix                           # Auto-fix issues
./tools/lint -m                              # Only modified files
```

**Specific linters:**
```bash
./tools/lint --only=ruff,ruff-format --fix   # Python formatting
./tools/lint --only=prettier --fix           # JS/TS/CSS formatting
./tools/lint --only=eslint                   # JS/TS linting
./tools/lint --only=mypy                     # Python type checking
```

### Type Checking
```bash
# TypeScript compilation happens automatically via webpack
# Python type checking with mypy:
./tools/lint --only=mypy
```

### Database Operations
```bash
./manage.py shell                            # Django shell
./manage.py dbshell                          # Database shell
./tools/rebuild-dev-database                 # Reset to pristine state
./manage.py makemigrations                   # Create migration
./manage.py migrate                          # Apply migrations
```

### Dependency Management
```bash
./tools/provision                            # Update dependencies (run after pulling)
pnpm install                                 # Install JS dependencies
```

## Code Architecture

### High-Level Technology Stack
- **Backend**: Python 3.10+ with Django 5.2 (main web app logic)
- **Real-time**: Tornado (event delivery, long-polling, WebSockets alternative)
- **Frontend**: JavaScript/TypeScript with jQuery (migrating to vanilla JS)
- **Database**: PostgreSQL (primary data store)
- **Caching**: Redis and memcached
- **Queue**: RabbitMQ (asynchronous task processing)
- **Templates**: Jinja2 (backend), Handlebars (frontend)
- **Build**: Webpack (JS/TS bundling), PostCSS (CSS processing)

### Directory Structure

**Core Backend (`zerver/`):**
- `models/*.py` - Database models (Django ORM)
- `views/*.py` - HTTP request handlers (Django views)
- `actions/*.py` - Code that writes to database and triggers events to clients
- `lib/*.py` - Shared library code and utilities
- `tornado/` - Tornado-based real-time push system
- `worker/` - RabbitMQ queue processors
- `webhooks/` - Incoming webhook integrations
- `tests/` - Backend test suite

**Frontend (`web/`):**
- `src/` - JavaScript/TypeScript source files
- `styles/` - CSS files (using PostCSS)
- `templates/` - Handlebars templates for client-side rendering
- `tests/` - Frontend unit tests (Node)
- `e2e-tests/` - End-to-end Puppeteer tests

**Configuration:**
- `zproject/` - Django project settings and configuration
- `zproject/urls.py` - Main URL routing
- `puppet/` - Production deployment configuration

**Other Django Apps:**
- `analytics/` - Server analytics
- `confirmation/` - Email confirmation system
- `corporate/` - Old Zulip.com website (not in production)
- `zilencer/` - Development-only management commands

**Infrastructure:**
- `tools/` - Development scripts
- `scripts/` - Production deployment scripts
- `docs/` - Documentation source
- `templates/zerver/` - Backend Jinja2 templates

### Key Architectural Patterns

**Events System (Real-time Sync):**
Zulip uses an events-based architecture for real-time updates. When data changes:
1. Code in `zerver/actions/` calls `send_event_on_commit(realm, event, users)` 
2. Event is queued to `notify_tornado` RabbitMQ queue
3. Tornado event queue server (`zerver/tornado/`) delivers to connected clients via long-polling
4. Clients call `GET /json/events` and receive events when available

This ensures all clients stay in sync. Any code that triggers client updates MUST be in `zerver/actions/`.

**Queue Workers:**
Asynchronous tasks are processed via RabbitMQ queues (defined in `zerver/worker/`):
- Email sending (expensive operations)
- Analytics updates (non-time-critical)
- Mobile push notifications
- Event delivery to Tornado

Queue events are published using `queue_event_on_commit()` from `zerver/lib/queue.py`.

**Database Access:**
- Never use direct queries like `UserProfile.objects.get(email=foo)`
- Use helper functions like `get_user_profile_by_email()` or `get_user_profile_by_id()`
- Avoid N+1 queries: use `.select_related()` or `.prefetch_related()` to fetch related objects

**Testing Philosophy:**
- Tests run in isolated transactions (rolled back after each test)
- Fixture data includes Shakespeare-themed users in "zulip.com" realm
- No outgoing network requests in tests - use mocks via `mock.patch()`
- Test files in development DB are independent from UI testing DB

**Frontend Architecture:**
- Webpack bundles defined in `web/webpack.*assets.json`
- Entry points map to templates in `templates/`
- Hot module replacement for CSS
- Auto-reload for JS/TS changes
- Manual reload needed for Jinja2 backend templates

### Code Style Requirements

**Python:**
- Formatted with Ruff (configured in `pyproject.toml`)
- Type checking with mypy (100% coverage required)
- Line length: aim for 85 chars, hard limit ~120
- Use `const`/`let` not `var` in any Python code
- All user-facing strings must be tagged for translation

**JavaScript/TypeScript:**
- Formatted with Prettier
- Linted with ESLint
- Use `const` and `let`, never `var`
- Build DOM in Handlebars templates, not inline JS
- Attach behaviors via jQuery event listeners, not `onclick` attributes
- Prefer modern ES6+ methods over Underscore.js

**General:**
- Tag all user-facing strings for translation
- Never include secrets inline - use `get_secret()` from `zproject/config.py`
- Run `./tools/provision` after switching branches
- Use `.warpindexingignore` to exclude files from indexing if needed

### Common Workflows

**Adding a new feature:**
1. Create database model changes in `zerver/models/*.py`
2. Generate migration: `./manage.py makemigrations`
3. Add view logic in `zerver/views/*.py`
4. Add routes in `zproject/urls.py`
5. If state changes, add action in `zerver/actions/*.py` with events
6. Add backend tests in `zerver/tests/`
7. Add frontend code in `web/src/`
8. Add Handlebars template in `web/templates/`
9. Add frontend tests in `web/tests/`
10. Run `./tools/test-backend` and `./tools/test-js-with-node`
11. Run `./tools/lint`

**Working with database:**
- Changes to `zerver/models/*.py` require migrations
- Test migrations with `./tools/test-migrations`
- Use `./manage.py shell` for interactive queries
- Reset dev DB with `./tools/rebuild-dev-database`

**Working with queue processors:**
- Define in `zerver/worker/` with `@assign_queue` decorator
- Auto-started by `./tools/run-dev`
- Manually run: `./manage.py process_queue --queue=<queue_name>`
- Clear queue: `./manage.py purge_queue <queue_name>`

### Important Development Notes

- Development server automatically restarts on Python/JS changes
- Queue workers auto-restart (unless they crash with syntax error)
- Watch `run-dev` console for 500 error tracebacks
- Default dev homepage lists all users - click any to login without password
- Use `/devtools` in browser for development utilities
- Tests use separate database from UI testing
- Git pre-commit hook available via `./tools/setup-git-repo`
- Rebase frequently: `git fetch upstream && git rebase upstream/main`

### Production vs Development

- Development uses Django's `runserver` (auto-reload)
- Production uses uWSGI for Django and separate Tornado processes
- Production deployment via Puppet (in `puppet/` directory)
- Release tarballs built with `tools/build-release-tarball`
- Some components excluded from production (see `.gitattributes`)
