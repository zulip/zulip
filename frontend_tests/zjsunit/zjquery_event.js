"use strict";

class FakeEvent {
    constructor(type, props) {
        if (!(this instanceof FakeEvent)) {
            return new FakeEvent(type, props);
        }
        this.type = type;
        Object.assign(this, props);
    }
    preventDefault() {}
    stopPropagation() {}
}

module.exports = FakeEvent;
