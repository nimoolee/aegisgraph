"""Self-contained read-only knowledge-graph view for AegisGraph.

The renderer intentionally has no third-party frontend/runtime dependency. It emits a
single HTML file that can be opened directly or served by Python's stdlib HTTP server.
"""

from __future__ import annotations

import html
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from aegis_graph.audit.invocations import (
    InvocationRecord,
    resolve_output_path,
    summarize_invocations,
)
from aegis_graph.graph.store import SoftwareGraph
from aegis_graph.proof.models import ChangeProof
from aegis_graph.ui._html_safety import json_for_script


def _metadata(value: Any) -> dict[str, Any]:
    metadata = getattr(value, "metadata", None)
    if metadata is None:
        return {}
    return {
        "version": getattr(metadata, "version", None),
        "provenance": getattr(getattr(metadata, "provenance", None), "value", getattr(metadata, "provenance", None)),
        "confidence": getattr(metadata, "confidence", None),
        "criticality": getattr(getattr(metadata, "criticality", None), "value", getattr(metadata, "criticality", None)),
        "valid_from": getattr(metadata, "valid_from", None),
        "valid_to": getattr(metadata, "valid_to", None),
        "commit_sha": getattr(metadata, "commit_sha", None),
    }


def build_graph_payload(
    graph: SoftwareGraph,
    *,
    proof: ChangeProof | None = None,
    fact_values: Mapping[str, Any] | None = None,
    evidence_sources: Mapping[str, tuple[str, ...]] | None = None,
    source_anchors: Mapping[str, tuple[str, ...]] | None = None,
    display_labels: Mapping[str, str] | None = None,
    invocations: tuple[InvocationRecord, ...] = (),
) -> dict[str, Any]:
    """Build a JSON-serialisable read-only view model from accepted semantics."""

    fact_values = fact_values or {}
    evidence_sources = evidence_sources or {}
    source_anchors = source_anchors or {}
    display_labels = display_labels or {}
    invariant_checks = {
        check.invariant_id: check for check in (proof.invariant_checks if proof else ())
    }
    impacted_facts = set(proof.impact.affected_fact_ids if proof else ())
    impacted_rules = set(proof.impact.affected_rule_ids if proof else ())
    impacted_invariants = set(proof.impact.affected_invariant_ids if proof else ())

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for fact in sorted(graph.facts.values(), key=lambda item: item.id):
        details = {
            "id": fact.id,
            "name": fact.name,
            "display_name": display_labels.get(fact.id, fact.name),
            "kind": fact.kind,
            "description": fact.description,
            "status": fact.status,
            "value": fact_values.get(fact.id),
            "evidence_sources": list(evidence_sources.get(fact.id, ())),
            "source_anchors": list(source_anchors.get(fact.id, ())),
            **_metadata(fact),
        }
        nodes.append(
            {
                "id": fact.id,
                "label": display_labels.get(fact.id, fact.name),
                "type": "fact",
                "status": "active",
                "impacted": fact.id in impacted_facts,
                "details": details,
            }
        )

    for rule in sorted(graph.rules.values(), key=lambda item: item.id):
        details = {
            "id": rule.id,
            "name": rule.name,
            "display_name": display_labels.get(rule.id, rule.name),
            "expression": rule.expression,
            "applies_when": rule.applies_when,
            "inputs": list(rule.inputs),
            "outputs": list(rule.outputs),
            "contexts": list(rule.context_ids),
            **_metadata(rule),
        }
        nodes.append(
            {
                "id": rule.id,
                "label": display_labels.get(rule.id, rule.name),
                "type": "rule",
                "status": "accepted",
                "impacted": rule.id in impacted_rules,
                "details": details,
            }
        )
        for fact_id in rule.inputs:
            edges.append({"source": fact_id, "target": rule.id, "type": "input"})
        for fact_id in rule.outputs:
            edges.append({"source": rule.id, "target": fact_id, "type": "output"})

    for invariant in sorted(graph.invariants.values(), key=lambda item: item.id):
        check = invariant_checks.get(invariant.id)
        status = check.status.value if check else "unverified"
        details = {
            "id": invariant.id,
            "name": invariant.name,
            "display_name": display_labels.get(invariant.id, invariant.name),
            "expression": invariant.expression,
            "applies_when": invariant.applies_when,
            "facts": list(invariant.facts),
            "contexts": list(invariant.context_ids),
            "verification_status": status,
            "verification_message": check.message if check else None,
            **_metadata(invariant),
        }
        nodes.append(
            {
                "id": invariant.id,
                "label": display_labels.get(invariant.id, invariant.name),
                "type": "invariant",
                "status": status,
                "impacted": invariant.id in impacted_invariants,
                "details": details,
            }
        )
        for fact_id in invariant.facts:
            edges.append({"source": fact_id, "target": invariant.id, "type": "validates"})

    for context in sorted(graph.contexts.values(), key=lambda item: item.id):
        nodes.append(
            {
                "id": context.id,
                "label": display_labels.get(context.id, context.id),
                "type": "context",
                "status": "accepted",
                "impacted": False,
                "details": {
                    "id": context.id,
                    "kind": context.kind,
                    "attributes": dict(context.attributes),
                    **_metadata(context),
                },
            }
        )

    for relationship in sorted(graph.relationships.values(), key=lambda item: item.id):
        edges.append(
            {
                "id": relationship.id,
                "source": relationship.source,
                "target": relationship.target,
                "type": relationship.type.value,
            }
        )

    summary = {
        "facts": len(graph.facts),
        "rules": len(graph.rules),
        "invariants": len(graph.invariants),
        "contexts": len(graph.contexts),
        "relationships": len(edges),
        "verdict": proof.verdict.value if proof else "unverified",
        "pass": sum(1 for check in invariant_checks.values() if check.status.value == "pass"),
        "fail": sum(1 for check in invariant_checks.values() if check.status.value == "fail"),
        "unknown": sum(1 for check in invariant_checks.values() if check.status.value == "unknown"),
    }
    invocation_summary = summarize_invocations(invocations)
    return {
        "summary": summary,
        "nodes": nodes,
        "edges": edges,
        "invocation_summary": invocation_summary,
        "invocations": [
            {
                "timestamp": row.timestamp,
                "mode": row.mode,
                "target": row.target,
                "source": row.source,
                "status": row.status,
                "verdict": row.verdict,
                "evidence_snapshot_id": row.evidence_snapshot_id,
                "target_commit": row.target_commit,
                "duration_ms": row.duration_ms,
                "note": row.note,
            }
            for row in reversed(invocations[-12:])
        ],
    }


def render_graph_html(payload: Mapping[str, Any], *, title: str = "AegisGraph") -> str:
    """Render one portable, dependency-free HTML knowledge graph."""

    data = json_for_script(payload)
    safe_title = html.escape(title)
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{safe_title}</title>
<style>
:root {{ color-scheme: dark; --bg:#0b0d10; --panel:#11151a; --line:#2a3139; --text:#e8edf2; --muted:#8b98a5; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:var(--bg); color:var(--text); }}
header {{ min-height:72px; display:flex; align-items:center; gap:18px; padding:10px 20px; border-bottom:1px solid var(--line); background:#0e1217; position:sticky; top:0; z-index:5; flex-wrap:wrap; }}
.brand {{ font-weight:800; font-size:18px; white-space:nowrap; }}
.brand small {{ color:var(--muted); font-weight:500; margin-left:8px; }}
.cards {{ display:flex; gap:8px; flex-wrap:wrap; }}
.card {{ padding:7px 10px; border:1px solid var(--line); border-radius:9px; font-size:12px; color:var(--muted); }}
.card b {{ color:var(--text); margin-left:5px; }}
.audit-strip {{ width:100%; display:flex; gap:8px; align-items:center; color:var(--muted); font-size:11px; overflow:auto; padding-bottom:2px; }}
.audit-run {{ border:1px solid var(--line); border-radius:8px; padding:5px 8px; white-space:nowrap; cursor:pointer; }}
.audit-run:hover {{ border-color:#607080; color:var(--text); }}
main {{ display:grid; grid-template-columns:minmax(0,1fr) 360px; height:calc(100vh - 118px); }}
.left {{ min-width:0; display:flex; flex-direction:column; }}
.toolbar {{ padding:10px 14px; display:flex; gap:8px; border-bottom:1px solid var(--line); }}
input, select {{ background:#0f1419; color:var(--text); border:1px solid var(--line); border-radius:8px; padding:8px 10px; }}
input {{ flex:1; }}
#viewport {{ flex:1; overflow:auto; position:relative; }}
svg {{ min-width:1100px; min-height:900px; width:100%; height:100%; }}
.edge {{ stroke:#39434d; stroke-width:1.2; opacity:.75; }}
.edge-label {{ fill:#65727f; font-size:9px; pointer-events:none; }}
.node rect {{ fill:#171d23; stroke:#46515c; stroke-width:1.2; rx:9; }}
.node text {{ fill:#dfe6ed; font-size:11px; pointer-events:none; }}
.node .type {{ fill:#7d8995; font-size:9px; text-transform:uppercase; }}
.node.pass rect {{ stroke:#43c977; }} .node.fail rect {{ stroke:#ff5f57; stroke-width:2; }} .node.unknown rect {{ stroke:#e6b84f; }}
.node.impacted rect {{ stroke-dasharray:4 3; stroke-width:2.4; }}
.node.selected rect {{ fill:#222b34; stroke:#6fb4ff; stroke-width:2.5; }}
.node.hidden {{ display:none; }} .edge.hidden, .edge-label.hidden {{ display:none; }}
aside {{ border-left:1px solid var(--line); background:var(--panel); overflow:auto; padding:18px; }}
aside h2 {{ margin:0 0 6px; font-size:16px; }}
aside .pill {{ display:inline-block; border:1px solid var(--line); border-radius:999px; padding:3px 7px; font-size:10px; color:var(--muted); margin:0 4px 8px 0; }}
.detail {{ margin:12px 0; }} .detail label {{ display:block; color:var(--muted); font-size:10px; text-transform:uppercase; margin-bottom:4px; }}
pre {{ white-space:pre-wrap; word-break:break-word; font-size:11px; line-height:1.45; background:#0c1014; padding:10px; border-radius:8px; border:1px solid #202831; }}
.empty {{ color:var(--muted); line-height:1.6; }}
.legend {{ display:flex; gap:10px; align-items:center; color:var(--muted); font-size:10px; padding:0 14px 10px; }}
.dot {{ width:8px; height:8px; border-radius:50%; display:inline-block; }}
@media (max-width:900px) {{ main {{ grid-template-columns:1fr; }} aside {{ display:none; }} header {{ height:auto; padding:10px; flex-wrap:wrap; }} main {{ height:calc(100vh - 112px); }} }}
</style>
</head>
<body>
<header><div class="brand">AegisGraph <small>REG 关系图 / Dashboard</small></div><div class="cards" id="cards"></div><div class="audit-strip" id="audit-strip"></div></header>
<main>
<section class="left">
  <div class="toolbar"><input id="search" placeholder="搜索 事实 Fact / 规则 Rule / 不变量 Invariant / ID…" /><select id="filter"><option value="all">全部 All</option><option value="fact">事实 Fact</option><option value="rule">规则 Rule</option><option value="invariant">不变量 Invariant</option><option value="context">上下文 Context</option></select></div>
  <div class="legend"><span><i class="dot" style="background:#43c977"></i> 通过 PASS</span><span><i class="dot" style="background:#ff5f57"></i> 失败 FAIL</span><span><i class="dot" style="background:#e6b84f"></i> 未知 UNKNOWN</span><span>虚线边框 = 受影响 Impacted</span></div>
  <div id="viewport"><svg id="graph" viewBox="0 0 1200 900" preserveAspectRatio="xMinYMin meet"></svg></div>
</section>
<aside id="detail"><div class="empty">点击任意节点查看：定义 Definition / 公式 Formula / 版本 Version / 来源 Provenance / 证据 Evidence / 验证 Verification。</div></aside>
</main>
<script>
const DATA = {data};
const svg = document.getElementById('graph');
const NS='http://www.w3.org/2000/svg';
const nodeById = new Map(DATA.nodes.map(n=>[n.id,n]));
const TYPE_ZH = {{fact:'事实 Fact',rule:'规则 Rule',invariant:'不变量 Invariant',context:'上下文 Context'}};
const STATUS_ZH = {{pass:'通过 PASS',fail:'失败 FAIL',unknown:'未知 UNKNOWN',unverified:'未验证 UNVERIFIED',accepted:'已接受 ACCEPTED',active:'生效 ACTIVE',completed:'已完成 COMPLETED'}};
const FIELD_ZH = {{id:'标识 ID',display_name:'显示名称 Display Name',name:'英文原名 Original Name',kind:'类型 Kind',status:'状态 Status',verification_status:'验证状态 Verification Status',verification_message:'验证说明 Verification Message',expression:'公式 Expression',applies_when:'适用条件 Applies When',value:'当前值 Value',version:'版本 Version',provenance:'来源 Provenance',confidence:'置信度 Confidence',criticality:'重要级别 Criticality',commit_sha:'提交 Commit SHA',valid_from:'生效自 Valid From',valid_to:'生效至 Valid To',inputs:'输入 Inputs',outputs:'输出 Outputs',facts:'事实 Facts',contexts:'上下文 Contexts',source_anchors:'代码锚点 Source Anchors',evidence_sources:'证据来源 Evidence Sources',description:'说明 Description',attributes:'属性 Attributes',timestamp:'时间 Timestamp',mode:'运行模式 Mode',target:'目标项目 Target',source:'调用来源 Source',verdict:'结论 Verdict',evidence_snapshot_id:'证据快照 Evidence Snapshot',target_commit:'目标提交 Target Commit',duration_ms:'耗时 Duration (ms)',note:'备注 Note'}};
const MODE_ZH = {{semantic_discovery:'语义发现 Semantic Discovery',accepted_rule_proof:'正式规则验证 Accepted Rule Proof',reg_dashboard:'REG 页面刷新 REG Dashboard'}};
const labelType=v=>TYPE_ZH[v]||v; const labelStatus=v=>STATUS_ZH[v]||String(v??'').toUpperCase(); const labelField=v=>FIELD_ZH[v]||v; const labelMode=v=>MODE_ZH[v]||v;
const summary = DATA.summary, invSummary = DATA.invocation_summary || {{total:0,pass:0,fail:0,unknown:0,last_run:null}};
document.getElementById('cards').innerHTML = [
 ['结论 Verdict', labelStatus(summary.verdict)], ['事实 Facts', summary.facts], ['规则 Rules', summary.rules], ['不变量 Invariants', summary.invariants],
 ['通过 PASS',summary.pass],['失败 FAIL',summary.fail],['未知 UNKNOWN',summary.unknown],['已记录运行 Tracked Runs',invSummary.total]
].map(x=>`<div class="card">${{esc(x[0])}} <b>${{esc(x[1])}}</b></div>`).join('');

const columns = {{ fact:120, rule:470, invariant:820, context:1050 }};
const groups = {{ fact:[], rule:[], invariant:[], context:[] }};
DATA.nodes.forEach(n => (groups[n.type] ||= []).push(n));
const positions = new Map();
for (const [type,nodes] of Object.entries(groups)) {{
  nodes.sort((a,b)=>a.label.localeCompare(b.label));
  nodes.forEach((n,i)=>positions.set(n.id, {{x:columns[type]||120, y:60+i*68}}));
}}
let maxY = Math.max(900, ...[...positions.values()].map(p=>p.y+80));
svg.setAttribute('viewBox',`0 0 1200 ${{maxY}}`); svg.style.minHeight=maxY+'px';

function el(name, attrs={{}}) {{ const x=document.createElementNS(NS,name); for(const [k,v] of Object.entries(attrs)) x.setAttribute(k,v); return x; }}
DATA.edges.forEach((e,i)=>{{
  const a=positions.get(e.source), b=positions.get(e.target); if(!a||!b) return;
  const line=el('line',{{x1:a.x+135,y1:a.y+23,x2:b.x-5,y2:b.y+23,class:'edge','data-source':e.source,'data-target':e.target}}); svg.appendChild(line);
  if(i<350) {{ const t=el('text',{{x:(a.x+b.x)/2,y:(a.y+b.y)/2,class:'edge-label','data-source':e.source,'data-target':e.target}}); t.textContent=e.type; svg.appendChild(t); }}
}});
DATA.nodes.forEach(n=>{{
  const p=positions.get(n.id); const g=el('g',{{class:`node ${{n.status||''}} ${{n.impacted?'impacted':''}}`,transform:`translate(${{p.x}},${{p.y}})`,'data-id':n.id,'data-type':n.type}});
  const r=el('rect',{{width:270,height:46}}); const type=el('text',{{x:10,y:13,class:'type'}}); type.textContent=labelType(n.type)+(n.status?` · ${{labelStatus(n.status)}}`: '');
  const label=el('text',{{x:10,y:31}}); label.textContent=n.label.length>38?n.label.slice(0,36)+'…':n.label;
  g.append(r,type,label); g.addEventListener('click',()=>selectNode(n.id)); svg.appendChild(g);
}});
function esc(v) {{ return String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c])); }}
const auditStrip=document.getElementById('audit-strip');
auditStrip.innerHTML=(DATA.invocations||[]).length ? (DATA.invocations||[]).map((r,i)=>`<div class="audit-run" data-run="${{i}}">${{esc(labelStatus(r.verdict||r.status||'run'))}} · ${{esc(labelMode(r.mode))}} · ${{esc(new Date(r.timestamp).toLocaleString('zh-CN'))}}</div>`).join('') : '<span>暂无已记录的 Aegis 运行 · No tracked Aegis runs yet</span>';
auditStrip.addEventListener('click',e=>{{ const item=e.target.closest('.audit-run'); if(!item) return; const r=DATA.invocations[Number(item.dataset.run)]; document.getElementById('detail').innerHTML=`<h2>Aegis 运行记录 / Run</h2><span class="pill">${{esc(labelMode(r.mode))}}</span><span class="pill">${{esc(labelStatus(r.verdict||r.status))}}</span>`+Object.entries(r).filter(([,v])=>v!==null&&v!=='').map(([k,v])=>`<div class="detail"><label>${{esc(labelField(k))}}</label><pre>${{esc(k==='mode'?labelMode(v):(k==='verdict'||k==='status')?labelStatus(v):v)}}</pre></div>`).join(''); }});
function selectNode(id) {{
  document.querySelectorAll('.node').forEach(x=>x.classList.toggle('selected',x.dataset.id===id));
  const n=nodeById.get(id), d=n.details||{{}}; const detail=document.getElementById('detail');
  const priority=['id','display_name','name','kind','status','verification_status','verification_message','expression','applies_when','value','version','provenance','confidence','criticality','commit_sha','valid_from','valid_to','inputs','outputs','facts','contexts','source_anchors','evidence_sources','description','attributes'];
  detail.innerHTML=`<h2>${{esc(n.label)}}</h2><span class="pill">${{esc(labelType(n.type))}}</span><span class="pill">${{esc(labelStatus(n.status))}}</span>${{n.impacted?'<span class="pill">受影响 IMPACTED</span>':''}}`+
    priority.filter(k=>d[k]!==undefined&&d[k]!==null&&d[k]!==''&&(Array.isArray(d[k])?d[k].length:true)).map(k=>`<div class="detail"><label>${{esc(labelField(k))}}</label><pre>${{esc((k==='verification_status'||k==='status')?labelStatus(d[k]):typeof d[k]==='object'?JSON.stringify(d[k],null,2):d[k])}}</pre></div>`).join('');
}}
function applyFilter() {{
 const q=document.getElementById('search').value.toLowerCase().trim(), type=document.getElementById('filter').value; const visible=new Set();
 document.querySelectorAll('.node').forEach(g=>{{ const n=nodeById.get(g.dataset.id); const hay=(n.id+' '+n.label+' '+JSON.stringify(n.details)).toLowerCase(); const show=(type==='all'||n.type===type)&&(!q||hay.includes(q)); g.classList.toggle('hidden',!show); if(show) visible.add(n.id); }});
 document.querySelectorAll('.edge,.edge-label').forEach(e=>e.classList.toggle('hidden',!(visible.has(e.dataset.source)&&visible.has(e.dataset.target))));
}}
document.getElementById('search').addEventListener('input',applyFilter); document.getElementById('filter').addEventListener('change',applyFilter);
</script>
</body></html>'''


def write_graph_html(
    path: str | Path,
    graph: SoftwareGraph,
    *,
    proof: ChangeProof | None = None,
    fact_values: Mapping[str, Any] | None = None,
    evidence_sources: Mapping[str, tuple[str, ...]] | None = None,
    source_anchors: Mapping[str, tuple[str, ...]] | None = None,
    display_labels: Mapping[str, str] | None = None,
    invocations: tuple[InvocationRecord, ...] = (),
    title: str = "AegisGraph",
    target_root: str | Path | None = None,
) -> Path:
    """Write one portable graph page and return its resolved path."""

    output = resolve_output_path(path, target_root=target_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_graph_payload(
        graph,
        proof=proof,
        fact_values=fact_values,
        evidence_sources=evidence_sources,
        source_anchors=source_anchors,
        display_labels=display_labels,
        invocations=invocations,
    )
    output.write_text(render_graph_html(payload, title=title), encoding="utf-8")
    return output
