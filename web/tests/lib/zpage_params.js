"use strict";

exports.page_params = {};

exports.reset = () => {
    for (const field in exports.page_params) {
        if (Object.hasOwn(exports.page_params, field)) {
            delete exports.page_params[field];
        }
    }
};
