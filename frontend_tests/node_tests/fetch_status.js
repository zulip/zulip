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

(function test_basics() {
    reset();

    fetch_status.start_initial_narrow();

    blocked_newer();
    blocked_older();

    fetch_status.finish_initial_narrow({
        found_oldest: true,
        found_newest: true,
    });

    blocked_newer();
    blocked_older();

    reset();

    fetch_status.start_initial_narrow();

    blocked_newer();
    blocked_older();

    fetch_status.finish_initial_narrow({
        found_oldest: false,
        found_newest: false,
    });

    can_load_older();
    can_load_newer();

    reset();

    can_load_older();

    fetch_status.start_older_batch();

    blocked_older();
    can_load_newer();

    fetch_status.finish_older_batch({
        found_oldest: false,
    });

    can_load_older();
    can_load_newer();

    fetch_status.start_older_batch();

    blocked_older();
    can_load_newer();

    fetch_status.finish_older_batch({
        found_oldest: true,
    });

    blocked_older();
    can_load_newer();

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
}());
