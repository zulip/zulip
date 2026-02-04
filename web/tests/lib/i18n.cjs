"use strict";

const {zrequire} = require("./namespace.cjs");

const i18n = zrequire("i18n");

Object.assign(exports, i18n);

exports.$t = (descriptor, values, opts) =>
    i18n.$t({id: descriptor.defaultMessage, descriptor}, values, opts);

/* istanbul ignore next */
exports.$t_html = (descriptor, values, opts) =>
    i18n.$t_html({id: descriptor.defaultMessage, descriptor}, values, opts);
