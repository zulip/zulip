$(function () {
    function show_realms_only() {
        $(".table").each(function () {
            var table = $(this);

            table.find('tbody tr[data-type="user"]').hide();
            table.find('tbody tr[data-type="realm"]').show();
        });
    }

    function filter_to_realm(realm) {
        $(".table").each(function () {
            var table = $(this);

            table.find("tbody tr").hide();
            var rows = table.find('tbody tr[data-realm="'+realm+'"]');
            rows.show();
        });

    }

    function set_up_realm_links() {
        $("a.realm").on("click", function () {
            var realm = $(this).attr("data-realm");
            filter_to_realm(realm);
        });
    }

    function set_up_summary_link() {
        $("a.show-summary").on("click", function () {
            show_realms_only();
        });
    }

    function set_up_show_all_link() {
        $("a.show-all").on("click", function () {
            $(".table tbody tr").show();
        });
    }

    show_realms_only();
    set_up_realm_links();
    set_up_summary_link();
    set_up_show_all_link();
});
