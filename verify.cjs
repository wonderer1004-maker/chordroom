const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('dist/app.js','utf8');
const detector=source.slice(source.indexOf('function fft('),source.indexOf("$('audioFile').onchange"));
const ctx=vm.createContext({});vm.runInContext("const notes=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];"+detector,ctx);
for(const [expected,midis] of [['C',[48,52,55]],['Am',[45,48,52]],['D',[50,54,57]],['G',[43,47,50]],['Em',[40,43,47]]]){
 const sr=44100,samples=new Float32Array(sr);
 for(let i=0;i<samples.length;i++)for(const midi of midis)for(let h=1;h<=3;h++)samples[i]+=.15/h*Math.sin(2*Math.PI*440*Math.pow(2,(midi-69)/12)*h*i/sr);
 ctx.samples=samples;const actual=vm.runInContext('detect(samples,44100,0)',ctx);assert.strictEqual(actual,expected);console.log('PASS synthetic triad '+expected);
}
ctx.samples=new Float32Array(9000);assert.strictEqual(vm.runInContext('detect(samples,44100,0)',ctx),'N.C.');console.log('PASS silence');
const html=fs.readFileSync('dist/index.html','utf8');for(const m of source.matchAll(/\$\('([^']+)'\)/g))assert(html.includes('id="'+m[1]+'"')||['dialogUpload'].includes(m[1]),'Missing DOM ID '+m[1]);console.log('PASS referenced DOM elements');
const helper=source.slice(source.indexOf('function shift('),source.indexOf('function list('));vm.runInContext(helper,ctx);assert.strictEqual(vm.runInContext("shift('Am',2)",ctx),'Bm');assert.strictEqual(vm.runInContext("shift('C',-1)",ctx),'B');console.log('PASS transpose');
