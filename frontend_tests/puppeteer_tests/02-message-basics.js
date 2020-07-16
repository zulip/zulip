const common = require("../puppeteer_lib/common");

async function message_basic_tests(page) {
    await common.log_in(page);

    console.log("Sending messages");
    await common.send_multiple_messages(page, [
        {stream: "Verona", topic: "test", content: "verona test a"},
        {stream: "Verona", topic: "test", content: "verona test b"},
        {stream: "Verona", topic: "other topic", content: "verona other topic c"},
        {recipient: "cordelia@zulip.com, hamlet@zulip.com", content: "group pm a"},
        {recipient: "cordelia@zulip.com, hamlet@zulip.com", content: "group pm b"},
        {recipient: "cordelia@zulip.com", content: "pm c"},
    ]);

    await common.check_messages_sent(page, "zhome", [
        ["Verona > test", ["verona test a", "verona test b"]],
        ["Verona > other topic", ["verona other topic c"]],
        ["You and Cordelia Lear, King Hamlet", ["group pm a", "group pm b"]],
        ["You and Cordelia Lear", ["pm c"]],
    ]);

    await common.log_out(page);
}

common.run_test(message_basic_tests);
