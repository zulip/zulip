var reaction = (function(){

  var exports = {};

  function on_success(){
    console.log('success');
  }

  exports.send_reaction = function(message_id){
    // Make HTTP Ajax request
    channel.post({
      url:      '/json/reactions',
      idempotent: true,
      data:     {'message_id': JSON.stringify(message_id),
                 'emoji': 'simple_smile'},
      success:  on_success
    });
  };

  return exports;
}());
