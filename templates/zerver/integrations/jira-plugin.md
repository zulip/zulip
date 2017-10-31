*If you are running JIRA version 5.2 or greater, or using the hosted
JIRA provided by Atlassian, we recommend using the
[web-hook method](./jira) above instead. This plugin supports older
versions of JIRA.*

{!create-stream.md!}

### Plugin mechanism

{!download-python-bindings.md!}

#### Plugin Installation

The JIRA integration plugin requires two JIRA plugins. Please install
the following plugins using the **Universal Plugin Manager** in your
JIRA installation:

* [Script Runner Plugin][script-runner]
* [SSL Plugin][ssl-plugin]

[script-runner]: https://marketplace.atlassian.com/plugins/com.onresolve.jira.groovy.groovyrunner
[ssl-plugin]: https://marketplace.atlassian.com/plugins/com.atlassian.jira.plugin.jirasslplugin

#### SSL Setup

As Zulip is using a StartCOM SSL certificate that is not recognized by
default in the Java installation shipped with JIRA, you will need to
tell JIRA about the certificate.

1. Navigate to **Administration > System > Configure SSL** and in the
   **Import SSL Certificates** field, enter `{{ api_url }}`.

2. After clicking **Save Certificates**, follow the on-screen
   instructions and restart JIRA for it to recognize the proper
   certificates.

#### Zulip Integration

1. Copy the folder `integrations/jira/org/` (from the tarball you
   downloaded above) to your JIRA `classes` folder.  For self-contained
   JIRA installations, this will be `atlassian-jira/WEB-INF/classes/`,
   but this may be different in your deployment.

2. Edit the constants at the top of
   `org/zulip/jira/ZulipListener.groovy` and fill them with the
   appropriate values:

``` Python
String zulipEmail = "jira-notifications-bot@example.com"
String zulipAPIKey = "0123456789abcdef0123456789abcdef"
String zulipStream = "{{ recommended_stream_name }}"
String issueBaseUrl = "https://jira.COMPANY.com/browse/"
```

3. On the **Administrators** page, navigate to
   **Plugins > Other > Script Listeners**.

4. In the **Add Listener** section, click on the **Custom Listener**
   option. Select the events you wish the Zulip integration to fire for,
   and the projects you wish Zulip to be notified for.

5. In the **Name of groovy class** field, enter
   `org.zulip.jira.ZulipListener`.

6. Click **Add Listener**, and JIRA will now notify your Zulip of
   changes to your issues! Updates from JIRA will be sent to the stream
   you've configured.

{!congrats.md!}

![](/static/images/integrations/jira/001.png)
