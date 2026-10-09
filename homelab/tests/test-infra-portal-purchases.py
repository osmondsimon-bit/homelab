#!/usr/bin/env python3
"""Verify purchase-list rendering and browser progress across portal regeneration."""

import importlib.util
from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "portal", Path(__file__).resolve().parents[1] / "scripts/infra-portal-generate.py"
)
portal = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(portal)


def fixture():
    return {"purchases": {"purchase_list": {"groups": [
        {"id": "required", "title": "Phase 1", "kind": "required", "items": [
            {"id": "rack", "name": "Rack & cabinet", "quantity": "1",
             "notes": "Check <clearance>", "url": "https://example.com/rack"},
        ]},
        {"id": "owned", "title": "Already owned", "kind": "owned", "items": [
            {"id": "leads", "name": "Patch leads", "quantity": "24"},
        ]},
        {"id": "future", "title": "Future", "kind": "future", "items": [
            {"id": "nas", "name": "Future storage", "quantity": "1"},
        ]},
    ]}}}


class PurchaseTests(unittest.TestCase):
    def test_loads_optional_private_purchase_source(self):
        with tempfile.TemporaryDirectory() as directory:
            rack = Path(directory) / "rack"
            rack.mkdir()
            (rack / "purchases.yaml").write_text("purchase_list:\n  groups: []\n")
            with redirect_stderr(io.StringIO()):
                self.assertEqual(portal.load_data(directory)["purchases"],
                                 {"purchase_list": {"groups": []}})
                (rack / "purchases.yaml").unlink()
                self.assertEqual(portal.load_data(directory)["purchases"], {})

    def test_generated_page_has_purchase_tab_and_escaped_rows(self):
        html = portal.generate_html(fixture(), "", "test")
        self.assertIn('href="#purchases"', html)
        self.assertIn('<section id="purchases">', html)
        self.assertIn('id="purchase-rack"', html)
        self.assertIn('for="purchase-rack"', html)
        self.assertIn('data-required="true"', html)
        self.assertIn('data-purchase-id="leads" checked', html)
        self.assertIn("Rack &amp; cabinet", html)
        self.assertIn("Check &lt;clearance&gt;", html)

    def test_rejects_duplicate_ids_and_unsafe_product_links(self):
        data = fixture()
        data["purchases"]["purchase_list"]["groups"][0]["items"][0]["url"] = "javascript:alert(1)"
        html = portal.purchases_section_html(data)
        self.assertNotIn("javascript:", html)
        data["purchases"]["purchase_list"]["groups"][1]["items"][0]["id"] = "rack"
        with self.assertRaises(ValueError):
            portal.purchases_section_html(data)

    def test_quantities_follow_panel_and_switch_schedule(self):
        data = fixture()
        items = data["purchases"]["purchase_list"]["groups"][0]["items"]
        items[0]["quantity_from"] = "occupied_panels"
        data["switch_ports"] = {"rack_equipment": {"connections": [
            {"pp": "PP-A01", "sw": 1}, {"pp": "PP-B01", "sw": 2},
        ]}}
        html = portal.purchases_section_html(data)
        self.assertIn('<td class="purchase-quantity">2</td>', html)
        data["switch_ports"]["rack_equipment"]["connections"].pop()
        self.assertIn('<td class="purchase-quantity">1</td>',
                      portal.purchases_section_html(data))

    def test_browser_checkmarks_survive_reload_and_handle_storage_failure(self):
        script = r"""
const assert = require('node:assert/strict');
const vm = require('node:vm');
const payload = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const saved = new Map();
function openPage(blocked=false) {
  const boxes = [
    {dataset:{purchaseId:'rack',required:'true'},checked:false},
    {dataset:{purchaseId:'leads',required:'false'},checked:true},
    {dataset:{purchaseId:'nas',required:'false'},checked:false},
  ];
  boxes.forEach(b=>b.addEventListener=(_,fn)=>b.change=fn);
  const progress = {textContent:''};
  const notice = {textContent:''};
  const node = {classList:{remove(){},add(){}}};
  const context = {
    document: {
      querySelectorAll(selector) {
        if(selector==='[data-purchase-id]') return boxes;
        return [];
      },
      querySelector:()=>node,
      getElementById(id) {
        if(id==='purchase-progress') return progress;
        if(id==='purchase-storage-note') return notice;
        return node;
      },
    },
    localStorage: {
      getItem(k){if(blocked)throw Error('blocked');return saved.get(k)??null;},
      setItem(k,v){if(blocked)throw Error('blocked');saved.set(k,v);},
    },
    window:{addEventListener:(_,fn)=>context.start=fn},
    history:{replaceState(){}}, location:{hash:'#purchases'},
  };
  vm.runInNewContext(payload.js,context);
  context.start();
  return {boxes,progress,notice};
}
let page=openPage();
assert.match(page.progress.textContent,/0 of 1/);
page.boxes[0].checked=true;page.boxes[0].change();
assert.match(page.progress.textContent,/1 of 1/);
page.boxes[1].checked=false;page.boxes[1].change();
page.boxes[2].checked=true;page.boxes[2].change();
page=openPage();
assert.equal(page.boxes[0].checked,true);
assert.equal(page.boxes[1].checked,false);
assert.equal(page.boxes[2].checked,true);
assert.match(page.progress.textContent,/1 of 1/);
page.boxes[0].checked=false;page.boxes[0].change();
assert.equal(openPage().boxes[0].checked,false);
page=openPage(true);
assert.match(page.notice.textContent,/cannot be saved/i);
page.boxes[0].checked=true;page.boxes[0].change();
assert.match(page.progress.textContent,/1 of 1/);
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "browser-test.cjs"
            path.write_text(script)
            result = subprocess.run(["node", str(path)],
                                    input=json.dumps({"js": portal.JS}),
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
