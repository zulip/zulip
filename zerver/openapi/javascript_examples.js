const ExamplesHandler = function () {
    const config = {
        username: process.env.ZULIP_USERNAME,
        apiKey: process.env.ZULIP_API_KEY,
        realm: process.env.ZULIP_REALM,
    };
    const examples = [];

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

    const generate_validation_data = async (client) => {
        const response_data = [];
        for (const example of examples) {
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
        }
        return response_data;
    };

    const format_example_code = (example) => {
        let body = example.func.toString();
        body = body.slice(body.indexOf("{") + 2, body.lastIndexOf("}") - 1);
        body = body.replace(/\n\s*\n\s*\n/g, '\n\n');
        const wrapper = [
            "Zulip(config).then(async (client) => {",
            `${body}`,
            "}).then(console.log).catch(console.err);",
        ].join('\n');
        return wrapper;
    };

    const main = async () => {
        const command = process.argv[2];
        if (command === 'generate-responses') {
            const Zulip = require('zulip-js');
            const client = await Zulip(config);
            const response_data = await generate_validation_data(client);
            console.log(JSON.stringify(response_data));
            return;
        }
        if (command === 'generate-example') {
            const endpoint = process.argv[3];
            if (!endpoint) {
                console.error("js-examples: Please specify an endpoint.");
                process.exit(1);
            }
            const example = examples.find(x => x.endpoint.toString() === endpoint);
            if (!example) {
                console.error(`js-examples: Endpoint ${endpoint} not found.`);
                process.exit(1);
            }
            console.log(format_example_code(example));
            return;
        }
        console.error("js-examples: Invalid command.");
        process.exit(1);
    };

    const add_example = (name, endpoint, status_code, func) => {
        examples.push({
            name,
            endpoint,
            status_code,
            func,
        });
    };

    return {
        main,
        add_example,
    };
};

const {main} = ExamplesHandler();

// Declare all the examples below.

main();
