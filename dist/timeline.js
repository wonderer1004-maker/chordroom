(function(root){
 const names=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
 function chord(c,amount){if(c==='N.C.')return c;return c.replace(/[A-G](?:#|b)?/g,r=>{const flats={Db:'C#',Eb:'D#',Gb:'F#',Ab:'G#',Bb:'A#'};const i=names.indexOf(flats[r]||r);return names[((i+amount)%12+12)%12]})}
 function timing(song){const count=song.sections.reduce((n,s)=>n+s[1].length,0);const parts=(song.meter||'4/4').split('/').map(Number);const beats=parts[0]*4/parts[1]||4;const step=60/(song.bpm||80)*beats;const starts=song.times?.length===count?song.times.slice():Array.from({length:count},(_,i)=>i*step);return {starts,duration:song.duration||(starts.at(-1)||0)+(song.audio?2:step)}}
 function indexAt(times,t){let low=0,high=times.length;while(low<high){const mid=(low+high)>>1;if(times[mid]<=t)low=mid+1;else high=mid}return low-1}
 function parseLRC(text){const result=[];const offset=Number(text.match(/\[offset:([+-]?\d+)\]/i)?.[1]||0)/1000;for(const line of text.split(/\r?\n/)){const stamps=[...line.matchAll(/\[(\d+):(\d{2})(?:[.:](\d{1,3}))?\]/g)];const lyric=line.replace(/\[[^\]]*\]/g,'').trim();for(const m of stamps){if(Number(m[2])>=60)continue;result.push({time:Math.max(0,Number(m[1])*60+Number(m[2])+Number('0.'+(m[3]||0))+offset),text:lyric})}}return result.sort((a,b)=>a.time-b.time)}
 function toLRC(rows){return rows.map(r=>{const t=Math.round(r.time*100);return '['+String(Math.floor(t/6000)).padStart(2,'0')+':'+String(Math.floor(t/100)%60).padStart(2,'0')+'.'+String(t%100).padStart(2,'0')+']'+r.text}).join('\n')}
 const api={chord,timing,indexAt,parseLRC,toLRC};if(typeof module!=='undefined')module.exports=api;else root.ChordTimeline=api;
})(typeof window!=='undefined'?window:globalThis);
