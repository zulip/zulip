# German translation style guide (Richtlinien für die deutsche Übersetzung)

Thank you for considering to contribute to the German translation!
Before you start writing, please make sure that you have read the
following general translation rules.


## Rules

### Formal or Informal?

**Informal.**

Although written German tends to be quite formal, websites in German are
usually following informal netiquette. As Zulip's guides are written
in a more colloquial style, German translations should be rather informal as well.

**Don't use slang or regional phrases in the German translation:**

* Instead of *"So'n Dreck kann jedem mal passieren."*, you could
say *"Dieser Fehler tritt häufiger auf."*

* "Das ist die Seite, wo der Quelltext steht." - the "*wo*" is regional,
say *"Das ist die Seite, auf der der Quelltext steht."* instead.

### Form of address

**Use "Du" instead of "Sie".**

For the reasons provided in [the previous section](#formal-or-informal),
stick to *Du* (informal) instead of *Sie* (formal) when addressing
the reader and remember to capitalize *Du*.

### Form of instruction

**Prefer imperative over constructions with auxiliary verbs.**

For instructions, try to use the imperative (e.g. *"Gehe auf die Seite"* -
*"Go to the page"*) instead of constructions with auxiliary verbs
(e.g. *"Du musst auf die Seite ... gehen"* - *"You have to go the page ..."*).
This keeps the phrases short, less stiff and avoids unnecessary addressings
of the reader.

### Rules for labels

**Use continuous labels with verbs in infinitive form**

To be consistent with other online platforms, use continuous labels for buttons,
item titles, etc. with verbs in infinitive form,
e.g. *Manage streams* - *Kanäle verwalten* instead of *Verwalte Kanäle*.

### Concatenation of words

**Try to avoid it.**

German is famous for its concatenations of nouns
(e.g. *Heizölrückstoßdämpfung*, which means *fuel oil recoil attenuation*).
For the sake of correct rendering and simplicity, you should try to avoid such
concatenations whenever possible, since they can break the layout of the Zulip
frontend. Try to stick to a maximum length of 20 characters and follow your
intuition.

* A term like *Tastaturkürzel* for *Keyboard shortcuts* is fine - it is
shorter than 20 characters and commonly used in web applications.

* A term like *Benachrichtigungsstichwörter* for *Alert words* should
not be used, it sounds odd and is longer than 20 characters.
You could use "*Stichwörter, die mich benachrichtigen*" instead.

### Anglicisms

**Use them if other web apps do so and a teenager could understand the term.**

Unlike other languages, German happily adapts modern words from English.
This becomes even more evident in internet applications,
so you should not be afraid of using them if they provide an advantage over
the German equivalent. Take the following two examples as a reference:

* Translating *Stream*: Use the German word *Kanal*, since it is just as short
and used in other web apps.

* Translating *Bot*: Use *Bot*, as a completely accurate German
equivalent **doesn't** exist (e.g. *Roboter*) and the term *Bot* is not
unknown to German speakers.

### Special characters

**Use "ä, ö, ü" and "ß" consistently.**

While *ä, ö, ü* and *ß* are more and more being replaced by *ae, oe, ue*
and *ss* in chats, forums and even websites, German translations
containing umlauts have a more trustworthy appearance.
For capitalizations, you can replace the *ß* by *ss*.

### False friends

**Watch out!**

A false friend is a word in another language that is spelled
or sounds similar to a word in one's own language,
yet has a different meaning.
False friends for the translation from German to English include
*actually* - *eigentlich*, *eventually* - *schließlich*, *map* - *Karte*, etc.
Make sure to not walk into such a trap.

### Other

* Try to keep words and phrases short and understandable. The front-end
developers will thank you ;)

* Be consistent. Use the same terms for the same things, even if that
means repeating. Have a look at other German translations on Zulip
to get a feeling for the vocabulary.

* Balance common verbs and nouns with specific IT-related translations
of English terms - this can be tricky, try to check how other resources
were translated (e.g. GMail, Microsoft websites, Facebook) to decide
what wouldn't sound awkward / rude in German.

* For additional translation information, feel free to check out
[this](https://en.wikipedia.org/wiki/Wikipedia:Translating_German_WP) Wikipedia guide
on translating German Wikipedia articles into English.

Some terms are very tricky to translate, so be sure to communicate with other German
speakers in the community. It's all about making Zulip friendly and usable.


## Terms (Begriffe)

* Message - **Nachricht**

*"Nachricht" (Facebook, WhatsApp, Transifex)*

* Private Message (PM) - **Private Nachricht (PN)**

Since we try to avoid concatenating words whenever possible, don't use
"Privatnachricht" . PN is the officially used abbreviation for
"Private Nachricht" and is used in many German chat forums.

*"Private Nachricht" (Youtube, Transifex)*

* Starred Message - **Markierte Nachricht**

We go with "markiert" instead of "gesternt" (which is not even a proper
German word) here, since it comes closer to the original meaning of "starred".

*"Markierte Nachricht" (GMail, Transifex),
"Nachricht mit Stern" (WhatsApp)*

* Realm - **Realm** (Developer documentation)

**The term "realm" is discouraged in the user documentation and should not be
used there anymore.** However, because of its relevance for the developer
documentation, we still have it included in this list.

* Realm - **Organization** (User documentation)

While the literal translation for "realm" is "Königreich", it is referring to
different domains/organizations on a Zulip server. Since the German term
"Bereich" is a little vague, "Organization" is preferable here.

*"Bereich" (Transifex), "Community" (Google+)*

* Stream - **Stream**

Even though the term **Stream** is not commonly used in German web applications,
it is both understood well enough by many Germans with only little English
skills, and the best choice for describing Zulip's chat hierarchy. The term
"Kanal" wouldn't fit here, since it translates to "channel" - these are used
by other chat applications with a simple, flat chat hierarchy, that is,
no differentiation between streams and topics.

*"Stream" (Transifex), "Kanal" (KDE IRC documentation, various
small German forums)*

* Topic - **Thema**

*(Gmail - for email subjects, Transifex)*

* Invite-Only Stream - **Geschlossener Stream**

For users to be able to join to an "invite-only" stream, they must have been
invited by some user in this stream. This type of stream is equivalent to
Facebook's "closed" groups, which in turn translates to "geschlossen" in German.
This translation seems to be appropriate, for example [Linguee](
http://www.linguee.de/englisch-deutsch/uebersetzung/invite-only.html)
search returns only paraphrases of this term.

*"Geschlossener Stream" (Transifex), "Geschlossene Gruppe" (Facebook),
paraphrases (Linguee)*

* Public Stream - **Öffentlicher Stream**

While some might find this direct translation a tad long, the alternative
"Offener Stream" can be ambiguous - especially users who are inexperienced
with Zulip could think of this as streams that are online.

*"Öffentlicher Stream" (Transifex)*

* Bot - **Bot**

Not only is "bot" a short and easily memorable term, it is also widely used
in German technology magazines, forums, etc.

*"Bot" (Transifex, Heise, Die Zeit)*

* Integration - **Integration**

While the German translation of "Integration" is spelled just like the English
version, the translation is referring to the German term. For this reason,
use "Integrationen" instead of "Integrations" when speaking of multiple
integrations in German. There aren't many German sources available for this
translation, but "Integration" has the same meaning in German and English.

*"Integration/-en" (Transifex)*

* Notification - **Benachrichtigung**

Nice and easy. Other translations for "notification" like
"Erwähnung", "Bescheid" or "Notiz" don't fit here.

*"Benachrichtigung" (Facebook, Gmail, Transifex, Wikipedia)*

* Alert Word - **Signalwort**

This one is tricky, since one might initially think of "Alarmwort" as a proper
translation. "Alarm", however, has a negative connotation, people link it to
unpleasant events. "Signal", on the other hand, is neutral, just like
"alert word". Nevertheless, [Linguee](
http://www.linguee.de/deutsch-englisch/search?source=auto&query=alert+word)
shows that some websites misuse "Alarm" for the translation.

*"Signalwort" (Transifex), "Wort-Alarm" (Linguee)*

* View - **View** (Developer documentation)

Since this is a Zulip-specific term for
> every path that the Zulip server supports (doesn’t show a 404 page for),

and there is no German equivalent, talking of "Views" is preferable in the
developer documentation and makes it easier to rely on parts of the German
*and* parts of the English documentation.

* View - **Ansicht** (User documentation)

For the user documentation, we want to use "Ansicht" instead of "view", as
"Ansicht" provides a translated description for what you think of when hearing
"view". "Ansicht" is not desirable for the developer documentation, since it
does not emphasize the developing aspects of views (in contrast to anglicisms,
which Germans often link to IT-related definitions).

*"Ansicht" (Transifex)*

* Home - **Startseite**

Nice and easy. "Zuhause" obviously doesn't fit here ;).

*"Startseite" (Facebook, Transifex)*

* Emoji - **Emoji**

"Emoji" is the standard term for Emojis. Any other Germanized translation like
"Bildschriftzeichen" (which exists!) would sound stiff and outdated. "Emoticon"
works as well, but is not that common in German.

*"Emoji" (Facebook, WhatsApp), "Emoticon" (Google+)*


## Phrases (Ausdrücke)

* Subscribe/Unsubscribe - **Abonnieren/Deabonnieren**

This translation is unambiguous.

*"Deabonnieren" (Youtube, Transifex)*

* Narrow to - **Begrenzen auf**

Transifex has two different translations for "Narrow to" -
"Schränke auf ... ein." and "Begrenze auf ... ." Both sound a bit strange to a
German speaker, since they would expect grammatically correct sentences when
using the imperative (e.g. "Schränke diesen Stream ein auf ... .") Since this
would be too long for many labels, the infinitive "begrenzen auf" is preferable.
"einschränken auf" sounds equally good, but Transifex shows more use cases for
"begrenzen auf".

*"Schränke auf ... ein." (Transifex) "Begrenze auf ... ." (Transifex)*

* Filter - **Filtern**

A direct translation is fine here. Watch out to to use the infinitive instead
of the imperative, e.g. "Nachrichten filtern" instead of "Filtere Nachrichten".

*"Filtern" (Thunderbird, LinkedIn)*

* Mute/Unmute - **Stummschalten/Lautschalten**

"Lautschalten" is rarely used in German, but so is "Stummschaltung
deaktivieren". Since anyone can understand the idea behind "Lautschalten", it is
preferable due to its brevity.

* Deactivate/Reactivate - **Deaktivieren/Reaktivieren**

*"Deaktivieren/Reaktivieren" (Transifex)*

* Search - **Suchen**

*"Suchen" (Youtube, Google, Facebook, Transifex)*

* Pin/Unpin - **Anpinnen/Loslösen**

While "pinnen" is shorter than "anpinnen", "anpinnen" sweeps any amiguity out of
the way. This term is not used too often on Zulip, so the length shouldn't be a
problem.

*"Anpinnen/Ablösen" (Transifex), "Pinnen" (Pinterest)*

* Mention/@mention - **Erwähnen/"@-Erwähnen**

Make sure to say "@-erwähnen", but "die @-Erwähnung" (capitalized).

*"Erwähnen/@-Erwähnen" (Transifex)*

* Invalid - **Ungültig**

*"Ungültig" (Transifex)*

* Customization - **Anpassen**

The literal translation "Anpassung" would sound weird in most cases, so we use
the infinitive form "anpassen".

* I want - **Ich möchte**

"Ich möchte" is the polite form of "Ich will".

*"Ich möchte" - (Transifex, general sense of politeness)*

* User - **Nutzer**

"Benutzer" would work as well, but "Nutzer" is shorter and more commonly
used in web applications.

*"Nutzer" (Facebook, Gmail), "Benutzer" (Transifex)*

* Person/People - Nutzer/Personen

We use "Personen" instead of plural "Nutzer" for "people", as "Nutzer" stays
the same in plural.

*"Nutzer/Personen" (Transifex)*

## Other (Verschiedenes)

* You - **Du**

Why not "Sie"? In brief, Zulip and other web applications tend to use a rather
informal language. If you would like to read more about the reasoning behind
this, refer to the [general notes](#formal-or-informal) for
translating German.

*"Du" (Google, Facebook), "Sie" (Transifex)*

* We - **Wir** (rarely used)

German guides don't use "wir" very often - they tend to reformulate the
phrases instead.

*"Wir" (Google, Transifex)*
