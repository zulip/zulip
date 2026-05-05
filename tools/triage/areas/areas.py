"""Canonical area definitions + meta-area rollups for the area-mapping
exercise.

Each canonical area is a key. Its value is a dict with:
  - aliases: list of normalized raw prefixes that map here
  - meta: list of meta-areas this rolls up to (excluding self)

A commit's raw prefix is normalized (lowercase, dashes/underscores → space,
collapsed whitespace) and looked up. If it matches an alias of some
canonical area, the commit scores in that canonical area + all listed meta-
areas. If it doesn't match any alias, the canonical area defaults to the
raw prefix itself with no meta-areas.

Multi-colon prefixes (e.g., `tests: foo.test.cjs`) collapse to their first
segment before lookup — a `tests: <file>: <subj>` commit looks up against
"tests".
"""

# Canonical areas to drop entirely from scoring — too generic to be useful.
EXCLUDED: set[str] = {"tests", "settings", "realm"}


AREAS: dict[str, dict[str, list[str]]] = {
    # =====================================================================
    # COMPOSE
    # =====================================================================
    "compose": {"aliases": ["compose"], "meta": []},
    "compose typeahead": {
        "aliases": ["composebox typeahead", "compose typeahead", "compose box typeahead"],
        "meta": ["compose", "typeahead"],
    },
    "compose banner": {"aliases": ["compose banner"], "meta": ["compose"]},
    "compose reply": {"aliases": ["compose reply"], "meta": ["compose"]},
    "compose validate": {"aliases": ["compose validate"], "meta": ["compose"]},
    "compose recipient": {"aliases": ["compose recipient"], "meta": ["compose"]},
    "compose call": {
        "aliases": ["compose call", "compose call ui"],
        "meta": ["compose", "video calls"],
    },
    "compose ui": {
        "aliases": ["compose ui", "compose closed ui", "closed compose"],
        "meta": ["compose"],
    },
    "compose actions": {"aliases": ["compose actions"], "meta": ["compose"]},
    "compose paste": {"aliases": ["compose paste"], "meta": ["compose"]},
    "compose state": {"aliases": ["compose state"], "meta": ["compose"]},
    "compose setup": {"aliases": ["compose setup"], "meta": ["compose"]},
    "compose notifications": {
        "aliases": ["compose notifications"],
        "meta": ["compose", "notifications"],
    },
    "compose send menu popover": {
        "aliases": ["compose send menu popover"],
        "meta": ["compose", "popovers"],
    },
    # =====================================================================
    # MESSAGE
    # =====================================================================
    "message edit": {"aliases": ["message edit"], "meta": ["message"]},
    "message edit history": {
        "aliases": ["message edit history"],
        "meta": ["message", "message edit"],
    },
    "message send": {"aliases": ["message send"], "meta": ["message"]},
    "message view": {"aliases": ["message view", "message view header"], "meta": ["message"]},
    "message fetch": {"aliases": ["message fetch"], "meta": ["message"]},
    "message cache": {"aliases": ["message cache"], "meta": ["message"]},
    "message feed": {"aliases": ["message feed", "message feed loading"], "meta": ["message"]},
    "message events": {
        "aliases": ["message events", "message events test"],
        "meta": ["message", "events"],
    },
    # =====================================================================
    # SETTINGS PAGES
    # ("settings" alone is too generic to be useful, so we don't roll
    # specific settings pages up to a "settings" meta-area, and we
    # explicitly skip bare "settings:" commits below.)
    # =====================================================================
    "channel settings": {
        "aliases": [
            "channel settings",
            "channel setting",
            "stream settings",
            "stream setting",
            "stream settings ui",
            "stream settings data",
            "stream-settings",
        ],
        "meta": ["channels"],
    },
    "group settings": {"aliases": ["group settings"], "meta": []},
    "user group settings": {"aliases": ["user group settings"], "meta": ["user groups"]},
    "user settings": {"aliases": ["user settings", "settings users"], "meta": []},
    "settings emoji": {"aliases": ["settings emoji", "emoji settings"], "meta": ["emoji"]},
    "settings bots": {"aliases": ["settings bots"], "meta": ["bots"]},
    "settings profile": {
        "aliases": ["settings profile fields", "profile settings", "settings profile"],
        "meta": ["user profile"],
    },
    "notification settings": {
        "aliases": ["notification settings", "notifications settings"],
        "meta": ["notifications"],
    },
    # =====================================================================
    # CHANNELS (formerly streams; canonical name is now "channels")
    # =====================================================================
    "channels": {
        "aliases": [
            # Bare stream/channel synonyms
            "channels",
            "channel",
            "streams",
            "stream",
            "streams ui",
            "channels ui",
            "channels overlay",
            # Small stream-prefixed sub-features rolled in
            "default streams",
            "example stream",
            "selected stream title",
            "stream color",
            "stream description",
            "stream subscription",
            "stream members",
            "stream pill",
            "stream privacy icon",
            "stream traffic",
            "stream type icon",
            "stream types",
            "stream ui updates",
            "add stream options",
            # Channel-prefixed minor things
            "channel email",
            "channel email address",
            "channel permissions",
            "decorated channel name",
        ],
        "meta": [],
    },
    "channel list": {
        "aliases": ["channel list", "stream list", "channel list item"],
        "meta": ["channels", "left sidebar"],
    },
    "channel list sort": {
        "aliases": ["channel list sort", "stream list sort"],
        "meta": ["channel list", "channels"],
    },
    "channel data": {"aliases": ["channel data", "stream data"], "meta": ["channels"]},
    "channel events": {
        "aliases": ["channel events", "stream events", "stream events dispatch"],
        "meta": ["channels", "events"],
    },
    "channel edit": {
        "aliases": ["channel edit", "stream edit", "stream edit subscribers"],
        "meta": ["channels"],
    },
    "channel create": {
        "aliases": ["channel create", "stream create", "create channel", "test channel creation"],
        "meta": ["channels"],
    },
    "channel folders": {
        "aliases": [
            "channel folders",
            "channel folder",
            "channel folder ui",
            "channel folders ui",
            "channel folders popover",
            "test channel folders",
        ],
        "meta": ["channels"],
    },
    "channel privacy": {
        "aliases": ["channel privacy", "test channel permissions"],
        "meta": ["channels"],
    },
    "channel popover": {
        "aliases": ["channel popover", "stream popover", "stream card popover"],
        "meta": ["channels", "popovers"],
    },
    # =====================================================================
    # RECENT VIEW
    # =====================================================================
    "recent view": {
        "aliases": [
            "recent view",
            "recents",
            "recent_view",
            "recent-view",
            "recent conversations",
            "recent-conversations",
        ],
        "meta": [],
    },
    "recent view ui": {"aliases": ["recent view ui"], "meta": ["recent view"]},
    "recent topics": {"aliases": ["recent topics"], "meta": ["recent view"]},
    "recent senders": {
        "aliases": ["recent senders", "recent senders test"],
        "meta": ["recent view"],
    },
    # =====================================================================
    # INBOX
    # =====================================================================
    "inbox": {"aliases": ["inbox", "inbox view"], "meta": []},
    "inbox ui": {"aliases": ["inbox ui"], "meta": ["inbox"]},
    # =====================================================================
    # USER GROUPS / USER PROFILE / PEOPLE
    # `user groups` is one canonical area; `user group settings` and
    # `groups ui` stay distinct as sub-areas (settings vs UI) but roll up.
    # =====================================================================
    "user groups": {
        "aliases": ["user groups", "user group", "groups", "group", "user group edit"],
        "meta": [],
    },
    "groups ui": {"aliases": ["groups ui", "user groups ui"], "meta": ["user groups"]},
    "user profile": {"aliases": ["user profile", "user profile widget"], "meta": []},
    "user card popover": {"aliases": ["user card popover"], "meta": ["user profile", "popovers"]},
    "user events": {"aliases": ["user events"], "meta": ["events"]},
    "user status": {"aliases": ["user status"], "meta": []},
    "people": {"aliases": ["people"], "meta": []},
    "custom profile fields": {"aliases": ["custom profile fields"], "meta": ["user profile"]},
    # =====================================================================
    # API / DOCS / HELP
    # =====================================================================
    "api": {"aliases": ["api"], "meta": []},
    "api docs": {"aliases": ["api docs", "api-docs"], "meta": ["api", "docs"]},
    "openapi": {"aliases": ["openapi"], "meta": ["api"]},
    # `help:` is content (Help Center articles); `help-beta:` and
    # `starlight help:` are technical work on the Starlight framework
    # (build, components, plugins) — different skill set, kept distinct.
    "help": {"aliases": ["help", "help center"], "meta": []},
    "starlight": {"aliases": ["starlight", "starlight help", "help beta"], "meta": []},
    "docs": {"aliases": ["docs", "docs build"], "meta": []},
    "contributor docs": {"aliases": ["contributor docs"], "meta": ["docs"]},
    # =====================================================================
    # SEARCH / NARROW / FILTER
    # =====================================================================
    "search": {"aliases": ["search"], "meta": []},
    "search pill": {"aliases": ["search pill", "search user pill"], "meta": ["search"]},
    "search results": {"aliases": ["search results"], "meta": ["search"]},
    "search suggestion": {
        "aliases": ["search suggestion", "search suggestions"],
        "meta": ["search"],
    },
    "narrow": {"aliases": ["narrow"], "meta": []},
    "narrow banner": {"aliases": ["narrow banner"], "meta": ["narrow"]},
    "narrow state": {"aliases": ["narrow state"], "meta": ["narrow"]},
    "narrow title": {"aliases": ["narrow title"], "meta": ["narrow"]},
    "filter": {"aliases": ["filter", "filter inputs"], "meta": []},
    # =====================================================================
    # SIDEBARS / NAVIGATION
    # =====================================================================
    "sidebar ui": {"aliases": ["sidebar ui", "sidebar", "sidebars"], "meta": []},
    "left sidebar": {"aliases": ["left sidebar"], "meta": []},
    "right sidebar": {"aliases": ["right sidebar"], "meta": []},
    "navbar": {"aliases": ["navbar", "gear menu", "personal menu", "navbar menus"], "meta": []},
    "buddy list": {"aliases": ["buddy list"], "meta": ["right sidebar"]},
    "dm list": {
        "aliases": ["dm list", "pm list", "pm list data", "pm list item", "pm list test"],
        "meta": ["direct messages", "left sidebar"],
    },
    # =====================================================================
    # POPOVERS / OVERLAYS / MODALS / TOOLTIPS
    # =====================================================================
    "popovers": {"aliases": ["popovers", "popover"], "meta": []},
    "popover menus": {"aliases": ["popover menus"], "meta": ["popovers"]},
    "topic popover": {"aliases": ["topic popover"], "meta": ["popovers", "topics"]},
    "overlays": {"aliases": ["overlays", "overlay"], "meta": []},
    "settings overlay": {"aliases": ["settings overlay"], "meta": ["overlays"]},
    "info overlay": {"aliases": ["info overlay"], "meta": ["overlays"]},
    "tooltips": {"aliases": ["tooltips", "tooltip"], "meta": []},
    "lightbox": {"aliases": ["lightbox"], "meta": []},
    "modals": {"aliases": ["modals", "modal"], "meta": []},
    "dropdown": {
        "aliases": ["dropdown", "dropdown widget", "dropdown lists", "folder dropdown widget"],
        "meta": [],
    },
    # =====================================================================
    # DRAFTS / TYPEAHEAD / etc.
    # =====================================================================
    "drafts": {"aliases": ["drafts"], "meta": []},
    "typeahead": {"aliases": ["typeahead"], "meta": []},
    "bootstrap typeahead": {"aliases": ["bootstrap typeahead"], "meta": ["typeahead"]},
    "pill typeahead": {"aliases": ["pill typeahead"], "meta": ["typeahead"]},
    "typeahead helper": {"aliases": ["typeahead helper"], "meta": ["typeahead"]},
    "hotkey": {"aliases": ["hotkey", "hotkeys"], "meta": []},
    "quote": {"aliases": ["quote", "quote message", "quote messages"], "meta": []},
    "topic list": {
        "aliases": [
            "topic list",
            "topic list data",
            "topic list data test",
            "channel topic list",
            "channel topics list",
            "stream topic history util",
            "test stream topic history",
        ],
        "meta": [],
    },
    # =====================================================================
    # MARKDOWN / RENDERING
    # =====================================================================
    "markdown": {
        "aliases": ["markdown", "markdown render", "rendered markdown", "rendered markdown tests"],
        "meta": [],
    },
    "linkifiers": {"aliases": ["linkifiers", "linkifier"], "meta": []},
    "url decoding": {"aliases": ["url decoding"], "meta": ["markdown"]},
    "url encoding": {"aliases": ["url encoding"], "meta": ["markdown"]},
    # =====================================================================
    # NOTIFICATIONS / EMAIL / PUSH
    # =====================================================================
    "notifications": {"aliases": ["notifications"], "meta": []},
    "email": {"aliases": ["email", "emails"], "meta": []},
    "email mirror": {"aliases": ["email mirror", "email mirror server"], "meta": ["email"]},
    "email backends": {"aliases": ["email backends"], "meta": ["email"]},
    "send email": {"aliases": ["send email"], "meta": ["email"]},
    "email notifications": {
        "aliases": ["email notifications", "email notification"],
        "meta": ["notifications", "email"],
    },
    "push notifications": {
        "aliases": ["push notifications", "push notification"],
        "meta": ["notifications"],
    },
    "push registration": {"aliases": ["push registration"], "meta": ["push notifications"]},
    # =====================================================================
    # AUTH / BILLING / EXPORT / IMPORT
    # =====================================================================
    "auth": {"aliases": ["auth", "authentication"], "meta": []},
    "billing": {"aliases": ["billing"], "meta": []},
    "stripe": {"aliases": ["stripe", "test stripe"], "meta": ["billing"]},
    "corporate": {"aliases": ["corporate"], "meta": []},
    "export": {"aliases": ["export"], "meta": []},
    "import": {
        "aliases": [
            "import",
            "import realm",
            "import util",
            "data import",
            "import export",
            "test import export",
        ],
        "meta": [],
    },
    # X and X-importer are merged into one canonical per platform; they
    # roll up to `import`.
    "slack": {
        "aliases": [
            "slack",
            "slack importer",
            "slack import",
            "slack converter",
            "slack integration",
            "slack integration doc",
            "slack import doc",
            "slack importer doc",
            "slack importer test",
            "slack incoming",
            "slack message conversion",
            "slack util",
            "test slack importer",
            "test slack integration",
            "webhooks/slack",
        ],
        "meta": ["import"],
    },
    "mattermost": {
        "aliases": [
            "mattermost",
            "mattermost importer",
            "mattermost import",
            "mattermost converter",
            "test mattermost",
            "test mattermost importer",
        ],
        "meta": ["import"],
    },
    "rocketchat": {"aliases": ["rocketchat", "rocketchat importer"], "meta": ["import"]},
    "microsoft teams": {
        "aliases": ["microsoft teams", "microsoft teams importer", "ms teams importer"],
        "meta": ["import"],
    },
    # =====================================================================
    # INTEGRATIONS / WEBHOOKS / BOTS
    # =====================================================================
    "integrations": {"aliases": ["integrations", "integration"], "meta": []},
    "integration url modal": {"aliases": ["integration url modal"], "meta": ["integrations"]},
    "webhooks": {"aliases": ["webhooks", "webhook"], "meta": ["integrations"]},
    "webhooks/github": {
        "aliases": ["webhooks/github", "integrations/github"],
        "meta": ["webhooks", "integrations"],
    },
    "webhooks/sentry": {"aliases": ["webhooks/sentry"], "meta": ["webhooks", "integrations"]},
    "webhooks/intercom": {"aliases": ["webhooks/intercom"], "meta": ["webhooks", "integrations"]},
    "webhooks/gitlab": {"aliases": ["webhooks/gitlab"], "meta": ["webhooks", "integrations"]},
    "webhooks/gitea": {
        "aliases": ["webhooks/gitea", "webhooks gitea"],
        "meta": ["webhooks", "integrations"],
    },
    "webhooks/jira": {"aliases": ["webhooks/jira"], "meta": ["webhooks", "integrations"]},
    "webhooks/notion": {"aliases": ["webhooks/notion"], "meta": ["webhooks", "integrations"]},
    "webhooks/pagerduty": {"aliases": ["webhooks/pagerduty"], "meta": ["webhooks", "integrations"]},
    "webhooks/taiga": {"aliases": ["webhooks/taiga"], "meta": ["webhooks", "integrations"]},
    "integration docs": {"aliases": ["integration docs"], "meta": ["integrations", "docs"]},
    "bots": {"aliases": ["bots", "bot"], "meta": []},
    "video calls": {"aliases": ["video calls"], "meta": []},
    # =====================================================================
    # PRESENCE / EVENTS
    # =====================================================================
    "presence": {"aliases": ["presence"], "meta": []},
    "events": {"aliases": ["events"], "meta": []},
    "event queue": {"aliases": ["event queue"], "meta": ["events"]},
    "event types": {"aliases": ["event types"], "meta": ["events"]},
    "server events": {"aliases": ["server events"], "meta": ["events"]},
    "server events dispatch": {
        "aliases": ["server events dispatch"],
        "meta": ["events", "server events"],
    },
    "demo orgs": {"aliases": ["demo orgs"], "meta": []},
    # =====================================================================
    # MEDIA / EMOJI / UPLOADS
    # =====================================================================
    "emoji": {"aliases": ["emoji", "emoji picker"], "meta": []},
    "emoji frequency": {"aliases": ["emoji frequency", "emoji frequency data"], "meta": ["emoji"]},
    "realm emoji": {"aliases": ["realm emoji"], "meta": ["emoji"]},
    "gifs": {"aliases": ["gifs", "gif picker"], "meta": []},
    "upload": {"aliases": ["upload", "uploads"], "meta": []},
    "upload widget": {"aliases": ["upload widget", "image upload widget"], "meta": ["upload"]},
    "icons": {"aliases": ["icons"], "meta": []},
    "thumbnail": {"aliases": ["thumbnail", "thumbnails"], "meta": ["upload"]},
    # =====================================================================
    # FRONTEND PLATFORM
    # =====================================================================
    "css": {"aliases": ["css", "scss"], "meta": []},
    "templates": {"aliases": ["templates"], "meta": []},
    "web": {"aliases": ["web"], "meta": []},
    "i18n": {"aliases": ["i18n", "internationalization"], "meta": []},
    "portico": {
        "aliases": [
            "portico",
            "portico signin",
            "portico markdown",
            "legacy portico",
            "docs and portico",
        ],
        "meta": [],
    },
    "marketing page": {"aliases": ["marketing page"], "meta": ["portico"]},
    # =====================================================================
    # BACKEND CORE
    # =====================================================================
    "zerver": {"aliases": ["zerver"], "meta": []},
    "models": {"aliases": ["models"], "meta": ["zerver"]},
    "migrations": {"aliases": ["migrations", "migration"], "meta": ["zerver"]},
    "zproject": {"aliases": ["zproject"], "meta": []},
    "cache": {"aliases": ["cache"], "meta": []},
    # =====================================================================
    # PRODUCTION / DEPLOYMENT
    # =====================================================================
    "production": {"aliases": ["production"], "meta": []},
    "nginx": {"aliases": ["nginx"], "meta": ["production"]},
    "puppet": {"aliases": ["puppet"], "meta": ["production"]},
    "kandra": {"aliases": ["kandra"], "meta": ["production"]},
    "letsencrypt": {"aliases": ["letsencrypt"], "meta": ["production"]},
    "setup certbot": {"aliases": ["setup certbot"], "meta": ["production"]},
    "setup docs": {"aliases": ["setup docs"], "meta": ["production"]},
    "setup upgrade postgresql": {"aliases": ["setup upgrade postgresql"], "meta": ["production"]},
    "restart server": {"aliases": ["restart server"], "meta": ["production"]},
    "provision": {"aliases": ["provision"], "meta": ["production"]},
    "restore backup": {"aliases": ["restore backup"], "meta": ["production"]},
    "backup": {"aliases": ["backup"], "meta": ["production"]},
    "tornado": {"aliases": ["tornado"], "meta": ["production"]},
    "sharding": {"aliases": ["sharding"], "meta": ["production"]},
    # =====================================================================
    # TOPICS / MESSAGES (other)
    # =====================================================================
    "topics": {"aliases": ["topics", "topic"], "meta": []},
    "messages": {"aliases": ["messages"], "meta": ["message"]},
    "personal recipients": {"aliases": ["personal recipients", "personal recipient"], "meta": []},
    "direct messages": {
        "aliases": [
            "direct messages",
            "direct message group",
            "dm groups",
            "private messages",
            "pm conversation",
            "pms",
            "dms",
        ],
        "meta": [],
    },
    "polls": {"aliases": ["polls", "poll"], "meta": []},
    "unread ops": {"aliases": ["unread ops", "unread"], "meta": []},
    "invites": {"aliases": ["invites", "invite"], "meta": []},
    "muted users": {"aliases": ["muted users"], "meta": []},
    "scheduled messages": {"aliases": ["scheduled messages"], "meta": ["message"]},
    "reminders": {"aliases": ["reminders", "reminder"], "meta": []},
    # =====================================================================
    # TESTING (rolls all sub-tests up; "tests" is excluded from output)
    # =====================================================================
    "tests": {
        "aliases": [
            "tests",
            "test",
            "node tests",
            "test backend",
            "test runner",
            "test classes",
            "test helpers",
            "web/tests",
            "zulip test",
            "e2e tests",
            "filter tests",
            "activity tests",
            "test docs",
            "test subs",
        ],
        "meta": [],
    },
    "puppeteer tests": {"aliases": ["puppeteer tests", "puppeteer"], "meta": ["tests"]},
    "zjquery": {"aliases": ["zjquery"], "meta": ["tests"]},
    # =====================================================================
    # TOOLING
    # =====================================================================
    "tools": {"aliases": ["tools"], "meta": []},
    "ruff": {"aliases": ["ruff"], "meta": ["tools"]},
    "lint": {"aliases": ["lint"], "meta": ["tools"]},
    "eslint": {"aliases": ["eslint"], "meta": ["tools"]},
    "mypy": {"aliases": ["mypy"], "meta": ["tools"]},
    "stylelint": {"aliases": ["stylelint"], "meta": ["tools"]},
    "ci": {"aliases": ["ci"], "meta": []},
    "dependencies": {"aliases": ["dependencies"], "meta": []},
    "requirements": {"aliases": ["requirements"], "meta": ["dependencies"]},
    "install": {"aliases": ["install", "install uv", "install node", "install shfmt"], "meta": []},
    "run dev": {"aliases": ["run dev"], "meta": ["tools"]},
    "populate db": {
        "aliases": ["populate db", "populate_db", "populate analytics"],
        "meta": ["tools"],
    },
}


def build_alias_lookup() -> dict[str, str]:
    """Inverse map: normalized raw prefix → canonical area."""
    lookup: dict[str, str] = {}
    for canonical, info in AREAS.items():
        # Canonical name itself is always an alias.
        lookup[canonical] = canonical
        for alias in info["aliases"]:
            lookup[alias] = canonical
    return lookup


def get_meta_areas(canonical: str) -> list[str]:
    """Returns the meta-areas a canonical area rolls up to (excluding self)."""
    if canonical in AREAS:
        return AREAS[canonical]["meta"]
    return []
