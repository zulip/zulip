import $ from "jquery";
$(() => {
    $("body").on("click", ".reveal_hidden_event",  function (e){
        console.log("YASSSSSSSs")
        const event_id = (e.currentTarget.id)
        console.log(event_id)
        $(this).toggleClass("expand");
        $("#"+event_id+".event-content").slideToggle(250);
        // if ( $div.height() > 0 ) {
        //     $div.animate({ height: 0 }, { duration: 5000 }).css('overflow', 'hidden');
        // } else {
        //     $div.animate({ height : height }, { duration: 5000 });
        // }
    });
});