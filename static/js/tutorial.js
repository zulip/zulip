var tutorial = (function () {

var exports = {};
var is_running = false;
var event_handlers = {};
var deferred_work = [];

// Keep track of where we are for handling resizing.
var current_popover_info;

// We'll temporarily set stream colors for the streams we use in the demo
// tutorial messages.
var real_default_color;
var tutorial_default_color = '#76ce90';

// Each message object contains the minimal information necessary for it to be
// processed by our system for adding messages to your feed.
var today = new Date().getTime() / 1000;
var fake_messages = [
    {
        id: 1,
        content: "<p>We're working on some new screenshots for our landing page!</p>",
        is_stream: true,
        sender_full_name: "Abbie Patel",
        sender_email: "abbie@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/5a8d2b3836d546d523f460924a8a9973",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "screenshots",
        timestr: "12:11",
        timestamp: today,
        type: "stream",
    },
    {
        id: 2,
        content: "<p>Here's the <a href='https://zulip.com/static/images/app-screenshots/zulip-desktop-windows.png' target='_blank' title='https://zulip.com/static/images/app-screenshots/zulip-desktop-windows.png'>latest version</a>:<div class='message_inline_image'><a href='https://zulip.com/static/images/app-screenshots/zulip-desktop-windows.png' target='_blank' title='https://zulip.com/static/images/app-screenshots/zulip-desktop-windows.png'><img src='https://zulip.com/static/images/app-screenshots/zulip-desktop-windows.png'></a></div> for the Windows app -- thoughts? I'm particularly wondering whether people think the screenshot should be from Windows 7 or some other version.</p>",
        is_stream: true,
        sender_full_name: "Abbie Patel",
        sender_email: "abbie@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/5a8d2b3836d546d523f460924a8a9973",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "screenshots",
        timestr: "12:11",
        timestamp: today,
        type: "stream",
    },
    {
        id: 3,
        content: "<p>Looks good to me! <img alt=':+1:' class='emoji' src='/static/generated/emoji/images/emoji/+1.png' title=':+1:'></p>",
        is_stream: true,
        sender_full_name: "Jeff Arnold",
        sender_email: "jeff@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/dd0cf69d6d1989aa0b0d8c722f7d5840",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "screenshots",
        timestr: "12:16",
        timestamp: today,
        type: "stream",
    },
    {
        id: 4,
        content: "<p>Adam and I just finished a brainstorming session for the next set of integrations we want to support.</p><p><a href=''>Here</a> are our notes. I'll open tickets for the action items.</p>",
        is_stream: true,
        sender_full_name: "Jessica McKellar",
        sender_email: "jessica@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/2a1ffb4ef0b4a20c04d540a35f430cf6",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "integrations",
        timestr: "12:25",
        timestamp: today,
        type: "stream",
    },
    {
        id: 5,
        content: "<p>Yay, Twitter integration. <img alt=':heart_eyes:' class='emoji' src='/static/generated/emoji/images/emoji/heart_eyes.png' title=':heart_eyes:'></p>",
        is_stream: true,
        sender_full_name: "Leo Franchi",
        sender_email: "leo@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/4309007c980e1e8b9a2453488586482a",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "integrations",
        timestr: "12:25",
        timestamp: today,
        type: "stream",
    },
    {
        id: 6,
        content: "<p>We need to add support for a few more markdown features before we can do GitHub integration.</p>",
        is_stream: true,
        sender_full_name: "Li Jing",
        sender_email: "li@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/2950c2c87fe7daaa56fd6a403ecc2ee0",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "integrations",
        timestr: "12:26",
        timestamp: today,
        type: "stream",
    },
    {
        id: 7,
        content: "<p>Good point, I'll add that to the ticket.</p>",
        is_stream: true,
        sender_full_name: "Jessica McKellar",
        sender_email: "jessica@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/2a1ffb4ef0b4a20c04d540a35f430cf6",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "integrations",
        timestr: "12:26",
        timestamp: today,
        type: "stream",
    },
    {
        id: 8,
        content: "<p><img alt=':clock1130:' class='emoji' src='/static/generated/emoji/images/emoji/clock1130.png' title=':clock1130:'> Reminder: engineering meeting in 1 hour. <img alt=':clock1130:' class='emoji' src='/static/generated/emoji/images/emoji/clock1130.png' title=':clock1130:'></p>",
        is_stream: true,
        sender_full_name: "Reminder Bot",
        sender_email: "reminder-bot@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/78873d7213d102dc36773046560d403a",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "weekly meeting",
        timestr: "12:30",
        timestamp: today,
        type: "stream",
    },
    {
        id: 9,
        content: "<p>Quickly brainstorming my remaining TODO list out loud for you all:</p>",
        is_stream: true,
        sender_full_name: "Abbie Patel",
        sender_email: "abbie@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/5a8d2b3836d546d523f460924a8a9973",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "screenshots",
        timestr: "12:32",
        timestamp: today,
        type: "stream",
    },
    {
        id: 10,
        content: "<p><ul><li>Redo iPhone shot</li><li>Double-check layout on iPad</li><li>Update copy for new iOS app version</li><li>Check with Android team on timeline for login redesign</li></ul></p>",
        is_stream: true,
        sender_full_name: "Abbie Patel",
        sender_email: "abbie@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/5a8d2b3836d546d523f460924a8a9973",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "screenshots",
        timestr: "12:32",
        timestamp: today,
        type: "stream",
    },
    {
        id: 11,
        content: "<p>Oops, I actually took care of the text for iOS and forgot to update the ticket -- I'll do that now.</p>",
        is_stream: true,
        sender_full_name: "Jeff Arnold",
        sender_email: "jeff@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/dd0cf69d6d1989aa0b0d8c722f7d5840",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "screenshots",
        timestr: "12:16",
        timestamp: today,
        type: "stream",
    },
    {
        id: 12,
        content: "<p>No problem, less work for me. <img alt=':smile:' class='emoji' src='/static/generated/emoji/images/emoji/smile.png' title=':smile:'></p>",
        is_stream: true,
        sender_full_name: "Abbie Patel",
        sender_email: "abbie@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/5a8d2b3836d546d523f460924a8a9973",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "screenshots",
        timestr: "12:32",
        timestamp: today,
        type: "stream",
    },
];

function send_delayed_stream_message(stream, topic, content, delay) {
    var data = {type: JSON.stringify('stream'),
                recipient: JSON.stringify(stream),
                topic: JSON.stringify(topic),
                content: JSON.stringify(content)};
    setTimeout(function () {
        $.ajax({
            dataType: 'json',
            url: '/json/tutorial_send_message',
            type: 'POST',
            data: data,
        });
    }, delay * 1000); // delay is in seconds.
}

function disable_event_handlers() {
    $('body').css({overflow: 'hidden'}); // prevents scrolling the feed
    _.each(["keydown", "keyup", "keypress", "scroll"], function (event_name) {
        var existing_events = $._data(document, "events")[event_name];
        if (existing_events === undefined) {
            existing_events = [];
        }
        event_handlers[event_name] = existing_events;
        $._data(document, "events")[event_name] = [];
    });
}

function enable_event_handlers() {
    $('body').css({overflow: 'auto'}); // enables scrolling the feed
    _.each(["keydown", "keyup", "keypress", "scroll"], function (event_name) {
        $._data(document, "events")[event_name] = event_handlers[event_name];
    });
}

function set_tutorial_status(status, callback) {
    return channel.post({
        url:      '/json/tutorial_status',
        data:     {status: JSON.stringify(status)},
        success:  callback,
    });
}

exports.is_running = function () {
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

function message_groups_in_viewport() {
    var vp = message_viewport.message_viewport_info();
    var top = vp.visible_top;
    var height = vp.visible_height;
    var last_group = rows.get_message_recipient_row(rows.last_visible());

    return $.merge(last_group, last_group.prevAll()).filter(function (idx, row) {
        var row_offset = $(row).offset();
        return (row_offset.top > top && row_offset.top < top + height);
    });
}

function small_window() {
    return !$("#left-sidebar").is(":visible");
}

function maybe_tweak_placement(placement) {
    // If viewed on a small screen, move popovers on the left to the center so
    // they won't be cut off.

    if (!small_window()) {
        return placement;
    }

    if (placement === "left") {
        return "bottom";
    }

    if (placement === "bottom") {
        return "right";
    }
}

function create_and_show_popover(target_div, placement, title, content_template) {
    $(".popover").remove();
    target_div.popover("destroy");
    target_div.popover({
        placement: placement,
        title: templates.render("tutorial_title", {title: title,
                                                   placement: placement}),
        content: templates.render(content_template, {placement: placement,
                                                     page_params: page_params}),
        trigger: "manual",
    });
    target_div.popover("show");

    $(".popover").css("z-index", 20001);
    $(".popover-title").addClass("popover-" + placement);
}

exports.defer = function (callback) {
    deferred_work.push(callback);
};

function update_popover_info(popover_func) {
    current_popover_info = popover_func;
}

function finale(skip) {
    var finale_modal = $("#tutorial-finale");
    if (skip) {
        finale_modal.modal("hide");
        $(".screen").css({opacity: 0.0, width: 0, height: 0});
    } else {
        $(".screen").css({opacity: 0.0});
        finale_modal.css("z-index", 20001);
        finale_modal.modal("show");

        $("#tutorial-get-started").click(function () {
            finale_modal.modal("hide");
            $(".screen").css({opacity: 0.0, width: 0, height: 0});
        }).focus();
    }

    // Restore your actual stream colors and rerender to display any
    // messages received during the tutorial.
    set_tutorial_status("finished");
    is_running = false;
    current_msg_list.clear();
    update_popover_info(undefined);
    // Force a check on new events before we re-render the message list.
    server_events.force_get_events();
    stream_color.default_color = real_default_color;
    $('#first_run_message').show();
    current_msg_list.rerender();
    enable_event_handlers();
    _.each(deferred_work, function (callback) {
        callback();
    });
    deferred_work = [];

    // We start you in a narrow so it's not overwhelming.
    var newbie_stream = stream_data.get_newbie_stream();

    if (newbie_stream) {
        narrow.activate([{operator: "stream", operand: newbie_stream}]);
    }

    if (page_params.first_in_realm) {
        // 'engineering' is the best possible stream since we used it in the
        // tutorial, but fall back to something else if we have to.
        var work_stream;
        if (stream_data.in_home_view("engineering")) {
            work_stream = "engineering";
        } else {
            work_stream = _.find(stream_data.home_view_stream_names(),
                                 function (stream_name) {
                return (stream_name !== "social") && (stream_name !== page_params.notifications_stream);
            });
        }

        if (stream_data.in_home_view(page_params.notifications_stream)) {
            send_delayed_stream_message(page_params.notifications_stream, "welcome", "Practice sending sending some messages here, or starting a new topic.", 15);
            send_delayed_stream_message(page_params.notifications_stream, "Zulip tips", "Here's a message on a new topic: `Zulip tips`.\n\nAs you settle into Zulip, customize your account and notifications on your [Settings page](#settings).", 30);
            send_delayed_stream_message(page_params.notifications_stream, "Zulip tips", "You might also enjoy:\n\n* Our lightweight !modal_link(#markdown-help, message formatting) (including emoji! :thumbsup:)\n* !modal_link(#keyboard-shortcuts, Keyboard shortcuts)\n* [Desktop and mobile apps](/apps)", 40);
        }

        if (work_stream !== undefined) {
            send_delayed_stream_message(work_stream, "projects", "This is a message on stream `" + work_stream + "` with the topic `projects`.", 60);
            send_delayed_stream_message(work_stream, "projects", "Take a peek at our [integrations](/integrations). Now's a great time to set one up!", 65);
        }

        if (stream_data.in_home_view("social")) {
            send_delayed_stream_message("social", "cute animals", "This is a message on stream `social` with the topic `cute animals`. Try uploading or pasting in some pictures. Here's a [guinea pig](/static/images/cute/guinea.jpg) to get you started:", 75);
        }
    }
}

function box_first_message() {
    var spotlight_message = rows.first_visible();
    var bar = rows.get_message_recipient_row(spotlight_message);
    var header = bar.find('.message_header');
    var x = bar.offset().left;
    var y = bar.offset().top;
    var message_height = header.height() + spotlight_message.height();
    var message_width = bar.width();

    box(x, y, message_width, message_height);
}

function box_messagelist() {
    var spotlight_message_row = rows.get_message_recipient_row(rows.first_visible());
    var x = spotlight_message_row.offset().left;
    var y = spotlight_message_row.offset().top;
    var height = 0;

    _.each(message_groups_in_viewport(), function (row) {
        height += $(row).height();
    });

    box(x, y, spotlight_message_row.width(), height);
}

function reply() {
    var spotlight_message = rows.get_message_recipient_row(rows.first_visible());
    box_messagelist();
    create_and_show_popover(spotlight_message, maybe_tweak_placement("left"),
                            "Replying", "tutorial_reply");

    var my_popover = $("#tutorial-reply").closest(".popover");
    my_popover.offset({left: my_popover.offset().left - 10});
    update_popover_info(reply, spotlight_message);

    $("#tutorial-reply-next").click(function () {
        spotlight_message.popover("destroy");
        finale(false);
    }).focus();
}

function home() {
    var spotlight_message = rows.get_message_recipient_header(rows.first_visible());
    box_messagelist();
    create_and_show_popover(spotlight_message, maybe_tweak_placement("left"),
                            "Narrowing", "tutorial_home");

    var my_popover = $("#tutorial-home").closest(".popover");
    my_popover.offset({left: my_popover.offset().left - 10});
    update_popover_info(home, spotlight_message);

    $("#tutorial-home-next").click(function () {
        spotlight_message.popover("destroy");
        reply();
    }).focus();
}

function subject() {
    var spotlight_message = rows.first_visible();
    var bar = rows.get_message_recipient_header(spotlight_message);
    var placement = maybe_tweak_placement("bottom");
    box_first_message();
    create_and_show_popover(bar, placement, "Topics", "tutorial_subject");

    var my_popover = $("#tutorial-subject").closest(".popover");
    if (placement === "bottom") { // Wider screen, popover is on bottom.
        my_popover.offset({left: bar.offset().left + 140 - my_popover.width() / 2});
    } else {
        my_popover.offset({left: bar.offset().left + 194});
    }
    update_popover_info(subject, bar);

    $("#tutorial-subject-next").click(function () {
        bar.popover("destroy");
        home();
    }).focus();
}

function stream() {
    var bar = rows.get_message_recipient_header(rows.first_visible());
    var placement = maybe_tweak_placement("bottom");
    box_first_message();
    create_and_show_popover(bar, placement, "Streams", "tutorial_stream");

    var my_popover = $("#tutorial-stream").closest(".popover");
    if (placement === "bottom") { // Wider screen, popover is on bottom.
        my_popover.offset({left: bar.offset().left + 50 - my_popover.width() / 2});
    } else { // Smaller screen, popover is to the right of the stream label.
        my_popover.offset({left: bar.offset().left + 98});
    }
    update_popover_info(stream, bar);

    $("#tutorial-stream-next").click(function () {
        bar.popover("destroy");
        subject();
    }).focus();
}

function welcome() {
    // Grey out everything.
    $('#top-screen').css({opacity: 0.7, width: $(document).width(),
                          height: $(document).height()});
    var spotlight_message = rows.first_visible();
    var bar = rows.get_message_recipient_header(spotlight_message);
    box_first_message();
    create_and_show_popover(bar, maybe_tweak_placement("left"), "Welcome to Zulip",
                            "tutorial_message");

    var my_popover = $("#tutorial-message").closest(".popover");
    my_popover.offset({left: my_popover.offset().left - 10});
    update_popover_info(welcome, bar);

    $("#tutorial-message-next").click(function () {
        bar.popover("destroy");
        stream();
    }).focus();
    $("#tutorial-message-skip").click(function () {
        bar.popover("destroy");
        finale(true);
    });
}

exports.start = function () {
    if (ui.home_tab_obscured()) {
        ui.change_tab_to('#home');
    }
    narrow.deactivate();

    // Set temporarly colors for the streams used in the tutorial.
    real_default_color = stream_color.default_color;
    stream_color.default_color = tutorial_default_color;
    // Add the fake messages to the feed and get started.
    current_msg_list.add_and_rerender(fake_messages);
    disable_event_handlers();
    is_running = true;
    set_tutorial_status("started");
    welcome();
};

exports.initialize = function () {
    if (page_params.needs_tutorial) {
        exports.start();
    }
    $(window).resize($.debounce(100, function () {
        if (current_popover_info !== undefined) {
            current_popover_info();
        }
    }));
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = tutorial;
}
