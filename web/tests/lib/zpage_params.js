"use strict";

exports.current_user = {};
exports.page_params = {};
exports.realm = {};
exports.realm_user_settings_defaults = {};
exports.user_settings = {};

exports.reset = () => {
    for (const field in exports.current_user) {
        if (Object.hasOwn(exports.current_user, field)) {
            delete exports.current_user[field];
        }
    }
    for (const field in exports.page_params) {
        if (Object.hasOwn(exports.page_params, field)) {
            delete exports.page_params[field];
        }
    }
    for (const field in exports.realm) {
        if (Object.hasOwn(exports.realm, field)) {
            delete exports.realm[field];
        }
    }
    for (const field in exports.user_settings) {
        if (Object.hasOwn(exports.user_settings, field)) {
            delete exports.user_settings[field];
        }
    }
    for (const field in exports.realm_user_settings_defaults) {
        if (Object.hasOwn(exports.realm_user_settings_defaults, field)) {
            delete exports.realm_user_settings_defaults[field];
        }
    }
};
