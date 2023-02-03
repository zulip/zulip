When collaborating with people in another time zone, you often need to
express a specific time clearly. Rather than typing out your time zone
and having everyone translate the time in their heads, in Zulip, you
can mention a time, and it'll be displayed to each user in their own
time zone (just like the timestamps on Zulip messages).

A date picker will appear once you type `<time`.

```
Our next meeting is scheduled for <time:2020-05-28T13:30:00+05:30>
```

A person in San Francisco will see:

> Our next meeting is scheduled for *Thu, May 28 2020, 1:00 AM*.

While someone in India will see:

> Our next meeting is scheduled for *Thu, May 28 2020, 1:30 PM*.

You can also use other formats such as UNIX timestamps or human readable
dates, for example, `<time:May 28 2020, 1:30 PM IST>`.
