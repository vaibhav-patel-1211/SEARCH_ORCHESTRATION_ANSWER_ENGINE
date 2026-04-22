// Auth_Screen/signup.jsx
import React, { useState, useEffect, useRef } from 'react';
import { authAPI } from '../services/api';
import './login.css';

/* ── pixel helpers ── */
const P = (ctx,c,x,y,w,h) => { ctx.fillStyle=c; ctx.fillRect(x,y,w,h); };

function drawCrab(ctx, x, y, frame, dead) {
  if (dead) {
    P(ctx,'#C0432A',x+4,y+4,30,22); P(ctx,'#d45030',x+6,y+6,26,18);
    P(ctx,'#111',x+6,y+4,6,6);      P(ctx,'#111',x+26,y+4,6,6);
    P(ctx,'#fff',x+6,y+4,3,3);      P(ctx,'#fff',x+26,y+4,3,3);
    P(ctx,'#C0432A',x,y+10,5,6);    P(ctx,'#C0432A',x+33,y+10,5,6);
    P(ctx,'#C0432A',x+8,y+26,5,6);  P(ctx,'#C0432A',x+18,y+26,5,6);
    ctx.fillStyle='#fff'; ctx.font='bold 10px sans-serif';
    ctx.fillText('x',x+7,y+12); ctx.fillText('x',x+27,y+12);
    return;
  }
  P(ctx,'#C0432A',x+6,y+8,26,20);  P(ctx,'#d45030',x+8,y+10,22,16);
  P(ctx,'#c84a35',x+11,y+13,16,9);
  P(ctx,'#C0432A',x+8,y+2,6,8);    P(ctx,'#C0432A',x+24,y+2,6,8);
  P(ctx,'#111',x+8,y+0,6,6);       P(ctx,'#111',x+24,y+0,6,6);
  P(ctx,'#fff',x+8,y+0,3,3);       P(ctx,'#fff',x+24,y+0,3,3);
  P(ctx,'#C0432A',x+0,y+8,8,6);    P(ctx,'#C0432A',x+0,y+5,4,6);
  P(ctx,'#C0432A',x+30,y+8,8,6);   P(ctx,'#C0432A',x+34,y+5,4,6);
  const lo = frame%2===0?0:3;
  P(ctx,'#C0432A',x+10,y+28,4,8-lo); P(ctx,'#8a2e1a',x+8,y+34-lo,6,2);
  P(ctx,'#C0432A',x+18,y+28,4,6+lo); P(ctx,'#8a2e1a',x+16,y+32+lo,6,2);
  P(ctx,'#C0432A',x+26,y+28,4,8-lo); P(ctx,'#8a2e1a',x+24,y+34-lo,6,2);
  P(ctx,'#8a2e1a',x+13,y+26,12,3);
}

function drawRock(ctx,x,y,w,h) {
  ctx.fillStyle='#b89040'; ctx.beginPath();
  ctx.roundRect(x,y,w,h,4); ctx.fill();
  ctx.fillStyle='#d4a840'; ctx.fillRect(x+3,y+2,w*.4,h*.28);
  ctx.fillStyle='#886020'; ctx.fillRect(x+2,y+h-3,w-4,3);
}

function drawSeaweed(ctx,x,y,w,h) {
  const s=x+w/2-4;
  ctx.fillStyle='#2a6e40'; ctx.fillRect(s,y,8,h);
  ctx.fillStyle='#3a9058'; ctx.fillRect(x,y+h*.25,s-x+4,6); ctx.fillRect(s+4,y+h*.6,x+w-s-4,6);
  ctx.fillStyle='#4aaa68'; ctx.fillRect(s+2,y+2,4,h-4);
}

function drawBird(ctx,x,y,frame) {
  const wy=frame===0?0:5;
  ctx.fillStyle='#C0432A'; ctx.fillRect(x,y+6,28,12); ctx.fillRect(x+22,y+2,12,14);
  ctx.fillStyle='#8a2e1a'; ctx.fillRect(x,y+14,28,5); ctx.fillRect(x+4,y+wy,16,7);
  ctx.fillStyle='#111'; ctx.fillRect(x+26,y+4,5,5);
  ctx.fillStyle='#fff'; ctx.fillRect(x+26,y+4,2,2);
  ctx.fillStyle='#e8a020'; ctx.fillRect(x+32,y+8,9,4);
}

function lerp(c1,c2,t) {
  const h=s=>{const r=parseInt(s.slice(1),16);return[(r>>16)&255,(r>>8)&255,r&255];};
  if(!c1.startsWith('#')||!c2.startsWith('#')) return c1;
  const [a,b]=[h(c1),h(c2)];
  return `rgb(${Math.round(a[0]+(b[0]-a[0])*t)},${Math.round(a[1]+(b[1]-a[1])*t)},${Math.round(a[2]+(b[2]-a[2])*t)})`;
}

/* ── icons ── */
const GoogleIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24">
    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/>
    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
  </svg>
);

/* ══════════════════════════════════════════
   SIGN UP
══════════════════════════════════════════ */
export default function Signup({ onSwitchToLogin, onSignupSuccess }) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [score, setScore] = useState(0);
  const [hiScore, setHiScore] = useState(0);
  const [isDead,  setIsDead]  = useState(false);
  const [deadScore,setDeadScore]=useState(0);

  const canvasRef = useRef(null);
  const wrapRef   = useRef(null);

  /* all game state */
  const g = useRef({
    W:0, H:0, GY:0,
    crabX:80, crabY:300, crabVY:0, onGround:true,
    frame:0, frameT:0,
    obstacles:[], clouds:[], stars:[],
    score:0, hi:0, speed:4.5,
    spawnClock:0, spawnInterval:140,
    groundOff:0, dayT:1.0,
    phase:'running',
    restartTimer:0,
    raf:null,
  }).current;

  useEffect(()=>{
    for(let i=0;i<6;i++) g.clouds.push({ x:Math.random()*900, y:25+Math.random()*70, w:55+Math.random()*65, sp:.3+Math.random()*.8 });
    for(let i=0;i<60;i++) g.stars.push({ x:Math.random()*900, y:Math.random()*220, sz:Math.random()<.25?2:1, a:.3+Math.random()*.7 });
  // eslint-disable-next-line
  },[]);

  useEffect(()=>{
    const wrap=wrapRef.current, cv=canvasRef.current;
    if(!wrap||!cv) return;
    const ro=new ResizeObserver(([e])=>{
      const {width:W,height:H}=e.contentRect;
      cv.width =Math.round(W); cv.height=Math.round(H);
      g.W=cv.width; g.H=cv.height;
      g.GY=Math.round(H*0.84);
      g.crabX=Math.round(W*0.12);
      if(g.onGround) g.crabY=g.GY-34;
      if(g.spawnClock===0) g.spawnClock=Math.round(W*1.3);
    });
    ro.observe(wrap);
    return()=>ro.disconnect();
  // eslint-disable-next-line
  },[]);

  useEffect(()=>{
    const cv=canvasRef.current;
    if(!cv) return;

    const tick=()=>{
      const ctx=cv.getContext('2d');
      const {W,H,GY}=g;
      if(!W||!H){ g.raf=requestAnimationFrame(tick); return; }

      ctx.clearRect(0,0,W,H);

      g.dayT+=0.0004;
      const day=(Math.sin(g.dayT)+1)/2;
      const sg=ctx.createLinearGradient(0,0,0,GY);
      sg.addColorStop(0,lerp('#0a0820','#48a8d8',day));
      sg.addColorStop(1,lerp('#1a1040','#b8dff0',day));
      ctx.fillStyle=sg; ctx.fillRect(0,0,W,GY);

      if(day<0.5){
        ctx.globalAlpha=Math.max(0,(0.5-day)*2);
        g.stars.forEach(s=>{ ctx.fillStyle=`rgba(255,255,255,${s.a})`; ctx.fillRect(s.x%W,s.y%(GY*.88),s.sz,s.sz); });
        ctx.globalAlpha=1;
      }

      const sx=W-65, sy=52;
      if(day>0.05){
        ctx.globalAlpha=Math.min(1,(day-.05)/.35);
        ctx.fillStyle='#ffe066'; ctx.beginPath(); ctx.arc(sx,sy,20,0,Math.PI*2); ctx.fill();
        ctx.fillStyle='rgba(255,224,100,.15)'; ctx.beginPath(); ctx.arc(sx,sy,30,0,Math.PI*2); ctx.fill();
        ctx.globalAlpha=1;
      } else {
        ctx.fillStyle='#dde'; ctx.beginPath(); ctx.arc(sx,sy,16,0,Math.PI*2); ctx.fill();
        ctx.fillStyle=lerp('#0a0820','#1a1040',day); ctx.beginPath(); ctx.arc(sx-5,sy-3,13,0,Math.PI*2); ctx.fill();
      }

      g.clouds.forEach(c=>{
        if(g.phase==='running'){ c.x-=c.sp; if(c.x+c.w<0) c.x=W+10; }
        ctx.globalAlpha=.2+day*.7;
        ctx.fillStyle='rgba(255,255,255,0.85)';
        ctx.beginPath();
        ctx.ellipse(c.x+c.w*.5,c.y+10,c.w*.52,10,0,0,Math.PI*2);
        ctx.ellipse(c.x+c.w*.28,c.y+13,c.w*.3,12,0,0,Math.PI*2);
        ctx.ellipse(c.x+c.w*.74,c.y+14,c.w*.26,10,0,0,Math.PI*2);
        ctx.fill();
        ctx.globalAlpha=1;
      });

      ctx.fillStyle=day<.4?'rgba(10,5,60,.25)':'rgba(55,135,200,.18)';
      ctx.fillRect(0,GY-11,W,13);

      const gg=ctx.createLinearGradient(0,GY,0,H);
      gg.addColorStop(0,lerp('#3c3c3c','#d4a848',day));
      gg.addColorStop(1,lerp('#242424','#b07020',day));
      ctx.fillStyle=gg; ctx.fillRect(0,GY,W,H-GY);
      ctx.fillStyle=lerp('#1a1a1a','#b88820',day); ctx.fillRect(0,GY,W,3);
      if(g.phase==='running') g.groundOff=(g.groundOff+g.speed)%30;
      ctx.fillStyle='rgba(0,0,0,.07)';
      for(let x=-g.groundOff;x<W;x+=30) ctx.fillRect(x,GY+7,12,2);

      if(g.phase==='running'){
        g.speed=4.5+g.score*.0025;

        const gObs=g.obstacles.filter(o=>!o.bird&&o.x>g.crabX&&o.x-g.crabX<W*.42).sort((a,b)=>a.x-b.x);
        if(gObs.length){
          const dist=gObs[0].x-(g.crabX+36);
          if(dist<g.speed*28&&g.onGround){ g.crabVY=-14.5; g.onGround=false; }
        }
        const bObs=g.obstacles.filter(o=>o.bird&&o.x>g.crabX&&o.x-g.crabX<W*.38&&o.y>GY-85).sort((a,b)=>a.x-b.x);
        if(bObs.length){
          const dist=bObs[0].x-(g.crabX+36);
          if(dist<g.speed*24&&g.onGround){ g.crabVY=-14.5; g.onGround=false; }
        }

        g.spawnClock--;
        if(g.spawnClock<=0){
          const bird=Math.random()<.2, tall=Math.random()>.5;
          const h=bird?20:(tall?34:18);
          const w=bird?34:(tall?16:24);
          g.obstacles.push({ x:W+10, y:bird?GY-60-Math.random()*18:GY-h, w,h, bird, bf:0, tall });
          g.spawnInterval=Math.max(70,130-g.score*.08);
          g.spawnClock=Math.round(g.spawnInterval+Math.random()*80);
        }

        g.obstacles=g.obstacles.filter(o=>o.x+o.w>-10);
        for(const o of g.obstacles){
          o.x-=g.speed;
          if(o.bird){ o.bf=(o.bf+.15)%2; drawBird(ctx,o.x,o.y,Math.floor(o.bf)); }
          else if(o.tall) drawSeaweed(ctx,o.x,o.y,o.w,o.h);
          else drawRock(ctx,o.x,o.y,o.w,o.h);
        }

        g.crabVY+=0.68; g.crabY+=g.crabVY;
        if(g.crabY>=GY-34){ g.crabY=GY-34; g.crabVY=0; g.onGround=true; }
        if(g.onGround){ g.frameT++; if(g.frameT>7){g.frame=(g.frame+1)%4;g.frameT=0;} }
        drawCrab(ctx,g.crabX,g.crabY,g.frame,false);

        const cx1=g.crabX+9,cy1=g.crabY+7,cx2=g.crabX+29,cy2=g.crabY+30;
        for(const o of g.obstacles){
          if(cx1<o.x+o.w-3&&cx2>o.x+3&&cy1<o.y+o.h-3&&cy2>o.y+3){
            g.phase='dead';
            const sc=Math.floor(g.score);
            if(sc>g.hi) g.hi=sc;
            setDeadScore(sc); setHiScore(g.hi); setIsDead(true);
            g.restartTimer=150;
            break;
          }
        }

        g.score+=.12;
        if(Math.floor(g.score)%5===0) setScore(Math.floor(g.score));

      } else {
        for(const o of g.obstacles){
          if(o.bird) drawBird(ctx,o.x,o.y,0);
          else if(o.tall) drawSeaweed(ctx,o.x,o.y,o.w,o.h);
          else drawRock(ctx,o.x,o.y,o.w,o.h);
        }
        drawCrab(ctx,g.crabX,g.crabY,0,true);

        g.restartTimer--;
        if(g.restartTimer<=0){
          g.phase='running';
          g.crabVY=0; g.onGround=true; g.crabY=GY-34;
          g.obstacles=[]; g.score=0; g.speed=4.5;
          g.spawnClock=Math.round(W*1.1);
          g.frame=0; g.frameT=0;
          setScore(0); setIsDead(false);
        }
      }

      g.raf=requestAnimationFrame(tick);
    };

    g.raf=requestAnimationFrame(tick);
    return()=>{ cancelAnimationFrame(g.raf); };
  // eslint-disable-next-line
  }, []);

  const handleSignup = async () => {
    if (!name.trim() || !email.trim() || !password.trim()) return;
    setLoading(true);
    setError('');
    try {
      await authAPI.signup(name, email, password);
      await authAPI.login(email, password);
      onSignupSuccess();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">

      {/* ══ LEFT — SIGN UP ══ */}
      <div className="login-left">
        <div className="left-inner">

          <div className="brand">
            <img src="/favicon.svg" alt="Horizon" className="brand-logo"/>
            <span className="brand-name">Horizon</span>
          </div>

          <div className="headline">
            <h1>Create your<br/><em>account</em></h1>
          </div>

          <p className="tagline">
            Join Horizon to unlock AI-powered<br/>research, coding, and more.
          </p>

          <div className="auth-card">
            <p className="auth-card-title">
              Get started — it's free
            </p>


            {error && <p className="error-msg" style={{color: 'red', textAlign: 'center', marginBottom: 10}}>{error}</p>}



            <input
              className="email-input"
              type="text"
              placeholder="Full name"
              value={name}
              onChange={e => setName(e.target.value)}
            />

            <input
              className="email-input"
              type="email"
              placeholder="name@yourcompany.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
            />

            <input
              className="email-input"
              type="password"
              placeholder="Create a password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              onKeyDown={e => e.key==='Enter' && name.trim() && email.trim() && password.trim() && handleSignup()}
            />

            <button className="btn-email" type="button" disabled={loading}
              onClick={handleSignup}>
              {loading ? 'Creating account...' : 'Create account'}
            </button>

            <p className="switch-auth">
              Already have an account?{' '}
              <button className="switch-auth-btn" onClick={onSwitchToLogin}>
                Sign in
              </button>
            </p>

          </div>

        </div>
      </div>

      {/* ══ RIGHT — AUTO-PLAY GAME ══ */}
      <div className="login-right">
        <div className="game-container">

          <div className="game-topbar">
            <div className="game-topbar-left">
              <div className="topbar-dots">
                <div className="topbar-dot td-red"/>
                <div className="topbar-dot td-yellow"/>
                <div className="topbar-dot td-green"/>
              </div>
              <span className="topbar-title">🦀 Claud-O's Beach Runner</span>
            </div>
            <div className="topbar-scores">
              <span className="topbar-score ts-current">{String(score).padStart(5,'0')}</span>
              <span className="topbar-score ts-hi">HI {String(hiScore).padStart(5,'0')}</span>
            </div>
          </div>

          <div className="canvas-area" ref={wrapRef}>
            <canvas ref={canvasRef} className="game-canvas"/>
            {isDead&&(
              <div className="demo-death-flash">
                <span style={{fontSize:30}}>💥</span>
                <span className="death-score">{deadScore}</span>
                {deadScore>=hiScore&&deadScore>0&&<span className="death-record">★ New Best!</span>}
                <span className="death-restart">Restarting…</span>
              </div>
            )}
          </div>

          <div className="game-bottombar">
            <div className="demo-dot"/>
            <span className="demo-label">Live Demo — AI plays automatically</span>
            <div className="demo-dot"/>
          </div>

        </div>
      </div>

    </div>
  );
}
