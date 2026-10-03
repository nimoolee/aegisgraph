from aegis_graph.ui.spatial_view import render_spatial_html


def _payload() -> dict:
    return {
        "summary": {"facts": 1, "rules": 1, "invariants": 1, "contexts": 0, "relationships": 2, "verdict": "fail", "pass": 0, "fail": 1, "unknown": 0},
        "nodes": [
            {"id": "cash", "label": "现金 · Cash", "type": "fact", "status": "active", "impacted": True, "details": {"id": "cash", "value": 10}},
            {"id": "rule.cash", "label": "现金规则 · Cash Rule", "type": "rule", "status": "accepted", "impacted": True, "details": {"id": "rule.cash", "expression": "cash >= 0"}},
            {"id": "inv.cash", "label": "现金守恒 · Cash Conservation", "type": "invariant", "status": "fail", "impacted": True, "details": {"id": "inv.cash", "verification_status": "fail"}},
        ],
        "edges": [
            {"source": "cash", "target": "rule.cash", "type": "input"},
            {"source": "cash", "target": "inv.cash", "type": "validates"},
        ],
        "invocation_summary": {"total": 3, "pass": 0, "fail": 2, "unknown": 0},
        "invocations": [{"timestamp": "2026-10-03T11:00:00+00:00", "mode": "accepted_rule_proof", "target": "/tmp/x", "status": "completed", "verdict": "fail", "duration_ms": 44}],
    }


def test_spatial_view_is_self_contained_bilingual_and_interactive() -> None:
    html = render_spatial_html(_payload(), title="Spatial Test")
    assert "Spatial Test" in html
    assert "空间语义控制台" in html
    assert "不变量 INVARIANT" in html
    assert "Invocation History" in html
    assert "focusNode" in html
    assert "requestAnimationFrame" in html
    assert "backdrop-filter" not in html
    assert "feDropShadow" not in html
    assert "feGaussianBlur" not in html
    assert "applyRiskFilter" in html
    assert "startNodeDrag" in html
    assert "updateEdgesFor" in html
    assert "if(e.target.closest('.node'))return" in html
    assert "node-fact" in html
    assert "node-rule" in html
    assert "node-invariant" in html
    assert "suppressCanvasClick" in html
    assert "青=事实 Fact" in html
    assert "https://" not in html
    assert "恢复布局" in html
    assert "resetLayout" in html
    assert "defaultPositions" in html
    assert "grid-template-columns:repeat(auto-fit" in html
    assert "overflow-x:hidden" in html
    assert "历史运行记录 · Invocation History" in html
    assert "不代表当前图谱状态" in html
    assert "Historical Invocation" in html
    assert ".run.fail,.run.pass,.run.unknown{border-color:rgba(124,154,184,.18)}" in html
    assert 'class="history-state"' in html
    assert "r.verdict?'status-'+r.verdict" not in html


def test_spatial_view_embeds_bilingual_node_data() -> None:
    html = render_spatial_html(_payload())
    assert "现金 · Cash" in html
    assert "现金守恒 · Cash Conservation" in html
    assert "accepted_rule_proof" in html
