const assert=require('node:assert/strict');const T=require('./dist/timeline.js');
assert.equal(T.chord('C',-2),'A#');assert.equal(T.chord('Am',-2),'Gm');assert.equal(T.chord('D/F#',-2),'C/E');assert.equal(T.chord('Bbmaj7',2),'Cmaj7');assert.equal(T.chord('N.C.',5),'N.C.');assert.equal(T.chord('G',-250),'A');
// Real sounding pitch stays invariant for all fret/key combinations.
const names=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];for(const c of names)for(let capo=0;capo<=7;capo++)for(let transpose=-12;transpose<=12;transpose++)assert.equal(T.chord(T.chord(c,transpose-capo),capo),T.chord(c,transpose));
assert.deepEqual(T.timing({bpm:120,meter:'3/4',sections:[['A',['C','G']]]}),{starts:[0,1.5],duration:3});assert.equal(T.timing({bpm:60,meter:'6/8',sections:[['A',['C','G']]]}).duration,6);
assert.deepEqual(T.timing({audio:true,times:[0,2,4],duration:4.7,sections:[['A',['C','G','Am']]]}),{starts:[0,2,4],duration:4.7});
assert.equal(T.indexAt([2,4,6],0),-1);assert.equal(T.indexAt([2,4,6],4),1);assert.equal(T.indexAt([],12),-1);
const lrc='[ar:Artist]\n[offset:-500]\n[00:01.25][00:03.500]첫 줄\n[00:02.00]둘째 줄\n[00:04.00]\n[00:75]invalid';const rows=T.parseLRC(lrc);assert.deepEqual(rows,[{time:.75,text:'첫 줄'},{time:1.5,text:'둘째 줄'},{time:3,text:'첫 줄'},{time:3.5,text:''}]);assert.deepEqual(T.parseLRC(T.toLRC(rows)),rows);assert.deepEqual(T.parseLRC('가사만\n입력'),[]);
console.log('PASS capo invariance (2400 cases), slash/minor/flat chords, negative transpose, 3/4 and 6/8 clocks, audio duration, seeking boundaries, LRC offsets/repeated timestamps/round trip');
