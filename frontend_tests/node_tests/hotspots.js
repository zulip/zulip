const hotspots = require('js/hotspots');

const test_hotspots = [
    {
        delay: 5,
        description: 'Click anywhere on a message to reply.',
        name: 'click_to_reply',
        title: 'Respond to a message',
    },
];

const TEST_HOTSPOT_LOCATIONS = {
    click_to_reply: {
        element: '.selected_message .messagebox-content',
        icon: {
            top: -71,
            left: 284,
        },
        popover: {
            top: -213,
            left: -176,
            arrow: {
                placement: 'bottom',
                top: -5,
                left: -5,
            },
        },
    },
};

(function test_map_hotspot_to_DOM() {
    const test_hotspot = test_hotspots[0];
    assert.equal(test_hotspot.location, undefined);

    hotspots.map_hotspots_to_DOM(test_hotspots, TEST_HOTSPOT_LOCATIONS);

    assert.deepEqual(test_hotspot.location, TEST_HOTSPOT_LOCATIONS[test_hotspot.name]);
}());
