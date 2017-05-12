set_global("page_params", {
    realm_uri: "https://chat.example.com",
});

var settings_bots = require("js/settings_bots.js");

(function test_generate_zuliprc_uri() {
    var bot = {
        email: "error-bot@zulip.org",
        api_key: "QadL788EkiottHmukyhHgePUFHREiu8b",
    };
    var uri = settings_bots.generate_zuliprc_uri(bot.email, bot.api_key);
    var expected = "data:application/octet-stream;charset=utf-8," + encodeURIComponent(
        "[api]\nemail=error-bot@zulip.org\n" +
        "key=QadL788EkiottHmukyhHgePUFHREiu8b\n" +
        "site=https://chat.example.com\n"
    );

    assert.equal(uri, expected);
}());

(function test_generate_zuliprc_content() {
    var user = {
        email: "admin12@chatting.net",
        api_key: "nSlA0mUm7G42LP85lMv7syqFTzDE2q34",
    };
    var content = settings_bots.generate_zuliprc_content(user.email, user.api_key);
    var expected = "[api]\nemail=admin12@chatting.net\n" +
                   "key=nSlA0mUm7G42LP85lMv7syqFTzDE2q34\n" +
                   "site=https://chat.example.com\n";

    assert.equal(content, expected);
}());
