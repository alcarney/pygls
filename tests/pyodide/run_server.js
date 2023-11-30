const fs = require('fs');
const { loadPyodide } = require('pyodide');

const consoleLog = console.log

// Create a file to log pyodide output to.
const logFile = fs.createWriteStream("pyodide.log")

function writeToFile(...args) {
    logFile.write(args[0] + `\n`);
}

async function runServer(serverCode) {
    // Annoyingly, while we can redirect stderr/stdout to a file during this setup stage
    // it doesn't prevent `micropip.install` from indirectly writing to console.log.
    //
    // Internally, `micropip.install` calls `pyodide.loadPackage` and doesn't expose loadPacakge's
    // options for redirecting output i.e. messageCallback.
    //
    // So instead, we override console.log globally.
    console.log = writeToFile
    const pyodide = await loadPyodide({
        // stdin:
        stderr: writeToFile,
    })

    await pyodide.loadPackage("micropip")
    const micropip = pyodide.pyimport("micropip")
    await micropip.install("file:///var/home/alex/Projects/pygls/tests/pyodide/node_modules/pyodide/pygls-1.2.0-py3-none-any.whl")

    // Restore the original console.log
    console.log = consoleLog
    await pyodide.runPythonAsync(serverCode)
}

if (process.argv.length < 3) {
    console.error("Missing server.py file")
    process.exit(1)
}

const serverCode = fs.readFileSync(process.argv[2], 'utf8')
let returnCode = 0
logFile.once('open', (fd) => {
    runServer(serverCode).then(() => {
        logFile.end();
        process.exit(0)
    }).catch(err => {
        logFile.write(`Error in server process\n${err}`)
        logFile.end();
        process.exit(1);
    })
})
