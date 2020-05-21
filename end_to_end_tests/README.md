# End-to-end tests for `jp_proxy_widgets`

This folder contains the infrastructure for testing that `jp_proxy_widgets` work
in Jupyter notebooks running in a browser.  The infrastructure uses "headless chrome"
and browser automation to implement the tests.

## Running the tests

The `npm` tests for the module are end-to-end tests which do not attempt
to install all the components required to run the tests.  The tests assume
the following have been installed in the environment:

- Python 3 (tested with 3.6)
- node and npm
- jupyterlab=2.1.2
- jupyter labextension install @jupyter-widgets/jupyterlab-manager
- ipywidgets
- jp_proxy_widgets

The test suite was built using these versions:

```bash
$ npm -v
6.14.4
$ node -v
v10.13.0
```

Before running the tests you must install the dependencies:

```
$ cd <root>/jp_proxy_widget/end_to_end_tests
$ npm install
```

After the external and internal dependencies have been installed run the tests like this:

```
$ npm run test
```

To watch the tests running in slow motion (not headless)

```
HEADLESS="false" SLOWMO=100 npm run test
```

To watch the a single test running by itself in slow motion, specify its name:

```
HEADLESS="false" SLOWMO=100 jest -t "runs a widget in an example notebook"
```


## How to install tests for a widget repository:

The following is an outline of the steps to create these tests:

```
$ cp -r ~/tmp/jupyter_puppeteer_helpers/* .
$ git add *
$ git commit -m "copy test framework from jupyter_puppeteer_helpers"
$ git rm src/jp_helpers.js 
$ git commit -m "don't include the source module -- add it to dev dependencies instead"
```
Then edit package.json to change the package name and description and remove stuff.
```
$ npm install
$ npm install git+https://git@github.com/AaronWatters/jupyter_puppeteer_helpers.git --save-dev
```

Edit import in `jest/globalSetup.js`.

```
$ git diff jest/globalSetup.js 
diff --git a/end_to_end_tests/jest/globalSetup.js b/end_to_end_tests/jest/globalSetup.js
index 7917162..90a9a70 100644
--- a/end_to_end_tests/jest/globalSetup.js
+++ b/end_to_end_tests/jest/globalSetup.js
@@ -1,6 +1,6 @@
 const { setup: setupDevServer } = require('jest-dev-server')
 const { setup: setupPuppeteer } = require('jest-environment-puppeteer')
-const { RUN_JUPYTER_SERVER_CMD } = require("../src/jp_helpers");
+const { RUN_JUPYTER_SERVER_CMD } = require("jupyter_puppeteer_helpers");
```

Similarly edit `tests/headless.test.js`

```
$ git diff tests/headless.test.js 
diff --git a/end_to_end_tests/tests/headless.test.js b/end_to_end_tests/tests/headless.test.js
index 810ee42..51b6c77 100644
--- a/end_to_end_tests/tests/headless.test.js
+++ b/end_to_end_tests/tests/headless.test.js
@@ -2,7 +2,7 @@
 // These end-to-end tests use puppeteer and headless chrome using the default jest-environment configuration.
 
 const fs = require("fs");
-const { JupyterContext, sleep, JUPYTER_URL_PATH } = require("../src/jp_helpers");
+const { JupyterContext, sleep, JUPYTER_URL_PATH } = require("jupyter_puppeteer_helpers");
 
 const verbose = true;
 //const JUPYTER_URL_PATH = "./_jupyter_url.txt";
```

Then run the basic tests
```
$ npm test
```

Then modify contents of `notebook_test` and `tests` to add local tests and examples.
