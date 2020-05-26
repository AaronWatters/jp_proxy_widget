
const fs = require("fs");
const { JupyterContext, sleep, JUPYTER_URL_PATH } = require("jupyter_puppeteer_helpers");

const verbose = true;
//const JUPYTER_URL_PATH = "./_jupyter_url.txt";

var context = null;

beforeAll(function() {
    // this file is created when the jupyter server starts by jest/run_jupyter.py
    var url = fs.readFileSync(JUPYTER_URL_PATH, 'utf8');
    context = new JupyterContext(url, browser, verbose);
});

describe("test suites in notebooks" , async () => {
    
    it("reports the browser version",  async () => {
        var version = await browser.version();
        console.log("browser version: " + version);
        expect(version).toBeTruthy();
    },
    120000, // timeout in 2 minutes...
    );

    async function run_notebook(path, test_string, initial_string) {
        var nb_context = await context.classic_notebook_context(path);
        console.log("wait for the page to initialize... looking for " + initial_string);
        await nb_context.wait_for_contained_text(initial_string);
        await nb_context.restart_and_clear();
        console.log("   verify the test text is not found or vanishes");
        //await nb_context.wait_until_gone(nb_context.selectors.container, test_string);
        await nb_context.wait_for_contained_text_gone(test_string);
        console.log("  restart and run all...");
        await nb_context.restart_and_run_all();
        //console.log("   sleep to allow events to clear... (???)")
        await sleep(200);
        console.log("Verify that test_string appears in widget output")
        //await nb_context.wait_until_there(nb_context.selectors.container, test_string);
        //console.log("sleeping 20 seconds... ")
        //await sleep(20000);
        await nb_context.wait_for_contained_text(test_string);
        console.log("now shutting down notebook and kernel");
        var result = await nb_context.shut_down_notebook();
        // success!
        expect(result).toBeTruthy();
        return result;
    }

    it("runs basic proxy widget tests in a notebook",  async () => {
        const path = "notebook_tests/basic_tests.ipynb";
        const test_string = "Tests completed with no exception.";
        const initial_string = "Basic functionality tests";
        return await run_notebook(path, test_string, initial_string);
    },
    120000, // timeout in 2 minutes...
    );

    it("runs jqueryui in a notebook",  async () => {
        const path = "notebook_tests/jqueryui_tests.ipynb";
        const test_string = "Tests completed with no exception.";
        const initial_string = "These tests verify that JQueryUI loads with CSS styling when requested.";
        return await run_notebook(path, test_string, initial_string);
    },
    120000, // timeout in 2 minutes...
    );

    it("loads stuff using require in a notebook",  async () => {
        const path = "notebook_tests/require_test.ipynb";
        const test_string = "Tests completed with no exception.";
        const initial_string = "requireJS -- load a define/require style javascript module";
        return await run_notebook(path, test_string, initial_string);
    },
    120000, // timeout in 2 minutes...
    );

    it("does chaining and other Python/JS syntax mapping correctly",  async () => {
        const path = "notebook_tests/construct_mapping_tests.ipynb";
        const test_string = "Tests completed with no exception.";
        const initial_string = "Python to Javascript construct mapping tests";
        return await run_notebook(path, test_string, initial_string);
    },
    120000, // timeout in 2 minutes...
    );

});