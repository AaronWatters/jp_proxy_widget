
Unit tests for Python code.

These tests mainly exercise the code paths.
To test the underlying functionality, use the end_to_end_tests.

To run the tests in the parent directory:

$ nosetests --with-coverage --cover-html-dir=coverage --cover-html --cover-package=jp_proxy_widget

To view the HTML report from the parent directory:

$ open coverage/index.html
