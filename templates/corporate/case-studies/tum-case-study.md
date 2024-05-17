## How do you teach 1400+ students?

The [Technical University of Munich](https://www.tum.de/en/) (TUM) is
one of Europe’s top universities. Every year, its Department of
Informatics ([ranked #1 in Germany][tum-ranking]) welcomes over a
thousand freshmen to the undergraduate program.

Teaching introductory computer science courses to 1400-2000 students
at a time is a massive undertaking. Just answering student questions
easily takes 1500+ messages *per homework exercise*. Instructors have
cycled through product after product in search of a way to manage
communication with students, and among the 30-50 person course staff.

## Communication platform is key

[Tobias Lasser](https://ciip.in.tum.de/people/lasser.html), lecturer
at the TUM Department of Informatics, set out to teach an introductory
algorithms class with 1400 students in April 2020, as the COVID-19
pandemic was sweeping across Europe. With instruction moving online,
he knew that finding an effective communication platform was more
important than ever.

“Our default teaching platform is Moodle, which is fine for
announcements, but does not scale for discussions,” Tobias says. “Our
university also hosts Rocket.Chat, but when some colleagues tried it
for a large class, it was a complete mess.” Due to strict European
regulations, cloud-only solutions like Piazza, Slack and Discord were
non-starters for data privacy reasons. “I checked Mattermost and
Element, but wasn’t happy with the user interface for either.” That’s
when Tobias came across Zulip.

## “Better user experience than Slack”

Tobias evaluated Zulip by [visiting the Zulip development
community](/try-zulip/) to see it in action. “It takes a bit of
time to get used to, but Zulip has the best user experience of all the
chat apps I’ve tried,” Tobias says. “With the discussion organized by
topic within each channel, Zulip is the only app that makes hundreds of
conversations manageable.”

Despite initially asking to use Slack, students came to love Zulip’s
model. “Many students commented how great Zulip was on the course
evaluation forms,” Tobias says.

## Word about Zulip spreads

Word about Tobias’s success with teaching with Zulip quickly spread
throughout the department. One year later, the department’s Zulip
organization is used by 4400 students and educators. “I’m working to
establish Zulip as the new default communication platform for teaching
in the department, for classes of all sizes”, Tobias says.

Other instructors have loved using Zulip as well. “I consider Zulip to
be the best tool in terms of privacy and usability, and try to
implement it in all courses where I collaborate,” says Johannes Stöhr,
teaching assistant for multiple courses at the department.

## A welcoming open-source community

Robert Imschweiler, an undergraduate at the TUM, is responsible for
maintaining the department’s Zulip server. “Our chat needs to be
self-hosted to comply with European laws about protecting student
data,” Robert says. “Zulip has been extremely stable and requires no
maintenance beyond installing updates.”

When questions arise, Robert stops by the Zulip development community to ask for
advice. “Right before exams, we had over 1000 students online at once, and I
was worried that the CPU usage was high. The community investigated my
problem immediately, and a couple of days later they [shared a patch]
[czo-patch-thread] that resolved it.” This patch to improve performance at
scale was released to all users as part of [Zulip 4.0][zulip-4-blog].

Since then, Robert has built several Zulip customizations for the
department, and has had them merged to the upstream project. “I feel
very welcomed as a new contributor and am glad that I’ve been able to
contribute a few patches of my own,” Robert says.

---

Learn more about [Zulip for Education](/for/education/), and how
Zulip is being used at the [University of California San Diego](/case-studies/ucsd/).
You can also check out our guides on using Zulip for [conferences](/for/events/)
and [research](/for/research/)!


[tum-ranking]: https://www.in.tum.de/en/the-department/profile-of-the-department/facts-figures/facts-and-figures-2020/
[czo-patch-thread]: https://chat.zulip.org/#narrow/stream/3-backend/topic/Tornado.20performance/near/1111686
[zulip-4-blog]: https://blog.zulip.com/2021/05/13/zulip-4-0-released/
