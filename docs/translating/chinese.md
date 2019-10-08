# Chinese translation style guide(中文翻译指南)

## Note(题记)

The language style of Zulip is a little colloquial, while the Chinese
translation prefers a formal style and also avoids stereotypes. Since
Zulip is a modern internet application, many Chinese translations are
borrowed from the popular Web software, such as WeiBo, WeChat, QQ
Mail etc. that most Chinese users are familiar with.

Zulip的文风比较口语化，考虑到大多数中国用户的习惯，翻译时的语言习惯稍
微正式了一点，但也尽量避免刻板。Zulip是一款时尚的互联网应用，翻译时也
借鉴了中国用户熟悉的微博、微信、QQ邮箱等软件的用语习惯，以期贴近用户。

## Terms(术语)

* Message - **消息**

"Message" can be literally translated as "消息" and "信息", both
OK. Here "消息" is chosen for translation. For example, "Stream
Message" is translated as "频道消息", while "Private Message" is
translated as "私信". The domestic WeiBo, WeChat also keep in line
with the habit. "Starred Message" is similar to "Star Mail (星标邮件)"
feature in QQ Mail, so it is translated into "星标消息".

Message可直译为“消息”、“信息”等，两者皆可，这里统一选用“消息”。例如，
“Stream Message”译作“频道消息”；但“Private Message”又译为“私信"，与国
内微博、微信的使用习惯保持一致。“Starred Message”类似于QQ邮箱中的“星标
邮件”功能，这里也借鉴翻译为“星标消息”。

* Realm - **社区**

In Chinese "Realm" is literally translated as "域(domain)", "王国
(Kingdom)" and is clearly inappropriate for Zulip. "Realm" in Zulip
documents is also interpreted as "Organization". And "Realm" has some
relation with "domain", e.g. Settings can be done in setting page to
restrict user login coming from different "domain". Here "Realm" is
translated as "社区(Community)" temporarily. Another choice is "社群
(Communities)", which is borrowed from Google+. Recently "团队(Team)"
is being taken into account for translation, because it seems more
appropriate and many sentences can be translated much better and
easier than "社区".

Realm直译为“领域”、“王国”，取直译显然不合适。Zulip中关于“Realm”的解释
为“组织”或者“机构”（Organization）；另外，“Realm”还与“域”（domain）有
所联系；例如，“设置页”中可以对“Realm”设置限制，仅允许有相同邮件域名的
用户登录。因此这里选择译为“社区”，可能更接近本义。可选的翻译还有“社群”
（Google+的习惯）。最近发现，“Realm”译为“团队”似乎更合适。尝试在
Transifex中将“社区”替换为“团队”后，发现不少地方比以前通顺了许多。

* Stream - **频道**

There were several other optional translations, e.g. "群组(Group)", "
主题(Subject)", and "栏目(Column)". The "频道(Channel)" is in use now,
which is inspired by the chat "Channel" in the game Ingress. Since
"Stream" can be "Created/Deleted" or "Subscribed/Unsubscribed",
"Stream" can also initiate a "Topic" discussion, the meanings of "频道
(Channel) are closer to "Stream" than others. Another translation is "
讨论组", which is a term of QQ, in which it is a temporary chat
group. However, "讨论组" has one more Chinese character than "频道
(Channel)".

曾经使用的翻译有“群组”、“主题”、“版块”，还有“栏目”。现在选择的“频道”灵
感来源于Ingress游戏中的聊天“Channel”。因为“Stream”可以“新建/删除
（Create/Delete）”、也可以“订阅/退订（Subscribe/Unsubscribe）”，
“Stream”内部还可以发起“话题（Topic）讨论。“Stream”还有一个备选方案，就
是“讨论组”，字多一个，稍微有点啰嗦。主要参考自以前QQ的“讨论组”，在QQ中
是一种临时的群组。

* Topic - **话题**

* Invite-Only/Public Stream - **私有/公开频道**

"Invite-Only Stream" requires users must be invited explicitly to
subscribe, which assures a high privacy. Other users cannot perceive
the presence of such streams. Since literal translation is hard to
read, it is translated sense to sense as "私有频道(Private Stream)"。

“Invite-Only Stream”是需要频道内部用户邀请才能订阅的频道；“Invite-Only
Stream”具有非常好的私密性，用户在没有订阅时是不能感知这类频道的存在的。
直译读起来有点拗口，因此选择译为“私有频道”。

* Bot - **机器人**

* Integration - **应用整合**

"Integration" is literally translated as "集成" or "整合". It means
integrating Zulip production with other applications and services. For
integrity in Chinese expression, it is translated as "应用整合
(Application Integration)".

“Integration”原意为“集成”与“整合”，这里表示将其它的应用或者服务与Zulip
实现整合。为表达意思完整，补充翻译为“应用整合”。

* Notification - **通知**

* Alert Word - **提示词**

## Phrases(习惯用语)

* Subscribe/Unsubscribe - **订阅/退订**

The perfect tense subscribed/unsubscribed is translated as "已订阅/已
退订". Sometimes "Join" is used to express the same meanings as
"Subscribe", also be translated as "订阅(Subscribe)".

完成时态译为“已订阅（Subscribed）”和“已退订（Unsubscribed）”。有时，
“Join”也会用来表达与“Subscribe”相同的意思，也一并翻译为“订阅”。

* Narrow to ... - **筛选**

"Narrow to" is translated as "筛选(Filter by)" for now, based on two considerations:

1. In Chinese, the word "筛选(Filter)" means a way to select according
   to the specific conditions. "Narrow to ..." means "to narrow the
   scope of ...". The two words share the common meanings.

2. "筛选" is a common computer phrase and has been well
   accepted by public, e.g. the "Filter(筛选)" feature in Microsoft
   Excel.

In addition, in the searching context "Narrow to ..." is not
translated as "筛选(Filter)" but as "搜索(Search)" because of
readability considerations.

这里暂且翻译为“筛选”。主要有两点考虑：

1. 在汉语中，“筛选”表示按照指定条件进行挑选的方式。“Narrow to ...”的含
   义为“使...缩小范围”，两者有一定共通性。

2. “筛选”也是比较大众化的计算机用语，易于为大家所接受。例如Microsoft
   Excel中的“筛选”功能。

另外，在搜索功能的语境中，“Narrow to ...”没有翻译为“筛选”，而翻译为“搜
索”，这是出于可读性的考虑。

* Mute/Unmute - **开启/关闭免打扰**

"Mute" is mostly translated as "静音(Silent)", which is common in TV
set.  Such a translation is not appropriate for Zulip. "开启/关闭免打
扰(Turn off/on Notification)" is a sense to sense translation, which
is also borrowed from the WeChat.

“Mute”常见的中文翻译为“静音”，在电视设备中常见，用在Zulip中并不太合适。
这里取意译，与大家常用的微信（WeChat）中“消息免打扰”用语习惯一致。

* Deactivate/Reactivate - **禁用/启用(帐户)，关闭/激活(社区)**

When applied to a user account, translated as "禁用/启用
(Disable/Enable)", for example, "Deactivated users" to "禁用的用户";
when applied to a realm, translated as "关闭/激活(Close/Open)", for
example "Your realm has been deactivated." to "您的社区已关闭".

当应用于用户帐户时，选择翻译为“禁用/启用”，例如“Deactivated users”翻译
为“禁用的用户”；当应用于“社区”（Realm）时，选择翻译为“关闭/激活”，如
“Your realm has been deactivated.”翻译为“您的社区已关闭”。

* Invalid - **不正确**

"Invalid" is mainly used in exception information, which is uncommon
for general users. Other translations "错误(Error)", "非法(Illegal)",
"不合法(Invalid)" are all ok. Generally, it is translated as "不正确
(Incorrect)" for consistency. For example, "Invalid API key" is
translated as "API码不正确".

“Invalid”大部分用于一些异常信息，这些信息普通用户应该很少见到。可选翻
译有“错误”、“非法”、“不合法”；为保持一致的习惯，这里统一翻译为“不正确”。
例如“Invalid API key”翻译为“API码不正确”。

* I want - **开启**

Mainly used in the settings page, literally translated as "I want to
...", which is colloquial and inappropriate in Chinese expression. It
is translated sense to sense as "开启(Turn on some options)".

主要出现在设置页面（Setting Page）中，直译为“我想...”、“我要...”。取直
译过于口语化，并不合乎中文的使用习惯。因此这里取意译，翻译为“开启（某
某功能选项）”。

* User/People/Person - **用户**

All translated as "用户(User)".

统一翻译为“用户”。

## Others(其它)

* You/Your - **您/您的**

It is translated as 您/您的(You/Your) rather than "你/你的(You/Your)",
so as to express respect to the user.

出于尊重用户的目的，翻译为敬语“您/您的”，而不翻译为“你/你的”。

* We - **我们（或不翻）**

"We" is generally translated as the first person "我们(We)", while in
formal Chinese, extensive use of "We" is relatively rare. So in many
times and places it can be ignored not to translate or transforming
expression. For example, "Still no email? We can resend it" is
translated as "仍然没有收到邮件？点击重新发送(Still no email? Click to
resend.)".

一般翻译为第一人称“我们”；但也有不少地方选择不翻译，因为在中文使用习惯
中，不太以自我为中心，大量使用“我们”的情况比较少。因此有时会有下面这样
翻译：“Still no email? We can resend it” 译为 “仍然没有收到邮件？点击
重新发送”。

* The Exclamation/Dot - (一般省略)

The exclamation appears in many places in Zulip. The tone that the
exclamation expresses should be stronger in Chinese than in
English. So the exclamation can be just deleted when translating or
replaced with the dot, unless you are sure to write it. In addition,
the dot in Chinese (。) often has a bad effect on page layout. It is
recommended to omit the dot, just leave empty at the end of the
sentence or paragraph.

感叹号在Zulip中出现非常多，可能英文中感叹号的语气比中文中略轻一点。在
中文翻译建议省略大部分的感叹号。另外，句号在中文排版中比较影响美观，因
此也一般建议省略不翻。句末留空即可。
