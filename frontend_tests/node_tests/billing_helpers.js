set_global('$', global.make_zjquery());
set_global('page_params', {});

zrequire('helpers', "js/billing/helpers");

run_test("is_in_array", () => {
    var good_houses_array = ["Gryffindor", "Hufflepuff", "Ravenclaw"];
    assert.equal(helpers.is_in_array("Hufflepuff", good_houses_array), true);
    assert.equal(helpers.is_in_array("Slytherin", good_houses_array), false);
});
