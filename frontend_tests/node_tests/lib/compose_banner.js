"use strict";

const compose_banner = require("../../../static/js/compose_banner");
const $ = require("../../zjsunit/zjquery");

exports.mock_banners = () => {
    // zjquery doesn't support `remove`, which is used when clearing the compose box.
    // TODO: improve how we test this so that we don't have to mock things like this.
    for (const classname of Object.values(compose_banner.CLASSNAMES)) {
        $(`#compose_banners .${classname}`).remove = () => {};
    }
};
