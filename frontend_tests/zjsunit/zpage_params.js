"use strict";

exports.page_params = {};

exports.reset = () => {
    for (const field in exports.page_params) {
        if (Object.prototype.hasOwnProperty.call(exports.page_params, field)) {
            delete exports.page_params[field];
        }
    }
};
