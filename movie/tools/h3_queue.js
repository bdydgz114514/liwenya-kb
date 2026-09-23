const fs = require('fs');
const { chromium } = require('/tmp/node_modules/playwright-core');
const WF = '/root/ComfyUI/user/default/workflows/视频/0005--MiniMax H3-潜空间二次放大--参考生成视频--新.json';

const S = (defs, summary, ret) => `subject_definitions:
<Subject 1> is the middle-aged Chinese man whose appearance comes from <Picture 1>: a weathered face, short thinning hair, wearing a dark worn jacket.

summary:
[reference generation] ${summary}

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - his weathered face, thinning hair and dark worn jacket from <Picture 1> are retained.`;

const JOBS = [
  S('', 'A cinematic 15-second shot in a flower nursery at dawn: <Subject 1> walks slowly between long rows of potted flowers, brushing the leaves with one hand, warm low sunlight and mist; the camera tracks alongside him at chest height, shallow depth of field, muted amber and green, 35mm film grain.'),
  S('', 'A cinematic 15-second shot in a dim rented room at night: <Subject 1> sits at a small desk writing on stacked papers under a single lamp, the window behind him dark with rain; slow push-in on his face, warm lamp against cold blue shadow, 35mm film grain.'),
  S('', 'A cinematic 15-second shot at two in the morning on a rooftop: <Subject 1> stands alone looking up at a star-filled sky above distant city lights, his breath visible in the cold air; the camera slowly tilts from his back up to the Milky Way, deep blue tones, 35mm film grain.'),
  S('', 'A cinematic 15-second shot in a bare room: <Subject 1> stands in front of a whiteboard covered in hand-drawn orbit diagrams, speaking earnestly and gesturing at the drawings; handheld camera, slight drift, warm tungsten light, muted colours, 35mm film grain.'),
  S('', 'A cinematic 15-second shot in a winter field: <Subject 1> in a thick coat writes in a small notebook beside high-voltage power lines, snow falling, his breath and the wires visible against a pale grey sky; slow lateral dolly, desaturated blue palette, 35mm film grain.'),
];

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
  await page.goto('http://127.0.0.1:8188/', { waitUntil: 'load', timeout: 90000 });
  await page.waitForTimeout(6000);
  const wf = JSON.parse(fs.readFileSync(WF, 'utf8'));
  await page.evaluate((w) => { window.app.loadGraphData(w); }, wf);
  await page.waitForTimeout(2500);
  for (let i = 0; i < JOBS.length; i++) {
    const r = await page.evaluate(async (txt) => {
      const n = window.app.graph.getNodeById(127);
      n.widgets[0].value = txt;
      [142, 132, 146, 144, 140, 131].forEach(id => {
        const node = window.app.graph.getNodeById(id);
        if (node && node.widgets && node.widgets[0]) node.widgets[0].value = 'wenya_ref_' + 0 + '.jpg';
      });
      await window.app.queuePrompt(0, 1);
      return 'queued ' + (window.app.graph._nodes.length);
    }, JOBS[i]);
    console.log('任务', i + 1, r);
    await page.waitForTimeout(1500);
  }
  const q = await page.evaluate(async () => {
    const res = await fetch('/queue'); const j = await res.json();
    return { running: j.queue_running.length, pending: j.queue_pending.length };
  });
  console.log('队列:', JSON.stringify(q));
  await browser.close();
})();