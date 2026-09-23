const fs = require('fs');
const { chromium } = require('/tmp/node_modules/playwright-core');
const WF = '/root/ComfyUI/user/default/workflows/视频/0005--MiniMax H3-潜空间二次放大--参考生成视频--新.json';
const PROMPT = `subject_definitions:
<Subject 1> is the middle-aged Chinese man whose appearance comes from <Picture 1>: a weathered face, short thinning hair, wearing a dark worn jacket. His voice comes from the reference audio.

summary:
[reference generation] A cinematic 15-second shot of <Subject 1> standing under high-voltage power lines at dusk, holding a stopwatch, speaking quietly to the camera in his own voice about observing the sun through the wires; slow push-in, shallow depth of field, amber backlight and deep teal shadow, 35mm film grain.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - his weathered face, thinning hair, dark worn jacket and the timbre of his voice from the reference audio are retained.`;

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
  await page.goto('http://127.0.0.1:8188/', { waitUntil: 'load', timeout: 90000 });
  await page.waitForTimeout(6000);
  const wf = JSON.parse(fs.readFileSync(WF, 'utf8'));
  await page.evaluate((w) => { window.app.loadGraphData(w); }, wf);
  await page.waitForTimeout(2500);
  const info = await page.evaluate(async (txt) => {
    const out = {};
    window.app.graph.getNodeById(127).widgets[0].value = txt;
    // 参考图 → 他本人的帧
    [142, 132, 146, 144, 140, 131].forEach(id => {
      const n = window.app.graph.getNodeById(id);
      if (n && n.widgets && n.widgets[0]) n.widgets[0].value = 'wenya_ref_0.jpg';
    });
    // 参考音频 → 他自己的声音
    [149, 150].forEach(id => {
      const n = window.app.graph.getNodeById(id);
      if (n && n.widgets && n.widgets[0]) { n.widgets[0].value = 'wenya_voice_01.wav'; out['audio' + id] = 'set'; }
    });
    // 保持 bf16 高质量
    const unet = window.app.graph.getNodeById(39);
    unet.widgets[0].value = 'minimax_h3_ref2va_bf16.safetensors'; out.unet = 'bf16';
    const lora = window.app.graph.getNodeById(56);
    if (lora && lora.widgets[1]) { lora.widgets[1].value = 0.35; out.lora = 0.35; }
    const sch = window.app.graph.getNodeById(69);
    if (sch && sch.widgets[1]) { sch.widgets[1].value = 14; out.steps = 14; }
    await window.app.queuePrompt(0, 1);
    const res = await fetch('/queue'); const j = await res.json();
    out.queue = { running: j.queue_running.length, pending: j.queue_pending.length };
    return out;
  }, PROMPT);
  console.log('入队结果:', JSON.stringify(info));
  await browser.close();
})();