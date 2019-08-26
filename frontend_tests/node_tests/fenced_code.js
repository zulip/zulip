zrequire('fenced_code');

run_test('get_unused_fence', () => {
    assert.equal(fenced_code.get_unused_fence('```js\nsomething\n```'), '`'.repeat(4));
    assert.equal(fenced_code.get_unused_fence('````\nsomething\n````'), '`'.repeat(5));
    assert.equal(fenced_code.get_unused_fence('```\n````\n``````'), '`'.repeat(7));
    assert.equal(fenced_code.get_unused_fence('~~~\nsomething\n~~~'), '`'.repeat(3));
    assert.equal(fenced_code.get_unused_fence('```code\nterminating fence is indented and longer\n   ````'), '`'.repeat(5));
    assert.equal(fenced_code.get_unused_fence('```code\nterminating fence is extra indented\n    ````'), '`'.repeat(4));
    let large_testcase = '';
    // ```
    // ````
    // `````
    // ... upto 500 chars
    // We insert a 501 character fence.
    for (let i = 3; i <= 500; i += 1) {
        large_testcase += '`'.repeat(i) + '\n';
    }
    assert.equal(fenced_code.get_unused_fence(large_testcase), '`'.repeat(501));
});
