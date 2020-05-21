"use strict";

const LINK_BROWSER_LOGS = false;

function jp_helpers_is_loaded() {
    return true;
}

var classic_selectors = {
    confirm: {css: "div.modal-dialog button.btn-danger", str: ""},
    container: {css: "#notebook-container", str: ""},
    restart_clear: {css: "#restart_clear_output a", str: ""},
    restart_run: {css: "#restart_run_all a", str: ""},
    kernel_dropdown: {css: "#kernellink", str: ""},
    file_menu: {css: "#file_menu", str: ""},
    close_halt: {css: "#close_and_halt a", str: ""},
    save_checkpoint: {css: "#save_checkpoint a", str: ""},
    notification_kernel: {css: "#notification_kernel", str: ""},
    checkpoint_status: {css: "span.checkpoint_status", str: ""},
};

var lab_selectors = {
    confirm: {css: "button.jp-mod-warn", str: ""},
    container: {css: "div.jp-Activity:not(.lm-mod-hidden) div.jp-Notebook", str: ""},
    restart_clear: {css: "div.lm-Menu div.lm-Menu-itemLabel", str: "Restart Kernel and Clear"}, 
    restart_run: {css: "div.lm-Menu div.lm-Menu-itemLabel", str: "Restart Kernel and Run All"}, 
    kernel_dropdown: {css: "#jp-MainMenu div.lm-MenuBar-itemLabel", str: "Kernel"},
    file_menu: {css: "#jp-MainMenu div.lm-MenuBar-itemLabel", str: "File"},
    close_halt: {css: "div.lm-Menu div.lm-Menu-itemLabel", str: "Shutdown Notebook"}, 
    save_checkpoint: {css: "div.lm-Menu div.lm-Menu-itemLabel", str: "Save Notebook"},  // not "Save Notebook as"!
    notification_kernel: {css: "div.jp-Activity:not(.lm-mod-hidden) div.jp-Toolbar-kernelStatus", str: ""},
    checkpoint_status: {css: "ul.lm-TabBar-content li.jp-mod-current", str: ""},
};


class JupyterContext {
    constructor(url_with_token, browser, verbose) {
        this.verbose = verbose;
        this.url_with_token = url_with_token;
        this.browser = browser;
    };
    async classic_notebook_context(path, verbose) {
        var context = new ClassicNotebookContext(this, path, classic_selectors, verbose);
        await context.get_page();
        return context;
    };
    async lab_notebook_context(path, verbose) {
        var context = new LabNotebookContext(this, path, lab_selectors, verbose);
        await context.get_page();
        return context;
    }
};

function sleep(time) {
    return new Promise(function(resolve) { 
        setTimeout(resolve, time)
    });
};

class BaseNotebookContext {
    constructor(jupyter_context, path, selectors, verbose) {
        this.jupyter_context = jupyter_context;
        this.path = path;
        this.selectors = selectors;
        this.verbose = verbose || jupyter_context.verbose;
        this.page = null;
    };

    async get_page() {
        if (this.page) {
            return this.page;
        }
        var path = this.path;
        //var page_url = this.jupyter_context.url_with_token.replace("?", path + "?");
        var page_url = this.notebook_url(path);
        const page = await this.jupyter_context.browser.newPage();
        // https://stackoverflow.com/questions/47539043/how-to-get-all-console-messages-with-puppeteer-including-errors-csp-violations
        if (LINK_BROWSER_LOGS) {
            page
                .on('console', message =>
                    console.log(`${message.type().substr(0, 3).toUpperCase()} ${message.text()}`))
                .on('pageerror', ({ message }) => console.log(message))
                .on('response', response =>
                    console.log(`${response.status()} ${response.url()}`))
                .on('requestfailed', request =>
                    console.log(`${request.failure().errorText} ${request.url()}`));
        }
        if (this.verbose) {
            console.log("  sending page to " + page_url);
        }
        await page.goto(page_url, {waitUntil: 'networkidle2'});
        await page.waitForFunction(async () => !!(document.title));
        this.page = page;
        return page;
    };

    wait_for_page_to_close() {
        // this doesn't work... some security issue prevents the page close
        var that = this;
        return new Promise(function(resolve) {
            that.page.on("close", resolve);
        })
    };

    async shut_down_notebook() {
        // don't wait for notification to clear
        await this.find_click_confirm(this.selectors.file_menu, this.selectors.close_halt, this.selectors.confirm, false);
        //await this.wait_for_page_to_close();
        // this doesn't work in Lab:
        //await this.wait_until_there(this.selectors.notification_kernel.css, "No kernel");
        await sleep(1000);
        return true;
    };

    async wait_for_kernel_notification_to_go_away() {
        return await this.wait_until_empty(this.selectors.notification_kernel.css)
    };

    async restart_and_clear() {
        await this.find_click_confirm(this.selectors.kernel_dropdown, this.selectors.restart_clear, this.selectors.confirm, true)
    };

    async restart_and_run_all() {
        await this.find_click_confirm(this.selectors.kernel_dropdown, this.selectors.restart_run, this.selectors.confirm, true)
    };

    async save_and_checkpoint() {
        await this.find_click_confirm(this.selectors.file_menu, this.selectors.save_checkpoint, this.selectors.confirm, false)
    };

    async wait_for_contained_text(text) {
        await this.wait_until_there(this.selectors.container.css, text);
        return true;
    }
    async wait_for_contained_text_gone(text) {
        await this.wait_until_gone(this.selectors.container.css, text);
        return true;
    };

    async get_checkpoint_status() {
        return await this.get_attribute(this.selectors.checkpoint_status.css, "title");
    };

    async set_checkpoint_status(value) {
        return await this.set_attribute(this.selectors.checkpoint_status.css, "title", value);
    };

    async find_click_confirm(tab_selector, button_selector, confirm_selector, notification_wait, sleep_time) {
        sleep_time = sleep_time || 1000;
        if (this.verbose) {
            console.log("  click/confirm" + [tab_selector.css, button_selector.css, confirm_selector.css, sleep_time])
        }
        await this.find_and_click(tab_selector.css, tab_selector.str);
        await this.wait_until_there(button_selector.css, button_selector.str);
        await this.find_and_click(button_selector.css, button_selector.str);
        await sleep(sleep_time);
        // sometimes the confirm button doesn't pop up?
        if (await this.match_exists(confirm_selector.css)) {
            if (this.verbose) {
                console.log("  now confirming " + confirm_selector.css)
            }
            await this.find_and_click(confirm_selector.css, confirm_selector.str);
        }
        if (notification_wait) {
            await this.wait_for_kernel_notification_to_go_away();
        }
        if (this.verbose) {
            console.log("  clicked and confirmed " + [button_selector.css, button_selector.str, confirm_selector.css]);
        }
    };

    async find_and_click(selector, substring) {
        // keep looking until the test times out.
        // alternate implementation...
        substring = substring || "";
        if (!selector) {
            throw new Error("selector is required " + selector);
        }
        if (this.verbose) {
            console.log("  find and clicking " + [selector, substring])
        }
        var found = false;
        var page = this.page;
        while (!found) {
            found = await page.evaluate(
                async function(selector, substring) {
                    //console.log("looking for '" + selector + "' in " + document);
                    // document.querySelector("button.button-danger")
                    var element = document.querySelector(selector);
                    if (element && element.textContent.includes(substring)) {
                        //console.log("element found " + element);
                        element.click();
                        return true;
                    }
                    //console.log("no element for selector: " + selector);
                    return false;
                },
                selector, substring
            );
            if (!found) {
                //console.log("looking for " + selector);
                //console.log("OUTPUT:: " + await page.evaluate(() => document.querySelectorAll("div .output")[2].innerHTML));
                await sleep(2500);
            }
        }
    };

    async wait_for_attribute(selector, name, substring, sleeptime) {
        // keep looking until the test timeout.
        // This implementation uses polling: fancier methods sometimes failed (??)
        sleeptime = sleeptime || 2000;
        var found = false;
        while (!found) {
            //console.log("looking in " + selector + "." + name + " for " + substring);
            var value = await this.get_attribute(selector, name);
            found = value.includes(substring);
            if (!found) {
                await sleep(sleeptime)
            }
        }
        return true;
    };

    async wait_until_there(selector, substring, sleeptime) {
        // keep looking until the test timeout.
        // This implementation uses polling: fancier methods sometimes failed (??)
        sleeptime = sleeptime || 2000;
        var found = false;
        while (!found) {
            //console.log("looking in " + selector + " for " + substring);
            found = await this.match_exists(selector, substring);
            if (!found) {
                await sleep(sleeptime)
            }
        }
        return true;
    };

    async wait_until_gone(selector, substring, sleeptime) {
        // keep looking until the test timeout.
        // This implementation uses polling: fancier methods sometimes failed (??)
        sleeptime = sleeptime || 1000
        var found = true;
        while (found) {
            //console.log("looking in " + selector + " for absense of " + substring);
            found = await this.match_exists(selector, substring);
            if (found) {
                await sleep(sleeptime)
            }
        };
        return !found;
    };

    async wait_until_empty(selector, sleeptime) {
        // keep looking until the test timeout.
        // This implementation uses polling: fancier methods sometimes failed (??)
        sleeptime = sleeptime || 1000
        var empty = false;
        while (!empty) {
            //console.log("looking for empty " + selector);
            empty = await this.selection_empty(selector);
            if (!empty) {
                await sleep(sleeptime)
            }
        };
        return empty;
    };

    async match_exists(selector, text_substring) {
        text_substring = text_substring || "";
        var verbose = this.verbose;
        var texts = await this.get_matches(selector, text_substring);
        var text_found = false;
        if (verbose) {
            //console.log("   looking for '" + text_substring + "' in " + texts.length);
        }
        for (var i=0; i<texts.length; i++) {
            if (texts[i].includes(text_substring)) {
                text_found = true;
                if (verbose) {
                    //console.log("   found '" + text_substring + "' at index " + i);
                }
            }
        }
        // debugging...
        if (verbose &&  !text_found) {
            console.log("   NOT FOUND");
            console.log(texts[0]);
        }
        return text_found;
    };

    async selection_empty(selector) {
        var verbose = this.verbose;
        var texts = await this.get_matches(selector, "");
        // selection must exist
        if (!texts.length) {
            if (verbose) {
                //console.log("no selector to be empty: " + selector)
            }
            return false;
        }
        for (var i=0; i<texts.length; i++) {
            var text = texts[i].trim();
            if (text) {
                if (verbose) {
                    //console.log("found string in selecor: " + text);
                }
                return false;
            }
        }
        if (verbose) {
            //console.log("selector has white content: " + selector);
        }
        return true;
    };

    async set_attribute(selector, attribute_name, value) {
        var page = await this.get_page();
        var result = await page.evaluate(
            async function(selector, attribute_name, value) {
                var element = document.querySelector(selector);
                if (!element) {
                    return null;
                }
                element.setAttribute(attribute_name, value);
                return element.getAttribute(attribute_name);
            },
            selector, attribute_name, value
        );
        return result;
    };

    async get_attribute(selector, attribute_name) {
        var page = await this.get_page();
        var result = await page.evaluate(
            async function(selector, attribute_name) {
                var element = document.querySelector(selector);
                if (!element) {
                    return null;
                }
                return element.getAttribute(attribute_name);
            },
            selector, attribute_name
        );
        if ((result === null) && this.verbose) {
            //console.log("  no element found for selector: '" + selector + "'");
        } else if (this.verbose) {
            //console.log("   for " + selector + " found attribute " + attribute_name + " == '" + result + '"');
        }
        return result;
    };

    async get_matches(selector, text_substring) {
        var page = await this.get_page();
        // extracting text into puppeteer context.  Fancier matching in the browser sometimes didn't work (??)
        var texts = await page.$$eval(
            selector,
            (elements) => elements.map((el) => el.textContent),
        );
        return texts;
    };
};

class ClassicNotebookContext extends BaseNotebookContext {

    notebook_url(path) {
        var url_token = this.jupyter_context.url_with_token;
        var qualified_path = "notebooks/" + path;
        return url_token.replace("?", qualified_path + "?");
    };

    async execute_string_in_kernel(code_string) {
        // execute the string as Python (or Julia, etc) code in the Python (or Julia etc) kernel process
        var page = this.page;
        var result = await page.evaluate(
            async function(code_string) {
                IPython.notebook.kernel.execute(code_string)
            },
            code_string
        );
        await this.wait_for_kernel_notification_to_go_away();
        return result;
    };

    async restart_and_run_all() {
        // Call notebook method directly
        var result = await this.call_notebook_method("restart_run_all", {confirm: false});
        await this.wait_for_kernel_notification_to_go_away();
        return result;
    };

    async restart_and_clear() {
        // Call notebook method directly
        var result = await this.call_notebook_method("restart_clear_output", {confirm: false});
        await this.wait_for_kernel_notification_to_go_away();
        return result;
    }

    async execute_all_cells() {
        // Call notebook method directly
        var result = await this.call_notebook_method("execute_all_cells", {confirm: false});
        await this.wait_for_kernel_notification_to_go_away();
        return result;
    };

    async call_notebook_method(method_name, options) {
        // execute the string as Python code in the Python kernel process
        options = options || {};
        var page = this.page;
        return await page.evaluate(
            async function(method_name, options) {
                IPython.notebook[method_name] (options);
            },
            method_name, options
        );
    };
};

class LabNotebookContext extends BaseNotebookContext {
    
    notebook_url(path) {
        var url_token = this.jupyter_context.url_with_token;
        // https://jupyterlab.readthedocs.io/en/stable/user/urls.html
        var qualified_path = "lab/tree/" + path;
        return url_token.replace("?", qualified_path + "?");
    };

    async wait_for_kernel_notification_to_go_away() {
        //return await this.wait_until_empty(this.selectors.notification_kernel.css)
        return await this.wait_for_attribute(this.selectors.notification_kernel.css, "title", "Kernel Idle");
    };

    async find_and_click(selector, substring) {
        // keep looking until the test times out.
        // alternate implementation...
        substring = substring || "";
        if (!selector) {
            throw new Error("selector is required " + selector);
        }
        if (this.verbose) {
            //console.log("  find and clicking " + [selector, substring])
        }
        var found = false;
        var page = this.page;
        while (!found) {
            found = await page.evaluateHandle(
                async function(selector, substring) {
                    //console.log("looking for '" + selector + "' in " + document);
                    // document.querySelector("button.button-danger")
                    var elements = document.querySelectorAll(selector);
                    for (var i=0; i<elements.length; i++) {
                        var element = elements[i];
                        if (element && element.textContent.includes(substring)) {
                            //console.log("element found " + element);
                            //element.click();
                            return element;
                        }
                    }
                    console.log("no element for selector: " + selector);
                    return false;
                },
                selector, substring
            );
            if (!found) {
                //console.log("looking for " + selector);
                //console.log("OUTPUT:: " + await page.evaluate(() => document.querySelectorAll("div .output")[2].innerHTML));
                await sleep(2500);
            }
        }
        console.log("  tring to click: " + found)
        found.click();  // click the element handle?
    };

};

const JUPYTER_URL_PATH = './_jupyter_url.txt';

const RUN_JUPYTER_SERVER_PYTHON_SCRIPT = `

'''
Run a Jupyter server and save the token URL in a file.
This script is left here for testing and maintenance.
The script is available as a string constant in '../src/jp_helpers.js'.
'''

# https://stackoverflow.com/questions/2804543/read-subprocess-stdout-line-by-line

import subprocess
import os
import signal

proc = None
cmd = None

JUPYTER_URL_PATH = '${JUPYTER_URL_PATH}'

def run():
    global proc, cmd
    signal.signal(signal.SIGINT, exit_cleanly)
    signal.signal(signal.SIGTERM, exit_cleanly)
    cmd = ['jupyter', 'notebook', '--port=3000', '--no-browser']
    print ('Starting jupyter server: ' + repr(cmd))
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE)
    url_emitted = False
    try:
        for line in proc.stderr:
            print('Jupyter_server: ' + repr(line))
            line = str(line, encoding='utf8')
            if not url_emitted:
                # assume first line starting 'http:...' gives the start url with token similar to
                # http://localhost:3000/?token=793337e53c6ca95680623cb6556afdb32c7a1ee002f60119
                sline = line.strip()
                if sline.startswith('http://'):
                    with open(JUPYTER_URL_PATH, 'w') as f:
                        f.write(sline)
                    url_emitted = True
                    print ('Jupyter url emitted: ' + repr(sline))
                    print ('   saved to: ' + repr(JUPYTER_URL_PATH))
    finally:
        exit_cleanly()

def exit_cleanly(*arguments):
    print ('Stopping jupyter server', cmd)
    proc.kill()
    if os.path.exists(JUPYTER_URL_PATH):
        print('removing', JUPYTER_URL_PATH)
        os.remove(JUPYTER_URL_PATH)

if __name__=='__main__':
    run()
`

// Command to start a jupyter server and store the URL to a file.
// Used with jest-puppeteer setup.
const RUN_JUPYTER_SERVER_CMD = 
    `python -u -c "${RUN_JUPYTER_SERVER_PYTHON_SCRIPT}" > _jupyter_server_out.txt`;

exports.default = jp_helpers_is_loaded;
exports.JupyterContext = JupyterContext;
exports.sleep = sleep;
exports.RUN_JUPYTER_SERVER_PYTHON_SCRIPT = RUN_JUPYTER_SERVER_PYTHON_SCRIPT;
exports.RUN_JUPYTER_SERVER_CMD = RUN_JUPYTER_SERVER_CMD;
exports.JUPYTER_URL_PATH = JUPYTER_URL_PATH;
