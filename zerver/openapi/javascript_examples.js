"use strict";

/* eslint-disable arrow-body-style */
/*
  This file makes use of functional comments in a way that makes the
  code confusing with the arrow-body-style lint rule applied.

  Zulip's OpenAPI-based API documentation system is documented at
  https://zulip.readthedocs.io/en/latest/documentation/api.html

  This file contains example code fenced off by comments, and is
  designed to be run as part of Zulip's test-api test suite to verify
  that the documented examples are all correct, runnable code.
*/

const ExamplesHandler = function () {
    const config = {
        username: process.env.ZULIP_USERNAME,
        apiKey: process.env.ZULIP_API_KEY,
        realm: process.env.ZULIP_REALM,
    };
    const examples = {};
    const response_data = [];

    const make_result_object = (example, result, count = false) => {
        const name = count !== false ? `${example.name}_${count}` : example.name;
        return {
            name,
            endpoint: example.endpoint.split(":")[0],
            method: example.endpoint.split(":")[1],
            status_code: example.status_code.toString(),
            result,
        };
    };

    const generate_validation_data = async (client, example) => {
        const result = await example.func(client);
        if (Array.isArray(result)) {
            // Handle special cases where some examples make
            // more than 1 API requests.
            result.forEach((r, index) => {
                response_data.push(make_result_object(example, r, index));
            });
        } else {
            response_data.push(make_result_object(example, result));
        }
    };

    const main = async () => {
        const Zulip = require("zulip-js");
        const client = await Zulip(config);

        await generate_validation_data(client, examples.send_message);
        await generate_validation_data(client, examples.create_user);
        await generate_validation_data(client, examples.get_custom_emoji);
        await generate_validation_data(client, examples.delete_queue);
        await generate_validation_data(client, examples.get_messages);
        await generate_validation_data(client, examples.get_own_user);
        await generate_validation_data(client, examples.get_stream_id);
        await generate_validation_data(client, examples.get_stream_topics);
        await generate_validation_data(client, examples.get_subscriptions);
        await generate_validation_data(client, examples.get_users);
        await generate_validation_data(client, examples.register_queue);
        await generate_validation_data(client, examples.render_message);
        await generate_validation_data(client, examples.set_typing_status);
        await generate_validation_data(client, examples.add_subscriptions);
        await generate_validation_data(client, examples.remove_subscriptions);
        await generate_validation_data(client, examples.update_message_flags);
        await generate_validation_data(client, examples.update_message);
        await generate_validation_data(client, examples.get_events);
        await generate_validation_data(client, examples.get_streams);

        console.log(JSON.stringify(response_data));
        return;
    };

    const add_example = (name, endpoint, status_code, func) => {
        const example = {
            name,
            endpoint,
            status_code,
            func,
        };
        examples[name] = example;
    };

    return {
        main,
        add_example,
    };
};

const {main, add_example} = ExamplesHandler();

const send_test_message = async (client) => {
    const params = {
        to: "Verona",
        type: "stream",
        topic: "Castle",
        // Use some random text for easier debugging if needed. We don't
        // depend on the content of these messages for the tests.
        content: `Random test message ${Math.random()}`,
    };
    const result = await client.messages.send(params);
    // Only return the message id.
    return result.id;
};

// Declare all the examples below.

add_example("send_message", "/messages:post", 200, async (client) => {
    // {code_example|start}
    // Send a stream message
    let params = {
        to: "social",
        type: "stream",
        topic: "Castle",
        content: "I come not, friends, to steal away your hearts.",
    };
    const result_1 = await client.messages.send(params);
    // {code_example|end}

    // {code_example|start}
    // Send a private message
    const user_id = 9;
    params = {
        to: [user_id],
        type: "private",
        content: "With mirth and laughter let old wrinkles come.",
    };
    const result_2 = await client.messages.send(params);
    // {code_example|end}
    return [result_1, result_2];
});

add_example("create_user", "/users:post", 200, async (client) => {
    // {code_example|start}
    const params = {
        email: "notnewbie@zulip.com",
        password: "temp",
        full_name: "New User",
    };

    return await client.users.create(params);
    // {code_example|end}
});

add_example("get_custom_emoji", "/realm/emoji:get", 200, async (client) => {
    // {code_example|start}
    return await client.emojis.retrieve();
    // {code_example|end}
});

add_example("delete_queue", "/events:delete", 200, async (client) => {
    // {code_example|start}
    // Register a queue
    const queueParams = {
        event_types: ["message"],
    };
    const res = await client.queues.register(queueParams);

    // Delete a queue
    const deregisterParams = {
        queue_id: res.queue_id,
    };

    return await client.queues.deregister(deregisterParams);
    // {code_example|end}
});

add_example("get_messages", "/messages:get", 200, async (client) => {
    // {code_example|start}
    const readParams = {
        anchor: "newest",
        num_before: 100,
        num_after: 0,
        narrow: [
            {operator: "sender", operand: "iago@zulip.com"},
            {operator: "stream", operand: "Verona"},
        ],
    };

    // Get the 100 last messages sent by "iago@zulip.com" to the stream "Verona"
    return await client.messages.retrieve(readParams);
    // {code_example|end}
});

add_example("get_own_user", "/users/me:get", 200, async (client) => {
    // {code_example|start}
    // Get the profile of the user/bot that requests this endpoint,
    // which is `client` in this case:
    return await client.users.me.getProfile();
    // {code_example|end}
});

add_example("get_stream_id", "/get_stream_id:get", 200, async (client) => {
    // {code_example|start}
    // Get the ID of a given stream
    return await client.streams.getStreamId("Denmark");
    // {code_example|end}
});

add_example("get_stream_topics", "/users/me/{stream_id}/topics:get", 200, async (client) => {
    // {code_example|start}
    // Get all the topics in stream with ID 1
    return client.streams.topics.retrieve({stream_id: 1});
    // {code_example|end}
});

add_example("get_subscriptions", "/users/me/subscriptions:get", 200, async (client) => {
    // {code_example|start}
    // Get all streams that the user is subscribed to
    return await client.streams.subscriptions.retrieve();
    // {code_example|end}
});

add_example("get_users", "/users:get", 200, async (client) => {
    // {code_example|start}
    // Get all users in the realm
    const result_1 = await client.users.retrieve();
    // {code_example|end}

    // {code_example|start}
    // You may pass the `client_gravatar` query parameter as follows:
    const result_2 = await client.users.retrieve({client_gravatar: true});
    // {code_example|end}
    return [result_1, result_2];
});

add_example("register_queue", "/register:post", 200, async (client) => {
    // {code_example|start}
    // Register a queue
    const params = {
        event_types: ["message"],
    };

    return await client.queues.register(params);
    // {code_example|end}
});

add_example("render_message", "/messages/render:post", 200, async (client) => {
    // {code_example|start}
    // Render a message
    const params = {
        content: "**foo**",
    };

    return await client.messages.render(params);
    // {code_example|end}
});

add_example("set_typing_status", "/typing:post", 200, async (client) => {
    // {code_example|start}
    const user_id1 = 9;
    const user_id2 = 10;

    const typingParams = {
        op: "start",
        to: [user_id1, user_id2],
    };

    // The user has started to type in the group PM with Iago and Polonius
    return await client.typing.send(typingParams);
    // {code_example|end}
});

add_example("add_subscriptions", "/users/me/subscriptions:post", 200, async (client) => {
    // {code_example|start}
    // Subscribe to the streams "Verona" and "Denmark"
    const meParams = {
        subscriptions: JSON.stringify([{name: "Verona"}, {name: "Denmark"}]),
    };
    const result_1 = await client.users.me.subscriptions.add(meParams);
    // {code_example|end}

    // {code_example|start}
    // To subscribe another user to a stream, you may pass in
    // the `principals` parameter, like so:
    const user_id = 7;
    const anotherUserParams = {
        subscriptions: JSON.stringify([{name: "Verona"}, {name: "Denmark"}]),
        principals: JSON.stringify([user_id]),
    };
    const result_2 = await client.users.me.subscriptions.add(anotherUserParams);
    // {code_example|end}
    return [result_1, result_2];
});

add_example("remove_subscriptions", "/users/me/subscriptions:delete", 200, async (client) => {
    // {code_example|start}
    // Unsubscribe from the stream "Denmark"
    const meParams = {
        subscriptions: JSON.stringify(["Denmark"]),
    };
    const result_1 = await client.users.me.subscriptions.remove(meParams);
    // {code_example|end}

    // {code_example|start}
    const user_id = 7;
    // Unsubscribe Zoe from the stream "Denmark"
    const zoeParams = {
        subscriptions: JSON.stringify(["Denmark"]),
        principals: JSON.stringify([user_id]),
    };
    const result_2 = await client.users.me.subscriptions.remove(zoeParams);
    // {code_example|end}
    return [result_1, result_2];
});

add_example("update_message_flags", "/messages/flags:post", 200, async (client) => {
    // Send 3 messages to run this example on
    const message_ids = [...new Array(3)];
    for (let i = 0; i < message_ids.length; i = i + 1) {
        message_ids[i] = await send_test_message(client);
    }

    // {code_example|start}
    // Add the "read" flag to the messages with IDs in "message_ids"
    const addflag = {
        messages: message_ids,
        flag: "read",
    };
    const result_1 = await client.messages.flags.add(addflag);
    // {code_example|end}

    // {code_example|start}
    // Remove the "starred" flag from the messages with IDs in "message_ids"
    const removeflag = {
        messages: message_ids,
        flag: "starred",
    };
    const result_2 = await client.messages.flags.remove(removeflag);
    // {code_example|end}
    return [result_1, result_2];
});

add_example("update_message", "/messages/{message_id}:patch", 200, async (client) => {
    const request = {
        to: "Denmark",
        type: "stream",
        topic: "Castle",
        content: "I come not, friends, to steal away your hearts.",
    };
    const result = await client.messages.send(request);
    const message_id = result.id;

    // {code_example|start}
    // Update a message with the given "message_id"
    const params = {
        message_id,
        content: "New Content",
    };

    return await client.messages.update(params);
    // {code_example|end}
});

add_example("get_events", "/events:get", 200, async (client) => {
    // Register queue to receive messages for user.
    const queueParams = {
        event_types: ["message"],
    };
    const res = await client.queues.register(queueParams);
    const queue_id = res.queue_id;
    // For setup, we send a message to ensure there are events in the
    // queue; this lets the automated tests complete quickly.
    await send_test_message(client);

    // {code_example|start}
    // Retrieve events from a queue with given "queue_id"
    const eventParams = {
        queue_id,
        last_event_id: -1,
    };

    return await client.events.retrieve(eventParams);
    // {code_example|end}
});

add_example("get_streams", "/streams:get", 200, async (client) => {
    // {code_example|start}
    // Get all streams that the user has access to
    return await client.streams.retrieve();
    // {code_example|end}
});

main();
