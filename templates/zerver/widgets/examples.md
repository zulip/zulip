These docs are for our ** beta version ** of
composable message widgets.

<div class="widget_examples">
</div>

<style>
    .code {
        width: 80%;
    };
</style>
<script>
    var examples = [
        {
            data: {
                "type": "choices",
                "heading": "What is the capitol of Maryland?",
                "choices": [
                    {
                        "type": "multiple_choice",
                        "shortcut": "A",
                        "answer": "Annapolis",
                        "reply": "answer q123456 A"
                    },
                    {
                        "type": "multiple_choice",
                        "shortcut": "B",
                        "answer": "Baltimore",
                        "reply": "answer q123456 B"
                    }
                ],
            },
        },
		{
			data: {
				"type": "choices",
				"choices": [
					{
						"tokens": [
							{
								"name": "help"
							}
						]
					},
					{
						"tokens": [
							{
								"name": "hello"
							},
							{
								"type": "input",
								"field": "name"
							},
							{
								"name": "how are you doing?"
							}
						]
					}
				]
			}
		},
    ];

    function add_example(opts) {
        var data = opts.data;

        var container = $('<div>');
        form_letter.activate({
            elem: container,
            extra_data: data,
        });

        var source_pre = $('<pre class="code">').text(JSON.stringify(data, null, 4));
        var source = $('<div class="code">').append(source_pre);

		var main = $('.widget_examples');

        main.append('<hr>');
	    main.append($('<h4>Example</h4>'));
        main.append(container);
        main.append($('<h6>Source</h6>'));
        main.append(source);
    }
        
    $(function () {
        window.transmit = {
            reply_message: function (opts) {
                alert("Reply:\n" + opts.content);
            },
        };

        _.each(examples, function (example) {
            add_example({
                data: example.data,
            });
        });
    });

</script>
