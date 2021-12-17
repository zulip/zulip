# German translation style guide (Richtlinien für die deutsche Übersetzung)

Thank you for considering to contribute to the German translation!
Before you start writing, please make sure that you have read the
following general translation rules.

## Rules

### Formal or informal?

**Informal.**

Although written German tends to be quite formal, websites in German are
usually following informal netiquette. As Zulip's guides are written
in a more colloquial style, German translations should be rather informal as well.

**Don't use slang or regional phrases in the German translation:**

- Instead of _"So'n Dreck kann jedem mal passieren."_, you could
  say _"Dieser Fehler tritt häufiger auf."_

- "Das ist die Seite, wo der Quelltext steht." - the "_wo_" is regional,
  say _"Das ist die Seite, auf der der Quelltext steht."_ instead.

### Form of address

**Use "Du" instead of "Sie".**

For the reasons provided in [the previous section](#formal-or-informal),
stick to _Du_ (informal) instead of _Sie_ (formal) when addressing
the reader and remember to capitalize _Du_.

### Form of instruction

**Prefer imperative over constructions with auxiliary verbs.**

For instructions, try to use the imperative (e.g. _"Gehe auf die Seite"_ -
_"Go to the page"_) instead of constructions with auxiliary verbs
(e.g. _"Du musst auf die Seite ... gehen"_ - _"You have to go the page ..."_).
This keeps the phrases short, less stiff and avoids unnecessary addressing
of the reader.

### Rules for labels

**Use continuous labels with verbs in infinitive form**

To be consistent with other online platforms, use continuous labels for buttons,
item titles, etc. with verbs in infinitive form,
e.g. _Manage streams_ - _Kanäle verwalten_ instead of _Verwalte Kanäle_.

### Concatenation of words

**Try to avoid it.**

German is famous for its concatenations of nouns
(e.g. _Heizölrückstoßdämpfung_, which means _fuel oil recoil attenuation_).
For the sake of correct rendering and simplicity, you should try to avoid such
concatenations whenever possible, since they can break the layout of the Zulip
frontend. Try to stick to a maximum length of 20 characters and follow your
intuition.

- A term like _Tastaturkürzel_ for _Keyboard shortcuts_ is fine - it is
  shorter than 20 characters and commonly used in web applications.

- A term like _Benachrichtigungsstichwörter_ for _Alert words_ should
  not be used, it sounds odd and is longer than 20 characters.
  You could use "_Stichwörter, die mich benachrichtigen_" instead.

### Anglicisms

**Use them if other web apps do so and a teenager could understand the term.**

Unlike other languages, German happily adapts modern words from English.
This becomes even more evident in internet applications,
so you should not be afraid of using them if they provide an advantage over
the German equivalent. Take the following two examples as a reference:

- Translating _Stream_: Use the German word _Kanal_, since it is just as short
  and used in other web apps.

- Translating _Bot_: Use _Bot_, as a completely accurate German
  equivalent **doesn't** exist (e.g. _Roboter_) and the term _Bot_ is not
  unknown to German speakers.

### Special characters

**Use "ä, ö, ü" and "ß" consistently.**

While _ä, ö, ü_ and _ß_ are more and more being replaced by _ae, oe, ue_
and _ss_ in chats, forums and even websites, German translations
containing umlauts have a more trustworthy appearance.
For capitalizations, you can replace the _ß_ by _ss_.

### False friends

**Watch out!**

A false friend is a word in another language that is spelled
or sounds similar to a word in one's own language,
yet has a different meaning.
False friends for the translation from German to English include
_actually_ - _eigentlich_, _eventually_ - _schließlich_, _map_ - _Karte_, etc.
Make sure to not walk into such a trap.

### Other

- Try to keep words and phrases short and understandable. The front-end
  developers will thank you ;)

- Be consistent. Use the same terms for the same things, even if that
  means repeating. Have a look at other German translations on Zulip
  to get a feeling for the vocabulary.

- Balance common verbs and nouns with specific IT-related translations
  of English terms - this can be tricky, try to check how other resources
  were translated (e.g. Gmail, Microsoft websites, Facebook) to decide
  what wouldn't sound awkward / rude in German.

- For additional translation information, feel free to check out
  [this](https://en.wikipedia.org/wiki/Wikipedia:Translating_German_WP) Wikipedia guide
  on translating German Wikipedia articles into English.

Some terms are very tricky to translate, so be sure to communicate with other German
speakers in the community. It's all about making Zulip friendly and usable.

## Terms (Begriffe)

- Message - **Nachricht**

_"Nachricht" (Facebook, WhatsApp, Transifex)_

- Private Message (PM) - **Private Nachricht (PN)**

Since we try to avoid concatenating words whenever possible, don't use
"Privatnachricht" . PN is the officially used abbreviation for
"Private Nachricht" and is used in many German chat forums.

_"Private Nachricht" (YouTube, Transifex)_

- Starred Message - **Markierte Nachricht**

We go with "markiert" instead of "gesternt" (which is not even a proper
German word) here, since it comes closer to the original meaning of "starred".

_"Markierte Nachricht" (Gmail, Transifex),
"Nachricht mit Stern" (WhatsApp)_

_"Bereich" (Transifex), "Community" (Google+)_

- Stream - **Stream**

Even though the term **Stream** is not commonly used in German web applications,
it is both understood well enough by many Germans with only little English
skills, and the best choice for describing Zulip's chat hierarchy. The term
"Kanal" wouldn't fit here, since it translates to "channel" - these are used
by other chat applications with a simple, flat chat hierarchy, that is,
no differentiation between streams and topics.

_"Stream" (Transifex), "Kanal" (KDE IRC documentation, various
small German forums)_

- Topic - **Thema**

_(Gmail - for email subjects, Transifex)_

- Invite-Only Stream - **Geschlossener Stream**

For users to be able to join to an "invite-only" stream, they must have been
invited by some user in this stream. This type of stream is equivalent to
Facebook's "closed" groups, which in turn translates to "geschlossen" in German.
This translation seems to be appropriate, for example [Linguee](https://www.linguee.de/englisch-deutsch/uebersetzung/invite-only.html)
search returns only paraphrases of this term.

_"Geschlossener Stream" (Transifex), "Geschlossene Gruppe" (Facebook),
paraphrases (Linguee)_

- Public Stream - **Öffentlicher Stream**

While some might find this direct translation a tad long, the alternative
"Offener Stream" can be ambiguous - especially users who are inexperienced
with Zulip could think of this as streams that are online.

_"Öffentlicher Stream" (Transifex)_

- Bot - **Bot**

Not only is "bot" a short and easily memorable term, it is also widely used
in German technology magazines, forums, etc.

_"Bot" (Transifex, Heise, Die Zeit)_

- Integration - **Integration**

While the German translation of "Integration" is spelled just like the English
version, the translation is referring to the German term. For this reason,
use "Integrationen" instead of "Integrations" when speaking of multiple
integrations in German. There aren't many German sources available for this
translation, but "Integration" has the same meaning in German and English.

_"Integration/-en" (Transifex)_

- Notification - **Benachrichtigung**

Nice and easy. Other translations for "notification" like
"Erwähnung", "Bescheid" or "Notiz" don't fit here.

_"Benachrichtigung" (Facebook, Gmail, Transifex, Wikipedia)_

- Alert Word - **Signalwort**

This one is tricky, since one might initially think of "Alarmwort" as a proper
translation. "Alarm", however, has a negative connotation, people link it to
unpleasant events. "Signal", on the other hand, is neutral, just like
"alert word". Nevertheless, [Linguee](https://www.linguee.de/deutsch-englisch/search?source=auto&query=alert+word)
shows that some websites misuse "Alarm" for the translation.

_"Signalwort" (Transifex), "Wort-Alarm" (Linguee)_

- View - **View** (Developer documentation)

Since this is a Zulip-specific term for

> every path that the Zulip server supports (doesn’t show a 404 page for),

and there is no German equivalent, talking of "Views" is preferable in the
developer documentation and makes it easier to rely on parts of the German
_and_ parts of the English documentation.

- View - **Ansicht** (User-facing documentation)

For user-facing documentation, we want to use "Ansicht" instead of "view",
as "Ansicht" provides a translated description for what you think of when
hearing "view". "Ansicht" is not desirable for the developer documentation,
since it does not emphasize the developing aspects of views (in contrast to
anglicisms, which Germans often link to IT-related definitions).

_"Ansicht" (Transifex)_

- Home - **Startseite**

Nice and easy. "Zuhause" obviously doesn't fit here ;).

_"Startseite" (Facebook, Transifex)_

- Emoji - **Emoji**

"Emoji" is the standard term for Emojis. Any other Germanized translation like
"Bildschriftzeichen" (which exists!) would sound stiff and outdated. "Emoticon"
works as well, but is not that common in German.

_"Emoji" (Facebook, WhatsApp), "Emoticon" (Google+)_

## Phrases (Ausdrücke)

- Subscribe/Unsubscribe - **Abonnieren/Deabonnieren**

This translation is unambiguous.

_"Deabonnieren" (YouTube, Transifex)_

- Narrow to - **Begrenzen auf**

Transifex has two different translations for "Narrow to" -
"Schränke auf ... ein." and "Begrenze auf ... ." Both sound a bit strange to a
German speaker, since they would expect grammatically correct sentences when
using the imperative (e.g. "Schränke diesen Stream ein auf ... .") Since this
would be too long for many labels, the infinitive "begrenzen auf" is preferable.
"einschränken auf" sounds equally good, but Transifex shows more use cases for
"begrenzen auf".

_"Schränke auf ... ein." (Transifex) "Begrenze auf ... ." (Transifex)_

- Filter - **Filtern**

A direct translation is fine here. Watch out to to use the infinitive instead
of the imperative, e.g. "Nachrichten filtern" instead of "Filtere Nachrichten".

_"Filtern" (Thunderbird, LinkedIn)_

- Mute/Unmute - **Stummschalten/Lautschalten**

"Lautschalten" is rarely used in German, but so is "Stummschaltung
deaktivieren". Since anyone can understand the idea behind "Lautschalten", it is
preferable due to its brevity.

- Deactivate/Reactivate - **Deaktivieren/Reaktivieren**

_"Deaktivieren/Reaktivieren" (Transifex)_

- Search - **Suchen**

_"Suchen" (YouTube, Google, Facebook, Transifex)_

- Pin/Unpin - **Anpinnen/Loslösen**

While "pinnen" is shorter than "anpinnen", "anpinnen" sweeps any amiguity out of
the way. This term is not used too often on Zulip, so the length shouldn't be a
problem.

_"Anpinnen/Ablösen" (Transifex), "Pinnen" (Pinterest)_

- Mention/@mention - **Erwähnen/"@-Erwähnen**

Make sure to say "@-erwähnen", but "die @-Erwähnung" (capitalized).

_"Erwähnen/@-Erwähnen" (Transifex)_

- Invalid - **Ungültig**

_"Ungültig" (Transifex)_

- Customization - **Anpassen**

The literal translation "Anpassung" would sound weird in most cases, so we use
the infinitive form "anpassen".

- I want - **Ich möchte**

"Ich möchte" is the polite form of "Ich will".

_"Ich möchte" - (Transifex, general sense of politeness)_

- User - **Nutzer**

"Benutzer" would work as well, but "Nutzer" is shorter and more commonly
used in web applications.

_"Nutzer" (Facebook, Gmail), "Benutzer" (Transifex)_

- Person/People - Nutzer/Personen

We use "Personen" instead of plural "Nutzer" for "people", as "Nutzer" stays
the same in plural.

_"Nutzer/Personen" (Transifex)_

## Other (Verschiedenes)

- You - **Du**

Why not "Sie"? In brief, Zulip and other web applications tend to use a rather
informal language. If you would like to read more about the reasoning behind
this, refer to the [general notes](#formal-or-informal) for
translating German.

_"Du" (Google, Facebook), "Sie" (Transifex)_

- We - **Wir** (rarely used)

German guides don't use "wir" very often - they tend to reformulate the
phrases instead.

_"Wir" (Google, Transifex)_
