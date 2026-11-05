"""Exercise the actual DOM bridge parser in a bounded native Node process."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import unittest


BRIDGE = Path(__file__).resolve().parents[1] / 'src/ai_ad_editor/html_template_dom.mjs'
NODE = shutil.which('node')
PROBE = r'''
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
const { TEMPLATE_DOM } = await import(pathToFileURL(process.argv[1]));
const begin = TEMPLATE_DOM.indexOf('function urlValue(');
const end = TEMPLATE_DOM.indexOf('function sourceAddress(', begin);
assert.ok(begin >= 0 && end > begin, 'use the actual production bridge function');
const urlValue = new Function(TEMPLATE_DOM.slice(begin, end) + '\nreturn urlValue;')();
const mode = process.argv[2];
let cases = 0;
if (mode === 'valid') {
  for (const [css, expected] of [
    ['url("../assets/logo.png")', '../assets/logo.png'],
    ["url('a b.png')", 'a b.png'],
    [' url(logo.png) ', 'logo.png'],
    ['url("a\\"b.png")', 'a"b.png'],
    ["url('a\\'b.png')", "a'b.png"],
    ['url("folder\\\\logo.png")', 'folder\\logo.png'],
    ['none', null],
  ]) { assert.equal(urlValue(css), expected); cases++; }
} else {
  const quote = mode === 'double' ? '"' : "'";
  for (const count of [40, 1000]) {
    assert.equal(urlValue('url(' + quote + '\\!'.repeat(count)), null);
    cases++;
  }
}
process.stdout.write(JSON.stringify({ mode, cases, passed: true }) + '\n');
'''


@unittest.skipUnless(NODE, 'existing native Node is required; never downloaded')
class HtmlUrlParserTests(unittest.TestCase):
    def check_mode(self, mode):
        try:
            result = subprocess.run(
                [NODE, '--input-type=module', '-e', PROBE, str(BRIDGE), mode],
                capture_output=True, text=True, encoding='utf-8', timeout=5,
            )
        except subprocess.TimeoutExpired:
            self.fail(f'CSS URL parser exceeded the 5-second process deadline: {mode}')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['passed'])

    def test_valid_local_urls_keep_spaces_quotes_and_backslashes(self):
        self.check_mode('valid')

    def test_unclosed_double_quote_rejects_without_backtracking_stall(self):
        self.check_mode('double')

    def test_unclosed_single_quote_rejects_without_backtracking_stall(self):
        self.check_mode('single')
