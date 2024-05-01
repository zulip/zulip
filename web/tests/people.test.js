"use strict";

const {strict: assert} = require("assert");

const {parseISO} = require("date-fns");
const _ = require("lodash");
const MockDate = require("mockdate");

const {$t} = require("./lib/i18n");
const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const {current_user, page_params, realm, user_settings} = require("./lib/zpage_params");

const message_user_ids = mock_esm("../src/message_user_ids");
const settings_data = mock_esm("../src/settings_data", {
    user_can_access_all_other_users: () => true,
});

const muted_users = zrequire("muted_users");
const people = zrequire("people");

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
    is_moderator: false,
    is_bot: false,
    role: 400,
    // no avatar, so client should construct a /avatar/{user_id} URL.
};

const isaac = {
    email: "isaac@example.com",
    delivery_email: "isaac-delivery@example.com",
    user_id: 32,
    full_name: "Isaac Newton",
};

const unknown_user = people.make_user(1500, "unknown@example.com", "Unknown user");

function initialize() {
    people.init();
    people.add_active_user({...me});
    people.initialize_current_user(me.user_id);
    muted_users.set_muted_users([]);

    people._add_user(unknown_user);
}

function test_people(label, f) {
    run_test(label, (helpers) => {
        initialize();
        f(helpers);
    });
}

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
    is_moderator: false,
    is_billing_admin: true,
    is_bot: false,
    role: 200,
};

const guest = {
    email: "guest@example.com",
    full_name: "Guest User",
    user_id: 33,
    is_owner: false,
    is_admin: false,
    is_guest: true,
    is_moderator: false,
    is_billing_admin: false,
    is_bot: false,
    role: 600,
};

const realm_owner = {
    email: "realm_owner@example.com",
    full_name: "Realm Owner",
    user_id: 34,
    is_owner: true,
    is_admin: true,
    is_guest: false,
    is_moderator: false,
    is_billing_admin: false,
    is_bot: false,
    role: 100,
};

const bot_botson = {
    email: "botson-bot@example.com",
    user_id: 35,
    full_name: "Bot Botson",
    is_bot: true,
    bot_owner_id: isaac.user_id,
    role: 300,
};

const moderator = {
    email: "moderator@example.com",
    full_name: "Moderator",
    user_id: 36,
    is_owner: false,
    is_admin: false,
    is_guest: false,
    is_billing_admin: false,
    is_moderator: true,
    is_bot: false,
    role: 300,
};

const bot_with_inaccessible_owner = {
    email: "inaccessible-owner-bot@example.com",
    user_id: 37,
    full_name: "Inaccessible owner bot",
    is_bot: true,
    bot_owner_id: 38,
    role: 300,
};

const steven = {
    email: "steven@example.com",
    delivery_email: "steven-delivery@example.com",
    user_id: 77,
    full_name: "Steven",
};

const alice1 = {
    email: "alice1@example.com",
    delivery_email: "alice1-delivery@example.com",
    user_id: 202,
    full_name: "Alice",
};

const bob = {
    email: "bob@example.com",
    delivery_email: "bob-delivery@example.com",
    user_id: 203,
    full_name: "Bob van Roberts",
};

const charles = {
    email: "charles@example.com",
    user_id: 301,
    full_name: "Charles Dickens",
    avatar_url: "http://charles.com/foo.png",
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

const all1 = {
    email: "all1@example.com",
    user_id: 1202,
    full_name: "all",
};

const all2 = {
    email: "all2@example.com",
    user_id: 1203,
    full_name: "all",
};

const stewie = {
    email: "stewie@example.com",
    user_id: 1204,
    full_name: "Stewart Gilligan",
    profile_data: {
        1: "(888) 888-8888",
        2: "(555) 555-5555",
        3: "he/him",
    },
};

// This is for error checking--never actually
// tell people.js about this user.
const invalid_user = {
    email: "invalid@example.com",
    user_id: 999,
    unknown_local_echo_user: true,
};

function get_all_persons() {
    return people.filter_all_persons(() => true);
}

test_people("basics", ({override}) => {
    const persons = get_all_persons();

    assert.deepEqual(people.get_realm_users(), [me]);

    assert.equal(persons.length, 2);
    assert.equal(persons[0].full_name, "Me Myself");

    let realm_persons = people.get_realm_users();
    assert.equal(realm_persons[0].full_name, "Me Myself");

    realm_persons = people.get_realm_users();
    assert.equal(realm_persons.length, 1);
    assert.equal(people.get_realm_active_human_user_ids().length, 1);

    const full_name = "Isaac Newton";
    const email = "isaac@example.com";

    assert.ok(!people.is_known_user_id(32));
    assert.ok(!people.is_valid_full_name_and_user_id(full_name, 32));
    assert.equal(people.get_user_id_from_name(full_name), undefined);

    people.add_active_user(isaac);

    assert.equal(people.get_actual_name_from_user_id(32), full_name);

    assert.ok(people.is_valid_full_name_and_user_id(full_name, 32));
    assert.ok(people.is_known_user_id(32));
    assert.equal(people.get_active_human_count(), 2);

    assert.equal(people.get_user_id_from_name(full_name), 32);

    let person = people.get_by_email(email);
    assert.equal(person.full_name, full_name);

    realm_persons = people.get_realm_users();
    assert.equal(realm_persons.length, 2);

    const active_user_ids = people.get_active_user_ids().sort();
    assert.deepEqual(active_user_ids, [me.user_id, isaac.user_id]);
    assert.equal(people.is_active_user_for_popover(isaac.user_id), true);
    assert.ok(people.is_valid_email_for_compose(isaac.email));

    let bot_user_ids = people.get_bot_ids();
    assert.equal(bot_user_ids.length, 0);

    // Now deactivate isaac
    people.deactivate(isaac);
    assert.equal(people.get_non_active_human_ids().length, 1);
    assert.equal(people.get_active_human_count(), 1);
    assert.equal(people.is_active_user_for_popover(isaac.user_id), false);
    assert.equal(people.is_valid_email_for_compose(isaac.email), true);

    people.add_active_user(bot_botson);
    assert.equal(people.is_active_user_for_popover(bot_botson.user_id), true);
    bot_user_ids = people.get_bot_ids();
    assert.deepEqual(bot_user_ids, [bot_botson.user_id]);

    assert.equal(people.get_bot_owner_user(bot_botson).full_name, "Isaac Newton");

    assert.equal(people.can_admin_user(me), true);
    assert.equal(people.can_admin_user(bot_botson), false);

    // Add our cross-realm bot.  It won't add to our human
    // count, and it has no owner.
    people.add_cross_realm_user(welcome_bot);
    assert.equal(people.get_bot_owner_user(welcome_bot), undefined);
    assert.equal(people.get_active_human_count(), 1);
    assert.equal(people.get_by_email(welcome_bot.email).full_name, "Welcome Bot");

    override(settings_data, "user_can_access_all_other_users", () => false);
    assert.equal(
        people.get_bot_owner_user(bot_with_inaccessible_owner).full_name,
        "translated: Unknown user",
    );

    // get_realm_users() will include our active bot,
    // but will exclude isaac (who is deactivated)
    assert.deepEqual(
        people
            .get_realm_users()
            .map((u) => u.user_id)
            .sort(),
        [me.user_id, bot_botson.user_id],
    );

    // get_bot_ids() includes all bot users.
    bot_user_ids = people.get_bot_ids();
    assert.deepEqual(bot_user_ids, [bot_botson.user_id, welcome_bot.user_id]);

    // The bot doesn't add to our human count.
    assert.equal(people.get_active_human_count(), 1);

    // Invalid user ID returns false and warns.
    blueslip.expect("warn", "Unexpectedly invalid user_id in user popover query");
    assert.equal(people.is_active_user_for_popover(123412), false);

    // We can still get their info for non-realm needs.
    person = people.get_by_email(email);
    assert.equal(person.email, email);

    // The current user should still be there
    person = people.get_by_email("me@example.com");
    assert.equal(person.full_name, "Me Myself");

    // Test undefined people
    assert.equal(people.is_cross_realm_email("invalid@example.com"), false);

    // Test is_my_user_id function
    assert.equal(people.is_my_user_id(me.user_id), true);
    assert.equal(people.is_my_user_id(isaac.user_id), false);

    // Reactivating issac
    people.add_active_user(isaac);
    const active_humans = people.get_realm_active_human_user_ids();
    assert.equal(active_humans.length, 2);
    assert.deepEqual(
        active_humans.sort((p) => p.user_id),
        [me.user_id, isaac.user_id],
    );

    // get_users_from_ids
    assert.deepEqual(people.get_users_from_ids([me.user_id, isaac.user_id]), [me, isaac]);
});

test_people("sort_but_pin_current_user_on_top with me", () => {
    people.add_active_user(maria);
    people.add_active_user(steven);

    // We need the actual object from people.js, not the
    // "me" object we made a copy of.
    const my_user = people.get_by_user_id(me.user_id);
    const users = [steven, debbie, maria, my_user];

    people.sort_but_pin_current_user_on_top(users);

    assert.deepEqual(users, [my_user, debbie, maria, steven]);
});

test_people("sort_but_pin_current_user_on_top without me", () => {
    people.add_active_user(maria);
    people.add_active_user(steven);

    const users = [steven, maria];

    people.sort_but_pin_current_user_on_top(users);

    assert.deepEqual(users, [maria, steven]);
});

test_people("check_active_non_active_users", () => {
    people.add_active_user(bot_botson);
    people.add_active_user(isaac);

    let active_users = people.get_realm_users();
    let non_active_users = people.get_non_active_realm_users();
    assert.equal(active_users.length, 3);
    assert.equal(non_active_users.length, 0);

    people.add_active_user(maria);
    people.add_active_user(linus);
    active_users = people.get_realm_users();
    assert.equal(active_users.length, 5);
    // Invalid ID
    blueslip.expect("error", "No user found");
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

test_people("pm_lookup_key", () => {
    assert.equal(people.pm_lookup_key("30"), "30");
    assert.equal(people.pm_lookup_key("32,30"), "32");
    assert.equal(people.pm_lookup_key("101,32,30"), "32,101");
});

test_people("get_recipients", () => {
    people.add_active_user(isaac);
    people.add_active_user(linus);
    assert.equal(people.get_recipients("30"), "Me Myself");
    assert.equal(people.get_recipients("30,32"), "Isaac Newton");

    muted_users.add_muted_user(304);
    assert.equal(people.get_recipients("304,32"), "Isaac Newton, translated: Muted user");
});

test_people("get_full_name", () => {
    people.add_active_user(isaac);
    const names = people.get_full_name(isaac.user_id);
    assert.equal(names, "Isaac Newton");
});

test_people("get_full_names_for_poll_option", () => {
    people.add_active_user(isaac);
    const names = people.get_full_names_for_poll_option([me.user_id, isaac.user_id]);
    assert.equal(names, "Me Myself, Isaac Newton");
});

test_people("get_display_full_names", ({override}) => {
    people.initialize_current_user(me.user_id);
    people.add_active_user(steven);
    people.add_active_user(bob);
    people.add_active_user(charles);
    people.add_active_user(guest);
    realm.realm_enable_guest_user_indicator = true;

    let user_ids = [me.user_id, steven.user_id, bob.user_id, charles.user_id, guest.user_id];
    let names = people.get_display_full_names(user_ids);

    // This doesn't do anything special for the current user. The caller has
    // to take care of such cases and do the appropriate.
    assert.deepEqual(names, [
        "Me Myself",
        "Steven",
        "Bob van Roberts",
        "Charles Dickens",
        "translated: Guest User (guest)",
    ]);

    muted_users.add_muted_user(charles.user_id);
    realm.realm_enable_guest_user_indicator = false;
    names = people.get_display_full_names(user_ids);
    assert.deepEqual(names, [
        "Me Myself",
        "Steven",
        "Bob van Roberts",
        "translated: Muted user",
        "Guest User",
    ]);

    muted_users.add_muted_user(guest.user_id);
    names = people.get_display_full_names(user_ids);
    assert.deepEqual(names, [
        "Me Myself",
        "Steven",
        "Bob van Roberts",
        "translated: Muted user",
        "translated: Muted user",
    ]);

    realm.realm_enable_guest_user_indicator = true;
    names = people.get_display_full_names(user_ids);
    assert.deepEqual(names, [
        "Me Myself",
        "Steven",
        "Bob van Roberts",
        "translated: Muted user",
        "translated: Muted user (guest)",
    ]);

    override(settings_data, "user_can_access_all_other_users", () => false);
    const inaccessible_user_id = 99;
    user_ids = [me.user_id, steven.user_id, inaccessible_user_id];
    names = people.get_display_full_names(user_ids, true);
    assert.deepEqual(names, ["Me Myself", "Steven", "translated: Unknown user"]);
});

test_people("my_custom_profile_data", () => {
    const person = people.get_by_email(me.email);
    person.profile_data = {3: "My address", 4: "My phone number"};
    assert.equal(people.my_custom_profile_data(3), "My address");
    assert.equal(people.my_custom_profile_data(4), "My phone number");
});

test_people("get_custom_fields_by_type", () => {
    people.add_active_user(stewie);
    const person = people.get_by_user_id(stewie.user_id);
    realm.custom_profile_field_types = {
        SHORT_TEXT: {
            id: 1,
            name: "Short text",
        },
        PRONOUNS: {
            id: 8,
            name: "Pronouns",
        },
    };
    realm.custom_profile_fields = [
        {
            id: 1,
            name: "Phone number (mobile)",
            type: 1,
        },
        {
            id: 2,
            name: "Phone number (office)",
            type: 1,
        },
        {
            id: 3,
            name: "Pronouns",
            type: 8,
        },
    ];
    const SHORT_TEXT_ID = 1;
    assert.deepEqual(people.get_custom_fields_by_type(person.user_id, SHORT_TEXT_ID), [
        "(888) 888-8888",
        "(555) 555-5555",
    ]);
    assert.deepEqual(people.get_custom_fields_by_type(person.user_id, 8), ["he/him"]);
    assert.deepEqual(people.get_custom_fields_by_type(person.user_id, 100), []);
});

test_people("bot_custom_profile_data", () => {
    // If this test fails, then try opening organization settings > bots
    // http://localhost:9991/#organization/bot-list-admin
    // and then try to edit any of the bots.
    people.add_active_user(bot_botson);
    assert.equal(people.get_custom_profile_data(bot_botson.user_id, 3), null);
});

test_people("user_timezone", () => {
    MockDate.set(parseISO("20130208T080910").getTime());

    user_settings.twenty_four_hour_time = true;
    assert.equal(people.get_user_time(me.user_id), "00:09");

    user_settings.twenty_four_hour_time = false;
    assert.equal(people.get_user_time(me.user_id), "12:09 AM");
});

test_people("utcToZonedTime", ({override}) => {
    MockDate.set(parseISO("20130208T080910").getTime());
    user_settings.twenty_four_hour_time = true;

    assert.deepEqual(people.get_user_time(unknown_user.user_id), undefined);
    assert.equal(people.get_user_time(me.user_id), "00:09");

    override(people.get_by_user_id(me.user_id), "timezone", "Eriador/Rivendell");
    blueslip.expect(
        "warn",
        "Error formatting time in Eriador/Rivendell: RangeError: Invalid time zone specified: Eriador/Rivendell",
    );
    people.get_user_time(me.user_id);
});

test_people("user_type", () => {
    people.init();

    people.add_active_user(me);
    people.add_active_user(realm_admin);
    people.add_active_user(guest);
    people.add_active_user(realm_owner);
    people.add_active_user(moderator);
    people.add_active_user(bot_botson);
    assert.equal(people.get_user_type(me.user_id), $t({defaultMessage: "Member"}));
    assert.equal(people.get_user_type(realm_admin.user_id), $t({defaultMessage: "Administrator"}));
    assert.equal(people.get_user_type(guest.user_id), $t({defaultMessage: "Guest"}));
    assert.equal(people.get_user_type(realm_owner.user_id), $t({defaultMessage: "Owner"}));
    assert.equal(people.get_user_type(moderator.user_id), $t({defaultMessage: "Moderator"}));
    assert.equal(people.get_user_type(bot_botson.user_id), $t({defaultMessage: "Moderator"}));
});

test_people("updates", () => {
    const person = people.get_by_email("me@example.com");
    people.set_full_name(person, "Me the Third");
    assert.equal(people.my_full_name(), "Me the Third");
    assert.equal(person.full_name, "Me the Third");
    assert.equal(people.get_user_id_from_name("Me the Third"), me.user_id);
});

test_people("get_by_user_id", () => {
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

test_people("set_custom_profile_field_data", () => {
    const person = people.get_by_email(me.email);
    person.profile_data = {};
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

test_people("is_current_user_only_owner", () => {
    const person = people.get_by_email(me.email);
    person.is_owner = false;
    current_user.is_owner = false;
    assert.ok(!people.is_current_user_only_owner());

    person.is_owner = true;
    current_user.is_owner = true;
    assert.ok(people.is_current_user_only_owner());

    people.add_active_user(realm_owner);
    assert.ok(!people.is_current_user_only_owner());
});

test_people("recipient_counts", () => {
    const user_id = 99;
    assert.equal(people.get_recipient_count({user_id}), 0);
    people.incr_recipient_count(user_id);
    people.incr_recipient_count(user_id);
    assert.equal(people.get_recipient_count({user_id}), 2);

    assert.equal(people.get_recipient_count({pm_recipient_count: 5}), 5);
});

test_people("filtered_users", () => {
    people.add_active_user(charles);
    people.add_active_user(maria);
    people.add_active_user(ashton);
    people.add_active_user(linus);
    people.add_active_user(noah);
    people.add_active_user(plain_noah);

    const search_term = "a";
    const users = people.get_realm_users();
    let filtered_people = people.filter_people_by_search_terms(users, [search_term]);
    assert.equal(filtered_people.size, 2);
    assert.ok(filtered_people.has(ashton.user_id));
    assert.ok(filtered_people.has(maria.user_id));
    assert.ok(!filtered_people.has(charles.user_id));

    filtered_people = people.filter_people_by_search_terms(users, []);
    assert.equal(filtered_people.size, 0);

    filtered_people = people.filter_people_by_search_terms(users, ["ltorv"]);
    assert.equal(filtered_people.size, 1);
    assert.ok(filtered_people.has(linus.user_id));

    filtered_people = people.filter_people_by_search_terms(users, ["ch di", "maria"]);
    assert.equal(filtered_people.size, 2);
    assert.ok(filtered_people.has(charles.user_id));
    assert.ok(filtered_people.has(maria.user_id));

    // Test filtering of names with diacritics
    // This should match Nöôáàh by ignoring diacritics, and also match Nooaah
    filtered_people = people.filter_people_by_search_terms(users, ["noOa"]);
    assert.equal(filtered_people.size, 2);
    assert.ok(filtered_people.has(noah.user_id));
    assert.ok(filtered_people.has(plain_noah.user_id));

    // This should match ëmerson, but not emerson
    filtered_people = people.filter_people_by_search_terms(users, ["ëm"]);
    assert.equal(filtered_people.size, 1);
    assert.ok(filtered_people.has(noah.user_id));
});

test_people("multi_user_methods", () => {
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

test_people("emails_to_full_names_string", () => {
    people.add_active_user(charles);
    people.add_active_user(maria);
    assert.equal(
        people.emails_to_full_names_string([charles.email, maria.email]),
        `${charles.full_name}, ${maria.full_name}`,
    );

    assert.equal(
        people.emails_to_full_names_string([
            charles.email,
            "unknown-email@example.com",
            maria.email,
        ]),
        `${charles.full_name}, translated: Unknown user, ${maria.full_name}`,
    );
});

test_people("concat_huddle", () => {
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

test_people("message_methods", () => {
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
    assert.equal(
        people.medium_avatar_url_for_person(maria),
        "https://secure.gravatar.com/avatar/6dbdd7946b58d8b11351fcb27e5cdd55?d=identicon&s=500",
    );
    assert.equal(people.medium_avatar_url_for_person(charles), "/avatar/301/medium?version=0");
    assert.equal(people.medium_avatar_url_for_person(ashton), "/avatar/303/medium?version=0");

    muted_users.add_muted_user(30);
    assert.deepEqual(people.sender_info_for_recent_view_row([30]), [
        {
            avatar_url_small: "http://zulip.zulipdev.com/avatar/30?s=50",
            is_muted: true,
            email: "me@example.com",
            full_name: me.full_name,
            is_admin: false,
            is_bot: false,
            is_guest: false,
            is_moderator: false,
            role: 400,
            timezone: "America/Los_Angeles",
            user_id: 30,
        },
    ]);

    let message = {
        type: "private",
        display_recipient: [{id: maria.user_id}, {id: me.user_id}, {id: charles.user_id}],
        sender_id: charles.user_id,
    };
    assert.equal(people.pm_with_url(message), "#narrow/dm/301,302-group");
    assert.equal(people.pm_perma_link(message), "#narrow/dm/30,301,302-group");
    assert.equal(people.pm_reply_to(message), "Athens@example.com,charles@example.com");
    assert.equal(people.small_avatar_url(message), "http://charles.com/foo.png?s=50");

    message = {
        type: "private",
        display_recipient: [{id: maria.user_id}, {id: me.user_id}],
        avatar_url: "legacy.png",
    };
    assert.equal(people.pm_with_url(message), "#narrow/dm/302-Maria-Athens");
    assert.equal(people.pm_perma_link(message), "#narrow/dm/30,302-dm");
    assert.equal(people.pm_reply_to(message), "Athens@example.com");
    assert.equal(people.small_avatar_url(message), "http://zulip.zulipdev.com/legacy.png?s=50");

    message = {
        avatar_url: undefined,
        sender_id: maria.user_id,
    };
    assert.equal(
        people.small_avatar_url(message),
        "https://secure.gravatar.com/avatar/6dbdd7946b58d8b11351fcb27e5cdd55?d=identicon&s=50",
    );

    blueslip.expect("error", "Unknown user_id in maybe_get_user_by_id");
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
    assert.equal(
        people.small_avatar_url(message),
        `http://zulip.zulipdev.com/avatar/${ashton.user_id}?s=50`,
    );

    message = {
        type: "private",
        display_recipient: [{id: me.user_id}],
    };
    assert.equal(people.pm_with_url(message), "#narrow/dm/30-Me-Myself");
    assert.equal(people.pm_perma_link(message), "#narrow/dm/30-dm");

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

test_people("extract_people_from_message", () => {
    let message = {
        type: "stream",
        sender_full_name: maria.full_name,
        sender_id: maria.user_id,
        sender_email: maria.email,
    };
    assert.ok(!people.is_known_user_id(maria.user_id));

    blueslip.expect("error", "Added user late");
    people.extract_people_from_message(message);
    assert.ok(people.is_known_user_id(maria.user_id));
    blueslip.reset();

    // Get line coverage
    message = {
        type: "private",
        display_recipient: [invalid_user],
    };
    people.extract_people_from_message(message);
});

test_people("maybe_incr_recipient_count", () => {
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

    const other_invalid_recip = {
        email: "invalid2@example.com",
        id: 500,
        unknown_local_echo_user: true,
    };

    message = {
        type: "private",
        sent_by_me: true,
        display_recipient: [other_invalid_recip],
    };
    people.maybe_incr_recipient_count(message);
    assert.equal(people.get_recipient_count(maria), 1);

    message = {
        type: "stream",
    };
    people.maybe_incr_recipient_count(message);
    assert.equal(people.get_recipient_count(maria), 1);
});

test_people("slugs", () => {
    people.add_active_user(debbie);

    const slug = people.emails_to_slug(debbie.email);
    assert.equal(slug, "501-Debra-Henton");

    const email = people.slug_to_emails(slug);
    assert.equal(email, "debbie71@example.com");

    // Test undefined slug
    assert.equal(people.emails_to_slug("does@not.exist"), undefined);
});

test_people("get_people_for_search_bar", ({override}) => {
    let user_ids;

    override(message_user_ids, "user_ids", () => user_ids);

    for (const i of _.range(20)) {
        const person = {
            email: "whatever@email.com",
            full_name: "James Jones",
            user_id: 1000 + i,
        };
        people.add_active_user(person);
    }

    user_ids = [];
    const big_results = people.get_people_for_search_bar("James");

    assert.equal(big_results.length, 20);

    user_ids = [1001, 1002, 1003, 1004, 1005, 1006];
    const small_results = people.get_people_for_search_bar("Jones");

    // As long as there are 5+ results among the user_ids
    // in message_user_ids, we will get a small result and not
    // search all people.
    assert.equal(small_results.length, 6);
});

test_people("updates", () => {
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
    assert.ok(!people.is_cross_realm_email(old_email));

    assert.equal(people.get_by_email(new_email), undefined);

    // DO THE EMAIL UPDATE HERE.
    people.update_email(user_id, new_email);

    // Now look up using the new email.
    assert.equal(people.get_by_email(new_email).user_id, user_id);
    assert.ok(!people.is_cross_realm_email(new_email));

    const all_people = get_all_persons();
    assert.equal(all_people.length, 3);

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

test_people("update_email_in_reply_to", () => {
    people.add_active_user(charles);
    people.add_active_user(maria);

    let reply_to = "    charles@example.com,   athens@example.com";
    assert.equal(people.update_email_in_reply_to(reply_to, 9999, "whatever"), reply_to);
    assert.equal(
        people.update_email_in_reply_to(reply_to, maria.user_id, "maria@example.com"),
        "charles@example.com,maria@example.com",
    );

    reply_to = "    charles@example.com,   athens@example.com, invalid@example.com";
    assert.equal(people.update_email_in_reply_to(reply_to, 9999, "whatever"), reply_to);
});

test_people("track_duplicate_full_names", () => {
    people.add_active_user(maria);
    people.add_active_user(stephen1);

    assert.ok(!people.is_duplicate_full_name("Stephen King"));
    assert.equal(people.get_user_id_from_name("Stephen King"), stephen1.user_id);

    // Now duplicate the Stephen King name.
    people.add_active_user({...stephen2});

    // For duplicate names we won't try to guess which
    // user_id the person means; the UI should use
    // other codepaths for disambiguation.
    assert.equal(people.get_user_id_from_name("Stephen King"), undefined);

    assert.ok(people.is_duplicate_full_name("Stephen King"));
    assert.ok(!people.is_duplicate_full_name("Maria Athens"));
    assert.ok(!people.is_duplicate_full_name("Some Random Name"));

    // It is somewhat janky that we have to clone
    // stephen2 here.  It would be nice if people.set_full_name
    // just took a user_id as the first parameter.
    people.set_full_name({...stephen2}, "Stephen King JP");
    assert.ok(!people.is_duplicate_full_name("Stephen King"));
    assert.ok(!people.is_duplicate_full_name("Stephen King JP"));
});

test_people("get_mention_syntax", () => {
    // blueslip warning is not raised for wildcard mentions without a user_id
    assert.equal(people.get_mention_syntax("all"), "@**all**");
    assert.equal(people.get_mention_syntax("everyone", undefined, true), "@_**everyone**");
    assert.equal(people.get_mention_syntax("stream"), "@**channel**");
    assert.equal(people.get_mention_syntax("channel"), "@**channel**");
    assert.equal(people.get_mention_syntax("topic"), "@**topic**");

    people.add_active_user(stephen1);
    people.add_active_user(stephen2);
    people.add_active_user(maria);

    assert.ok(people.is_duplicate_full_name("Stephen King"));

    blueslip.expect("warn", "get_mention_syntax called without user_id.");
    assert.equal(people.get_mention_syntax("Stephen King"), "@**Stephen King**");
    blueslip.reset();

    assert.equal(people.get_mention_syntax("Stephen King", 601), "@**Stephen King|601**");
    assert.equal(people.get_mention_syntax("Stephen King", 602, true), "@_**Stephen King|602**");
    assert.equal(people.get_mention_syntax("Maria Athens", 603), "@**Maria Athens**");

    // Following tests handle a special case when `full_name` matches with a wildcard.
    //
    // At this point, there is no duplicate full name, `all`, so we should still get
    // mention syntax with `user_id` appended to it.
    people.add_active_user(all1);
    assert.equal(people.get_mention_syntax("all", 1202), "@**all|1202**");

    people.add_active_user(all2);
    assert.ok(people.is_duplicate_full_name("all"));
    assert.equal(people.get_mention_syntax("all", 1203, true), "@_**all|1203**");
});

test_people("initialize", () => {
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
    assert.ok(people.is_cross_realm_email("bot@example.com"));
    assert.ok(people.is_valid_email_for_compose("bot@example.com"));
    assert.ok(people.is_valid_email_for_compose("alice@example.com"));
    assert.ok(people.is_valid_email_for_compose("retiree@example.com"));
    assert.ok(!people.is_valid_email_for_compose("totally-bogus-username@example.com"));
    assert.ok(people.is_valid_bulk_emails_for_compose(["bot@example.com", "alice@example.com"]));
    assert.ok(!people.is_valid_bulk_emails_for_compose(["not@valid.com", "alice@example.com"]));
    assert.ok(people.is_my_user_id(42));

    const fetched_retiree = people.get_by_user_id(15);
    assert.equal(fetched_retiree.full_name, "Retiree");

    assert.equal(page_params.realm_users, undefined);
    assert.equal(page_params.cross_realm_bots, undefined);
    assert.equal(page_params.realm_non_active_users, undefined);
});

test_people("predicate_for_user_settings_filters", () => {
    /*
        This function calls matches_user_settings_search,
        so that is where we do more thorough testing.
        This test is just a sanity check for now.
    */
    current_user.is_admin = false;

    const fred_smith = {full_name: "Fred Smith", role: 100};

    // Test only when text_search filter is true
    assert.equal(
        people.predicate_for_user_settings_filters(fred_smith, {text_search: "fr", role_code: 0}),
        true,
    );
    // Test only when role_code filter is true
    assert.equal(
        people.predicate_for_user_settings_filters(fred_smith, {text_search: "", role_code: 100}),
        true,
    );
    // Test only when text_search filter is false
    assert.equal(
        people.predicate_for_user_settings_filters(fred_smith, {text_search: "ab", role_code: 0}),
        false,
    );
    // Test only when role_code filter is false
    assert.equal(
        people.predicate_for_user_settings_filters(fred_smith, {text_search: "", role_code: 200}),
        false,
    );
    // Test when both text_search and role_code filter are true
    assert.equal(
        people.predicate_for_user_settings_filters(fred_smith, {
            text_search: "smi",
            role_code: 100,
        }),
        true,
    );
    // Test when both text_search and role_code filter are false
    assert.equal(
        people.predicate_for_user_settings_filters(fred_smith, {text_search: "de", role_code: 300}),
        false,
    );
});

test_people("matches_user_settings_search", () => {
    const match = people.matches_user_settings_search;

    current_user.is_admin = false;

    assert.equal(match({email: "fred@example.com"}, "fred"), false);
    assert.equal(match({full_name: "Fred Smith"}, "fr"), true);

    current_user.is_admin = true;

    assert.equal(match({delivery_email: "fred@example.com"}, "fr"), true);
    assert.equal(
        match(
            {
                delivery_email: "bogus",
                email: "fred@example.com",
            },
            "fr",
        ),
        false,
    );

    assert.equal(match({delivery_email: "fred@example.com"}, "fr"), true);
    assert.equal(match({email: "fred@example.com"}, "fr"), false);

    // test normal stuff
    assert.equal(match({email: "fred@example.com"}, "st"), false);
    assert.equal(match({full_name: "Fred Smith"}, "st"), false);
    assert.equal(match({full_name: "Joe Frederick"}, "st"), false);

    assert.equal(match({delivery_email: "fred@example.com"}, "fr"), true);
    assert.equal(match({full_name: "Fred Smith"}, "fr"), true);
    assert.equal(match({full_name: "Joe Frederick"}, "fr"), true);

    // test in-string matches...we may want not to be so liberal
    // here about matching, as it's noisy for large realms (who
    // need search the most)
    assert.equal(match({delivery_email: "fred@example.com"}, "re"), true);
    assert.equal(match({full_name: "Fred Smith"}, "re"), true);
    assert.equal(match({full_name: "Joe Frederick"}, "re"), true);
});

test_people("is_valid_full_name_and_user_id", () => {
    assert.ok(!people.is_valid_full_name_and_user_id("bogus", 99));
    assert.ok(!people.is_valid_full_name_and_user_id(me.full_name, 99));
    assert.ok(people.is_valid_full_name_and_user_id(me.full_name, me.user_id));
});

test_people("emails_strings_to_user_ids_array", () => {
    people.add_active_user(steven);
    people.add_active_user(maria);

    let user_ids = people.emails_strings_to_user_ids_array(`${steven.email},${maria.email}`);
    assert.deepEqual(user_ids, [steven.user_id, maria.user_id]);

    blueslip.expect("warn", "Unknown emails");
    user_ids = people.emails_strings_to_user_ids_array("dummyuser@example.com");
    assert.equal(user_ids, undefined);
});

test_people("get_visible_email", () => {
    people.add_active_user(steven);
    people.add_active_user(maria);

    let email = people.get_visible_email(steven);
    assert.equal(email, steven.delivery_email);

    email = people.get_visible_email(maria);
    assert.equal(email, maria.email);
});

test_people("get_active_message_people", () => {
    message_user_ids.user_ids = () => [steven.user_id, maria.user_id, alice1.user_id];

    people.add_active_user(steven);
    people.add_active_user(maria);
    people.add_active_user(alice1);

    let active_message_people = people.get_active_message_people();
    assert.deepEqual(active_message_people, [steven, maria, alice1]);

    people.deactivate(alice1);
    active_message_people = people.get_active_message_people();
    assert.deepEqual(active_message_people, [steven, maria]);
});

test_people("huddle_string", () => {
    assert.equal(people.huddle_string({type: "stream"}), undefined);

    function huddle(user_ids) {
        return people.huddle_string({
            type: "private",
            display_recipient: user_ids.map((id) => ({id})),
        });
    }

    people.add_active_user(maria);
    people.add_active_user(bob);

    assert.equal(huddle([]), undefined);
    assert.equal(huddle([me.user_id, maria.user_id]), undefined);
    assert.equal(huddle([me.user_id, maria.user_id, bob.user_id]), "203,302");
});

test_people("get_realm_active_human_users", () => {
    let humans = people.get_realm_active_human_users();
    assert.equal(humans.length, 1);
    assert.deepEqual(humans, [me]);

    people.add_active_user(maria);
    people.add_active_user(bot_botson);
    humans = people.get_realm_active_human_users();
    assert.equal(humans.length, 2);
    assert.deepEqual(humans, [me, maria]);

    people.deactivate(maria);
    humans = people.get_realm_active_human_users();
    assert.equal(humans.length, 1);
    assert.deepEqual(humans, [me]);
});

test_people("should_show_guest_user_indicator", () => {
    people.add_active_user(charles);
    people.add_active_user(guest);

    realm.realm_enable_guest_user_indicator = false;
    assert.equal(people.should_add_guest_user_indicator(charles.user_id), false);
    assert.equal(people.should_add_guest_user_indicator(guest.user_id), false);

    realm.realm_enable_guest_user_indicator = true;
    assert.equal(people.should_add_guest_user_indicator(charles.user_id), false);
    assert.equal(people.should_add_guest_user_indicator(guest.user_id), true);
});

test_people("get_user_by_id_assert_valid", ({override}) => {
    people.add_active_user(charles);
    const inaccessible_user_id = 99;
    realm.realm_bot_domain = "zulipdev.com";
    override(settings_data, "user_can_access_all_other_users", () => false);

    let user = people.get_user_by_id_assert_valid(inaccessible_user_id);
    assert.equal(user.full_name, "translated: Unknown user");
    assert.equal(user.user_id, inaccessible_user_id);
    assert.ok(user.is_inaccessible_user);
    assert.equal(user.email, "user99@zulipdev.com");

    user = people.get_user_by_id_assert_valid(charles.user_id);
    assert.equal(user.full_name, charles.full_name);
    assert.ok(!user.is_inaccessible_user);
    assert.equal(user.email, charles.email);

    override(settings_data, "user_can_access_all_other_users", () => true);

    assert.throws(
        () => {
            people.get_user_by_id_assert_valid(199);
        },
        {
            name: "Error",
            message: "Unknown user_id in get_by_user_id: 199",
        },
    );

    user = people.get_user_by_id_assert_valid(charles.user_id);
    assert.equal(user.full_name, charles.full_name);
    assert.ok(!user.is_inaccessible_user);
    assert.equal(user.email, charles.email);
});

// reset to native Date()
run_test("reset MockDate", () => {
    MockDate.reset();
});
