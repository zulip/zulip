*If you are running Jira version 5.2 or greater, or using the hosted
Jira provided by Atlassian, we recommend using the
[web-hook method](./jira) above instead. This plugin supports older
versions of Jira.*

{!create-channel.md!}

### Plugin mechanism

{!download-python-bindings.md!}

#### Plugin installation

The Jira integration plugin requires two Jira plugins. Please install
the following plugins using the **Universal Plugin Manager** in your
Jira installation:

* [Script Runner Plugin][script-runner]
* [SSL Plugin][ssl-plugin]

[script-runner]: https://marketplace.atlassian.com/plugins/com.onresolve.jira.groovy.groovyrunner
[ssl-plugin]: https://marketplace.atlassian.com/plugins/com.atlassian.jira.plugin.jirasslplugin

#### SSL setup

As Zulip is using a StartCOM SSL certificate that is not recognized by
default in the Java installation shipped with Jira, you will need to
tell Jira about the certificate.

1. Navigate to **Administration > System > Configure SSL** and in the
   **Import SSL Certificates** field, enter `{{ api_url }}`.

2. After clicking **Save Certificates**, follow the on-screen
   instructions and restart Jira for it to recognize the proper
   certificates.

#### Zulip integration

1. Copy the folder `integrations/jira/org/` (from the tarball you
   downloaded above) to your Jira `classes` folder.  For self-contained
   Jira installations, this will be `atlassian-jira/WEB-INF/classes/`,
   but this may be different in your deployment.

2. Edit the constants at the top of
   `org/zulip/jira/ZulipListener.groovy` and fill them with the
   appropriate values:

``` Python
String zulipEmail = "jira-notifications-bot@example.com"
String zulipAPIKey = "0123456789abcdef0123456789abcdef"
String zulipStream = "{{ recommended_channel_name }}"
String issueBaseUrl = "https://jira.COMPANY.com/browse/"
```

3. On the **Administrators** page, navigate to
   **Plugins > Other > Script Listeners**.

4. In the **Add Listener** section, click on the **Custom Listener**
   option. Select the events you wish the Zulip integration to fire for,
   and the projects you wish Zulip to be notified for.

5. In the **Name of groovy class** field, enter
   `org.zulip.jira.ZulipListener`.

6. Click **Add Listener**, and Jira will now notify your Zulip of
   changes to your issues! Updates from Jira will be sent to the stream
   you've configured.

{!congrats.md!}

![Jira bot message](/static/images/integrations/jira/001.png)
