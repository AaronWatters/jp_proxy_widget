
import jp_proxy_widget
import time

class ValidationSuite:

    def __init__(self, success="Tests completed with no exception.", failure="TESTS FAILED"):
        self.widget_validator_list = []
        self.widget_to_validator = {}
        self.success = success
        self.failure = failure

    def add_validation(self, widget, validation):
        self.widget_validator_list.append((widget, validation))
        self.widget_to_validator[widget] = validation

    def validate(self, widget):
        validator = self.widget_to_validator[widget]
        validator()

    def run_all_in_widget(self, delay_ms=1000):
        """
        Validate all in a widget display.
        This is suitable for running in a notebook using "run all" as the last step
        because the final widget is guaranteed to initialize last (which is not true
        for other cell code execution at this writing).
        The implementation includes a delay in the python kernel and a javascript delay
        to allow any unresolved operations in tested widgets to complete.
        """
        print("sleeping in kernel interface...")
        time.sleep(delay_ms / 1000.0)
        print("initializing validator widget.")
        validator_widget = jp_proxy_widget.JSProxyWidget()

        def validate_all():
            try:
                for (widget, validator) in self.widget_validator_list:
                    validator()
            except:
                validator_widget.js_init("""
                    $("<div>" + failure + "</div>").appendTo(element);
                """, failure=self.failure)
                raise
            else:
                validator_widget.js_init("""
                    $("<div>" + success + "</div>").appendTo(element);
                """, success=self.success)

        validator_widget.js_init("""
        element.html("<em>Delaying validators to allow environment to stabilize</em>");

        var call_back = function() {
            element.html("<b>Validator Summary</b>");
            validate_all();
        };

        setTimeout(call_back, delay_ms);
        """, validate_all=validate_all, delay_ms=delay_ms)

        return  validator_widget.debugging_display()
