"use strict";

// We have to pass channel here so that the test file mocks channel.ts before
// tests start running, and so that channel.ts is only mocked once.
exports.mock_channel_get = function (channel, f) {
    channel.get = async (opts) => {
        // await an empty promise to ensure the "fetch" happens asynchronously
        await Promise.resolve();
        f(opts);
    };
};
