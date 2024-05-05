# Zulip GitLab integration

Receive GitLab notifications in Zulip!

{start_tabs}

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your repository on GitLab and click **Settings** on the left
   sidebar.  Click on **Integrations**.

1. Set **URL** to the URL you generated. Select the
   [events](#filtering-incoming-events) you you would like to receive
   notifications for, and click **Add Webhook**.

!!! warn ""

    **Note**: If your GitLab server and your Zulip server are on a local network
    together, and you're running GitLab 10.5 or newer, you may need to enable
    GitLab's "Allow requests to the local network from hooks and
    services" setting (by default, recent GitLab versions refuse to post
    webhook events to servers on the local network).  You can find this
    setting near the bottom of the GitLab "Settings" page in the "Admin area".

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/gitlab/001.png)

{% if all_event_types is defined %}

{!event-filtering-additional-feature.md!}

{% endif %}

### Configuration options

* By default, the Zulip topics for merge requests will contain the title
  of the GitLab merge request. You can change the topic format to just
  contain the merge request ID by adding `&use_merge_request_title=false`
  to the generated URL.

{!git-branches-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
