"use strict";

const {strict: assert} = require("assert");

const {parseISO} = require("date-fns");
const _ = require("lodash");
const MockDate = require("mockdate");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

set_global("message_store", {});
set_global("page_params", {});
set_global("settings_data", {});

const people = zrequire("people");
const settings_config = zrequire("settings_config");
const visibility = settings_config.email_address_visibility_values;
const admins_only = visibility.admins_only.code;
const everyone = visibility.everyone.code;

function set_email_visibility(code) {
    page_params.realm_email_address_visibility = code;
}

set_email_visibility(admins_only);

MockDate.set(parseISO("20130208T080910").getTime());

const welcome_bot = {
    email: "welcome-bot@example.com",
    user_id: 4,
    full_name: "Welcome Bot",
    is_bot: true,
    // cross realm bots have no owner
};

const me = {
    email: "me@example.com",
    user_id: 30,
    full_name: "Me Myself",
    timezone: "America/Los_Angeles",
    is_admin: false,
    is_guest: false,
    is_bot: false,
    // no avatar, so client should construct a /avatar/{user_id} URL.
};

const isaac = {
    email: "isaac@example.com",
    delivery_email: "isaac-delivery@example.com",
    user_id: 32,
    full_name: "Isaac Newton",
};

function initialize() {
    people.init();
    people.add_active_user(me);
    people.initialize_current_user(me.user_id);
}

initialize();

/*
    TEST SETUP NOTES:

    We don't add all these users right away,
    but they are convenient to have for various
    tests, and we just add them as needed after
    calling something like `people.init()`.

    Note that we deliberately make it so that
    alphabetical order mismatches id order,
    since that can uncover bugs where we neglect
    to be rigorous about sort order.
*/

const realm_admin = {
    email: "realm_admin@example.com",
    full_name: "Realm Admin",
    user_id: 32,
    is_owner: false,
    is_admin: true,
    is_guest: false,
    is_bot: false,
};

const guest = {
    email: "guest@example.com",
    full_name: "Guest User",
    user_id: 33,
    is_owner: false,
    is_admin: false,
    is_guest: true,
    is_bot: false,
};

const realm_owner = {
    email: "realm_owner@example.com",
    full_name: "Realm Owner",
    user_id: 34,
    is_owner: true,
    is_admin: true,
    is_guest: false,
    is_bot: false,
};

const bot_botson = {
    email: "botson-bot@example.com",
    user_id: 35,
    full_name: "Bot Botson",
    is_bot: true,
    bot_owner_id: isaac.user_id,
};

const steven = {
    email: "steven@example.com",
    delivery_email: "steven-delivery@example.com",
    user_id: 77,
    full_name: "Steven",
};

const alice1 = {
    email: "alice1@example.com",
    user_id: 202,
    full_name: "Alice",
};

const bob = {
    email: "bob@example.com",
    user_id: 203,
    full_name: "Bob van Roberts",
};

const alice2 = {
    email: "alice2@example.com",
    user_id: 204,
    full_name: "Alice",
};

const charles = {
    email: "charles@example.com",
    user_id: 301,
    full_name: "Charles Dickens",
    avatar_url: "charles.com/foo.png",
    is_guest: false,
};

const maria = {
    email: "Athens@example.com",
    user_id: 302,
    full_name: "Maria Athens",
    // With client_gravatar enabled, requests that client compute gravatar
    avatar_url: null,
};

const ashton = {
    email: "ashton@example.com",
    user_id: 303,
    full_name: "Ashton Smith",
};

const linus = {
    email: "ltorvalds@example.com",
    user_id: 304,
    full_name: "Linus Torvalds",
};

const emp401 = {
    email: "emp401@example.com",
    user_id: 401,
    full_name: "whatever 401",
};

const emp402 = {
    email: "EMP402@example.com",
    user_id: 402,
    full_name: "whatever 402",
};

const debbie = {
    email: "deBBie71@example.com",
    user_id: 501,
    full_name: "Debra Henton",
};

const stephen1 = {
    email: "stephen-the-author@example.com",
    user_id: 601,
    full_name: "Stephen King",
};

const stephen2 = {
    email: "stephen-the-explorer@example.com",
    user_id: 602,
    full_name: "Stephen King",
};

const noah = {
    email: "emnoa@example.com",
    user_id: 1200,
    full_name: "Nöôáàh Ëmerson",
};

const plain_noah = {
    email: "otheremnoa@example.com",
    user_id: 1201,
    full_name: "Nooaah Emerson",
};

// This is for error checking--never actually
// tell people.js about this user.
const unknown_user = {
    email: "unknown@example.com",
    user_id: 999,
    unknown_local_echo_user: true,
};

function get_all_persons() {
    return people.filter_all_persons(() => true);
}

run_test("basics", () => {
    const persons = get_all_persons();

    assert.deepEqual(people.get_realm_users(), [me]);

    assert.equal(persons.length, 1);
    assert.equal(persons[0].full_name, "Me Myself");

    let realm_persons = people.get_realm_users();
    assert.equal(realm_persons[0].full_name, "Me Myself");

    realm_persons = people.get_realm_users();
    assert.equal(realm_persons.length, 1);
    assert.equal(people.get_active_human_ids().length, 1);

    const full_name = "Isaac Newton";
    const email = "isaac@example.com";

    assert(!people.is_known_user_id(32));
    assert(!people.is_valid_full_name_and_user_id(full_name, 32));
    assert.equal(people.get_user_id_from_name(full_name), undefined);

    people.add_active_user(isaac);

    assert.equal(people.get_actual_name_from_user_id(32), full_name);

    assert(people.is_valid_full_name_and_user_id(full_name, 32));
    assert(people.is_known_user_id(32));
    assert.equal(people.get_active_human_count(), 2);

    assert.equal(people.get_user_id_from_name(full_name), 32);

    let person = people.get_by_email(email);
    assert.equal(person.full_name, full_name);

    realm_persons = people.get_realm_users();
    assert.equal(realm_persons.length, 2);

    const active_user_ids = people.get_active_user_ids().sort();
    assert.deepEqual(active_user_ids, [me.user_id, isaac.user_id]);
    assert.equal(people.is_active_user_for_popover(isaac.user_id), true);
    assert(people.is_valid_email_for_compose(isaac.email));

    // Now deactivate isaac
    people.deactivate(isaac);
    assert.equal(people.get_non_active_human_ids().length, 1);
    assert.equal(people.get_active_human_count(), 1);
    assert.equal(people.is_active_user_for_popover(isaac.user_id), false);
    assert.equal(people.is_valid_email_for_compose(isaac.email), false);

    people.add_active_user(bot_botson);
    assert.equal(people.is_active_user_for_popover(bot_botson.user_id), true);

    assert.equal(people.get_bot_owner_user(bot_botson).full_name, "Isaac Newton");

    // Add our cross-realm bot.  It won't add to our human
    // count, and it has no owner.
    people.add_cross_realm_user(welcome_bot);
    assert.equal(people.get_bot_owner_user(welcome_bot), undefined);
    assert.equal(people.get_active_human_count(), 1);
    assert.equal(people.get_by_email(welcome_bot.email).full_name, "Welcome Bot");

    // get_realm_users() will include our active bot,
    // but will exclude isaac (who is deactivated)
    assert.deepEqual(
        people
            .get_realm_users()
            .map((u) => u.user_id)
            .sort(),
        [me.user_id, bot_botson.user_id],
    );

    // The bot doesn't add to our human count.
    assert.equal(people.get_active_human_count(), 1);

    // Invalid user ID returns false and warns.
    blueslip.expect("warn", "Unexpectedly invalid user_id in user popover query: 123412");
    assert.equal(people.is_active_user_for_popover(123412), false);

    // We can still get their info for non-realm needs.
    person = people.get_by_email(email);
    assert.equal(person.email, email);

    // The current user should still be there
    person = people.get_by_email("me@example.com");
    assert.equal(person.full_name, "Me Myself");

    // Test undefined people
    assert.equal(people.is_cross_realm_email("unknown@example.com"), undefined);

    // Test is_my_user_id function
    assert.equal(people.is_my_user_id(me.user_id), true);
    assert.equal(people.is_my_user_id(isaac.user_id), false);
    assert.equal(people.is_my_user_id(undefined), false);

    // Reactivating issac
    people.add_active_user(isaac);
    const active_humans = people.get_active_human_ids();
    assert.equal(active_humans.length, 2);
    assert.deepEqual(
        active_humans.sort((p) => p.user_id),
        [me.user_id, isaac.user_id],
    );
});

run_test("check_active_non_active_users", () => {
    let active_users = people.get_realm_users();
    let non_active_users = people.get_non_active_realm_users();
    assert.equal(active_users.length, 3);
    assert.equal(non_active_users.length, 0);

    people.add_active_user(maria);
    people.add_active_user(linus);
    active_users = people.get_realm_users();
    assert.equal(active_users.length, 5);
    // Invalid ID
    blueslip.expect("error", "No user found.");
    people.is_person_active(1000001);
    assert.equal(people.is_person_active(maria.user_id), true);
    assert.equal(people.is_person_active(linus.user_id), true);

    people.deactivate(maria);
    non_active_users = people.get_non_active_realm_users();
    active_users = people.get_realm_users();
    assert.equal(non_active_users.length, 1);
    assert.equal(active_users.length, 4);
    assert.equal(people.is_person_active(maria.user_id), false);

    people.deactivate(linus);
    people.add_active_user(maria);
    non_active_users = people.get_non_active_realm_users();
    active_users = people.get_realm_users();
    assert.equal(non_active_users.length, 1);
    assert.equal(active_users.length, 4);
    assert.equal(people.is_person_active(maria.user_id), true);
    assert.equal(people.is_person_active(linus.user_id), false);
});

run_test("pm_lookup_key", () => {
    assert.equal(people.pm_lookup_key("30"), "30");
    assert.equal(people.pm_lookup_key("32,30"), "32");
    assert.equal(people.pm_lookup_key("101,32,30"), "32,101");
});

run_test("get_recipients", () => {
    assert.equal(people.get_recipients("30"), "Me Myself");
    assert.equal(people.get_recipients("30,32"), "Isaac Newton");
});

run_test("safe_full_names", () => {
    const names = people.safe_full_names([me.user_id, isaac.user_id]);
    assert.equal(names, "Me Myself, Isaac Newton");
});

run_test("my_custom_profile_data", () => {
    const person = people.get_by_email(me.email);
    person.profile_data = {3: "My address", 4: "My phone number"};
    assert.equal(people.my_custom_profile_data(3), "My address");
    assert.equal(people.my_custom_profile_data(4), "My phone number");
});

run_test("bot_custom_profile_data", () => {
    // If this test fails, then try opening organization settings > bots
    // http://localhost:9991/#organization/bot-list-admin
    // and then try to edit any of the bots.
    people.add_active_user(bot_botson);
    assert.equal(people.get_custom_profile_data(bot_botson.user_id, 3), null);
});

run_test("user_timezone", () => {
    const expected_pref = {
        timezone: "America/Los_Angeles",
        format: "H:mm",
    };

    page_params.twenty_four_hour_time = true;
    assert.deepEqual(people.get_user_time_preferences(me.user_id), expected_pref);

    expected_pref.format = "h:mm a";
    page_params.twenty_four_hour_time = false;
    assert.deepEqual(people.get_user_time_preferences(me.user_id), expected_pref);

    page_params.twenty_four_hour_time = true;
    assert.equal(people.get_user_time(me.user_id), "0:09");

    page_params.twenty_four_hour_time = false;
    assert.equal(people.get_user_time(me.user_id), "12:09 AM");
});

run_test("user_type", () => {
    people.init();

    people.add_active_user(me);
    people.add_active_user(realm_admin);
    people.add_active_user(guest);
    people.add_active_user(realm_owner);
    people.add_active_user(bot_botson);
    assert.equal(people.get_user_type(me.user_id), i18n.t("Member"));
    assert.equal(people.get_user_type(realm_admin.user_id), i18n.t("Administrator"));
    assert.equal(people.get_user_type(guest.user_id), i18n.t("Guest"));
    assert.equal(people.get_user_type(realm_owner.user_id), i18n.t("Owner"));
    assert.equal(people.get_user_type(bot_botson.user_id), i18n.t("Bot"));
});

run_test("updates", () => {
    const person = people.get_by_email("me@example.com");
    people.set_full_name(person, "Me the Third");
    assert.equal(people.my_full_name(), "Me the Third");
    assert.equal(person.full_name, "Me the Third");
    assert.equal(people.get_user_id_from_name("Me the Third"), me.user_id);
});

run_test("get_by_user_id", () => {
    let person = {
        email: "mary@example.com",
        user_id: 42,
        full_name: "Mary",
    };
    people.add_active_user(person);
    person = people.get_by_email("mary@example.com");
    assert.equal(person.full_name, "Mary");
    person = people.get_by_user_id(42);
    assert.equal(person.email, "mary@example.com");

    people.set_full_name(person, "Mary New");
    person = people.get_by_user_id(42);
    assert.equal(person.full_name, "Mary New");

    // deactivate() should eventually just take a user_id, but
    // now it takes a full person object.  Note that deactivate()
    // won't actually make the user disappear completely.
    people.deactivate(person);
    person = people.get_by_user_id(42);
    assert.equal(person.user_id, 42);
});

initialize();

run_test("set_custom_profile_field_data", () => {
    const person = people.get_by_email(me.email);
    me.profile_data = {};
    const field = {
        id: 3,
        name: "Custom long field",
        type: "text",
        value: "Field value",
        rendered_value: "<p>Field value</p>",
    };
    people.set_custom_profile_field_data(person.user_id, field);
    assert.equal(person.profile_data[field.id].value, "Field value");
    assert.equal(person.profile_data[field.id].rendered_value, "<p>Field value</p>");
});

initialize();

run_test("get_people_for_stream_create", () => {
    people.add_active_user(alice1);
    people.add_active_user(bob);
    people.add_active_user(alice2);
    assert.equal(people.get_active_human_count(), 4);

    const others = people.get_people_for_stream_create();
    const expected = [
        {email: "alice1@example.com", user_id: alice1.user_id, full_name: "Alice"},
        {email: "alice2@example.com", user_id: alice2.user_id, full_name: "Alice"},
        {email: "bob@example.com", user_id: bob.user_id, full_name: "Bob van Roberts"},
    ];
    assert.deepEqual(others, expected);
});

initialize();

run_test("recipient_counts", () => {
    const user_id = 99;
    assert.equal(people.get_recipient_count({user_id}), 0);
    people.incr_recipient_count(user_id);
    people.incr_recipient_count(user_id);
    assert.equal(people.get_recipient_count({user_id}), 2);

    assert.equal(people.get_recipient_count({pm_recipient_count: 5}), 5);
});

run_test("filtered_users", () => {
    people.add_active_user(charles);
    people.add_active_user(maria);
    people.add_active_user(ashton);
    people.add_active_user(linus);
    people.add_active_user(noah);
    people.add_active_user(plain_noah);

    const search_term = "a";
    const users = people.get_people_for_stream_create();
    let filtered_people = people.filter_people_by_search_terms(users, [search_term]);
    assert.equal(filtered_people.size, 2);
    assert(filtered_people.has(ashton.user_id));
    assert(filtered_people.has(maria.user_id));
    assert(!filtered_people.has(charles.user_id));

    filtered_people = people.filter_people_by_search_terms(users, []);
    assert.equal(filtered_people.size, 0);

    filtered_people = people.filter_people_by_search_terms(users, ["ltorv"]);
    assert.equal(filtered_people.size, 1);
    assert(filtered_people.has(linus.user_id));

    filtered_people = people.filter_people_by_search_terms(users, ["ch di", "maria"]);
    assert.equal(filtered_people.size, 2);
    assert(filtered_people.has(charles.user_id));
    assert(filtered_people.has(maria.user_id));

    // Test filtering of names with diacritics
    // This should match Nöôáàh by ignoring diacritics, and also match Nooaah
    filtered_people = people.filter_people_by_search_terms(users, ["noOa"]);
    assert.equal(filtered_people.size, 2);
    assert(filtered_people.has(noah.user_id));
    assert(filtered_people.has(plain_noah.user_id));

    // This should match ëmerson, but not emerson
    filtered_people = people.filter_people_by_search_terms(users, ["ëm"]);
    assert.equal(filtered_people.size, 1);
    assert(filtered_people.has(noah.user_id));

    // Test filtering with undefined user
    users.push(unknown_user);

    filtered_people = people.filter_people_by_search_terms(users, ["ltorv"]);
    assert.equal(filtered_people.size, 1);
    assert(filtered_people.has(linus.user_id));
});

people.init();

run_test("multi_user_methods", () => {
    people.add_active_user(emp401);
    people.add_active_user(emp402);

    // The order of user_ids is relevant here.
    assert.equal(emp401.user_id, 401);
    assert.equal(emp402.user_id, 402);

    let emails_string = people.user_ids_string_to_emails_string("402,401");
    assert.equal(emails_string, "emp401@example.com,emp402@example.com");

    emails_string = people.slug_to_emails("402,401");
    assert.equal(emails_string, "emp401@example.com,emp402@example.com");

    emails_string = people.slug_to_emails("402,401-group");
    assert.equal(emails_string, "emp401@example.com,emp402@example.com");

    emails_string = "emp402@example.com,EMP401@EXAMPLE.COM";
    let user_ids_string = people.emails_strings_to_user_ids_string(emails_string);
    assert.equal(user_ids_string, "401,402");

    user_ids_string = people.reply_to_to_user_ids_string(emails_string);
    assert.equal(user_ids_string, "401,402");

    const slug = people.emails_to_slug(emails_string);
    assert.equal(slug, "401,402-group");

    assert.equal(people.reply_to_to_user_ids_string("invalid@example.com"), undefined);
});

initialize();

run_test("concat_huddle", () => {
    /*
        We assume that user_ids passed in
        to concat_huddle have already been
        validated, so we don't need actual
        people for these tests to pass.

        That may change in the future.
    */

    const user_ids = [303, 301, 302];

    assert.equal(people.concat_huddle(user_ids, 304), "301,302,303,304");

    // IMPORTANT: we always want to sort
    // ids numerically to create huddle strings.
    assert.equal(people.concat_huddle(user_ids, 99), "99,301,302,303");
});

initialize();

run_test("message_methods", () => {
    people.add_active_user(charles);
    people.add_active_user(maria);
    people.add_active_user(ashton);

    // We don't rely on Maria to have all flags set explicitly--
    // undefined values are just treated as falsy.
    assert.equal(maria.is_guest, undefined);

    assert.equal(
        people.small_avatar_url_for_person(maria),
        "https://secure.gravatar.com/avatar/6dbdd7946b58d8b11351fcb27e5cdd55?d=identicon&s=50",
    );

    assert.deepEqual(people.sender_info_with_small_avatar_urls_for_sender_ids([30]), [
        {
            avatar_url_small: "/avatar/30&s=50",
            email: "me@example.com",
            full_name: "Me the Third",
            is_admin: false,
            is_bot: false,
            is_guest: false,
            profile_data: {
                3: {
                    rendered_value: "<p>Field value</p>",
                    value: "Field value",
                },
            },
            timezone: "America/Los_Angeles",
            user_id: 30,
        },
    ]);

    let message = {
        type: "private",
        display_recipient: [{id: maria.user_id}, {id: me.user_id}, {id: charles.user_id}],
        sender_id: charles.user_id,
    };
    assert.equal(people.pm_with_url(message), "#narrow/pm-with/301,302-group");
    assert.equal(people.pm_perma_link(message), "#narrow/pm-with/30,301,302-group");
    assert.equal(people.pm_reply_to(message), "Athens@example.com,charles@example.com");
    assert.equal(people.small_avatar_url(message), "charles.com/foo.png&s=50");

    message = {
        type: "private",
        display_recipient: [{id: maria.user_id}, {id: me.user_id}],
        avatar_url: "legacy.png",
    };
    assert.equal(people.pm_with_url(message), "#narrow/pm-with/302-athens");
    assert.equal(people.pm_perma_link(message), "#narrow/pm-with/30,302-pm");
    assert.equal(people.pm_reply_to(message), "Athens@example.com");
    assert.equal(people.small_avatar_url(message), "legacy.png&s=50");

    message = {
        avatar_url: undefined,
        sender_id: maria.user_id,
    };
    assert.equal(
        people.small_avatar_url(message),
        "https://secure.gravatar.com/avatar/6dbdd7946b58d8b11351fcb27e5cdd55?d=identicon&s=50",
    );

    blueslip.expect("error", "Unknown user_id in get_by_user_id: 9999999");
    message = {
        avatar_url: undefined,
        sender_email: "foo@example.com",
        sender_id: 9999999,
    };
    assert.equal(
        people.small_avatar_url(message),
        "https://secure.gravatar.com/avatar/b48def645758b95537d4424c84d1a9ff?d=identicon&s=50",
    );

    message = {
        sender_id: ashton.user_id,
    };
    assert.equal(people.small_avatar_url(message), `/avatar/${ashton.user_id}&s=50`);

    message = {
        type: "private",
        display_recipient: [{id: me.user_id}],
    };
    assert.equal(people.pm_with_url(message), "#narrow/pm-with/30-me");
    assert.equal(people.pm_perma_link(message), "#narrow/pm-with/30-pm");

    message = {type: "stream"};
    assert.equal(people.pm_with_user_ids(message), undefined);
    assert.equal(people.all_user_ids_in_pm(message), undefined);

    // Test undefined user_ids
    assert.equal(people.pm_reply_to(message), undefined);
    assert.equal(people.pm_reply_user_string(message), undefined);
    assert.equal(people.pm_with_url(message), undefined);

    // Test sender_is_bot
    const bot = bot_botson;
    people.add_active_user(bot);

    message = {sender_id: bot.user_id};
    assert.equal(people.sender_is_bot(message), true);

    message = {sender_id: maria.user_id};
    assert.equal(people.sender_is_bot(message), undefined);

    message = {sender_id: undefined};
    assert.equal(people.sender_is_bot(message), false);

    // Test sender_is_guest
    people.add_active_user(guest);

    message = {sender_id: guest.user_id};
    assert.equal(people.sender_is_guest(message), true);

    message = {sender_id: maria.user_id};
    assert.equal(people.sender_is_guest(message), undefined);

    message = {sender_id: charles.user_id};
    assert.equal(people.sender_is_guest(message), false);

    message = {sender_id: undefined};
    assert.equal(people.sender_is_guest(message), false);
});

initialize();

run_test("extract_people_from_message", () => {
    let message = {
        type: "stream",
        sender_full_name: maria.full_name,
        sender_id: maria.user_id,
        sender_email: maria.email,
    };
    assert(!people.is_known_user_id(maria.user_id));

    let reported;
    people.__Rewire__("report_late_add", (user_id, email) => {
        assert.equal(user_id, maria.user_id);
        assert.equal(email, maria.email);
        reported = true;
    });

    people.extract_people_from_message(message);
    assert(people.is_known_user_id(maria.user_id));
    assert(reported);

    // Get line coverage
    people.__Rewire__("report_late_add", () => {
        throw new Error("unexpected late add");
    });

    message = {
        type: "private",
        display_recipient: [unknown_user],
    };
    people.extract_people_from_message(message);
});

initialize();

run_test("maybe_incr_recipient_count", () => {
    const maria_recip = {
        id: maria.user_id,
    };
    people.add_active_user(maria);

    let message = {
        type: "private",
        display_recipient: [maria_recip],
        sent_by_me: true,
    };
    assert.equal(people.get_recipient_count(maria), 0);
    people.maybe_incr_recipient_count(message);
    assert.equal(people.get_recipient_count(maria), 1);

    // Test all the no-op conditions to get test
    // coverage.
    message = {
        type: "private",
        sent_by_me: false,
        display_recipient: [maria_recip],
    };
    people.maybe_incr_recipient_count(message);
    assert.equal(people.get_recipient_count(maria), 1);

    const unknown_recip = {
        email: "unknown@example.com",
        id: 500,
        unknown_local_echo_user: true,
    };

    message = {
        type: "private",
        sent_by_me: true,
        display_recipient: [unknown_recip],
    };
    people.maybe_incr_recipient_count(message);
    assert.equal(people.get_recipient_count(maria), 1);

    message = {
        type: "stream",
    };
    people.maybe_incr_recipient_count(message);
    assert.equal(people.get_recipient_count(maria), 1);
});

run_test("slugs", () => {
    people.add_active_user(debbie);

    const slug = people.emails_to_slug(debbie.email);
    assert.equal(slug, "501-debbie71");

    const email = people.slug_to_emails(slug);
    assert.equal(email, "debbie71@example.com");

    // Test undefined slug
    assert.equal(people.emails_to_slug("does@not.exist"), undefined);
});

initialize();

run_test("get_people_for_search_bar", () => {
    message_store.user_ids = () => [];

    for (const i of _.range(20)) {
        const person = {
            email: "whatever@email.com",
            full_name: "James Jones",
            user_id: 1000 + i,
        };
        people.add_active_user(person);
    }

    const big_results = people.get_people_for_search_bar("James");

    assert.equal(big_results.length, 20);

    message_store.user_ids = () => [1001, 1002, 1003, 1004, 1005, 1006];

    const small_results = people.get_people_for_search_bar("Jones");

    // As long as there are 5+ results among the user_ids
    // in message_store, we will get a small result and not
    // search all people.
    assert.equal(small_results.length, 6);
});

initialize();

run_test("updates", () => {
    const old_email = "FOO@example.com";
    const new_email = "bar@example.com";
    const user_id = 502;

    let person = {
        email: old_email,
        user_id,
        full_name: "Foo Barson",
    };
    people.add_active_user(person);

    // Do sanity checks on our data.
    assert.equal(people.get_by_email(old_email).user_id, user_id);
    assert(!people.is_cross_realm_email(old_email));

    assert.equal(people.get_by_email(new_email), undefined);

    // DO THE EMAIL UPDATE HERE.
    people.update_email(user_id, new_email);

    // Now look up using the new email.
    assert.equal(people.get_by_email(new_email).user_id, user_id);
    assert(!people.is_cross_realm_email(new_email));

    const all_people = get_all_persons();
    assert.equal(all_people.length, 2);

    person = all_people.find((p) => p.email === new_email);
    assert.equal(person.full_name, "Foo Barson");

    // Test shim where we can still retrieve user info using the
    // old email.
    blueslip.expect(
        "warn",
        "Obsolete email passed to get_by_email: FOO@example.com new email = bar@example.com",
    );
    person = people.get_by_email(old_email);
    assert.equal(person.user_id, user_id);
});

initialize();

run_test("update_email_in_reply_to", () => {
    people.add_active_user(charles);
    people.add_active_user(maria);

    let reply_to = "    charles@example.com,   athens@example.com";
    assert.equal(people.update_email_in_reply_to(reply_to, 9999, "whatever"), reply_to);
    assert.equal(
        people.update_email_in_reply_to(reply_to, maria.user_id, "maria@example.com"),
        "charles@example.com,maria@example.com",
    );

    reply_to = "    charles@example.com,   athens@example.com, unknown@example.com";
    assert.equal(people.update_email_in_reply_to(reply_to, 9999, "whatever"), reply_to);
});

initialize();

run_test("track_duplicate_full_names", () => {
    people.add_active_user(maria);
    people.add_active_user(stephen1);

    assert(!people.is_duplicate_full_name("Stephen King"));
    assert.equal(people.get_user_id_from_name("Stephen King"), stephen1.user_id);

    // Now duplicate the Stephen King name.
    people.add_active_user({...stephen2});

    // For duplicate names we won't try to guess which
    // user_id the person means; the UI should use
    // other codepaths for disambiguation.
    assert.equal(people.get_user_id_from_name("Stephen King"), undefined);

    assert(people.is_duplicate_full_name("Stephen King"));
    assert(!people.is_duplicate_full_name("Maria Athens"));
    assert(!people.is_duplicate_full_name("Some Random Name"));

    // It is somewhat janky that we have to clone
    // stephen2 here.  It would be nice if people.set_full_name
    // just took a user_id as the first parameter.
    people.set_full_name({...stephen2}, "Stephen King JP");
    assert(!people.is_duplicate_full_name("Stephen King"));
    assert(!people.is_duplicate_full_name("Stephen King JP"));
});

initialize();

run_test("get_mention_syntax", () => {
    people.add_active_user(stephen1);
    people.add_active_user(stephen2);
    people.add_active_user(maria);

    assert(people.is_duplicate_full_name("Stephen King"));

    blueslip.expect("warn", "get_mention_syntax called without user_id.");
    assert.equal(people.get_mention_syntax("Stephen King"), "@**Stephen King**");
    blueslip.reset();

    assert.equal(people.get_mention_syntax("Stephen King", 601), "@**Stephen King|601**");
    assert.equal(people.get_mention_syntax("Stephen King", 602), "@**Stephen King|602**");
    assert.equal(people.get_mention_syntax("Maria Athens", 603), "@**Maria Athens**");
});

run_test("initialize", () => {
    people.init();

    const params = {};

    params.realm_non_active_users = [
        {
            email: "retiree@example.com",
            user_id: 15,
            full_name: "Retiree",
        },
    ];

    params.realm_users = [
        {
            email: "alice@example.com",
            user_id: 16,
            full_name: "Alice",
        },
    ];
    params.cross_realm_bots = [
        {
            email: "bot@example.com",
            user_id: 17,
            full_name: "Test Bot",
        },
    ];

    const my_user_id = 42;
    people.initialize(my_user_id, params);

    assert.equal(people.is_active_user_for_popover(17), true);
    assert(people.is_cross_realm_email("bot@example.com"));
    assert(people.is_valid_email_for_compose("bot@example.com"));
    assert(people.is_valid_email_for_compose("alice@example.com"));
    assert(!people.is_valid_email_for_compose("retiree@example.com"));
    assert(!people.is_valid_email_for_compose("totally-bogus-username@example.com"));
    assert(people.is_valid_bulk_emails_for_compose(["bot@example.com", "alice@example.com"]));
    assert(!people.is_valid_bulk_emails_for_compose(["not@valid.com", "alice@example.com"]));
    assert(people.is_my_user_id(42));

    const fetched_retiree = people.get_by_user_id(15);
    assert.equal(fetched_retiree.full_name, "Retiree");

    assert.equal(page_params.realm_users, undefined);
    assert.equal(page_params.cross_realm_bots, undefined);
    assert.equal(page_params.realm_non_active_users, undefined);
});

run_test("filter_for_user_settings_search", () => {
    /*
        This function calls matches_user_settings_search,
        so that is where we do more thorough testing.
        This test is just a sanity check for now.
    */
    page_params.is_admin = false;

    const fred_smith = {full_name: "Fred Smith"};
    const alice_lee = {full_name: "Alice Lee"};
    const jenny_franklin = {full_name: "Jenny Franklin"};

    const persons = [fred_smith, alice_lee, jenny_franklin];

    assert.deepEqual(people.filter_for_user_settings_search(persons, "fr"), [
        fred_smith,
        jenny_franklin,
    ]);

    assert.deepEqual(people.filter_for_user_settings_search(persons, "le"), [alice_lee]);
});

run_test("matches_user_settings_search", () => {
    const match = people.matches_user_settings_search;

    page_params.is_admin = false;

    assert.equal(match({email: "fred@example.com"}, "fred"), false);
    assert.equal(match({full_name: "Fred Smith"}, "fr"), true);

    page_params.is_admin = true;

    assert.equal(match({delivery_email: "fred@example.com"}, "fr"), true);
    assert.equal(match({delivery_email: "bogus", email: "fred@example.com"}, "fr"), false);

    set_email_visibility(everyone);
    page_params.is_admin = false;
    assert.equal(match({delivery_email: "fred@example.com"}, "fr"), false);
    assert.equal(match({email: "fred@example.com"}, "fr"), true);

    // test normal stuff
    assert.equal(match({email: "fred@example.com"}, "st"), false);
    assert.equal(match({full_name: "Fred Smith"}, "st"), false);
    assert.equal(match({full_name: "Joe Frederick"}, "st"), false);

    assert.equal(match({email: "fred@example.com"}, "fr"), true);
    assert.equal(match({full_name: "Fred Smith"}, "fr"), true);
    assert.equal(match({full_name: "Joe Frederick"}, "fr"), true);

    // test in-string matches...we may want not to be so liberal
    // here about matching, as it's noisy for large realms (who
    // need search the most)
    assert.equal(match({email: "fred@example.com"}, "re"), true);
    assert.equal(match({full_name: "Fred Smith"}, "re"), true);
    assert.equal(match({full_name: "Joe Frederick"}, "re"), true);
});

initialize();

run_test("is_valid_full_name_and_user_id", () => {
    assert(!people.is_valid_full_name_and_user_id("bogus", 99));
    assert(!people.is_valid_full_name_and_user_id(me.full_name, 99));
    assert(people.is_valid_full_name_and_user_id(me.full_name, me.user_id));
});

run_test("emails_strings_to_user_ids_array", () => {
    people.add_active_user(steven);
    people.add_active_user(maria);

    let user_ids = people.emails_strings_to_user_ids_array(`${steven.email},${maria.email}`);
    assert.deepEqual(user_ids, [steven.user_id, maria.user_id]);

    blueslip.expect("warn", "Unknown emails: dummyuser@example.com");
    user_ids = people.emails_strings_to_user_ids_array("dummyuser@example.com");
    assert.equal(user_ids, undefined);
});

run_test("get_visible_email", () => {
    people.add_active_user(steven);
    people.add_active_user(maria);

    let email = people.get_visible_email(steven);
    assert.equal(email, steven.delivery_email);

    email = people.get_visible_email(maria);
    assert.equal(email, maria.email);
});

run_test("get_active_message_people", () => {
    message_store.user_ids = () => [steven.user_id, maria.user_id, alice1.user_id];

    people.add_active_user(steven);
    people.add_active_user(maria);
    people.add_active_user(alice1);

    let active_message_people = people.get_active_message_people();
    assert.deepEqual(active_message_people, [steven, maria, alice1]);

    people.deactivate(alice1);
    active_message_people = people.get_active_message_people();
    assert.deepEqual(active_message_people, [steven, maria]);
});

// reset to native Date()
MockDate.reset();
