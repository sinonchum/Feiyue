import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const files = ['src/index.html', 'src/app.js', 'src/styles.css'];
const contents = Object.fromEntries(await Promise.all(files.map(async (file) => [file, await readFile(resolve(root, file), 'utf8')])));
const combined = Object.values(contents).join('\n');

const failures = [];
if (!contents['src/index.html'].includes('Feiyue Operator Console')) failures.push('missing console title');
if (!combined.includes('Hermes Bridge')) failures.push('missing Hermes Bridge boundary language');
if (!combined.includes('data-action="create-hermes-session-draft"')) failures.push('Hermes dry-run session draft action is missing');
if (!combined.includes('data-action="approve-first-session-draft"')) failures.push('approve-first-session-draft action is missing');
if (!combined.includes('verifier-report')) failures.push('verifier-report endpoint reference is missing');
if (!combined.includes('review-item-create-draft')) failures.push('review item create draft button class is missing');
if (!combined.includes('execute-approved-dry-run')) failures.push('execute-approved-dry-run button id is missing');
if (combined.includes('start-hermes-session-draft')) failures.push('legacy Hermes session start action must stay absent');
if (!combined.includes('disabled data-action="apply-routing-proposal"')) failures.push('routing apply action is not visibly disabled');
if (/<form\b/i.test(combined)) failures.push('forms are not allowed in the static scaffold');
if (/method=["']?post/i.test(combined)) failures.push('POST forms are not allowed in the static read-only scaffold');
if (/localStorage|sessionStorage/i.test(combined)) failures.push('browser storage is not allowed for scaffold state');
if (/api[_-]?key|token\s*[:=]|secret\s*[:=]/i.test(combined)) failures.push('secret-like literals are not allowed in frontend scaffold');

if (failures.length) {
  console.error(JSON.stringify({ status: 'failed', failures }, null, 2));
  process.exit(1);
}

console.log(JSON.stringify({ status: 'ok', checked: files }, null, 2));
