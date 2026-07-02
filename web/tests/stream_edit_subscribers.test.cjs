"use strict";

const assert = require("node:assert/strict");

const {make_user} = require("./lib/example_user.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const {compute_bulk_unsubscribe_modal_props} = zrequire("stream_edit_subscribers");

const me = make_user({email: "me@zulip.com", full_name: "Me", user_id: 1});
const alice = make_user({email: "alice@zulip.com", full_name: "Alice", user_id: 2});
const bob = make_user({email: "bob@zulip.com", full_name: "Bob", user_id: 3});

run_test("compute_bulk_unsubscribe_modal_props: public channel never shows modal", () => {
    const props = compute_bulk_unsubscribe_modal_props({
        invite_only: false,
        subscribed_target_ids: [me.user_id, alice.user_id],
        sub_count: 5,
        self_user_id: me.user_id,
        self_can_rejoin: false,
        nobody_can_subscribe: true,
    });
    assert.equal(props.needs_modal, false);
});

run_test("compute_bulk_unsubscribe_modal_props: empty target list never shows modal", () => {
    const props = compute_bulk_unsubscribe_modal_props({
        invite_only: true,
        subscribed_target_ids: [],
        sub_count: 5,
        self_user_id: me.user_id,
        self_can_rejoin: false,
        nobody_can_subscribe: true,
    });
    assert.equal(props.needs_modal, false);
});

run_test(
    "compute_bulk_unsubscribe_modal_props: self with rejoin permission alone, no modal",
    () => {
        const props = compute_bulk_unsubscribe_modal_props({
            invite_only: true,
            subscribed_target_ids: [me.user_id],
            sub_count: 5,
            self_user_id: me.user_id,
            self_can_rejoin: true,
            nobody_can_subscribe: false,
        });
        assert.equal(props.needs_modal, false);
    },
);

run_test(
    "compute_bulk_unsubscribe_modal_props: self without rejoin shows modal with rejoin warning",
    () => {
        const props = compute_bulk_unsubscribe_modal_props({
            invite_only: true,
            subscribed_target_ids: [me.user_id],
            sub_count: 5,
            self_user_id: me.user_id,
            self_can_rejoin: false,
            nobody_can_subscribe: false,
        });
        assert.deepEqual(props, {
            needs_modal: true,
            show_private_stream_warning: true,
            unsubscribing_other_user: false,
            organization_will_lose_content_access: false,
        });
    },
);

run_test(
    "compute_bulk_unsubscribe_modal_props: removing others without emptying channel, no modal",
    () => {
        const props = compute_bulk_unsubscribe_modal_props({
            invite_only: true,
            subscribed_target_ids: [alice.user_id, bob.user_id],
            sub_count: 5,
            self_user_id: me.user_id,
            self_can_rejoin: false,
            nobody_can_subscribe: true,
        });
        assert.equal(props.needs_modal, false);
    },
);

run_test("compute_bulk_unsubscribe_modal_props: emptying channel shows modal", () => {
    const props = compute_bulk_unsubscribe_modal_props({
        invite_only: true,
        subscribed_target_ids: [alice.user_id, bob.user_id],
        sub_count: 2,
        self_user_id: me.user_id,
        self_can_rejoin: false,
        nobody_can_subscribe: false,
    });
    assert.deepEqual(props, {
        needs_modal: true,
        show_private_stream_warning: true,
        unsubscribing_other_user: true,
        organization_will_lose_content_access: false,
    });
});

run_test(
    "compute_bulk_unsubscribe_modal_props: emptying channel with no re-subscribers shows org warning",
    () => {
        const props = compute_bulk_unsubscribe_modal_props({
            invite_only: true,
            subscribed_target_ids: [alice.user_id, bob.user_id],
            sub_count: 2,
            self_user_id: me.user_id,
            self_can_rejoin: false,
            nobody_can_subscribe: true,
        });
        assert.deepEqual(props, {
            needs_modal: true,
            show_private_stream_warning: true,
            unsubscribing_other_user: true,
            organization_will_lose_content_access: true,
        });
    },
);

run_test(
    "compute_bulk_unsubscribe_modal_props: mixed self+others, self has rejoin, won't empty, no modal",
    () => {
        const props = compute_bulk_unsubscribe_modal_props({
            invite_only: true,
            subscribed_target_ids: [me.user_id, alice.user_id],
            sub_count: 5,
            self_user_id: me.user_id,
            self_can_rejoin: true,
            nobody_can_subscribe: false,
        });
        assert.equal(props.needs_modal, false);
    },
);

run_test(
    "compute_bulk_unsubscribe_modal_props: mixed self+others, self has rejoin, will empty -> modal without rejoin warning",
    () => {
        const props = compute_bulk_unsubscribe_modal_props({
            invite_only: true,
            subscribed_target_ids: [me.user_id, alice.user_id],
            sub_count: 2,
            self_user_id: me.user_id,
            self_can_rejoin: true,
            nobody_can_subscribe: false,
        });
        assert.deepEqual(props, {
            needs_modal: true,
            show_private_stream_warning: true,
            unsubscribing_other_user: true,
            organization_will_lose_content_access: false,
        });
    },
);

run_test(
    "compute_bulk_unsubscribe_modal_props: mixed self+others, self no rejoin, will empty -> both warnings",
    () => {
        const props = compute_bulk_unsubscribe_modal_props({
            invite_only: true,
            subscribed_target_ids: [me.user_id, alice.user_id],
            sub_count: 2,
            self_user_id: me.user_id,
            self_can_rejoin: false,
            nobody_can_subscribe: true,
        });
        assert.deepEqual(props, {
            needs_modal: true,
            show_private_stream_warning: true,
            unsubscribing_other_user: false,
            organization_will_lose_content_access: true,
        });
    },
);

run_test(
    "compute_bulk_unsubscribe_modal_props: removing 10+ users shows a volume confirmation",
    () => {
        const props = compute_bulk_unsubscribe_modal_props({
            invite_only: false,
            subscribed_target_ids: Array.from({length: 10}, (_, i) => i + 100),
            sub_count: 50,
            self_user_id: me.user_id,
            self_can_rejoin: true,
            nobody_can_subscribe: false,
        });
        assert.deepEqual(props, {
            needs_modal: true,
            show_private_stream_warning: false,
            unsubscribing_other_user: true,
            organization_will_lose_content_access: false,
        });
    },
);

run_test(
    "compute_bulk_unsubscribe_modal_props: removing fewer than 10 users on a public channel, no modal",
    () => {
        const props = compute_bulk_unsubscribe_modal_props({
            invite_only: false,
            subscribed_target_ids: Array.from({length: 9}, (_, i) => i + 100),
            sub_count: 50,
            self_user_id: me.user_id,
            self_can_rejoin: true,
            nobody_can_subscribe: false,
        });
        assert.equal(props.needs_modal, false);
    },
);

run_test(
    "compute_bulk_unsubscribe_modal_props: large private removal without edge cases shows volume confirmation only",
    () => {
        const props = compute_bulk_unsubscribe_modal_props({
            invite_only: true,
            subscribed_target_ids: Array.from({length: 12}, (_, i) => i + 100),
            sub_count: 50,
            self_user_id: me.user_id,
            self_can_rejoin: false,
            nobody_can_subscribe: true,
        });
        assert.deepEqual(props, {
            needs_modal: true,
            show_private_stream_warning: false,
            unsubscribing_other_user: true,
            organization_will_lose_content_access: false,
        });
    },
);

run_test(
    "compute_bulk_unsubscribe_modal_props: large removal that empties a private channel keeps the private warning",
    () => {
        const props = compute_bulk_unsubscribe_modal_props({
            invite_only: true,
            subscribed_target_ids: Array.from({length: 10}, (_, i) => i + 100),
            sub_count: 10,
            self_user_id: me.user_id,
            self_can_rejoin: false,
            nobody_can_subscribe: true,
        });
        assert.deepEqual(props, {
            needs_modal: true,
            show_private_stream_warning: true,
            unsubscribing_other_user: true,
            organization_will_lose_content_access: true,
        });
    },
);
