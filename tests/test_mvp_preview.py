"""Run shared JS model contracts without a browser or a live model."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_preview_is_target_scoped_and_identity_replacements_are_not_hits():
    script = r'''
    const assert = require('node:assert/strict');
    global.window={SC:{}};
    require('./site/model.js');
    const SC=window.SC, hits=new Set();
    const plan=[{key:1,from:'Yes',to:'Yes, I bought it',page_id:'p1',question_id:'q1'}];
    assert.equal(SC.applyFixes('Yes',plan,hits,{page_id:'p2',question_id:'q2'}),'Yes');
    assert.equal(hits.size,0);
    assert.equal(SC.applyFixes('Yes',plan,hits,{page_id:'p1',question_id:'q1'}),'Yes, I bought it');
    assert.deepEqual([...hits],[1]);
    const same=new Set();
    assert.equal(SC.applyFixes('Yes',[{key:2,from:'Yes',to:'Yes'}],same),'Yes');
    assert.equal(same.size,0);
    '''
    completed = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
