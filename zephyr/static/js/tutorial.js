var tutorial = (function () {

var exports = {};
var script = [];

function go(fn, arg) {
    return function() { return fn(arg); };
}

function go2(fn, arg1, arg2) {
    return function() { return fn(arg1, arg2); };
}

// Inspired by
// http://www.intridea.com/blog/2011/2/8/fun-with-jquery-deferred
//
// Basically, we make a new Deferred object that gets resolved
// when our setTimeout returns. Which means we effectively sleep
// for some amount of time, but can also chain it with .thens
// with our other deferred objects.
function sleep(time_in_ms) {
    return $.Deferred(function(deferred) {
        setTimeout(deferred.resolve, time_in_ms);
    });
}

function pm(message) {
    return $.ajax({
        dataType: 'json',
        url: '/json/tutorial_send_message',
        type: 'POST',
        data: {'type': 'private',
               'content': message}
    });
}

function stream_message(subject, message) {
    return $.ajax({
        dataType: 'json',
        url: '/json/tutorial_send_message',
        type: 'POST',
        data: {'type': 'stream',
               'subject': subject,
               'content': message}
    });
}

// populated later -- should be e.g. tutorial-wdaher
var my_tutorial_stream;

var tutorial_running = false;

function stream_to_me(message) {
    return message.type === 'stream' && message.to === my_tutorial_stream;
}

function pm_to_me(message) {
    return message.type === 'private' && message.to[0] === 'humbug+tutorial@humbughq.com';
}

function any_message_to_me(message) {
    return pm_to_me(message) || stream_to_me(message);
}

var received_messages = [];
exports.message_was_sent = function(request) {
    // We copy our version of the message in case someone in compose.js
    // modifies it later -- this is important!
    // (right after this code is called, the "to" field is JSON stringified,
    // which messes up the code below)
    var message = $.extend({}, request, {});
    // Don't let casing or stray punctuation get in the way.
    var trimmed_content = message.content.substring(0, 4).toLowerCase();
    if (any_message_to_me(message) &&
        (trimmed_content === 'exit' || trimmed_content === 'stop')) {
        sleep(1000).then(function () {
            var text = "OK, cool, we'll stop the tutorial here. If you have any questions, you can always email support@humbughq.com!";
            var deferred;
            if (pm_to_me(message)) {
                deferred = pm(text);
            } else {
                deferred = stream_message(message.subject, text);
            }
            deferred.always(exports.stop);
        });
        return;
    }
    received_messages.push(message);
};

function wait_for_message(time_to_wait_sec, condition) {
    var POLL_INTERVAL_MS = 500;
    received_messages = [];
    return $.Deferred(function (deferred) {
        var numCalls = 0;
        var intervalId = setInterval(function () {
            if (!tutorial_running) {
                clearInterval(intervalId);
                deferred.fail();
            }
            numCalls += 1;
            if (numCalls > time_to_wait_sec * (1000 / POLL_INTERVAL_MS)) {
                clearInterval(intervalId);
                // We didn't get an answer; end the tutorial.
                var signoff_message = "**I didn't hear from you, so I stopped waiting** :broken_heart:\n\nSince we're done, I've also removed you from `" + my_tutorial_stream + "`.\n\nEnjoy using Humbug, and let us know if you have any questions -- if you click the gear at the top-right, there's an option labeled 'Feedback', which is a great way to reach us.";
                stream_message("tutorial", signoff_message).then(function () {
                    // This needs to be in a 'then' because otherwise we unsub
                    // before the message arrives!
                    exports.stop();
                    deferred.fail();
                });
            }

            if (received_messages.length > 0) {
                var success = true;
                if (condition) {
                    success = false;
                    $.each(received_messages, function (idx, val) {
                        if (condition(val)) success = true;
                    });
                }

                received_messages = [];
                if (success) {
                    deferred.resolve();
                    clearInterval(intervalId);
                }
            }

        }, POLL_INTERVAL_MS);
    });
}

function pick_hello_stream() {
    // Try to guess at one of your main streams. Ideally it's your
    // company name, but do our best and try to avoid streams mostly
    // used for alerts.

    var company_name = page_params.domain.split('.')[0].toLowerCase();
    var my_streams = subs.subscribed_streams();
    var hello_stream;

    $.each(my_streams, function (idx, stream_name) {
        var lowered = stream_name.toLowerCase();
        if (lowered === company_name) {
            // The best case is that your company name is your stream name.
            hello_stream = stream_name;
            return false;
        } else {
            // See if you're subbed to a stream that is probably
            // pretty good for saying hello.
            if ($.inArray(lowered, ["social", "office"]) !== -1) {
                hello_stream = stream_name;
                return false;
            }
        }
    });
    if (hello_stream === undefined) {
        // Try to avoid alert/notification streams if possible.
        var alert_streams = ["commits", "jenkins", "nagios", "support", "builds"];
        $.each(my_streams, function (idx, stream_name) {
            if (($.inArray(stream_name.toLowerCase(), alert_streams) === -1) &&
                (stream_name.substring(0, 9) !== "tutorial-")) {
                hello_stream = stream_name;
                return false;
            }
        });
    }

    if (hello_stream === undefined) {
        // Give up and pick the first stream.
        hello_stream = my_streams[0];
    }

    return hello_stream;
}

function run_tutorial(stepNumber) {
    if (stepNumber >= script.length) {
        return;
    }

    if (!tutorial_running) {
        return;
    }
    var step = script[stepNumber];
    var res = step();
    if (res) {
        res.then(function () { run_tutorial(++stepNumber); });
    } else {
        // Our last function wasn't async at all, so just proceed with the next step
        run_tutorial(++stepNumber);
    }
}

function set_tutorial_status(status, callback) {
    return $.ajax({
      type:     'POST',
      url:      '/json/tutorial_status',
      data:     {status: status},
      success:  callback
    });
}

function start_tutorial() {
    tutorial_running = true;
    run_tutorial(0);
    set_tutorial_status("started");
}

function load_real_subs() {
    set_tutorial_status("finished", function () {
        // We need to reload the streams list so the sidebar is populated
        // with the new streams
        subs.reload_subscriptions({clear_first: true})
            .fail(function () {
                blueslip.error("Unable to load subs after tutorial.");
            });
    });
}

function end_tutorial(dont_load_subs) {
    tutorial_running = false;
    subs.tutorial_unsubscribe_me_from(my_tutorial_stream);
    if (dont_load_subs !== true) {
        load_real_subs();
    }
    onboarding.initialize();
}

exports.start = function () {
    if (tutorial_running) {
        // Not more than one of these at once!
        return;
    }

    if ($.inArray(my_tutorial_stream, subs.subscribed_streams()) === -1) {
        subs.tutorial_subscribe_or_add_me_to(my_tutorial_stream)
            .then(start_tutorial, end_tutorial);
    }
};

function send_action_message() {
    if (subs.subscribed_streams().length > 0) {
        var hello_stream = pick_hello_stream();
        return stream_message("tutorial", "Say hello on stream `" +
                              hello_stream + "` to let everyone know you're here!");
    } else {
        // Something went wrong, but still try to give them something to do.
        blueslip.error("Unable to load subs after tutorial.");
        return stream_message("tutorial", "How about adding some streams on your " +
                              "streams page and then saying hello!");
    }
}

// This technique is not actually that awesome, because it's pretty
// race-y. Let's say I start() and then stop() and then start() again;
// an async from the first start() might still be returning, and it'll
// come back and say "Oh, we're still going!" and the tutorial #1 will
// continue.
//
// Fortunately, in v1, the only real thing that initiates the tutorial
// is logging in to a fresh system, so this is mostly a non-issue;
// the rationale being that you could just scroll back up and read
// the tutorial if you still need it.
exports.stop = function () {
    if (tutorial_running) {
        end_tutorial();
    }
};

exports.is_running = function () {
    return tutorial_running;
};

function make_script() {
    my_tutorial_stream = 'tutorial-' + page_params.email.split('@')[0];
    // If you change this, you need to change the corresponding
    // client-computed version in models.py on the server.
    my_tutorial_stream = my_tutorial_stream.substring(0, 30);

    script = [
  go(sleep, 1000), // The first message seems to sometimes get eaten in Chrome otherwise.
  go2(stream_message, "tutorial", "Hello " + page_params.fullname + ", and welcome to Humbug!"),
  go(sleep, 2000),
  go2(stream_message, "tutorial", "I'm the Humbug tutorial bot and I'll be showing you around."),
  go(sleep, 2000),
  go2(stream_message, "tutorial",'At any time, you can stop this tutorial by replying to me with the word "exit".'),
  go(sleep, 3000),
  go2(stream_message, "tutorial", "Why don't you **reply to this message and say hello?** "
    + "(Click on this message to reply.)"),
  go2(wait_for_message, 300, any_message_to_me),
  go(sleep, 1000),
  go2(stream_message, "tutorial",'Great, thanks! After you\'ve typed your reply, you can send it by clicking "Send", but you can also send from the keyboard by pressing `Tab` and then `Enter`.'),
  go(sleep, 4000),
  go2(stream_message, "tutorial", "Give it a shot!\n**Reply to me again, and use Tab, then Enter to send it.**"),
  go2(wait_for_message, 300, any_message_to_me),
  go(sleep, 1000),
  go2(stream_message, "tutorial", "Nice work. In Humbug, time flows down and your new messages will always appear at the very bottom of the screen. We're always receiving messages for you—even when you're logged out."),
  go(sleep, 6000),
  go2(stream_message, "tutorial", "By the way, right now, these messages are going to stream `" + my_tutorial_stream + "`.\n\nA stream is like a chatroom or mailing list; anyone on `" + my_tutorial_stream +"` can see and respond to these messages. (In this case, it's just us on this stream right now, so that no one distracts us.)"),
  go(sleep, 8000),
  go2(stream_message, "tutorial", "Every stream message has a subject associated with it. (In this case, `tutorial`.) "
      + "The subject should be **one or two words** describing the topic of the message.\n\nGood subjects: `lunch`, `website redesign` or `Bug #4567`.\n"),
  go(sleep, 10000),
  go2(stream_message, "tutorial", "Subjects sound like a tiny idea, but they are really powerful. They make it easy to keep track of multiple conversations and to easily skim what you care about and ignore what you don't.\n\n**Send me a reply** when you're ready to continue."),
  go2(wait_for_message, 300, any_message_to_me),
  go(sleep, 1000),
  go(pm, "Psst, Humbug also has private messages, like this one, which you can send to one or more people. No one else can see this message.\n\n**Reply to this private message** to continue."),
  go2(wait_for_message, 300, pm_to_me),
  go(sleep, 1000),
  go(pm, "Nicely done. Alright, back to stream messages we go!"),
  go(sleep, 2000),
  go2(stream_message, "tutorial", "It's easy to make or join streams. If you click the gear on the top right of the page, and then pick 'Streams', you can create your own stream or join streams that other people have made."),
  go(sleep, 4000),
  // Narrowing
  go2(stream_message, "narrowing", "Another valuable feature of Humbug is **narrowing**. Click on the word \"narrowing\" directly above this message, and **tell me when you've done so**."),
  go2(wait_for_message, 300, any_message_to_me),
  go(sleep, 1000),
  go2(stream_message, "narrowing", "Great! We're now only looking at messages on stream `" + my_tutorial_stream + "`, subject `narrowing`. You can tell because the background is grey, and the search bar at the top has a query in it. You can narrow on:\n"
   + "* A specific stream, by clicking on the stream name\n"
   + "* A specific stream-subject pair, by clicking on the subject name (like we just did)\n"
   + "* Private messages with a specific person\n\n"
   + "Press `Esc` to get out of this narrowed view, scroll down to the bottom, and **tell me when you've done so**.\n"),
  go2(wait_for_message, 300, any_message_to_me),
  go(sleep, 1000),
  go2(stream_message, "tutorial", "Great, you've got the hang of the basics. I'll say goodbye for now, but here are some Humbug features you might like to explore:\n"
    + "* Keyboard shortcuts (press `?` to see them)\n"
    + "* Message formatting, including pretty syntax-highlighting. Click on the 'Message formatting' link under the gear icon at the top right to learn more\n"
    + "* Our [API](https://humbughq.com/api) and [integrations](https://humbughq.com/integrations)\n"
    + '* Alpha mobile apps for [Android](https://play.google.com/store/apps/details?id=com.humbughq.mobile) and [iPhone](mailto:support@humbughq.com?subject=Request%20for%20Humbug%20iPhone%20app&body=Hi%20Humbug,%20can%20you%20send%20me%20a%20link%20to%20the%20iPhone%20app%20alpha?%20I%20have%20an%20iPhone%20__.)\n'
    + "* Feedback! Found a bug or have a feature request? We want to hear from you. Click on the feedback tab under the gear icon to get in touch."),
  go(sleep, 4000),
  // Have them go talk to people
  go2(stream_message, "tutorial", ":white_check_mark: **Congratulations! The tutorial is now complete** :tada:\n"
      + "Since you're done, I'll remove you from the `" + my_tutorial_stream + "` stream and add your real streams on the left."),
  // We need to load our actual subscriptions before we can recommend a stream to say hello on.
  go(sleep, 1000),
  go(set_tutorial_status, "finished"),
  go(subs.reload_subscriptions, {clear_first: true}),
  go(send_action_message),
  go(end_tutorial, true)
    ];
}

exports.initialize = function () {
    make_script();
    // Global variable populated by the server code
    if (page_params.needs_tutorial) {
        exports.start();
    }
};

return exports;
}());
