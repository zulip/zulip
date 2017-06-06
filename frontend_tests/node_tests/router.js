var jsdom = require("jsdom");
set_global('window', jsdom.jsdom().defaultView);

var Router = require("js/router.js");
var router = new Router(window);

// test the parsing components to make sure that they are structurally what we
// expect them to be.
assert.deepEqual(router.parse("organization/emoji-settings"), [
    { type: router.type.PATH, component: "organization" },
    { type: router.type.PATH, component: "emoji-settings" },
]);

assert.deepEqual(router.parse("organization/:organization"), [
    { type: router.type.PATH, component: "organization" },
    { type: router.type.VARIABLE, component: ":organization" },
]);

assert.deepEqual(router.parse("narrow/:action/then/:verb"), [
    { type: router.type.PATH, component: "narrow" },
    { type: router.type.VARIABLE, component: ":action" },
    { type: router.type.PATH, component: "then" },
    { type: router.type.VARIABLE, component: ":verb" },
]);

assert.deepEqual(router.parse("/narrow/*"), [
    { type: router.type.PATH, component: "narrow" },
    { type: router.type.ALL, component: "*" },
]);

// assert that the path matches a defined generic path.
assert.equal(!!router.matches("/narrow/:stream", "narrow/Verona"), true);
assert.equal(!!router.matches("/narrow/:stream", "blah"), false);
assert.equal(!!router.matches("/narrow/*", "/narrow/to/something/else"), true);
assert.equal(!!router.matches("/settings/:type", "/settings/display-settings"), true);
assert.equal(!!router.matches("*", "/something/else/"), true);

// assert that the map of key/value pairs collects the variables correctly from proper
// paths or is false for invalid paths.
assert.deepEqual(router.matches("/weather/:city/:date", "weather/Berkeley/today"), {
    city: "Berkeley",
    date: "today",
});

assert.deepEqual(router.matches("*", "/some/test/about/something"), {
    __ALL: "some/test/about/something",
});

assert.deepEqual(router.matches("/settings/:key", "/settings/organization-settings"), {
    key: "organization-settings",
});

assert.deepEqual(router.matches("/some/path/:with/some/:keys", "/some/path/test/some/test"), {
    with: "test",
    keys: "test",
});

assert.equal(router.matches("/some/path/:with/some/:keys", "blah"), false);
