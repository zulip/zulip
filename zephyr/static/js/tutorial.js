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

function box(x, y, width, height) {
    // Blanket everything ouside the box defined by the parameters in a
    // translucent black screen, and cover the box itself with a clear screen so
    // nothing in it is clickable.
    //
    // x and y are the coordinates for hte upper-left corner of the box.

    var doc_width = $(document).width();
    var doc_height = $(document).height();

    $("#top-screen").css({opacity: 0.7, width: doc_width, height: y});
    $("#bottom-screen").offset({top: y + height, left: 0});
    $("#bottom-screen").css({opacity: 0.7, width: doc_width, height: doc_height});
    $("#left-screen").offset({top: y, left: 0});
    $("#left-screen").css({opacity: 0.7, width: x, height: height});
    $("#right-screen").offset({top: y, left: x + width});
    $("#right-screen").css({opacity: 0.7, width: x, height: height});
    $("#clear-screen").css({opacity: 0.0, width: doc_width, height: doc_height});
}

function messages_in_viewport() {
    var vp = viewport.message_viewport_info();
    var top = vp.visible_top;
    var height = vp.visible_height;
    var last_row = rows.last_visible();

    return $.merge(last_row, last_row.prevAll()).filter(function (idx, row) {
        var row_offset = $(row).offset();
        return (row_offset.top > top && row_offset.top < top + height);
    });
}

function create_and_show_popover(target_div, placement, title, content_template) {
    target_div.popover({
        placement: placement,
        title: templates.render("tutorial_title", {title: title}),
        content: templates.render(content_template),
        trigger: "manual"
    });
    target_div.popover("show");

    $(".popover").css("z-index", 20001);
}

function finale() {
    var finale_modal = $("#tutorial-finale");
    $(".screen").css({opacity: 0.0});
    finale_modal.css("z-index", 20001);
    finale_modal.modal("show");

    $("#tutorial-get-started").click(function () {
        finale_modal.modal("hide");
        $(".screen").css({opacity: 0.0, width: 0, height: 0});
    });

    // Restore your actual stream colors and rerender to display any
    // messages received during the tutorial.
    set_tutorial_status("finished");
    is_running = false;
    current_msg_list.clear();
    // Force a check on new events before we re-render the message list.
    force_get_updates();
    subs.stream_info(real_stream_info);
    util.show_first_run_message();
    current_msg_list.rerender();
}

function reply() {
    var spotlight_message = rows.first_visible().prev(".recipient_row");
    create_and_show_popover(spotlight_message, "left", "Replying", "tutorial_reply");

    var my_popover = $("#tutorial-reply").closest(".popover");
    my_popover.offset({left: my_popover.offset().left - 10});

    $("#tutorial-reply-next").click(function () {
        spotlight_message.popover("destroy");
        finale();
    });
}

function home() {
    var spotlight_message = rows.first_visible().prev(".recipient_row");
    var x = spotlight_message.offset().left;
    var y = spotlight_message.offset().top;
    var height = 0;
    $.each(messages_in_viewport(), function (idx, row) {
        height += $(row).height();
    });

    box(x, y, spotlight_message.width(), height);
    create_and_show_popover(spotlight_message, "left", "Home view", "tutorial_home");

    var my_popover = $("#tutorial-home").closest(".popover");
    my_popover.offset({left: my_popover.offset().left - 10});

    $("#tutorial-home-next").click(function () {
        spotlight_message.popover("destroy");
        reply();
    });
}

function private_message() {
    var bar = rows.first_visible().nextUntil(".private_message").first().next();
    var spotlight_message = bar.next();
    var x = bar.offset().left;
    var y = bar.offset().top;
    // In the current example we have back-to-back pms.
    var message_width = bar.width();
    var message_height = bar.height() + spotlight_message.height() +
        spotlight_message.next().height();

    box(x, y, message_width, message_height);
    create_and_show_popover(bar, "top", "Private messages", "tutorial_private");

    var my_popover = $("#tutorial-private").closest(".popover");
    my_popover.offset({top: my_popover.offset().top - 10,
                       left: bar.offset().left + 76 - my_popover.width() / 2});

    $("#tutorial-private-next").click(function () {
        bar.popover("destroy");
        home();
    });
}

function subject() {
    var spotlight_message = rows.first_visible();
    var bar = spotlight_message.prev(".recipient_row");
    create_and_show_popover(bar, "bottom", "Subjects", "tutorial_subject");

    var my_popover = $("#tutorial-subject").closest(".popover");
    my_popover.offset({left: bar.offset().left + 94 - my_popover.width() / 2});

    $("#tutorial-subject-next").click(function () {
        bar.popover("destroy");
        private_message();
    });
}

function stream() {
    var bar = rows.first_visible().prev(".recipient_row");
    create_and_show_popover(bar, "bottom", "Streams", "tutorial_stream");

    var my_popover = $("#tutorial-stream").closest(".popover");
    my_popover.offset({left: bar.offset().left + 24 - my_popover.width() / 2});

    $("#tutorial-stream-next").click(function () {
        bar.popover("destroy");
        subject();
    });
}

function message() {
    var spotlight_message = rows.first_visible();
    var bar = spotlight_message.prev(".recipient_row");
    var x = bar.offset().left;
    var y = bar.offset().top;
    var message_height = bar.height() + spotlight_message.height();
    var message_width = bar.width();

    box(x, y, message_width, message_height);
    create_and_show_popover(bar, "left", "Welcome " + page_params.fullname + "!",
                            "tutorial_message");

    var my_popover = $("#tutorial-message").closest(".popover");
    my_popover.offset({left: my_popover.offset().left - 10});

    $("#tutorial-message-next").click(function () {
        bar.popover("destroy");
        stream();
    });
}

function welcome() {
    // Grey out everything.
    $('#top-screen').css({opacity: 0.7, width: $(document).width(),
                          height: $(document).height()});

    // Highlight the first recipient row.
    var bar = rows.first_visible().prev(".recipient_row");
    create_and_show_popover(bar, "left", "Welcome " + page_params.fullname + "!",
                            "tutorial_welcome");

    var my_popover = $("#tutorial-welcome").closest(".popover");
    my_popover.offset({left: my_popover.offset().left - 10});

    $("#tutorial-welcome-next").click(function () {
        bar.popover("destroy");
        message();
    });
}

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
    welcome();
};

exports.initialize = function () {
    if (page_params.needs_tutorial) {
        exports.start();
    }
};

return exports;
}());
