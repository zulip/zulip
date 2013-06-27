var tutorial = (function () {

var exports = {};
var is_running = false;

// We'll temporarily set stream colors for the streams we use in the demo
// tutorial messages.
var real_stream_info;
var tutorial_stream_info = {"design": {"color": "#76ce90"},
                            "social": {"color": "#fae589"},
                            "devel": {"color": "#a6c7e5"}};

// Each message object contains the minimal information necessary for it to be
// processed by our system for adding messages to your feed.
var fake_messages = [
    {
        id: 1,
        content: "<p>We're working on some new screenshots for our landing page, and I'll show you what I have shortly.</p>",
        is_stream: true,
        sender_full_name: "Waseem Daher",
        avatar_url: "https://secure.gravatar.com/avatar/364a79a57718ede3fadf6dd3623d2e0a",
        display_recipient: "design",
        stream: "design",
        subject: "screenshots",
        timestr: "12:11",
        type: "stream"
    },
    {
        id: 2,
        content: "<p>Hey, if I work on Windows, can you two make one for Mac and Linux?</p>",
        is_stream: false,
        sender_full_name: "Waseem Daher",
        avatar_url: "https://secure.gravatar.com/avatar/364a79a57718ede3fadf6dd3623d2e0a",
        display_reply_to: "Jeff Arnold, Waseem Daher",
        reply_to: true,
        timestr: "12:12",
        type: "private"
    },
    {
        id: 3,
        content: "<p>Sure, no problem <img alt=':+1:' class='emoji' src='static/third/gemoji/images/emoji/+1.png' title=':+1:'></p>",
        is_stream: false,
        sender_full_name: "Jessica McKellar",
        avatar_url: "https://secure.gravatar.com/avatar/c89814a8ed5814421b617cf2242ff01a",
        display_reply_to: "Jeff Arnold, Waseem Daher",
        reply_to: true,
        timestr: "12:12",
        type: "private"
    },
    {
        id: 4,
        content: "<p>Ok, here's my <a href='https://humbughq.com/static/images/app-screenshots/humbug-chrome-windows.png' target='_blank' title='https://humbughq.com/static/images/app-screenshots/humbug-chrome-windows.png'>latest version</a><div class='message_inline_image'><a href='https://humbughq.com/static/images/app-screenshots/humbug-chrome-windows.png' target='_blank' title='https://humbughq.com/static/images/app-screenshots/humbug-chrome-windows.png'><img src='https://humbughq.com/static/images/app-screenshots/humbug-chrome-windows.png'></a></div> for the Windows app -- thoughts? I'm particularly wondering whether people think the screenshot should be from Windows 7 or some other version.</p>",
        is_stream: true,
        sender_full_name: "Waseem Daher",
        avatar_url: "https://secure.gravatar.com/avatar/364a79a57718ede3fadf6dd3623d2e0a",
        display_recipient: "design",
        stream: "design",
        subject: "screenshots",
        timestr: "12:15",
        type: "stream"
    },
    {
        id: 5,
        content: "<p>Looks good to me!</p>",
        is_stream: true,
        sender_full_name: "Jeff Arnold",
        avatar_url: "https://secure.gravatar.com/avatar/0e0080b53f71bb975c311a123acd8a48",
        display_recipient: "design",
        stream: "design",
        subject: "screenshots",
        timestr: "12:15",
        type: "stream"
    },
    {
        id: 6,
        content: "<p>@<strong>all</strong> Any interest in lunch? I'd go for:</p>" +
"<ul>" +
"<li><img alt=':pizza:' class='emoji' src='static/third/gemoji/images/emoji/pizza.png' title=':pizza:'> (Hi-fi)</li>" +
"<li><img alt=':hamburger:' class='emoji' src='static/third/gemoji/images/emoji/hamburger.png' title=':hamburger:'> (Four Burgers)</li>" +
"<li><img alt=':sushi:' class='emoji' src='static/third/gemoji/images/emoji/sushi.png' title=':sushi:'> (Thelonious)</li>" +
"</ul></p>",
        is_stream: true,
        sender_full_name: "Tim Abbott",
        avatar_url: "https://secure.gravatar.com/avatar/364a79a57718ede3fadf6dd3623d2e0a",
        display_recipient: "social",
        stream: "social",
        subject: "lunch",
        timestr: "12:20",
        type: "stream"
    },
    {
        id: 7,
        content: "<p>I'd go to Hi-fi</p>",
        is_stream: true,
        sender_full_name: "Luke Faraone",
        avatar_url: "https://secure.gravatar.com/avatar/948fcdfa93dd8986106032f1bad7f2c8",
        display_recipient: "social",
        stream: "social",
        subject: "lunch",
        timestr: "12:20",
        type: "stream"
    },
    {
        id: 8,
        content: "<p>Reminder: engineering meeting in 1 hour.</p>",
        is_stream: true,
        sender_full_name: "Jessica McKellar",
        avatar_url: "https://secure.gravatar.com/avatar/c89814a8ed5814421b617cf2242ff01a",
        display_recipient: "devel",
        stream: "devel",
        subject: "meeting",
        timestr: "12:34",
        type: "stream"
    }
];

function set_tutorial_status(status, callback) {
    return $.ajax({
        type:     'POST',
        url:      '/json/tutorial_status',
        data:     {status: status},
        success:  callback
    });
}

exports.is_running = function() {
    return is_running;
};

exports.start = function () {
    // If you somehow have messages, temporarily remove them from the visible
    // feed.
    current_msg_list.clear();
    // Set temporarly colors for the streams used in the tutorial.
    real_stream_info = subs.stream_info();
    subs.stream_info(tutorial_stream_info);
    // Add the fake messages to the feed and get started.
    current_msg_list.add_and_rerender(fake_messages);
    is_running = true;
    set_tutorial_status("started");
};

exports.initialize = function () {
    if (page_params.needs_tutorial) {
        exports.start();
    }
};

return exports;
}());
