#!/usr/bin/env node
/**
 * ELK Layout Bridge
 * 
 * Reads an ELK JSON graph from stdin, runs the ELK layered layout
 * algorithm, and writes the positioned graph to stdout.
 * 
 * Usage: echo '{"id":"root",...}' | node elk_bridge.js
 */
const ELK = require('elkjs');

const elk = new ELK();

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', async () => {
    try {
        const graph = JSON.parse(input);
        const result = await elk.layout(graph);
        process.stdout.write(JSON.stringify(result, null, 2));
        process.exit(0);
    } catch (err) {
        process.stderr.write(`ELK layout error: ${err.message}\n`);
        process.exit(1);
    }
});
