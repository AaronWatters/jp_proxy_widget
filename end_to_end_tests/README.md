# jupyter_puppeteer_helpers

[![Build Status](https://travis-ci.org/AaronWatters/jupyter_puppeteer_helpers.svg?branch=master)](https://travis-ci.org/AaronWatters/jupyter_puppeteer_helpers)

Some helpful code for controlling Jupyter from puppeteer using a headless browser.

Although the code does not depend on `jest` and `jest-puppeteer` this repository
was primarily built to provide common tools for creating end-to-end tests for Jupyter
widget implementations using `jest` with `puppeteer` as a testing engine.

The module may also be helpful for automatically capturing (very many) images from notebook based visualizations
in an automated manner, among other use cases.

# Running the tests

The `npm` tests for the module are end-to-end tests which do not attempt
to install all the components required to run the tests.  The tests assume
the following have been installed in the environment:

- Python 3 (tested with 3.6)
- jupyterlab=2.1.2
- jupyter labextension install @jupyter-widgets/jupyterlab-manager
- ipywidgets

The test suite was built using these versions:

```bash
$ npm -v
6.14.4
$ node -v
v10.13.0
```

Before running the tests you must install the dependencies:

```
$ cd <root>/jupyter_puppeteer_helpers
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
