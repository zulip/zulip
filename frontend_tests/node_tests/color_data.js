zrequire('color_data');

run_test('pick_color', () => {
    color_data.colors = [
        'blue',
        'orange',
        'red',
        'yellow',
    ];

    color_data.reset();

    color_data.claim_colors([
        { color: 'orange' },
        { foo: 'whatever' },
        { color: 'yellow' },
        { color: 'bogus' },
    ]);

    var expected_colors = [
        'blue',
        'red',
        // ok, now we'll cycle through all colors
        'blue',
        'orange',
        'red',
        'yellow',
        'blue',
        'orange',
        'red',
        'yellow',
        'blue',
        'orange',
        'red',
        'yellow',
    ];

    _.each(expected_colors, (expected_color) => {
        assert.equal(color_data.pick_color(), expected_color);
    });

    color_data.claim_color('blue');
    assert.equal(color_data.pick_color(), 'orange');
});
