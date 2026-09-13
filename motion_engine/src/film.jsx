import React,{useLayoutEffect,useRef,useState} from 'react';
import {AbsoluteFill, Audio, Img, Sequence, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

export const durationFrames = m => Math.max(1, (m.scenes || []).reduce((sum,s)=>sum+Math.round(s.duration*30),0));
const palettes = {
  'field-journal': {bg:'#ede8db', ink:'#243a32', accent:'#a16b22', soft:'#d8d4c2', line:'#9da99b'},
  midnight: {bg:'#101d26', ink:'#f3edde', accent:'#edbb65', soft:'#20343e', line:'#5b797e'},
  blueprint: {bg:'#102f45', ink:'#e8f5f6', accent:'#71d8d5', soft:'#1c465e', line:'#3f7588'},
};
const ease = t => 1-Math.pow(1-Math.max(0,Math.min(1,t)),3);

function Diagram({scene, p, t}) {
  const labels = scene.labels || [];
  const gold = '#d9a33e';
  const flow = scene.component === 'flow';
  if(scene.component==='summary') return <div style={{display:'grid',gap:28,padding:'40px 12px'}}>{(labels.length?labels:['Observe the details','Compare the evidence','Keep exploring']).map((text,i)=><div key={i} style={{display:'flex',alignItems:'center',gap:30,padding:'35px 30px',background:p.soft,borderRadius:18,opacity:ease((t-i*.3)*2),transform:`translateY(${(1-ease((t-i*.3)*2))*25}px)`}}><span style={{color:p.accent,fontFamily:'DM Serif Display',fontSize:56}}>0{i+1}</span><span style={{fontSize:32,lineHeight:1.4}}>{text}</span></div>)}</div>;
  if (scene.component === 'comparison') return <svg viewBox="0 0 920 720" width="100%" height="100%">
    {[0,1].map((n)=><g key={n} transform={`translate(${n*470},0)`}>
      <rect x="8" y="20" width="434" height="650" rx="28" fill={p.soft}/>
      <path d={n===0?'M90 305L142 181 280 160 360 259 311 412 172 435Z':'M105 220L258 137 357 245 318 415 144 439 88 345Z'} fill={n===0?gold:p.line} stroke={p.ink} strokeWidth="3" transform={`translate(0,${Math.sin(t+n)*8})`}/>
      <text x="225" y="550" textAnchor="middle" fontFamily="DM Sans" fontSize="25" fill={p.ink}>{labels[n] || `Observation ${n+1}`}</text>
      <path d="M170 605H280" stroke={p.accent} strokeWidth="5"/>
    </g>)}
  </svg>;
  if(scene.component === 'timeline') return <svg viewBox="0 0 920 720" width="100%" height="100%">
    <path d="M155 95V635" stroke={p.line} strokeWidth="4"/>
    {(labels.length ? labels : ['Observe','Record','Compare']).map((l,i)=><g key={i} opacity={ease((t-i*.35)*2)}>
      <circle cx="155" cy={125+i*150} r="16" fill={p.accent}/><text x="212" y={135+i*150} fill={p.ink} fontSize="27" fontFamily="DM Sans">{l}</text>
      <text x="65" y={134+i*150} fill={p.accent} fontSize="22">0{i+1}</text>
    </g>)}
  </svg>;
  if (scene.component === 'cutaway' || flow) return <svg viewBox="0 0 920 720" width="100%" height="100%">
    <defs><marker id={`arrow-${scene.id}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5 0 10Z" fill={p.accent}/></marker></defs>
    <rect x="0" y="65" width="920" height="530" rx="30" fill={p.soft}/>
    <path d="M0 410Q210 350 450 420T920 400V650H0Z" fill="#72664c"/>
    <path d="M0 510Q250 450 500 530T920 510V650H0Z" fill="#4e5141"/>
    <path d="M0 590Q300 525 560 605T920 585V650H0Z" fill="#323d36"/>
    {flow ? <>
      {[0,1,2].map(n=><path key={n} d={`M45 ${105+n*43} Q300 ${80+n*43} 490 ${110+n*43} T865 ${105+n*43}`} fill="none" stroke={p.accent} strokeWidth="4" strokeDasharray="18 15" strokeDashoffset={-t*42} markerEnd={`url(#arrow-${scene.id})`}/>)}
      <path d="M435 430L420 344 450 272 548 260 595 330 590 417Z" fill="#80928c" stroke={p.ink} strokeWidth="3"/>
      {Array.from({length:22},(_,n)=>{const q=(t*.10+n*.047)%1;const x=65+q*770;const y=140+n%4*18+Math.max(0,q-.68)*640;return <circle key={n} cx={x} cy={y} r={3+n%3} fill={gold}/>})}
      {Array.from({length:12},(_,n)=>{const q=(t*.14+n*.089)%1;return <circle key={'sand'+n} cx={40+q*820} cy={90+n%3*24} r="2.5" fill={p.line}/>})}
    </> : <>
      {scene.diagram==='river-bed'?<>
        {Array.from({length:42},(_,n)=><ellipse key={n} cx={30+n%14*66} cy={435+Math.floor(n/14)*42+Math.sin(n)*12} rx={14+n%4*3} ry="11" fill={n%2?p.line:'#b3ad97'} transform={`rotate(${n*13} ${30+n%14*66} ${435+Math.floor(n/14)*42+Math.sin(n)*12})`}/>)}
        {Array.from({length:12},(_,n)=><circle key={'gold'+n} cx={160+n*52} cy={552+Math.sin(n*2)*13} r="5" fill={gold}/>)}
      </>:<>
        <path d="M320 648L393 533 348 450 434 330 475 242" stroke="#ece7ce" strokeWidth="43" fill="none"/>
        <path d="M322 645L391 534 350 450 434 330 475 242" stroke={gold} strokeWidth="8" strokeDasharray="8 15" fill="none"/>
      </>}
      {[0,1,2].map((n)=><path key={n} d={`M${560+n*65} ${290+n*90}h110`} stroke={p.accent} strokeWidth="3" markerEnd={`url(#arrow-${scene.id})`}/>)}
    </>}
    <text x="30" y="700" fontFamily="DM Sans" fontSize="19" letterSpacing="3" fill={p.ink}>CONCEPTUAL ILLUSTRATION · NOT TO SCALE</text>
  </svg>;
  return <svg viewBox="0 0 920 720" width="100%" height="100%">
    {[0,1,2,3].map(n=><ellipse key={n} cx="460" cy="348" rx={170+n*66} ry={118+n*51} fill="none" stroke={p.line} strokeWidth="2" opacity={.6} transform={`rotate(${-20+n*8} 460 348)`}/>)}
    <path d="M287 400L306 257 441 183 579 237 630 376 524 487 373 495Z" fill={p.soft} stroke={p.ink} strokeWidth="4" transform={`translate(0,${Math.sin(t)*8})`}/>
    <path d="M306 257L446 324 441 183M446 324L630 376M446 324L373 495" stroke={p.accent} strokeWidth="4" fill="none"/>
    <circle cx="446" cy="324" r={18+Math.sin(t*2)*3} fill={gold}/>
    <path d="M458 310L651 169H842" stroke={p.accent} strokeWidth="3" fill="none"/>
    <text x="650" y="144" fill={p.ink} fontSize="22" fontFamily="DM Sans">{labels[0] || 'LOOK CLOSER'}</text>
  </svg>;
}

function Scene({scene, style, index, total}) {
  const contentRef=useRef(null);
  const [fit,setFit]=useState(1);
  const {width}=useVideoConfig();
  useLayoutEffect(()=>{
    const node=contentRef.current;
    if(!node)return;
    const measure=()=>{if(node.clientWidth>0)setFit(Math.min(1,1380/Math.max(1,node.scrollHeight)));};
    measure();
    const observer=new ResizeObserver(measure);
    observer.observe(node);
    let active=true;
    document.fonts.ready.then(()=>{if(active)measure();});
    return ()=>{active=false;observer.disconnect();};
  },[width,scene.title,scene.text,scene.component,(scene.labels||[]).join('|')]);
  const f = useCurrentFrame(), t=f/30, frames=Math.round(scene.duration*30);
  const p=palettes[style] || palettes['field-journal'];
  const enter=ease(f/20), exit=ease((frames-1-f)/12);
  const opacity=scene.transition==='cut'?1:Math.min(enter,exit);
  const scale=scene.motion==='push-in'?1+t*.005:1;
  const dy=scene.motion==='float'?Math.sin(t)*12:scene.motion==='glide'?-t*4:0;
  const image=scene.asset_url;
  const large=scene.component==='title';
  const caption=(scene.captions||[]).find(c=>t>=c.start&&t<c.end)?.text || '';
  return <AbsoluteFill style={{background:p.bg,color:p.ink,fontFamily:'DM Sans',padding:'136px 80px 240px',overflow:'hidden'}}>
    <AbsoluteFill style={{backgroundImage:`radial-gradient(${p.line}55 1px, transparent 1px)`,backgroundSize:'22px 22px',opacity:.25}}/>
    <div style={{position:'absolute',top:85,left:80,right:100,display:'flex',justifyContent:'space-between',fontSize:20,letterSpacing:4,borderBottom:`2px solid ${p.line}`,paddingBottom:20}}><b>GOLDGEN</b><span>FIELD NOTES / {String(index+1).padStart(2,'0')}</span></div>
    <div ref={contentRef} style={{width:width-160,flexShrink:0,opacity,transform:`translateX(${scene.transition==='push'?(1-enter)*100:0}px) scale(${fit})`,transformOrigin:'top left',position:'relative'}}>
      <div style={{fontSize:19,letterSpacing:4,color:p.accent,marginTop:56,marginBottom:26,textTransform:'uppercase'}}>{scene.component === 'flow'?'Follow the process':scene.component === 'comparison'?'Observe the differences':'A closer look'}</div>
      <h1 style={{fontFamily:'DM Serif Display',fontWeight:400,fontSize:scene.title.length>85?66:large?92:78,lineHeight:1.08,margin:'0 0 30px',overflowWrap:'anywhere'}}>{scene.title}</h1>
      <div style={{position:'relative',height:large?680:620,marginTop:35,overflow:'hidden',borderRadius:24,transform:`translateY(${dy}px) scale(${scale})`}}>
        {image ? <>
          {scene.component==='parallax' && <Img src={image} style={{position:'absolute',width:'100%',height:'100%',objectFit:'cover',filter:'blur(20px)',transform:`scale(${1.2+t*.004})`,opacity:.5}}/>}
          <Img src={image} style={{position:'absolute',width:'100%',height:'100%',objectFit:scene.component==='parallax'?'contain':'cover',objectPosition:`${scene.focal_x}% ${scene.focal_y}%`,transform:scene.component==='parallax'?`translateX(${Math.sin(t*.4)*14}px) scale(.88)`:'none'}}/>
          {scene.component==='annotated' && <svg viewBox="0 0 920 620" style={{position:'absolute',inset:0,width:'100%',height:'100%'}}><circle cx="460" cy="310" r="85" fill="none" stroke="#f4c767" strokeWidth="5" strokeDasharray="14 8"/><path d="M550 300L740 150H855M550 300l32-7m-32 7l14-32" fill="none" stroke="#f4c767" strokeWidth="6"/></svg>}
        </> : <Diagram scene={scene} p={p} t={t}/>}
      </div>
      <div style={{display:'flex',flexWrap:'wrap',gap:12,margin:'24px 0'}}>{(scene.labels||[]).map((l,i)=><span key={i} style={{fontSize:23,padding:'10px 17px',border:`1px solid ${p.line}`,borderRadius:6,opacity:ease((t-i*.15)*3)}}>{l}</span>)}</div>
      <p style={{fontSize:scene.text.length>200?32:38,lineHeight:1.42,margin:'24px 0 0',maxWidth:860,overflowWrap:'anywhere'}}>{scene.text}</p>
    </div>
    {caption && <div style={{position:'absolute',left:90,right:100,bottom:185,background:'#10231eea',color:'#fff9e8',padding:'18px 24px',fontSize:29,lineHeight:1.35,borderRadius:10,textAlign:'center'}}>{caption}</div>}
    <div style={{position:'absolute',left:80,right:100,bottom:122,display:'flex',justifyContent:'space-between',fontSize:18,color:p.accent,letterSpacing:2}}><span>OBSERVE · TEST · COMPARE</span><span>{index+1} / {total}</span></div>
    <div style={{position:'absolute',height:5,bottom:94,left:80,right:100,background:p.soft}}><div style={{height:'100%',width:`${100*f/frames}%`,background:p.accent}}/></div>
    {scene.audio_url && <Audio src={scene.audio_url}/>}
  </AbsoluteFill>;
}

export function Film({manifest}) {
  let offset=0;
  const frame=useCurrentFrame();
  const duration=durationFrames(manifest);
  const active=(()=>{let o=0;for(const s of manifest.scenes){o+=Math.round(s.duration*30);if(frame<o)return s;}return {};})();
  return <AbsoluteFill>{manifest.scenes.map((s,i)=>{const from=offset;offset+=Math.round(s.duration*30);return <Sequence key={s.id} from={from} durationInFrames={Math.round(s.duration*30)}><Scene scene={s} style={manifest.style} index={i} total={manifest.scenes.length}/></Sequence>})}
    {manifest.music_url && <Audio src={manifest.music_url} loop volume={f=>Math.min(1,f/30,(duration-f)/30)*(active.audio_url ? .07:.16)}/>}
  </AbsoluteFill>;
}
