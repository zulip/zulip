# Croatian translation style guide

Croatian translations of Zulip use the informal singular ("ti"), the same
register as the Polish and German translations, because the app speaks to
one person at a time and formal plural ("Vi") reads like a bank letter in a
chat application.

A few specifics:

- Informal "you" (_ti_) instead of the formal plural (_Vi_) or any titles:
  _Obrati se administratoru_, not _Obratite se administratoru_.

- Imperative for buttons and actions: _Pošalji_, _Spremi_, _Odustani_,
  _Pritisni_, _Klikni_, _Provjeri_.

- Keep the wording gender-neutral wherever Croatian would otherwise have to
  guess the reader's gender. Prefer the imperative, the present tense or
  impersonal forms (_zatraženo je_, _spremljeno_, _poslano_, _nije moguće
  pristupiti_) over past-tense verbs that agree with the subject (_poslao
  si_, _poslala si_). This matters most in e-mail subjects and system
  notifications, where there is no visible "you" to lean on.

- Croatian has three plural forms: _one_ (1, 21, 31…), _few_ (2–4, 22–24…)
  and _other_ (0, 5–20, 25…). Always fill all three in ICU plural strings
  and in Weblate's plural tabs, even when the English source only has
  _one_/_other_. Copying the English two-form pattern leaves the few-form
  grammatically wrong.

- Croatian typography: quotation marks „…”, the en dash for ranges (5–10),
  a decimal comma (1,5) and a full stop in dates (1. 8. 2024.). Use the
  month name form in prose (_1. kolovoza 2024._) and the numeric form in
  compact UI (_1. 8. 2024._).

- Sentence case for buttons, labels and menu items, as in the English
  source: _Spremi promjene_, not _Spremi Promjene_.

- Do not translate product and brand names: _Zulip_, _Slack_, _GitHub_,
  _GitLab_, _Mastodon_, _Bluesky_, _LinkedIn_, _Gravatar_, _Codeberg_,
  _Discord_, _Klipy_. They are also left in Latin script when the rest of
  the sentence is Croatian, e.g., _Poveži svoj GitHub račun_.

- Prefer standard Croatian vocabulary over regional or Serbian variants
  (_tisuća_, _tjedan_, _točka_, _računalo_ rather than _hiljada_,
  _nedjelja_ in the "week" sense, _tačka_, _kompjuter_). Avoid loanwords
  where a settled Croatian term exists, but keep the established IT ones
  (_bot_, _webhook_, _emoji_, _spoiler_, _hostanje_).

- Watch the length. Croatian strings run 10–20 % longer than English, so
  left-sidebar labels, buttons and menu items need the shortest workable
  phrasing. When a term does not fit, shorten the surrounding words rather
  than inventing a new translation for the term.

- Use one verb for one action everywhere, even when it repeats. A single
  "Save" that is sometimes _Spremi_ and sometimes _Pohrani_ reads like two
  different features.

Some terms are very tricky to translate, so be sure to communicate with
other Croatian speakers in the community. It's all about making Zulip
friendly and usable.

## Special terms used in Zulip

The glossary on Hosted Weblate
(<https://hosted.weblate.org/projects/zulip/glossary/hr/>) holds the same
terms and should be updated first when a decision changes, so that the
term suggestions in the translation editor stay correct.

**alert word**: riječ upozorenja

example:

You can set your own alert words for Zulip messages.

> Možeš postaviti vlastite riječi upozorenja za Zulip poruke.

**bot**: bot, plural _botovi_

example:

You can add bots to your organization.

> Možeš dodati botove u svoju organizaciju.

**channel**: kanal. Zulip used to call these "streams"; do not translate the
old term as _strunj_ or _tok_, use _kanal_ for both.

example:

Public channels are visible to everyone in the organization.

> Javni kanali vidljivi su svima u organizaciji.

**combined feed**: objedinjeni pregled

example:

You can see all messages in unmuted channels and topics in the "combined
feed".

> Sve poruke iz neutišanih kanala i tema možeš vidjeti u "objedinjenom
> pregledu".

**direct message**: izravna poruka. The abbreviation _DM_ stays _DM_.

example:

You can send a direct message to any user in your organization.

> Izravnu poruku možeš poslati bilo kojem korisniku u svojoj organizaciji.

**emoji**: emoji, unchanged in singular and plural

example:

Zulip supports emoji both in messages and as reactions.

> Zulip podržava emoji u porukama i kao reakcije.

**integration**: integracija

example:

Zulip supports hundreds of integrations.

> Zulip podržava stotine integracija.

**mention**: spominjanje (noun), spomenuti (verb)

example:

You'll be notified when someone mentions you.

> Dobit ćeš obavijest kad te netko spomene.

**message**: poruka

example:

Move the message to another topic.

> Premjesti poruku u drugu temu.

**mute**: utišati (verb), utišano (adjective)

example:

Muted topics don't appear in your inbox.

> Utišane teme ne prikazuju se u tvom sandučiću.

**narrow**: suziti (verb), sužavanje (noun). _Filtar_ is what the search box
does, _sužavanje_ is what a view does; keep the two apart.

example:

Narrow to messages sent by you.

> Suzi na poruke koje si poslao.

**notification**: obavijest, plural _obavijesti_

example:

Turn on desktop notifications.

> Uključi obavijesti na desktopu.

**organization**: organizacija

example:

Your organization uses Zulip Cloud.

> Tvoja organizacija koristi Zulip Cloud.

**pin**: prikvačiti (verb), _otkvačiti_ for unpinning

example:

Pin a channel to the top of your list.

> Prikvači kanal na vrh popisa.

**reaction**: reakcija

example:

Add a reaction to the message.

> Dodaj reakciju na poruku.

**settings**: postavke

example:

Open your notification settings.

> Otvori svoje postavke obavijesti.

**star**: označiti zvjezdicom (verb), ukloniti zvjezdicu for unstarring;
_starred messages_ is _poruke sa zvjezdicom_

example:

Star this message to find it later.

> Označi ovu poruku zvjezdicom da je kasnije pronađeš.

**subscribe**: pretplatiti se (verb), pretplata (noun)

example:

You are not subscribed to this channel.

> Nisi pretplaćen na ovaj kanal.

**topic**: tema

example:

Start a new topic for a new conversation.

> Započni novu temu za novi razgovor.

**user**: korisnik

example:

Zulip supports an unlimited number of users in an organization.

> Zulip ne ograničava broj korisnika u organizaciji.

**webhook**: webhook, unchanged

example:

Configure the webhook URL in the integration settings.

> Postavi URL webhooka u postavkama integracije.

## Open questions

- **Past-tense agreement.** Croatian past tense reveals gender (_poslao
  si_ / _poslala si_). The current translation avoids it with impersonal
  and present-tense forms, which occasionally sounds more formal than the
  English. A future revision may prefer a gendered form where the reader's
  gender is known (bots' messages, system e-mails to a named user).

- **_Kanal_ vs _stream_.** Zulip renamed "streams" to "channels" and the
  Croatian translation follows the new vocabulary. Older help pages and
  the mobile apps may still show the old wording until their syncs land.

- **Short plural labels.** Sidebar counts (_3 poruke_ / _5 poruka_) fit the
  three-form plural, but very short UI slots sometimes need the genitive
  plural regardless of the number. Where this happens, the string is
  intentionally written with _poruka_ for all counts.

- **Tenant vocabulary.** "Organization" is _organizacija_ throughout, even
  though _tvrtka_ reads more naturally for business deployments; changing
  it would require touching several hundred strings.
