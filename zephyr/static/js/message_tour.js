var message_tour = (function () {
// A "message tour" starts with the first narrow from the home view,
// continues when a user visits several narrows in a row, and ends
// when they return to the home view.  This module helps us track
// where a user has visited during the tour.

// For a message tour, we keep track of messages that get visited
// below our original starting message id.  This helps us with
// pointer positioning, knowing where the user has visited.
// Call start_tour to start the tour.
// Call get_tour to get a list of visited nodes.
// Only after calling get_tour, call finish_tour to finish the tour.

var exports = {};

var ids_visited = [];
var in_tour = false;
var start_msg_id;

exports.visit = function (msg_id) {
	if (!in_tour) {
		return;
	}
	if (msg_id < start_msg_id) {
		return;
	}
	ids_visited.push(msg_id);
};

exports.start_tour = function (msg_id) {
	ids_visited = [];
	start_msg_id = msg_id;
	in_tour = true;
};

exports.finish_tour = function () {
	ids_visited = [];
	in_tour = false;
};

exports.get_tour = function () {
	return ids_visited.slice(0);
};

return exports;
}());
