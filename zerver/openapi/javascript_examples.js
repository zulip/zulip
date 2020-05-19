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
            endpoint: example.endpoint.split(':')[0],
            method: example.endpoint.split(':')[1],
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
        const Zulip = require('zulip-js');
        const client = await Zulip(config);

        await generate_validation_data(client, examples.send_message);
        await generate_validation_data(client, examples.create_user);

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

const {main} = ExamplesHandler();

// Declare all the examples below.

main();
