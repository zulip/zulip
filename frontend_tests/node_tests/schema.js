zrequire('schema');

run_test('basics', () => {
    assert.equal(schema.check_string('x', 'fred'), undefined);
    assert.equal(schema.check_string('x', [1, 2]), 'x is not a string');

    const fields = {
        foo: schema.check_string,
        bar: schema.check_string,
    };

    const check_rec = (val) => {
        return schema.check_record('my_rec', val, fields);
    };

    assert.equal(
        check_rec({foo: 'apple', bar: 'banana'}),
        undefined
    );

    assert.equal(
        check_rec('bogus'),
        'my_rec is not a record'
    );

    assert.equal(
        check_rec({foo: 'apple'}),
        'in my_rec bar is missing'
    );

    assert.equal(
        check_rec({}),
        'in my_rec bar is missing, foo is missing'
    );

    assert.equal(
        check_rec({foo: 'apple', bar: 42}),
        'in my_rec bar is not a string'
    );

    const check_array = (val) => {
        return schema.check_array('lst', val, schema.check_string);
    };

    assert.equal(
        check_array(['foo', 'bar']),
        undefined
    );

    assert.equal(
        check_array('foo'),
        'lst is not an array'
    );

    assert.equal(
        check_array(['foo', 3]),
        'in lst we found an item where item is not a string'
    );
});
