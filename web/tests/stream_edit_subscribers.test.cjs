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

run_test(
    "compute_bulk_unsubscribe_modal_props: emptying a still-subscribable private channel shows no warning modal",
    () => {
        // Regression: this used to warn with no text to show (empty modal
        // body); an emptying-but-still-subscribable channel needs no warning.
        const props = compute_bulk_unsubscribe_modal_props({
            invite_only: true,
            subscribed_target_ids: [alice.user_id, bob.user_id],
            sub_count: 2,
            self_user_id: me.user_id,
            self_can_rejoin: false,
            nobody_can_subscribe: false,
        });
        assert.equal(props.needs_modal, false);
    },
);

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
    "compute_bulk_unsubscribe_modal_props: mixed self+others, self has rejoin, emptying a still-subscribable channel -> no modal",
    () => {
        const props = compute_bulk_unsubscribe_modal_props({
            invite_only: true,
            subscribed_target_ids: [me.user_id, alice.user_id],
            sub_count: 2,
            self_user_id: me.user_id,
            self_can_rejoin: true,
            nobody_can_subscribe: false,
        });
        assert.equal(props.needs_modal, false);
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

run_test(
    "compute_bulk_unsubscribe_modal_props: a private-stream warning always has body copy to render",
    () => {
        // The warning modal only renders text when the acting user can't
        // rejoin or the org loses access; if we set the warning without one of
        // those, its body is empty.
        for (const self_in_targets of [false, true]) {
            for (const self_can_rejoin of [false, true]) {
                for (const will_empty of [false, true]) {
                    for (const nobody_can_subscribe of [false, true]) {
                        const subscribed_target_ids = self_in_targets
                            ? [me.user_id, alice.user_id]
                            : [alice.user_id, bob.user_id];
                        const sub_count = will_empty
                            ? subscribed_target_ids.length
                            : subscribed_target_ids.length + 3;
                        const props = compute_bulk_unsubscribe_modal_props({
                            invite_only: true,
                            subscribed_target_ids,
                            sub_count,
                            self_user_id: me.user_id,
                            self_can_rejoin,
                            nobody_can_subscribe,
                        });
                        if (props.show_private_stream_warning) {
                            assert.ok(
                                !props.unsubscribing_other_user ||
                                    props.organization_will_lose_content_access,
                                `empty private-warning body for ${JSON.stringify({
                                    self_in_targets,
                                    self_can_rejoin,
                                    will_empty,
                                    nobody_can_subscribe,
                                })}`,
                            );
                        }
                    }
                }
            }
        }
    },
);
