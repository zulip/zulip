const assert = require('assert');

function split_array(_array, size) {
    // duplicate the array otherwise, by calling
    // [].splice will change the original array passed in!
    const array = [].concat(..._array);

    const { length } = array;
    const arrays = [];
    const split_length = Math.floor(length / size);

    while (array.length) {
        arrays.push(array.splice(0, split_length));
    }

    // at this point if we are lucky and got a event number
    // we are all good otherwise we need to distrubute a extra
    // array left.
    if (size === arrays.length) {
        return arrays;
    }

    const extra_array = arrays.splice(size, 1)[0];
    extra_array.forEach((item, index) => {
        arrays[index].push(item);
    });

    return arrays;
}

(function test_split_array() {
    function generate_array(size) {
        const array = [];
        for (let i = 0; i < size; i++) {
            array.push(i);
        }
        return array;
    }

    let array = generate_array(14);
    let distributed_array = split_array(array, 3);
    assert.deepEqual(distributed_array, [
        [ 0, 1, 2, 3, 12 ],
        [ 4, 5, 6, 7, 13 ],
        [ 8, 9, 10, 11 ]
    ]);

    array = generate_array(6);
    distributed_array = split_array(array, 2);
    assert.deepEqual(distributed_array, [
        [ 0, 1, 2 ],
        [ 3, 4, 5 ]
    ]);
})();

module.exports = {
    split_array
};
