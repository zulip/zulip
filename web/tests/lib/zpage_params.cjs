"use strict";

exports.page_params = {};

exports.reset = () => {
    for (const field in exports.page_params) {
        if (Object.hasOwn(exports.page_params, field)) {
            // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
            delete exports.page_params[field];
        }
    }
};
