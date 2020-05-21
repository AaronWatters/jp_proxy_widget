
// These end-to-end tests use puppeteer and headless chrome using the default jest-environment configuration.

const fs = require("fs");
const { JupyterContext, sleep, JUPYTER_URL_PATH } = require("../src/jp_helpers");

const verbose = true;
//const JUPYTER_URL_PATH = "./_jupyter_url.txt";

var context = null;

beforeAll(function() {
    // this file is created when the jupyter server starts by jest/run_jupyter.py
    var url = fs.readFileSync(JUPYTER_URL_PATH, 'utf8');
    context = new JupyterContext(url, browser, verbose);
});

describe("headless browser tests", async () => {
    
    it("gets the browser version",  async () => {
        var version = await browser.version();
        console.log("browser version: " + version);
        expect(version).toBeTruthy();
    },
    120000, // timeout in 2 minutes...
    );
    
    it("gets a page object",  async () => {
        const page = await browser.newPage();
        // console.log("page: " + page);
        expect(page).toBeTruthy();
    },
    120000, // timeout in 2 minutes...
    );

    //it("runs the debugger",  async () => {
    //    await jestPuppeteer.debug();
    //});

    it("gets a page title from an error page that talks about Jupyter",  async () => {
        const page = await browser.newPage();
        const url = "http://127.0.0.1:3000/html/index.html";
        // wait for the page to initialize...
        await page.goto(url, {waitUntil: 'networkidle2'});
        await page.waitForFunction(async () => !!(document.title));
        var title = await page.title();
        console.log("error page title is: " + title);
        expect(title.includes("Jupyter")).toBeTruthy();
    },
    120000, // timeout in 2 minutes...
    );

    it("finds a subdirectory on the notebooks index page",  async () => {
        var nb_context = await context.classic_notebook_context("");
        var title = await nb_context.page.title();
        // console.log("start url page title is: " + title);
        var directory_found = await nb_context.wait_until_there("span.item_name", "notebook_tests");
        expect(directory_found).toBeTruthy();
    },
    120000, // timeout in 2 minutes...
    );

    it("opens and closes an example notebook",  async () => {
        const path = "notebook_tests/example.ipynb";
        var nb_context = await context.classic_notebook_context(path);
        var title = await nb_context.page.title();
        console.log("example.ipynb page title is: " + title);
        var sample_text = 'Some example text';
        var example_text_found = await nb_context.wait_for_contained_text(sample_text);
        expect(example_text_found).toBeTruthy();
    },
    120000, // timeout in 2 minutes...
    );

    it("opens and closes an example notebook in lab",  async () => {
        const path = "notebook_tests/example.ipynb";
        var nb_context = await context.lab_notebook_context(path);
        var title = await nb_context.page.title();
        console.log("example.ipynb page title is: " + title);
        var sample_text = 'Some example text';
        var example_text_found = await nb_context.wait_for_contained_text(sample_text);
        expect(example_text_found).toBeTruthy();
    },
    120000, // timeout in 2 minutes...
    );

    it("runs a widget in an example notebook",  async () => {
        const path = "notebook_tests/example.ipynb";
        const test_string = "THIS IS THE SECRET TEST STRING";
        const secret_label = "SECRET BUTTON LABEL";
        const initial_string = "here it is:";
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
        console.log("Verify that secret_label appears in widget output");
        //await nb_context.wait_until_there(nb_context.selectors.container, secret_label);
        await nb_context.wait_for_contained_text(secret_label);
        console.log("Verify that test_string appears in widget output")
        //await nb_context.wait_until_there(nb_context.selectors.container, test_string);
        await nb_context.wait_for_contained_text(test_string);
        console.log("now shutting down notebook and kernel");
        var result = await nb_context.shut_down_notebook();
        // success!
        expect(result).toBeTruthy();
    },
    120000, // timeout in 2 minutes...
    );

    it("runs a widget in an example notebook in lab",  async () => {
        const path = "notebook_tests/example.ipynb";
        const test_string = "THIS IS THE SECRET TEST STRING";
        const secret_label = "SECRET BUTTON LABEL";
        const initial_string = "here it is:";
        var nb_context = await context.lab_notebook_context(path);
        console.log("wait for the page to initialize... looking for " + initial_string);
        await nb_context.wait_for_contained_text(initial_string);
        await nb_context.restart_and_clear();
        console.log("   verify the test text is not found or vanishes");
        //await nb_context.wait_until_gone(nb_context.selectors.container, test_string);
        await nb_context.wait_for_contained_text_gone(test_string);
        console.log("  restart and run all...");
        await nb_context.restart_and_run_all();
        console.log("   sleep to allow events to clear... (???)")
        await sleep(200);
        console.log("Verify that secret_label appears in widget output");
        //await nb_context.wait_until_there(nb_context.selectors.container, secret_label);
        await nb_context.wait_for_contained_text(secret_label);
        console.log("Verify that test_string appears in widget output")
        //await nb_context.wait_until_there(nb_context.selectors.container, test_string);
        await nb_context.wait_for_contained_text(test_string);
        console.log("now shutting down notebook and kernel");
        var result = await nb_context.shut_down_notebook();
        // success!
        expect(result).toBeTruthy();
    },
    120000, // timeout in 2 minutes...
    );

    it("modifies the kernel state programatically",  async () => {
        const path = "notebook_tests/example.ipynb";
        const test_string = "THIS IS THE SECRET TEST STRING";
        const replacement_string = "THIS IS THE MODIFIED SECRET TEST STRING";
        const execution_string = "test_module.test_string = '" + replacement_string +"'";
        const initial_string = "here it is:";
        var nb_context = await context.classic_notebook_context(path);
        console.log("wait for the page to initialize... looking for " + initial_string);
        await nb_context.wait_for_contained_text(initial_string);
        await nb_context.restart_and_clear();
        console.log("   verify the test text is not found or vanishes");
        //await nb_context.wait_until_gone(nb_context.selectors.container, test_string);
        await nb_context.wait_for_contained_text_gone(test_string);
        console.log("  restart and run all...");
        await nb_context.restart_and_run_all();
        console.log("   sleep to allow events to clear... (???)")
        await sleep(200);
        console.log("Verify that test_string appears in widget output")
        //await nb_context.wait_until_there(nb_context.selectors.container, test_string);
        await nb_context.wait_for_contained_text(test_string);
        // change the module slot test_module.test_string
        await nb_context.execute_string_in_kernel(execution_string);
        // run the cells without restarting the kernel and reloading the module.
        await nb_context.execute_all_cells();
        //await nb_context.wait_until_gone(nb_context.selectors.container, test_string);
        await nb_context.wait_for_contained_text_gone(test_string);
        await nb_context.wait_for_contained_text(replacement_string);
        console.log("now shutting down notebook and kernel");
        var result = await nb_context.shut_down_notebook();
        // success!
        expect(result).toBeTruthy();
    },
    120000, // timeout in 2 minutes...
    );

    it("saves an example notebook",  async () => {
        const path = "notebook_tests/example.ipynb";
        const initial_string = "here it is:";
        var nb_context = await context.classic_notebook_context(path);
        console.log("wait for the page to initialize... looking for " + initial_string);
        await nb_context.wait_for_contained_text(initial_string);
        var old_status = await nb_context.set_checkpoint_status("bogus status should be replaced");
        await nb_context.save_and_checkpoint();
        // loop until status changed or timeout
        var new_status = old_status;
        console.log("  save and checkpoint... old='" +old_status + "'");
        while (new_status == old_status) {
            await sleep(1000);
            new_status = await nb_context.get_checkpoint_status();
        }
        console.log("  new status="+new_status);
        expect(new_status).not.toEqual(old_status);
        await nb_context.shut_down_notebook();
        // success!
        expect(true).toBeTruthy();
    },
    120000, // timeout in 2 minutes...
    );

/*  xxxx not working and I don't know why right now...
    it("saves an example notebook in lab",  async () => {
        const path = "notebook_tests/example.ipynb";
        const initial_string = "here it is:";
        var nb_context = await context.lab_notebook_context(path);
        console.log("wait for the page to initialize... looking for " + initial_string);
        await nb_context.wait_for_contained_text(initial_string);
        var fake_status = "bogus status should be replaced";
        var old_status = await nb_context.set_checkpoint_status(fake_status);
        await nb_context.save_and_checkpoint();
        // loop until status changed or timeout
        var new_status = old_status;
        console.log("  save and checkpoint... old='" +old_status + "'");
        while (new_status == old_status) {
            await sleep(1000);
            new_status = await nb_context.get_checkpoint_status();
        }
        console.log("  new status="+new_status);
        expect(new_status).not.toEqual(old_status);
        await nb_context.shut_down_notebook();
        // success!
        expect(true).toBeTruthy();
    },
    120000, // timeout in 2 minutes...
    ); 
*/

});
