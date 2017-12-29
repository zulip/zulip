zrequire('emoji_conversions');

(function test_convert_emoji() {
    var message = "this is an emoji conversion test. <3";
    var expected_value = "this is an emoji conversion test. :heart:";
    var actual_value = emoji_conversions.convert_emoji(message);
    assert.equal(actual_value, expected_value);

    message = "nothing should be converted.";
    expected_value = "nothing should be converted.";
    actual_value = emoji_conversions.convert_emoji(message);
    assert.equal(actual_value, expected_value);
}());