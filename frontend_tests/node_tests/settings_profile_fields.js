set_global('page_params', {});
set_global('$', global.make_zjquery());
set_global('templates', {});
set_global('loading', {});
set_global('Sortable', {create: () => {}});


const SHORT_TEXT_ID = 1;
const CHOICE_ID = 3;

page_params.custom_profile_fields = {};

page_params.custom_profile_field_types = {
    SHORT_TEXT: {
        id: SHORT_TEXT_ID,
        name: "Short Text",
    },
    CHOICE: {
        id: CHOICE_ID,
        name: "Choice",
    },
};

zrequire('settings_profile_fields');

function test_populate(opts) {
    const fields_data = opts.fields_data;

    page_params.is_admin = opts.is_admin;
    const table = $('#admin_profile_fields_table');
    const rows = $.create('rows');
    const form = $.create('forms');
    table.set_find_results('tr.profile-field-row', rows);
    table.set_find_results('tr.profile-field-form', form);

    var num_appends = 0;
    table.append = () => {
        num_appends += 1;
    };

    loading.destroy_indicator = () => {};

    const template_data = [];
    templates.render = (fn, data) => {
        assert.equal(fn, 'admin_profile_field_list');
        template_data.push(data);
        return 'whatever';
    };

    settings_profile_fields.do_populate_profile_fields(fields_data);

    assert.deepEqual(template_data, opts.expected_template_data);
    assert.equal(num_appends, fields_data.length);
}

run_test('populate_profile_fields', () => {
    const fields_data = [
        {
            type: SHORT_TEXT_ID,
            id: 10,
            name: 'favorite color',
            hint: 'blue?',
            field_data: '',
        },
        {
            type: CHOICE_ID,
            id: 30,
            name: 'meal',
            hint: 'lunch',
            field_data: JSON.stringify([
                {
                    text: 'lunch',
                    order: 0,
                },
                {
                    text: 'dinner',
                    order: 1,
                },
            ]),
        },
    ];
    const expected_template_data = [
        {
            profile_field: {
                id: 10,
                name: 'favorite color',
                hint: 'blue?',
                type: 'Short Text',
                choices: [],
                is_choice_field: false,
            },
            can_modify: true,
        },
        {
            profile_field: {
                id: 30,
                name: 'meal',
                hint: 'lunch',
                type: 'Choice',
                choices: [
                    {order: 0, value: 0, text: 'lunch'},
                    {order: 1, value: 1, text: 'dinner'},
                ],
                is_choice_field: true,
            },
            can_modify: true,
        },
    ];

    test_populate({
        fields_data: fields_data,
        expected_template_data: expected_template_data,
        is_admin: true,
    });
});



