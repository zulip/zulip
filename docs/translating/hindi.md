# Hindi translation style guide(हिन्दी अनुवाद शैली मार्गदर्शक)

## Note(ध्यान रखें)

The language style of Zulip is a little colloquial, while the Hindi
translation prefers a formal style and also avoids stereotypes. Since
Zulip is a modern internet application, many Hindi translations are
borrowed from the popular Web software, such as facebook, bing, google 
search etc. that most Hindi users are familiar with.

Zulip की भाषा शैली थोड़ी बोलचाल की है, जबकि हिन्दी अनुवाद में औपचारिक शैली को पसंद किया जाता है
और रूढ़िवादी से बचा जाता है। Zulip एक आधुनिक इंटरनेट अनुप्रयोग है, कई हिंदी अनुवाद facebook,
bing, google search जैसे लोकप्रिय वेब सॉफ़्टवेयर से उधार लिए गए है

## Terms(शर्तें)

* Message - **संदेश**

"Message" can be literally translated as "संदेश" and "जानकारी", both
OK. Here "संदेश" is chosen for translation. For example, "Stream
Message" is translated as "चैनल संदेश", while "Private Message" is
translated as "व्यक्तिगत संचार". "Starred Message" is similar to "Star Mail (स्टार मेल)" 
so it is translated into "स्टार संदेश".

Message वस्तुतः "संदेश" और "जानकारी", दोनों के रूप में अनुवाद किया जा सकता है। 
यहां "संदेश" अनुवाद के लिए चुना जाता है । उदाहरण के लिए, "Stream Message"
"चैनल संदेश" के रूप में अनुवादित है, जबकि "Private Message" "व्यक्तिगत संचार" के रूप में 
अनुवादित है । "Starred Message" के समान है "Star Mail (स्टार मेल)"
इसलिए इसका "स्टार संदेश" में अनुवाद किया है ।

* Realm - **क्षेत्र**

In Hindi "Realm" is literally translated as "अधिकार क्षेत्र(domain)", "राज्य
(Kingdom)" and is clearly inappropriate for Zulip. "Realm" in Zulip
documents is also interpreted as "Organization". And "Realm" has some
relation with "domain", e.g. Settings can be done in setting page to
restrict user login coming from different "domain". Here "Realm" is
translated as "समाज(Community)" temporarily. Another choice is "समाज
(Communities)", which is borrowed from Google+. Recently "समूह(Team)"
is being taken into account for translation, because it seems more
appropriate and many sentences can be translated much better and
easier than "समाज".

हिंदी में "Realm" वस्तुतः "अधिकार क्षेत्र (domain)" के रूप में अनुवादित है, "राज्य(Kingdom)" 
और Zulip के लिए स्पष्ट रूप से अनुपयुक्त है । Zulip में "Realm" दस्तावेज़ को "Organization" 
के रूप में भी समझा जाता है । और "दायरे" के "अधिकार क्षेत्र" के साथ कुछ संबंध है, उदाहरण के लिए 
सेटिंग पृष्ठ में लॉगिन सीमित किया जा सकता है यदि उपयोगकर्ता अलग "अधिकार क्षेत्र" से आ रहा है । 
यहां "Realm" "समाज (Community)" के रूप में अस्थाई रूप से अनुवादित है । एक अंय विकल्प है "समाज
(Communities) ", जो Google + से उधार लिया जाता है । हाल ही में "समूह (Team)"
अनुवाद के लिए ध्यान में रखा जा रहा है, क्योंकि यह अधिक उचित लगता है और कई वाक्य बहुत बेहतर 
अनुवाद किए जा सकते है और "समाज" से आसान है।

* Topic - **विषय**

* Invite-Only/Public Stream - **केवल आमंत्रण/सार्वजनिक स्ट्रीम**

"Invite-Only Stream" requires users must be invited explicitly to
subscribe, which assures a high privacy. Other users can not perceive
the presence of such streams. Since literal translation is hard to
read, it is translated sense to sense as "निजी स्ट्रीम(Private Stream)".

"Invite-Only Stream" की आवश्यकता है उपयोगकर्ताओं को स्पष्ट रूप से सदस्यता लेने के लिए आमंत्रित 
किया जाना चाहिए जो एक उच्च गोपनीयता का आश्वासन दे। अंय उपभोक्ता ऐसी धाराओं की मौजूदगी को अनुभव 
नहीं कर सकते है। चूंकि शाब्दिक अनुवाद पड़ने के लिए कठिन है  यह अर्थ के रूप में "निजी स्ट्रीम 
(Private Stream)" भावना को अनुवादित है"


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

