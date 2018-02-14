zrequire('tabs');

var state;
var narrow = {
    activate: function (data) {
        state = data;
    },
};

tabs.update_indicator = function () {
    return true;
};

set_global('narrow', narrow);

// New Zulip web app instance started. Initial narrow:
tabs.set_current_operators(['first location']);

assert.deepEqual(tabs.get().length, 1);
assert.deepEqual(tabs.get()[0].operators, ['first location']);

// Create new tab.
tabs.new();

assert.deepEqual(tabs.get().length, 2);
assert.deepEqual(tabs.get()[0].operators, ['first location']);
assert.deepEqual(tabs.get()[1].operators, ['first location']);

// Navigate somewhere. Narrows to:
tabs.set_current_operators(['second location']);

assert.deepEqual(tabs.get().length, 2);
assert.deepEqual(tabs.get()[0].operators, ['first location']);
assert.deepEqual(tabs.get()[1].operators, ['second location']);

tabs.new();
tabs.set_current_operators(['third location']);
tabs.new();
tabs.set_current_operators(['fourth location']);

assert.deepEqual(tabs.get().length, 4);
assert.deepEqual(tabs.get()[0].operators, ['first location']);
assert.deepEqual(tabs.get()[1].operators, ['second location']);
assert.deepEqual(tabs.get()[2].operators, ['third location']);
assert.deepEqual(tabs.get()[3].operators, ['fourth location']);

tabs.next();

assert.deepEqual(state, ['first location']);

tabs.next();
tabs.next();
assert.deepEqual(state, ['third location']);

tabs.previous();

assert.deepEqual(state, ['second location']);

tabs.previous();
tabs.previous();

assert.deepEqual(state, ['fourth location']);

tabs.activate(1);

assert.deepEqual(state, ['second location']);

tabs.next();
tabs.close();

assert.deepEqual(tabs.get().length, 3);
assert.deepEqual(tabs.get()[0].operators, ['first location']);
assert.deepEqual(tabs.get()[1].operators, ['second location']);
assert.deepEqual(tabs.get()[2].operators, ['fourth location']);
assert.deepEqual(state, ['second location']);

tabs.close();
tabs.close();

assert.deepEqual(tabs.get().length, 1);
assert.deepEqual(tabs.get()[0].operators, ['fourth location']);
assert.deepEqual(state, ['fourth location']);
