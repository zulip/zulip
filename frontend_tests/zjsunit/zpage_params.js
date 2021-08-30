"use strict";

exports.page_params = {};
exports.realm_user_settings_defaults = {};
exports.user_settings = {};

exports.reset = () => {
    for (const field in exports.page_params) {
        if (Object.prototype.hasOwnProperty.call(exports.page_params, field)) {
            delete exports.page_params[field];
        }
    }
    for (const field in exports.user_settings) {
        if (Object.prototype.hasOwnProperty.call(exports.user_settings, field)) {
            delete exports.user_settings[field];
        }
    }
    for (const field in exports.realm_user_settings_defaults) {
        if (Object.prototype.hasOwnProperty.call(exports.realm_user_settings_defaults, field)) {
            delete exports.realm_user_settings_defaults[field];
        }
    }
};
