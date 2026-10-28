const assert=require('node:assert/strict'),S=require('./dist/score-core.js');
assert.equal(S.beatAt(1.5,120,0,'3/4').beat,0);
assert.equal(S.beatAt(.25,120,0,'6/8').beat,1);
assert.equal(S.beatAt(.4,120,.7,'4/4').started,false);
for(const bpm of [90,120,150]){const sr=4000,samples=new Float32Array(sr*16);for(let t=.7;t<16;t+=60/bpm)for(let j=0;j<80;j++)samples[Math.floor(t*sr)+j]=Math.exp(-j/12);const pulse=S.detectPulse(samples,sr);assert(Math.abs(pulse.bpm-bpm)<=2);assert(Math.abs(pulse.offset-.7)<.03)}
assert.equal(S.detectPulse(new Float32Array(64000),4000),null);
const manual=S.parseScore('[00:12.50][C]hello [G/B]world');
assert.equal(manual[0].time,12.5);assert.equal(manual[0].chords[1].at,6);assert.equal(manual[0].text,'hello world');
assert.throws(()=>S.parseScore('missing time'));
const song={sections:[['A',['C','G','Am']]]},timeline={starts:[0,2,4],duration:6};
const rows=S.lines(song,[{time:1,text:'hello world'},{time:3,text:'next line'}],timeline);
assert.equal(rows[0].chunks[0].chord,'C');assert.equal(rows[1].chunks[0].time,1);assert.equal(rows[1].chunks[0].chord,'C');
const pdf=S.pdf([{width:1,height:1,bytes:Uint8Array.of(255,216,255,217)}]),text=Buffer.from(pdf).toString('latin1'),xref=Number(text.match(/startxref\n(\d+)/)[1]);
assert.equal(text.slice(xref,xref+4),'xref');assert(text.includes('/Count 1'));
console.log('PASS source clock, meter, tempo/offset detection, silence, manual chord anchors, carried chords and PDF byte offsets');
