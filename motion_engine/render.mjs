import fs from 'node:fs';
import path from 'node:path';
import {renderMedia, renderStill, selectComposition, makeCancelSignal, openBrowser} from '@remotion/renderer';
const [input,output]=process.argv.slice(2);
const manifest=JSON.parse(fs.readFileSync(input,'utf8'));
const inputProps={manifest};
const serveUrl=path.resolve('build');
const browserExecutable=process.env.MOTION_BROWSER_PATH || undefined;
const puppeteerInstance=await openBrowser('chrome',{browserExecutable});
try {
const composition=await selectComposition({serveUrl,id:'GoldGen',inputProps,browserExecutable,puppeteerInstance});
const {cancelSignal,cancel}=makeCancelSignal();
process.on('SIGTERM',cancel);
await renderMedia({serveUrl,composition,inputProps,codec:'h264',outputLocation:output,
  browserExecutable, puppeteerInstance, concurrency: Number(process.env.MOTION_RENDER_CONCURRENCY || 1),
  scale: manifest.render_scale || 1, crf:20, x264Preset:'veryfast', cancelSignal,
  onProgress:({progress})=>console.log(JSON.stringify({progress:Math.round(progress*100)}))});
let offset=0;
for(let i=0;i<manifest.scenes.length;i++){
  const n=Math.round(manifest.scenes[i].duration*30);
  for(const [label,delta] of [['start',Math.min(20,n-1)],['middle',Math.floor(n/2)],['end',Math.max(0,n-15)]]){
    await renderStill({serveUrl,composition,inputProps,browserExecutable,puppeteerInstance,frame:offset+delta,
      output:path.join(path.dirname(output),`scene-${i+1}-${label}.png`),scale:.5});
  }
  offset+=n;
}
console.log(JSON.stringify({complete:true}));

} finally { await puppeteerInstance.close({silent:true}); }
