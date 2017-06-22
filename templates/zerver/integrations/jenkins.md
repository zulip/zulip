{!create-stream.md!}

### Install the plugin

Install the "Zulip" plugin by going to
**Manage Jenkins > Manage Plugins > Available**,
typing in **Zulip**, and clicking **Install without
restart**. (For historical reasons, the plugin might be named
"Humbug Plugin" in some places)

![](/static/images/integrations/jenkins/001.png)

### Configure the plugin

Once the plugin is installed, configure it by going to
**Manage Jenkins > Configure System**. Scroll to the section
labeled **Zulip Notification Settings**, and specify your
bot's email address, API key, the stream receiving the
notifications, and whether you'd like a notification on every
build, or only when the build fails (Smart Notification).

(If you don't see this option, you may first need to restart
Jenkins.)

![](/static/images/integrations/jenkins/002.png)

### Configure a post-build action for your project

Once you've done that, it's time to configure one of your
projects to use the Zulip notification plugin. From your
project page, click **Configure** on the left sidebar. Scroll to
the bottom until you find the section labeled **Post-build
Actions**. Click the dropdown and select **Zulip Notification**.
It should look as below. Then click **Save**.

![](/static/images/integrations/jenkins/003.png)

When your builds fail or succeed, you'll see a commit message
with a topic that matches the project name (in this case
"SecretProject").

{!congrats.md!}

![](/static/images/integrations/jenkins/004.png)

### Troubleshooting

1. Did you set up a post-build action for your project?

2. Does the stream you picked (e.g. `jenkins`) already exist?
   If not, add yourself to it and try again.

3. Are your access key and email address correct? Test them
   using [our curl API](/api).

4. Still stuck? Email [zulip-devel@googlegroups.com][mail].

[mail]: mailto:zulip-devel@googlegroups.com?subject=Jenkins
