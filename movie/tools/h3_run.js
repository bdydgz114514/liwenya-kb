const fs = require('fs');
const { chromium } = require('/tmp/node_modules/playwright-core');

const WF = '/root/ComfyUI/user/default/workflows/视频/0005--MiniMax H3-潜空间二次放大--参考生成视频--新.json';
const PROMPT = `subject_definitions:
<Subject 1> is the middle-aged Chinese man whose appearance comes from <Picture 1>: a weathered face, short thinning hair, wearing a dark worn jacket.

summary:
[reference generation] A cinematic 5-second shot of <Subject 1> standing alone beneath high-voltage power lines at dusk, holding an old stopwatch in his hand and looking up at the last light of the sun. Slow, steady camera move, shallow depth of field, muted teal and amber colour, 35mm film grain, quiet and dignified.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - his weathered face, thinning hair and dark worn jacket from <Picture 1> are retained.`;

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const logs = [];
  page.on('console', m => logs.push(m.type() + ': ' + m.text().slice(0, 120)));
  await page.goto('http://127.0.0.1:8188/', { waitUntil: 'load', timeout: 90000 });
  await page.waitForTimeout(6000);
  const ok = await page.evaluate(() => !!(window.app && window.app.graph));
  console.log('ComfyUI 前端就绪:', ok);
  const wf = JSON.parse(fs.readFileSync(WF, 'utf8'));
  await page.evaluate((w) => { window.app.loadGraphData(w); }, wf);
  await page.waitForTimeout(3000);
  const set = await page.evaluate((txt) => {
    const out = {};
    const n = window.app.graph.getNodeById(127);
    if (n && n.widgets && n.widgets[0]) { n.widgets[0].value = txt; out.prompt = 'ok'; }
    const imgs = [142, 132, 146, 144, 140, 131];
    out.images = [];
    for (const id of imgs) {
      const node = window.app.graph.getNodeById(id);
      if (node && node.widgets && node.widgets[0]) { node.widgets[0].value = 'wenya_ref_0.jpg'; out.images.push(id); }
    }
    out.total = window.app.graph._nodes.length;
    out.missing = window.app.graph._nodes.filter(x => x.has_errors).map(x => x.id + ':' + x.type);
    return out;
  }, PROMPT);
  console.log('设置结果:', JSON.stringify(set));
  try {
    const res = await page.evaluate(async () => { await window.app.queuePrompt(0, 1); return 'queued'; });
    console.log('入队:', res);
  } catch (e) { console.log('入队失败:', String(e).slice(0, 200)); }
  await page.waitForTimeout(5000);
  await page.screenshot({ path: '/tmp/comfyui_h3.png' });
  console.log('前端日志:', logs.slice(-5));
  await browser.close();
})();