"use strict";

exports.page_params = {};

exports.reset = () => {
    for (const field in exports.page_params) {
        if (Object.hasOwn(exports.page_params, field)) {
            // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
            delete exports.page_params[field];
        }
    }
    exports.page_params.request_language = "en";
    exports.page_params.translation_data = new Proxy(
        {},
        {
            get: (_target, key) => `translated: ${key}`,
            getOwnPropertyDescriptor: (_target, _key) => ({configurable: true}),
        },
    );
};

exports.reset();
