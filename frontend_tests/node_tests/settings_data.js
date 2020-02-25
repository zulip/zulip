const settings_data = zrequire('settings_data');

set_global('page_params', {});

/*
    Some methods in settings_data are fairly
    trivial, so the meaningful tests happen
    at the high layer, such as when we
    test people.js.
*/

const isaac = {
    email: 'isaac@example.com',
    delivery_email: 'isaac-delivery@example.com',
};

run_test('email_for_user_settings', () => {
    const email = settings_data.email_for_user_settings;

    settings_data.show_email = () => {
        return false;
    };

    assert.equal(email(isaac), undefined);

    settings_data.show_email = () => {
        return true;
    };

    page_params.is_admin = true;
    assert.equal(email(isaac), isaac.delivery_email);

    // Fall back to email if delivery_email is not there.
    assert.equal(
        email({email: 'foo@example.com'}),
        'foo@example.com');

    page_params.is_admin = false;
    assert.equal(email(isaac), isaac.email);
});

