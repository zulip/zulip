# AI integrations

Zulip’s [topics](https://zulip.com/help/introduction-to-topics) organize
conversations within a channel, which is ideal for integrating with AI systems
and collaborating with AI agents. With Zulip's structure, it's easy to prompt an AI
with the appropriate context for what you want to accomplish.

You can connect your AI models of choice with Zulip using the [interactive bots
API](https://zulip.com/api/running-bots), which makes it convenient to have AI
models participate in conversations in whatever ways your organization finds
most effective as the technology evolves.

Future Zulip releases will also contain built-in AI features, such as topic
summarization. A major advantage of self-hosting your team chat system
in the age of AI is that you maintain full control over your internal
communications. It’s up to you how you allow third parties and AI models to
process messages.

Zulip Server 10.x includes a beta topic summarization feature that is available
for testing and experimentation. We appreciate any
[feedback](../contributing/suggesting-features.md)
on your experience, and what configuration options and additional features your
organization would find useful.

## Built-in AI features

### Data privacy

Making sure customer data is protected is [our highest
priority](https://zulip.com/security/). We don’t train LLMs on Zulip Cloud
customer data, and we have [no plans to do
so](https://blog.zulip.com/2024/05/23/self-hosting-keeps-your-private-data-out-of-ai-models/).

We are committed to keeping Zulip 100% open-source, so the source code that
defines how data is processed is available for third parties to review and
audit.

### General configurations

Self-hosted Zulip installations can choose whether to self-host their own AI
models or use a third-party AI model API provider of their choice. Zulip’s AI
integrations use the [LiteLLM](https://www.litellm.ai/) library, which makes it
convenient to configure Zulip to use any popular AI model API provider.

- **Server settings**: You can control costs using `INPUT_COST_PER_GIGATOKEN`,
  `OUTPUT_COST_PER_GIGATOKEN`, and `MAX_PER_USER_MONTHLY_AI_COST` settings,
  which let you set a monthly per-user AI usage budget with whatever pricing is
  appropriate for your selected model.
- **Organization settings**: Administrators can specify who can use each AI
  feature that is enabled by the server. The permission can be assigned to any
  combination of roles, groups, and individual users.
- **Personal settings**: Users who find AI features intrusive or distracting can
  hide them from the UI with a **Hide AI features** personal preference setting.

### Topic summarization beta

:::{note}

Topic summarization is not yet available in Zulip Cloud.

:::

The Zulip server supports generating summaries of topics, with convenient
options for doing so in the web/desktop application’s topic actions menus.

#### How it works

:::{warning}

As with all features powered by LLMs, topic summaries may contain errors and
hallucinations.

:::

The topic summarization feature uses a Zulip-specific prompt with off-the-shelf
third-party large language models.

When a user asks for a summary of a given topic, the Zulip server fetches recent
messages in that conversation that are accessible to the acting user, and sends
them to the AI model to generate a summary.

Emoji reactions, images, and uploaded files are currently not included in what
is sent to the AI model, though some LLMs may have features that might follow
links in content they are asked to summarize. (Note that Zulip’s permissions
model for uploaded files will prevent the LLM from accessing them unless the
files have been posted to a channel with the [public access
option](https://zulip.com/help/public-access-option) enabled.)

#### Enabling topic summarization

:::{important}

If you use a third-party AI platform for topic summarization, you are trusting
the third party with the security and confidentiality of all the messages that
are sent for summarization.

:::

Enable topic summarization by configuring `TOPIC_SUMMARIZATION_MODEL`
and related configuration settings in `/etc/zulip/settings.py`. Topic
summarization and settings for controlling it will appear in the UI
only if your server is configured to enable it.

#### Choosing a model

When modeling the pricing for a given model provider, you’ll primarily want to
look at the cost per input token. Because useful summaries are short compared to
the messages being summarized, more than 90% of tokens used in generating topic
summaries end up being input tokens.

Our experience in early 2025 has been that midsize ~70B parameter models
generate considerably more useful and accurate summaries than smaller ~8B
parameter models.
