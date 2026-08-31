# Zulip Development Environment & LLM Features Setup

This repository contains the extended Zulip codebase with LLM-enabled features for **17-445/17-645/17-745 Machine Learning in Production (Individual Assignment 1)**.

---

## 1. Prerequisites & Environment Setup

Zulip is designed to run in a virtualized development environment using Vagrant or Docker.

### Option A: Using Vagrant (Recommended)
1. Install [Vagrant](https://www.vagrantup.com/) and [VirtualBox](https://www.virtualbox.org/).
2. In the repository root directory, start and provision the Vagrant guest machine:
   ```bash
   vagrant up
   ```
3. SSH into the development environment:
   ```bash
   vagrant ssh
   ```
4. Navigate to the Zulip directory:
   ```bash
   cd /srv/zulip
   ```

### Option B: Using Dev Container / Docker
1. Open this repository in Visual Studio Code.
2. When prompted, click **"Reopen in Container"** (or use the Command Palette: `Dev Containers: Reopen in Container`).

---

## 2. Configuring LLM Credentials

The LLM features utilize OpenAI-compatible endpoints (e.g., Groq, Google Gemini via OpenAI compatibility API, OpenAI, OpenRouter).

### Setting the API Key:
1. Open `zproject/dev-secrets.conf`.
2. Add your API key:
   ```ini
   [secrets]
   topic_summarization_api_key = your-api-key-here
   ```
   *(Note: `zproject/dev-secrets.conf` is gitignored and will never be committed).*

### Optional: Changing Model or API Endpoint
The default development settings are configured in `zproject/dev_settings.py`:
- `TOPIC_SUMMARIZATION_MODEL = "gemini-3.6-flash"` (or `"llama-3.3-70b-versatile"`)
- `TOPIC_SUMMARIZATION_API_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"` (or `"https://api.groq.com/openai/v1"`)

You can customize these in `zproject/dev_settings.py` or by setting environment variables if you wish to use a different provider.

---

## 3. Running the Development Server

From inside the development environment (`vagrant ssh` or container):
```bash
./tools/run-dev
```
- Open your browser and navigate to: **`http://localhost:9991/`** (or `http://localhost:9991/login` for dev login)
- Log in with any development account (e.g., `iago@zulip.com`, `hamlet@zulip.com`, or `desdemona@zulip.com`).

---

## 4. Using Feature 1: Message Recap

### In the Web UI:
1. Log into the Zulip web client (`http://localhost:9991`).
2. Ensure you have unread messages in channels or direct messages (or send test messages between users).
3. Access the **Message Recap** via either:
   - **Left Sidebar**: Click **"Message recap"** under the views list.
   - **Inbox View**: Click the **"Recap"** button (with the magic wand icon) in the Inbox search/filter bar.
4. An interactive modal dialog opens displaying an AI-generated summary of unread messages grouped by channel and topic.
5. Click on any reference link (e.g. `[link]` / `[message]`) inside the recap to jump directly to the target message in its conversation feed!

### Testing via API / cURL:
```bash
# 1. Fetch API key for a user (e.g., hamlet@zulip.com):
API_KEY=$(curl -s -X POST 'http://localhost:9991/api/v1/dev_fetch_api_key' --data-urlencode 'username=hamlet@zulip.com' | jq -r '.api_key')

# 2. Call the Message Recap endpoint:
curl -s -X GET "http://localhost:9991/api/v1/messages/recap" -u "hamlet@zulip.com:${API_KEY}" | jq .
```

---

## 5. Using Feature 2: Topic Title Improver

### In the Web UI:

#### A. Automatic Detection (On Message Send)
1. Navigate to any stream topic that contains messages (e.g., `#support > blue desktop wasn't linking erratically`).
2. Post a new message discussing a completely different topic (e.g. *"Should we switch our database cache to Redis? What TTL should we use?"*).
3. Immediately after posting, the backend analyzes recent messages for topic drift.
4. If drift is detected, a **Topic Drift Warning Banner** appears above the compose box:
   > ⚠️ *Topic discussion seems to have drifted. Suggested new title: "Redis Database Caching"*
   > **[Rename topic to "Redis Database Caching"]**
5. Click the rename button on the banner to update the topic title across the entire thread with a single click!

#### B. Manual On-Demand Improvement (Via Topic Menu)
1. Hover over any topic in the left sidebar or the topic recipient bar.
2. Click the three dots (**`...`**) topic actions menu.
3. Select **"Improve topic title (AI)"**.
4. An interactive modal opens showing a live AI analysis:
   - If the conversation is on-topic, it confirms that the topic title is accurate.
   - If drift is detected, it presents the suggested new title in an editable text box.
5. Click **"Update Topic Title"** to apply the rename to the conversation thread.

### Testing via API / cURL:
```bash
# 1. Fetch API key for a user (e.g., hamlet@zulip.com):
API_KEY=$(curl -s -X POST 'http://localhost:9991/api/v1/dev_fetch_api_key' --data-urlencode 'username=hamlet@zulip.com' | jq -r '.api_key')

# 2. Call Topic Drift Check endpoint:
curl -s -X POST "http://localhost:9991/api/v1/topics/check_drift" \
  -u "hamlet@zulip.com:${API_KEY}" \
  -d "stream_id=14" \
  --data-urlencode "topic_name=blue desktop wasn't linking erratically" | jq .
```

---

## 6. Running Automated Tests

Run Feature 1 (Message Recap) tests:
```bash
./tools/test-backend zerver/tests/test_message_recap.py
```

Run Feature 2 (Topic Title Improver) tests:
```bash
./tools/test-backend zerver/tests/test_topic_drift.py
```

Run both test suites:
```bash
./tools/test-backend zerver/tests/test_message_recap.py zerver/tests/test_topic_drift.py
```

Run the full backend test suite:
```bash
./tools/test-backend
```

---

## 7. Technical Documentation

For the comprehensive design document covering architecture, link generation, latency/cost/scale optimizations, and production considerations, please see:
- [**`implementation.md`**](file:///Users/akshay/CMU/sem1/MLIP/zulip/implementation.md)
