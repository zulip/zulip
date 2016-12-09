var reaction = (function () {

  var exports = {};
  // Reaction
  function update_reaction(message_id) {
    // Update the message object pointed to by the various message
    // lists.
    var message = ui.find_message(message_id);
    var reaction_name = "simple_smile";
    unread.mark_message_as_read(message);
    ui.update_reaction(message.id, reaction_name);
    reaction.send_reaction(message.id, reaction_name);
  }

  function on_success() {
    console.log('success');
  }

  exports.send_reaction = function (message_id) {
    // Make HTTP Ajax request
    channel.post({
      url: '/json/reactions',
      idempotent: true,
      data: {
        'message_id': JSON.stringify(message_id),
        'emoji': 'simple_smile'
      },
      success: on_success
    });
  };

  return exports;
} ());