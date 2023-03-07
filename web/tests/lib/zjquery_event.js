"use strict";

class FakeEvent {
    constructor(type, props) {
        this.type = type;
        Object.assign(this, props);
    }
    preventDefault() {}
    stopPropagation() {}
}

module.exports = FakeEvent;
