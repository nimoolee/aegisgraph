"""Spatial, read-only REG dashboard renderer.

This module is presentation-only. It consumes the same immutable graph payload as the
standard REG view and never changes semantics, evidence, or target software.
"""

from __future__ import annotations

import html
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from aegis_graph.audit.invocations import resolve_output_path
from aegis_graph.ui._html_safety import json_for_script


def render_spatial_html(payload: Mapping[str, Any], *, title: str = "AegisGraph Spatial REG") -> str:
    """Render a self-contained 2.5D spatial REG dashboard."""

    data = json_for_script(payload)
    safe_title = html.escape(title)
    template = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>__TITLE__</title>
<style>
:root{
  color-scheme:dark;
  --bg:#05070b;--panel:rgba(12,18,27,.78);--panel2:rgba(17,25,36,.68);
  --line:rgba(124,154,184,.18);--text:#eef6ff;--muted:#8190a3;
  --cyan:#66d9ff;--blue:#74a8ff;--green:#50df91;--red:#ff6670;--yellow:#ffc95f;--violet:#b094ff;
}
*{box-sizing:border-box}
html,body{margin:0;width:100%;height:100%;overflow:hidden;background:var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
body:before{content:"";position:fixed;inset:0;background:
  radial-gradient(circle at 22% 18%,rgba(42,124,255,.13),transparent 30%),
  radial-gradient(circle at 72% 22%,rgba(116,80,255,.10),transparent 28%),
  radial-gradient(circle at 54% 82%,rgba(46,211,161,.08),transparent 32%),
  linear-gradient(180deg,#070b12 0%,#040609 58%,#020306 100%);pointer-events:none}
body:after{content:"";position:fixed;inset:0;opacity:.2;pointer-events:none;background-image:radial-gradient(rgba(255,255,255,.52) .55px,transparent .55px);background-size:34px 34px;mask-image:linear-gradient(to bottom,black,transparent 70%)}
.shell{position:relative;width:100%;height:100%;display:grid;grid-template-rows:94px minmax(0,1fr) 174px;grid-template-columns:minmax(0,1fr) 356px;z-index:1}
.topbar{grid-column:1/3;display:flex;align-items:center;gap:16px;padding:12px 18px;border-bottom:1px solid var(--line);background:linear-gradient(180deg,rgba(8,13,20,.96),rgba(8,13,20,.88));z-index:10}
.brand{min-width:255px}.brand-kicker{font-size:10px;letter-spacing:.22em;color:var(--cyan);text-transform:uppercase}.brand h1{font-size:18px;margin:3px 0 0}.brand h1 span{font-weight:500;color:var(--muted);font-size:12px;margin-left:8px}.stats{display:flex;gap:8px;overflow:auto;flex:1;padding-bottom:2px}.stat{min-width:94px;padding:8px 10px;border:1px solid var(--line);background:linear-gradient(180deg,rgba(25,36,50,.72),rgba(10,16,24,.58));border-radius:12px;box-shadow:0 12px 40px rgba(0,0,0,.14),inset 0 1px rgba(255,255,255,.04)}.stat label{display:block;color:var(--muted);font-size:9px;letter-spacing:.03em}.stat b{font-size:15px;line-height:1.5}.status-pass{color:var(--green)!important}.status-fail{color:var(--red)!important}.status-unknown{color:var(--yellow)!important}
.actions{display:flex;gap:7px}.btn{border:1px solid var(--line);background:rgba(20,29,40,.72);color:#cbd6e2;border-radius:9px;padding:8px 10px;font-size:11px;cursor:pointer}.btn:hover{border-color:rgba(102,217,255,.55);color:white}.btn.active{color:var(--cyan);border-color:rgba(102,217,255,.45);box-shadow:0 0 18px rgba(102,217,255,.12)}
.stage-wrap{position:relative;grid-column:1;grid-row:2;min-width:0;min-height:0;overflow:hidden}.stage-wrap:after{content:"";position:absolute;left:0;right:0;bottom:0;height:34%;pointer-events:none;background:linear-gradient(transparent,rgba(3,5,8,.52))}.hud{position:absolute;left:16px;top:14px;z-index:5;display:flex;gap:7px;align-items:center}.chip{font-size:10px;color:var(--muted);padding:6px 8px;border:1px solid var(--line);border-radius:999px;background:rgba(8,13,20,.88)}.chip strong{color:#dbe8f5;font-weight:600}.hint{position:absolute;right:16px;top:14px;z-index:5;font-size:10px;color:#66778a;background:rgba(8,13,20,.56);padding:6px 8px;border-radius:8px;border:1px solid rgba(124,154,184,.1)}
#space{width:100%;height:100%;display:block;cursor:grab;user-select:none;touch-action:none}#space.dragging{cursor:grabbing}
.layer-plane{fill:url(#planeFill);stroke:rgba(118,159,200,.14);stroke-width:1}.layer-grid{stroke:rgba(101,152,200,.09);stroke-width:1}.layer-title{fill:#607b95;font-size:11px;letter-spacing:.14em;text-transform:uppercase}.layer-sub{fill:#405367;font-size:9px}
.edge{fill:none;stroke:rgba(84,126,164,.25);stroke-width:1.3;pointer-events:none}.edge.related{stroke:rgba(100,218,255,.86);stroke-width:2.15}.edge.dim{opacity:.055}
.node{cursor:grab}.node.dragging{cursor:grabbing}.node.dim{opacity:.12}.node .plate{fill:rgba(13,20,29,.9);stroke:rgba(111,144,174,.35);stroke-width:1.15}.node .inner{fill:rgba(255,255,255,.018);stroke:rgba(255,255,255,.04)}.node .accent{opacity:.95}.node-fact .plate{fill:rgba(8,30,39,.92)}.node-fact .accent{fill:#45d6e8}.node-rule .plate{fill:rgba(18,22,49,.94)}.node-rule .accent{fill:#7797ff}.node-invariant .plate{fill:rgba(35,20,51,.94)}.node-invariant .accent{fill:#b785ff}.node-context .plate{fill:rgba(29,31,36,.94)}.node-context .accent{fill:#9aa6b2}.node .type{font-size:8px;letter-spacing:.09em;fill:#8da0b4}.node .label{font-size:10.5px;font-weight:600;fill:#e7f0f9}.node .value{font-size:8.5px;fill:#8aa0b7}.node .pulse{opacity:0}.node.pass .plate{stroke:rgba(80,223,145,.68)}.node.fail .plate{stroke:rgba(255,102,112,.82);stroke-width:1.9}.node.unknown .plate{stroke:rgba(255,201,95,.72)}.node.impacted .inner{stroke:rgba(116,168,255,.7);stroke-dasharray:4 3}.node.selected .plate{stroke:var(--cyan);stroke-width:2.25}.node.selected .pulse{opacity:.32;fill:none;stroke:rgba(102,217,255,.5)}
.inspector{grid-column:2;grid-row:2/4;border-left:1px solid var(--line);background:linear-gradient(180deg,rgba(10,16,24,.96),rgba(7,11,17,.98));overflow:auto;z-index:8}.inspector-head{position:sticky;top:0;background:rgba(9,14,21,.92);padding:16px 16px 12px;border-bottom:1px solid var(--line);z-index:2}.eyebrow{font-size:9px;letter-spacing:.14em;color:var(--cyan);text-transform:uppercase}.inspector h2{font-size:15px;line-height:1.38;margin:5px 0 8px}.pills{display:flex;gap:5px;flex-wrap:wrap}.pill{font-size:9px;border:1px solid var(--line);padding:4px 7px;border-radius:999px;color:#8fa1b4}.inspect-body{padding:10px 16px 24px}.empty{color:var(--muted);font-size:12px;line-height:1.8;padding-top:8px}.kv{padding:10px 0;border-bottom:1px solid rgba(124,154,184,.1)}.kv label{display:block;color:#62778c;font-size:9px;letter-spacing:.05em;margin-bottom:5px}.kv pre{margin:0;white-space:pre-wrap;word-break:break-word;color:#cbd7e4;font:10.5px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;background:rgba(4,8,13,.52);border:1px solid rgba(124,154,184,.1);border-radius:8px;padding:8px}.focus-btn{width:100%;margin-top:10px}
.timeline{grid-column:1;grid-row:3;border-top:1px solid var(--line);background:linear-gradient(180deg,rgba(7,11,17,.94),rgba(5,8,12,.98));padding:9px 14px;z-index:7;overflow-y:auto;overflow-x:hidden}.timeline-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:7px}.timeline-head b{font-size:11px}.timeline-head span{font-size:9px;color:var(--muted)}.runs{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:6px;align-content:start}.run{min-width:0;max-width:none;border:1px solid var(--line);background:rgba(18,27,38,.58);border-radius:9px;padding:6px 7px;cursor:pointer;transition:transform .16s,border-color .16s}.run:hover{transform:translateY(-1px);border-color:rgba(102,217,255,.35)}.run .top{display:flex;gap:5px;justify-content:space-between;font-size:8.5px}.run .mode{font-size:9px;color:#bdcad7;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.run .time{font-size:8px;color:#62778c;margin-top:2px}.run.fail,.run.pass,.run.unknown{border-color:rgba(124,154,184,.18)}.run .history-state{color:#8fa1b4;font-weight:600}
@media(max-width:980px){.shell{grid-template-columns:1fr;grid-template-rows:auto minmax(0,1fr) 174px}.topbar{grid-column:1;min-height:92px}.inspector{display:none}.timeline{grid-column:1}.brand{min-width:200px}.actions{display:none}.runs{grid-template-columns:repeat(auto-fit,minmax(118px,1fr))}}
@media (prefers-reduced-motion:reduce){.edge.related,.node.selected .pulse,.run{animation:none!important;transition:none!important}}
</style>
</head>
<body>
<div class="shell">
  <header class="topbar">
    <div class="brand"><div class="brand-kicker">Semantic Verification Space</div><h1>AegisGraph <span>空间语义控制台 · Spatial REG</span></h1></div>
    <div class="stats" id="stats"></div>
    <div class="actions"><button class="btn active" id="allBtn">全部语义</button><button class="btn" id="riskBtn">只看风险</button><button class="btn" id="resetBtn">重置视角</button><button class="btn" id="layoutBtn">恢复布局</button></div>
  </header>
  <section class="stage-wrap">
    <div class="hud"><span class="chip">目标 Target <strong id="targetName">—</strong></span><span class="chip">证据快照 Evidence <strong id="snapshot">—</strong></span><span class="chip">青=事实 Fact · 蓝=规则 Rule · 紫=不变量 Invariant · 灰=上下文 Context</span></div>
    <div class="hint">拖空白平移 · 拖节点移动 · 滚轮缩放 · 点击节点看关系 · 双击聚焦</div>
    <svg id="space" viewBox="0 0 1600 1080" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="planeFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#18304a" stop-opacity=".13"/><stop offset="1" stop-color="#07111b" stop-opacity=".025"/></linearGradient>
      </defs>
      <g id="camera"><g id="planes"></g><g id="edges"></g><g id="nodes"></g></g>
    </svg>
  </section>
  <aside class="inspector"><div class="inspector-head"><div class="eyebrow">Semantic Inspector · 语义检查器</div><h2 id="inspectTitle">选择一个语义节点</h2><div class="pills" id="inspectPills"></div></div><div class="inspect-body" id="inspectBody"><div class="empty">点击图中的事实、规则或不变量，查看定义、公式、当前值、证据来源与验证状态。<br/><br/>选择节点后，与它直接相关的语义路径会自动高亮，其余内容淡出。</div></div></aside>
  <footer class="timeline"><div class="timeline-head"><b>历史运行记录 · Invocation History <small style="color:#62778c;font-weight:400">（不代表当前图谱状态）</small></b><span id="runCount">0 runs</span></div><div class="runs" id="runs"></div></footer>
</div>
<script>
const DATA=__DATA__;
const SVG=document.getElementById('space'),NS='http://www.w3.org/2000/svg';
const planes=document.getElementById('planes'),edgeLayer=document.getElementById('edges'),nodeLayer=document.getElementById('nodes');
const nodes=DATA.nodes||[],edges=DATA.edges||[],byId=new Map(nodes.map(n=>[n.id,n]));
const TYPE={fact:'事实 Fact',rule:'规则 Rule',invariant:'不变量 Invariant',context:'上下文 Context'};
const STATUS={pass:'通过 PASS',fail:'失败 FAIL',unknown:'未知 UNKNOWN',unverified:'未验证 UNVERIFIED',accepted:'已接受 ACCEPTED',active:'生效 ACTIVE',completed:'已完成 COMPLETED'};
const MODE={semantic_discovery:'语义发现 Semantic Discovery',accepted_rule_proof:'正式规则验证 Accepted Rule Proof',reg_dashboard:'REG 页面刷新 REG Dashboard',reg_spatial_preview:'空间预览刷新 Spatial Preview'};
const FIELD={id:'标识 ID',display_name:'显示名称 Display Name',name:'英文原名 Original Name',kind:'类型 Kind',status:'状态 Status',verification_status:'验证状态 Verification Status',verification_message:'验证说明 Verification Message',expression:'公式 Expression',applies_when:'适用条件 Applies When',value:'当前值 Value',version:'版本 Version',provenance:'来源 Provenance',confidence:'置信度 Confidence',criticality:'重要级别 Criticality',commit_sha:'提交 Commit SHA',valid_from:'生效自 Valid From',valid_to:'生效至 Valid To',inputs:'输入 Inputs',outputs:'输出 Outputs',facts:'事实 Facts',contexts:'上下文 Contexts',source_anchors:'代码锚点 Source Anchors',evidence_sources:'证据来源 Evidence Sources',description:'说明 Description',attributes:'属性 Attributes',timestamp:'时间 Timestamp',mode:'运行模式 Mode',target:'目标项目 Target',source:'调用来源 Source',verdict:'结论 Verdict',evidence_snapshot_id:'证据快照 Evidence Snapshot',target_commit:'目标提交 Target Commit',duration_ms:'耗时 Duration (ms)',note:'备注 Note'};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const statusLabel=v=>STATUS[v]||String(v??'').toUpperCase(); const modeLabel=v=>MODE[v]||v; const fieldLabel=v=>FIELD[v]||v;
const el=(name,attrs={})=>{const x=document.createElementNS(NS,name);Object.entries(attrs).forEach(([k,v])=>x.setAttribute(k,v));return x};
const summary=DATA.summary||{},invSummary=DATA.invocation_summary||{total:0};
const stats=[['结论 Verdict',statusLabel(summary.verdict),summary.verdict],['事实 Facts',summary.facts],['规则 Rules',summary.rules],['不变量 Invariants',summary.invariants],['通过 PASS',summary.pass,'pass'],['失败 FAIL',summary.fail,'fail'],['未知 UNKNOWN',summary.unknown,'unknown'],['已记录运行 Runs',invSummary.total]];
document.getElementById('stats').innerHTML=stats.map(([k,v,s])=>`<div class="stat"><label>${esc(k)}</label><b class="${esc(s?'status-'+s:'')}">${esc(v)}</b></div>`).join('');
const latest=(DATA.invocations||[])[0]||{};document.getElementById('targetName').textContent=(latest.target||'—').split('/').filter(Boolean).pop()||'—';document.getElementById('snapshot').textContent=(latest.evidence_snapshot_id||'—').slice(0,12);
const LAYERS={context:{y:125,label:'04 · 上下文 CONTEXT',sub:'适用范围与语义环境',width:1320},invariant:{y:315,label:'03 · 不变量 INVARIANT',sub:'必须始终成立的约束',width:1400},rule:{y:530,label:'02 · 规则 RULE',sub:'事实之间的逻辑与公式',width:1460},fact:{y:755,label:'01 · 事实 FACT',sub:'代码与运行证据映射出的事实',width:1510}};
const positions=new Map();
function drawPlane(type,cfg){const x=(1600-cfg.width)/2,y=cfg.y-55;const poly=el('polygon',{points:`${x+55},${y} ${x+cfg.width-55},${y} ${x+cfg.width},${y+155} ${x},${y+155}`,class:'layer-plane'});planes.appendChild(poly);for(let i=1;i<8;i++){const xx=x+(cfg.width/8)*i;planes.appendChild(el('line',{x1:xx,y1:y+4,x2:xx+((xx-800)*.035),y2:y+150,class:'layer-grid'}))}for(let j=1;j<3;j++){planes.appendChild(el('line',{x1:x+12,y1:y+j*51,x2:x+cfg.width-12,y2:y+j*51,class:'layer-grid'}))}const t=el('text',{x:x+30,y:y+24,class:'layer-title'});t.textContent=cfg.label;planes.appendChild(t);const s=el('text',{x:x+30,y:y+42,class:'layer-sub'});s.textContent=cfg.sub;planes.appendChild(s)}
Object.entries(LAYERS).forEach(([t,c])=>drawPlane(t,c));
for(const [type,cfg] of Object.entries(LAYERS)){const arr=nodes.filter(n=>n.type===type).sort((a,b)=>a.label.localeCompare(b.label,'zh-CN'));const cols=Math.min(type==='fact'?7:6,Math.max(1,arr.length));const cell=cfg.width/cols;arr.forEach((n,i)=>{const row=Math.floor(i/cols),col=i%cols;const x=(1600-cfg.width)/2+cell*col+cell/2;const y=cfg.y+row*68;positions.set(n.id,{x,y})})}
const defaultPositions=new Map([...positions].map(([id,p])=>[id,{x:p.x,y:p.y}]));
function edgePath(a,b){const dy=b.y-a.y,curve=Math.max(55,Math.abs(dy)*.42);return `M ${a.x} ${a.y} C ${a.x} ${a.y+(dy>0?curve:-curve)}, ${b.x} ${b.y-(dy>0?curve:-curve)}, ${b.x} ${b.y}`} function updateEdgesFor(id){edgeEls.forEach(p=>{if(p.dataset.source!==id&&p.dataset.target!==id)return;const a=positions.get(p.dataset.source),b=positions.get(p.dataset.target);if(a&&b)p.setAttribute('d',edgePath(a,b))})}
const edgeEls=[];edges.forEach((e,i)=>{const a=positions.get(e.source),b=positions.get(e.target);if(!a||!b)return;const p=el('path',{d:edgePath(a,b),class:'edge','data-source':e.source,'data-target':e.target});edgeLayer.appendChild(p);edgeEls.push(p)});function updateAllEdges(){edgeEls.forEach(p=>{const a=positions.get(p.dataset.source),b=positions.get(p.dataset.target);if(a&&b)p.setAttribute('d',edgePath(a,b))})}
const nodeEls=new Map();
function displayValue(n){const v=n.details?.value;if(v===undefined||v===null||v==='')return '';if(typeof v==='boolean')return v?'TRUE':'FALSE';const s=typeof v==='object'?JSON.stringify(v):String(v);return s.length>25?s.slice(0,23)+'…':s}
nodes.forEach(n=>{const p=positions.get(n.id);if(!p)return;const w=n.type==='invariant'?218:196,h=50;const g=el('g',{class:`node node-${n.type} ${n.status||''} ${n.impacted?'impacted':''}`,transform:`translate(${p.x-w/2},${p.y-h/2})`,'data-id':n.id,'data-w':w,'data-h':h});g.appendChild(el('rect',{x:-4,y:-4,width:w+8,height:h+8,rx:14,class:'pulse'}));g.appendChild(el('rect',{width:w,height:h,rx:11,class:'plate'}));g.appendChild(el('rect',{x:5,y:5,width:w-10,height:h-10,rx:8,class:'inner'}));g.appendChild(el('rect',{x:5,y:7,width:3,height:h-14,rx:2,class:'accent'}));const type=el('text',{x:14,y:15,class:'type'});type.textContent=(TYPE[n.type]||n.type)+' · '+statusLabel(n.status);g.appendChild(type);const label=el('text',{x:14,y:32,class:'label'});const text=n.label||n.id;label.textContent=text.length>28?text.slice(0,27)+'…':text;g.appendChild(label);const val=displayValue(n);if(val){const value=el('text',{x:w-10,y:44,'text-anchor':'end',class:'value'});value.textContent=val;g.appendChild(value)}g.addEventListener('pointerdown',ev=>startNodeDrag(ev,n.id));g.addEventListener('dblclick',ev=>{ev.stopPropagation();focusNode(n.id)});nodeLayer.appendChild(g);nodeEls.set(n.id,g)});
let selected=null,riskOnly=false,nodeDrag=null,suppressCanvasClick=false;
function relatedSet(id){const set=new Set([id]);edges.forEach(e=>{if(e.source===id)set.add(e.target);if(e.target===id)set.add(e.source)});return set}
function selectNode(id){selected=id;const rel=relatedSet(id);nodeEls.forEach((g,nid)=>{g.classList.toggle('selected',nid===id);g.classList.toggle('dim',!rel.has(nid))});edgeEls.forEach(p=>{const hit=p.dataset.source===id||p.dataset.target===id;p.classList.toggle('related',hit);p.classList.toggle('dim',!hit)});showNode(id)}
function clearSelection(){selected=null;nodeEls.forEach(g=>{g.classList.remove('selected','dim')});edgeEls.forEach(p=>p.classList.remove('related','dim'))}
function svgDelta(dx,dy){const r=SVG.getBoundingClientRect();return {x:dx/r.width*view.w,y:dy/r.height*view.h}}
function placeNode(id){const g=nodeEls.get(id),p=positions.get(id);if(!g||!p)return;const w=Number(g.dataset.w||196),h=Number(g.dataset.h||50);g.setAttribute('transform',`translate(${p.x-w/2},${p.y-h/2})`)}
function startNodeDrag(ev,id){ev.preventDefault();ev.stopPropagation();selectNode(id);nodeDrag={id,pointerId:ev.pointerId,lastX:ev.clientX,lastY:ev.clientY,moved:false};const g=nodeEls.get(id);g?.classList.add('dragging');SVG.setPointerCapture(ev.pointerId)}
function moveNodeDrag(ev){if(!nodeDrag||ev.pointerId!==nodeDrag.pointerId)return;const d=svgDelta(ev.clientX-nodeDrag.lastX,ev.clientY-nodeDrag.lastY);if(Math.abs(ev.clientX-nodeDrag.lastX)+Math.abs(ev.clientY-nodeDrag.lastY)>1)nodeDrag.moved=true;const p=positions.get(nodeDrag.id);if(p){p.x+=d.x;p.y+=d.y;placeNode(nodeDrag.id);updateEdgesFor(nodeDrag.id)}nodeDrag.lastX=ev.clientX;nodeDrag.lastY=ev.clientY}
function endNodeDrag(ev){if(!nodeDrag||ev.pointerId!==nodeDrag.pointerId)return false;nodeEls.get(nodeDrag.id)?.classList.remove('dragging');suppressCanvasClick=nodeDrag.moved;nodeDrag=null;return true}
const priority=['id','display_name','name','kind','status','verification_status','verification_message','expression','applies_when','value','version','provenance','confidence','criticality','commit_sha','valid_from','valid_to','inputs','outputs','facts','contexts','source_anchors','evidence_sources','description','attributes'];
function showNode(id){const n=byId.get(id),d=n.details||{};document.getElementById('inspectTitle').textContent=n.label;document.getElementById('inspectPills').innerHTML=`<span class="pill">${esc(TYPE[n.type]||n.type)}</span><span class="pill">${esc(statusLabel(n.status))}</span>${n.impacted?'<span class="pill">受影响 IMPACTED</span>':''}`;const body=document.getElementById('inspectBody');body.innerHTML=priority.filter(k=>d[k]!==undefined&&d[k]!==null&&d[k]!==''&&(!Array.isArray(d[k])||d[k].length)).map(k=>`<div class="kv"><label>${esc(fieldLabel(k))}</label><pre>${esc((k==='status'||k==='verification_status')?statusLabel(d[k]):typeof d[k]==='object'?JSON.stringify(d[k],null,2):d[k])}</pre></div>`).join('')+`<button class="btn focus-btn">聚焦此节点 · Focus</button>`;body.querySelector('.focus-btn')?.addEventListener('click',()=>focusNode(id))}
SVG.addEventListener('click',e=>{if(suppressCanvasClick){suppressCanvasClick=false;return}if(!e.target.closest('.node'))clearSelection()});
let view={x:0,y:0,w:1600,h:1080},viewFrame=0;function setView(){if(viewFrame)return;viewFrame=requestAnimationFrame(()=>{SVG.setAttribute('viewBox',`${view.x} ${view.y} ${view.w} ${view.h}`);viewFrame=0})}
function resetView(){view={x:0,y:0,w:1600,h:1080};setView();clearSelection()}
function resetLayout(){defaultPositions.forEach((p,id)=>positions.set(id,{x:p.x,y:p.y}));nodeEls.forEach((g,id)=>placeNode(id));updateAllEdges();clearSelection()}
function focusNode(id){const p=positions.get(id);if(!p)return;view.w=920;view.h=621;view.x=Math.max(-80,p.x-view.w/2);view.y=Math.max(-50,p.y-view.h/2);setView();selectNode(id)}
document.getElementById('resetBtn').onclick=resetView;
document.getElementById('layoutBtn').onclick=resetLayout;
SVG.addEventListener('wheel',e=>{e.preventDefault();const rect=SVG.getBoundingClientRect(),mx=view.x+(e.clientX-rect.left)/rect.width*view.w,my=view.y+(e.clientY-rect.top)/rect.height*view.h,f=e.deltaY>0?1.12:.88,nw=Math.min(2400,Math.max(620,view.w*f)),nh=nw*(1080/1600);view.x=mx-(e.clientX-rect.left)/rect.width*nw;view.y=my-(e.clientY-rect.top)/rect.height*nh;view.w=nw;view.h=nh;setView()},{passive:false});
let dragging=false,last=null;SVG.addEventListener('pointerdown',e=>{if(e.target.closest('.node'))return;dragging=true;last={x:e.clientX,y:e.clientY,pointerId:e.pointerId};SVG.setPointerCapture(e.pointerId);SVG.classList.add('dragging')});SVG.addEventListener('pointermove',e=>{if(nodeDrag){moveNodeDrag(e);return}if(!dragging||e.pointerId!==last?.pointerId)return;const r=SVG.getBoundingClientRect();view.x-=(e.clientX-last.x)/r.width*view.w;view.y-=(e.clientY-last.y)/r.height*view.h;last={x:e.clientX,y:e.clientY,pointerId:e.pointerId};setView()});SVG.addEventListener('pointerup',e=>{if(endNodeDrag(e))return;dragging=false;last=null;SVG.classList.remove('dragging')});SVG.addEventListener('pointercancel',e=>{if(endNodeDrag(e))return;dragging=false;last=null;SVG.classList.remove('dragging')});
function applyRiskFilter(){riskOnly=true;clearSelection();nodeEls.forEach((g,id)=>{const n=byId.get(id);const risky=n.status==='fail'||n.status==='unknown'||n.impacted;g.style.opacity=risky?'1':'.08'});edgeEls.forEach(p=>{const a=byId.get(p.dataset.source),b=byId.get(p.dataset.target);const risky=[a,b].some(n=>n&&(n.status==='fail'||n.status==='unknown'||n.impacted));p.style.opacity=risky?'.55':'.035'});document.getElementById('riskBtn').classList.add('active');document.getElementById('allBtn').classList.remove('active')}
function showAll(){riskOnly=false;clearSelection();nodeEls.forEach(g=>g.style.opacity='');edgeEls.forEach(p=>p.style.opacity='');document.getElementById('allBtn').classList.add('active');document.getElementById('riskBtn').classList.remove('active')}
document.getElementById('riskBtn').onclick=applyRiskFilter;document.getElementById('allBtn').onclick=showAll;
const runs=document.getElementById('runs'),records=DATA.invocations||[];document.getElementById('runCount').textContent=`${records.length} recent · ${invSummary.total||0} tracked`;
function showRun(r){document.getElementById('inspectTitle').textContent='历史运行记录 · Historical Invocation';document.getElementById('inspectPills').innerHTML=`<span class="pill">${esc(modeLabel(r.mode))}</span><span class="pill">${esc('历史 · Historical '+statusLabel(r.verdict||r.status))}</span>`;document.getElementById('inspectBody').innerHTML=Object.entries(r).filter(([,v])=>v!==null&&v!=='').map(([k,v])=>`<div class="kv"><label>${esc(fieldLabel(k))}</label><pre>${esc(k==='mode'?modeLabel(v):(k==='verdict'||k==='status')?statusLabel(v):v)}</pre></div>`).join('')}
runs.innerHTML=records.length?records.map((r,i)=>`<div class="run ${esc(r.verdict||'')}" data-i="${i}"><div class="top"><span class="history-state">${esc('历史 '+statusLabel(r.verdict||r.status))}</span><span>${esc(r.duration_ms??'—')} ms</span></div><div class="mode">${esc(modeLabel(r.mode))}</div><div class="time">${esc(new Date(r.timestamp).toLocaleString('zh-CN'))}</div></div>`).join(''):'<div class="empty">暂无运行记录 · No invocation records yet</div>';
runs.addEventListener('click',e=>{const item=e.target.closest('.run');if(item)showRun(records[Number(item.dataset.i)])});
</script>
</body></html>'''
    return template.replace("__TITLE__", safe_title).replace("__DATA__", data)


def write_spatial_html(
    path: str | Path,
    payload: Mapping[str, Any],
    *,
    title: str = "AegisGraph Spatial REG",
    target_root: str | Path | None = None,
) -> Path:
    """Write one self-contained spatial dashboard outside any declared target."""

    output = resolve_output_path(path, target_root=target_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_spatial_html(payload, title=title), encoding="utf-8")
    return output
