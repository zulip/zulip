const zulip = require('zulip-js');
const config = {
    username: process.env.ZULIP_USERNAME,
    apiKey: process.env.ZULIP_API_KEY,
    realm: process.env.ZULIP_REALM,
};

function process_data(obj) {
    console.log(JSON.stringify(obj));
}

const example = {};

// DOC
example.send_message = function () {
    zulip(config).then((client) => {
        // Send a message
        const params = {
            to: 'Denmark',
            type: 'stream',
            topic: 'Castle',
            content: 'I come not, friends, to steal away your hearts.',
        };

        client.messages.send(params).then(process_data);
    });

    // Send a private message
    zulip(config).then((client) => {
        // Send a private message
        const user_id = 9;
        const params = {
            to: [user_id],
            type: 'private',
            content: 'With mirth and laughter let old wrinkles come.',
        };

        client.messages.send(params).then(console.log);
    });
};

example.create_user = function () {
    zulip(config).then((client) => {
        // Create a user
        const params = {
            email: 'newbie@zulip.com',
            password: 'temp',
            full_name: 'New User',
            short_name: 'newbie',
        };
        client.users.create(params).then(process_data);
    });
};

function run() {
    const suite = [
        'send_message',
        'create_user',
    ];

    for (const test of suite) {
        example[test]();
    }
}

run();
