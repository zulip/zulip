var FetchStatus = zrequire('fetch_status');

var fetch_status = FetchStatus();

function reset() {
    fetch_status = FetchStatus();
}

function can_load_newer() {
    assert.equal(fetch_status.can_load_newer_messages(), true);
}

function blocked_newer() {
    assert.equal(fetch_status.can_load_newer_messages(), false);
}

function can_load_older() {
    assert.equal(fetch_status.can_load_older_messages(), true);
}

function blocked_older() {
    assert.equal(fetch_status.can_load_older_messages(), false);
}

function has_found_newest() {
    assert.equal(fetch_status.has_found_newest(), true);
}

function has_not_found_newest() {
    assert.equal(fetch_status.has_found_newest(), false);
}

function can_load_history() {
    assert.equal(fetch_status.history_limited(), false);
}

function blocked_history() {
    assert.equal(fetch_status.history_limited(), true);
}

run_test('basics', () => {
    reset();

    fetch_status.start_newer_batch();
    fetch_status.start_older_batch();

    blocked_newer();
    blocked_older();
    can_load_history();
    has_not_found_newest();

    var data = {
        found_oldest: true,
        found_newest: true,
        history_limited: true,
    };
    fetch_status.finish_newer_batch(data);
    fetch_status.finish_older_batch(data);

    has_found_newest();
    blocked_newer();
    blocked_older();
    blocked_history();

    reset();

    fetch_status.start_newer_batch();
    fetch_status.start_older_batch();

    blocked_newer();
    blocked_older();
    can_load_history();

    data = {
        found_oldest: false,
        found_newest: false,
        history_limited: false,
    };
    fetch_status.finish_newer_batch(data);
    fetch_status.finish_older_batch(data);

    can_load_older();
    can_load_newer();
    can_load_history();

    reset();

    can_load_older();

    fetch_status.start_older_batch();

    blocked_older();
    can_load_newer();
    can_load_history();

    fetch_status.finish_older_batch({
        found_oldest: false,
        history_limited: false,
    });

    can_load_older();
    can_load_newer();
    can_load_history();

    fetch_status.start_older_batch();

    blocked_older();
    can_load_newer();
    can_load_history();

    fetch_status.finish_older_batch({
        found_oldest: true,
        history_limited: true,
    });

    blocked_older();
    can_load_newer();
    blocked_history();

    reset();

    can_load_older();
    can_load_newer();

    fetch_status.start_newer_batch();

    can_load_older();
    blocked_newer();

    fetch_status.finish_newer_batch({
        found_newest: false,
    });

    can_load_older();
    can_load_newer();

    fetch_status.start_newer_batch();

    can_load_older();
    blocked_newer();

    fetch_status.finish_newer_batch({
        found_newest: true,
    });

    can_load_older();
    blocked_newer();
});
