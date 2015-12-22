var mobile_redirect = (function(){
  var exports = {};

  function show_app_alert(contents) {
    $('#custom-alert-bar-content').html(contents);
    $('#alert-bar-container').show();
    $('#alert-bar-container .close-alert-icon').expectOne().click(hide_app_alert);
  }

  function hide_app_alert() {
      $('#alert-bar-container').slideUp(100);
  }

  exports.try_to_display = function(){
    alert_contents = "<i class='icon-vector-mobile'></i>What's better than " + page_params.product_name + " in your mobile browser? The <a href='/accounts/login/mobile_redirect/' target='_blank'>"+ page_params.product_name + " Mobile app</a>!";
    show_app_alert(alert_contents);
  };

  exports.initialize = function() {
    if (page_params.should_offer_mobile_redirect) {
      exports.try_to_display();
    }
  };
return exports;
}());
