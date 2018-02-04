global.stub_out_jquery();

zrequire('stream_color');

(function test_pick_color() {
    var used_colors = ["#76ce90", "#fae589"];

    // Colors are assigned randomly, so this test is a little vague and brittle,
    // but we can verify a few things, like not reusing colors and making sure
    // the color has length 7.
    var color = stream_color.pick_color(used_colors);
    assert.notEqual(color, "#76ce90");
    assert.notEqual(color, "#fae589");
    assert.equal(color.length, 7);
}());
