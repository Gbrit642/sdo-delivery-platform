// Interactive SDO Web Dashboard Client Logic

let currentLoopId = null;
let currentLoopState = null;

const PIPELINE_NODES = [
    "INTAKE", "SPECIFY", "SPEC_HARNESS", "GATE_H1",
    "DESIGN", "IMPLEMENT", "REVIEW", "GATE_H2",
    "CLOSE", "WATCH", "DONE"
];

document.addEventListener("DOMContentLoaded", () => {
    setupTabListeners();
    setupForm();
    setupPathSelector();
    setupTradeoffEvaluator();
    setupGateButtons();
});

function setupTabListeners() {
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
            
            btn.classList.add("active");
            const targetId = btn.getAttribute("data-tab");
            document.getElementById(targetId).classList.add("active");

            if (targetId === "tab-catalog" && currentLoopId) {
                fetchAndRenderArtifacts(currentLoopId);
            }
        });
    });
}

function setupPathSelector() {
    const directRadio = document.getElementById("path-direct");
    const multiRadio = document.getElementById("path-multi-agent");
    const cards = document.querySelectorAll(".path-card");

    cards.forEach(card => {
        card.addEventListener("click", () => {
            cards.forEach(c => {
                c.classList.remove("selected");
                c.style.borderColor = "#dadce0";
                c.style.background = "white";
            });
            card.classList.add("selected");
            card.style.borderColor = "#1a73e8";
            card.style.background = "#e8f0fe";
        });
    });
}

function setupTradeoffEvaluator() {
    const btn = document.getElementById("btn-eval-tradeoff");
    btn.addEventListener("click", async () => {
        const briefText = document.getElementById("brief_text").value;
        const nodeId = document.getElementById("node_id").value;
        btn.disabled = true;
        btn.textContent = "Analyzing...";

        try {
            const resp = await fetch("/api/v1/tradeoffs/evaluate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ brief_text: briefText, node_id: nodeId })
            });
            if (resp.ok) {
                const data = await resp.json();
                renderTradeoffBox(data);
            }
        } catch (err) {
            console.error("Failed to evaluate trade-off:", err);
        } finally {
            btn.disabled = false;
            btn.textContent = "📊 Compare Pros & Cons";
        }
    });
}

function renderTradeoffBox(data) {
    const box = document.getElementById("tradeoff-box");
    box.style.display = "block";
    
    document.getElementById("tradeoff-rec-title").textContent = 
        `💡 AI Recommendation: ${data.recommended_path === 'direct_connector_automation' ? '⚡ Direct Connector Automation' : '🤖 Multi-Agent Software Development'}`;
    document.getElementById("tradeoff-rec-rationale").textContent = data.recommendation_rationale;

    const directPros = document.getElementById("direct-pros");
    directPros.innerHTML = data.direct_connector_option.pros.map(p => `<li>✓ ${p}</li>`).join("");
    const directCons = document.getElementById("direct-cons");
    directCons.innerHTML = data.direct_connector_option.cons.map(c => `<li>• ${c}</li>`).join("");

    const agentPros = document.getElementById("agent-pros");
    agentPros.innerHTML = data.multi_agent_option.pros.map(p => `<li>✓ ${p}</li>`).join("");
    const agentCons = document.getElementById("agent-cons");
    agentCons.innerHTML = data.multi_agent_option.cons.map(c => `<li>• ${c}</li>`).join("");

    // Auto-select recommended radio
    if (data.recommended_path === "direct_connector_automation") {
        document.getElementById("path-direct").checked = true;
        document.getElementById("path-direct").parentElement.click();
    } else {
        document.getElementById("path-multi-agent").checked = true;
        document.getElementById("path-multi-agent").parentElement.click();
    }
}

function setupForm() {
    const form = document.getElementById("loop-form");
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const btn = document.getElementById("btn-launch");
        btn.disabled = true;
        btn.innerHTML = "<span>⏳ Synthesizing & Executing...</span>";

        const nodeId = document.getElementById("node_id").value;
        const ownerEmail = document.getElementById("owner_email").value;
        const briefText = document.getElementById("brief_text").value;
        const deliveryPath = document.querySelector('input[name="delivery_path"]:checked').value;

        try {
            const resp = await fetch("/api/v1/loops", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    node_id: nodeId,
                    owner_email: ownerEmail,
                    brief_text: briefText,
                    delivery_path: deliveryPath
                })
            });

            if (!resp.ok) {
                const err = await resp.json();
                alert(`Failed to launch loop: ${err.detail || 'Unknown error'}`);
                return;
            }

            const state = await resp.json();
            currentLoopId = state.loop_id;
            currentLoopState = state;
            renderLoopView(state);
        } catch (err) {
            console.error("Error launching loop:", err);
            alert(`Network error launching loop: ${err.message}`);
        } finally {
            btn.disabled = false;
            btn.innerHTML = "<span>⚡ Launch SDO Loop</span>";
        }
    });
}

function setupGateButtons() {
    document.getElementById("btn-gate-approve").addEventListener("click", () => resolveActiveGate("approve"));
    document.getElementById("btn-gate-changes").addEventListener("click", () => resolveActiveGate("request_changes"));
    document.getElementById("btn-gate-reject").addEventListener("click", () => resolveActiveGate("reject"));
}

async function resolveActiveGate(decision) {
    if (!currentLoopId || !currentLoopState) return;

    let gate = "h1";
    if (currentLoopState.current_state === "WAIT_GATE_H2") {
        gate = "h2";
    }

    try {
        const resp = await fetch(`/api/v1/loops/${currentLoopId}/gates/${gate}/resolve`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                decision: decision,
                comment: `Resolved via Web Dashboard with decision: ${decision}`
            })
        });

        if (!resp.ok) {
            const err = await resp.json();
            alert(`Failed to resolve gate: ${err.detail || 'Unknown error'}`);
            return;
        }

        const updatedState = await resp.json();
        currentLoopState = updatedState;
        renderLoopView(updatedState);
    } catch (err) {
        console.error("Error resolving gate:", err);
        alert(`Network error resolving gate: ${err.message}`);
    }
}

async function fetchAndRenderArtifacts(loopId) {
    try {
        const resp = await fetch(`/api/v1/loops/${loopId}/artifacts`);
        if (resp.ok) {
            const artifacts = await resp.json();
            const listEl = document.getElementById("catalog-list");
            if (artifacts.length === 0) {
                listEl.innerHTML = "<p style='color: #70757a;'>No artifacts cataloged for this loop yet.</p>";
                return;
            }

            let html = `
            <table style="width: 100%; border-collapse: collapse; font-size: 12px; background: white; border: 1px solid #e0e0e0; border-radius: 6px;">
                <thead>
                    <tr style="background: #f1f3f4; text-align: left;">
                        <th style="padding: 8px; border-bottom: 1px solid #dadce0;">Artifact Name</th>
                        <th style="padding: 8px; border-bottom: 1px solid #dadce0;">Type</th>
                        <th style="padding: 8px; border-bottom: 1px solid #dadce0;">GCS Partitioned Path</th>
                        <th style="padding: 8px; border-bottom: 1px solid #dadce0;">Size</th>
                        <th style="padding: 8px; border-bottom: 1px solid #dadce0;">SHA-256 Digest</th>
                    </tr>
                </thead>
                <tbody>
            `;
            artifacts.forEach(a => {
                html += `
                <tr style="border-bottom: 1px solid #f1f3f4;">
                    <td style="padding: 8px; font-weight: bold; color: #1a73e8;">${a.artifact_name}</td>
                    <td style="padding: 8px;"><span class="badge" style="background: #e8f0fe; color: #1a73e8; font-size: 11px;">${a.artifact_type}</span></td>
                    <td style="padding: 8px; font-family: monospace; color: #3c4043;">${a.gcs_uri}</td>
                    <td style="padding: 8px;">${a.size_bytes} B</td>
                    <td style="padding: 8px; font-family: monospace; color: #5f6368;" title="${a.content_sha256}">${a.content_sha256.substring(0, 16)}...</td>
                </tr>
                `;
            });
            html += `</tbody></table>`;
            listEl.innerHTML = html;
        }
    } catch (err) {
        console.error("Failed to fetch artifacts:", err);
    }
}

function renderLoopView(state) {
    document.getElementById("loop-view").style.display = "block";
    document.getElementById("view-loop-id").textContent = `Loop: ${state.loop_id}`;
    document.getElementById("view-domain").textContent = state.node_id.toUpperCase();
    document.getElementById("view-state-pill").textContent = state.current_state;

    // Update FSM pipeline visualizer
    const currentState = state.current_state;
    let reachedIdx = -1;

    if (currentState === "WAIT_GATE_H1") reachedIdx = 3;
    else if (currentState === "WAIT_GATE_H2") reachedIdx = 7;
    else if (currentState === "DONE") reachedIdx = 10;
    else reachedIdx = PIPELINE_NODES.indexOf(currentState);

    PIPELINE_NODES.forEach((nodeName, idx) => {
        const el = document.getElementById(`step-${nodeName}`);
        if (!el) return;

        el.classList.remove("active", "passed");
        if (idx < reachedIdx) {
            el.classList.add("passed");
        } else if (idx === reachedIdx) {
            el.classList.add("active");
        }
    });

    // Gate Action Panel
    const gatePanel = document.getElementById("gate-action-panel");
    if (currentState === "WAIT_GATE_H1") {
        gatePanel.style.display = "flex";
        document.getElementById("gate-title").textContent = "Gate H1: Human Specification Sign-Off";
        document.getElementById("gate-desc").textContent = "Review the generated spec.md and Gherkin scenarios below. Approve to proceed to architectural design.";
    } else if (currentState === "WAIT_GATE_H2") {
        gatePanel.style.display = "flex";
        document.getElementById("gate-title").textContent = "Gate H2: Final Merge & Deploy Sign-Off";
        document.getElementById("gate-desc").textContent = "Review the sandbox test report (100% pass rate) and deliverables. Approve to deploy the asset to Google Cloud.";
    } else {
        gatePanel.style.display = "none";
    }

    // Render Business Deliverable Card if present
    const delivPanel = document.getElementById("business-deliverable-panel");
    if (state.business_deliverable_card) {
        const card = state.business_deliverable_card;
        delivPanel.style.display = "block";
        document.getElementById("deliv-title").textContent = card.title;
        document.getElementById("deliv-purpose").textContent = card.business_purpose;
        document.getElementById("deliv-resource").textContent = card.full_resource_id;
        document.getElementById("deliv-console-link").href = card.console_deep_link;
        document.getElementById("deliv-freshness").textContent = card.data_freshness;
        document.getElementById("deliv-sla").textContent = card.target_sla;
        document.getElementById("deliv-zero-cli").textContent = card.zero_cli_note;

        // Render Sample Table
        if (card.sample_data && card.sample_data.length > 0) {
            const keys = Object.keys(card.sample_data[0]);
            let tableHtml = `<table style="width:100%; border-collapse:collapse; font-size:11px; background:white; border:1px solid #ceead6; border-radius:4px;">
                <thead><tr style="background:#f1f8f3; text-align:left;">`;
            keys.forEach(k => tableHtml += `<th style="padding:6px; border-bottom:1px solid #ceead6;">${k}</th>`);
            tableHtml += `</tr></thead><tbody>`;
            card.sample_data.forEach(row => {
                tableHtml += `<tr style="border-bottom:1px solid #f8f9fa;">`;
                keys.forEach(k => tableHtml += `<td style="padding:6px;">${row[k]}</td>`);
                tableHtml += `</tr>`;
            });
            tableHtml += `</tbody></table>`;
            document.getElementById("deliv-sample-table").innerHTML = tableHtml;
        }
    } else {
        delivPanel.style.display = "none";
    }

    // Populate Artifact Tabs
    document.getElementById("content-spec").textContent = state.spec_content || "No specification available.";
    document.getElementById("content-design").textContent = state.design_content || "No technical design available.";
    
    // Code Artifacts
    if (state.code_artifacts && Object.keys(state.code_artifacts).length > 0) {
        let codeText = "";
        for (const [filename, content] of Object.entries(state.code_artifacts)) {
            codeText += `=== ${filename} ===\n${content}\n\n`;
        }
        document.getElementById("content-code").textContent = codeText;
    } else {
        document.getElementById("content-code").textContent = "No code artifacts generated yet.";
    }

    // Sandbox Report
    if (state.test_results && Object.keys(state.test_results).length > 0) {
        const tr = state.test_results;
        document.getElementById("content-sandbox").textContent = 
            `Status: ${tr.passed ? 'PASSED (100%)' : 'FAILED'}\n` +
            `Duration: ${tr.duration_ms} ms\n` +
            `Executed Test Types: ${JSON.stringify(tr.executed_test_types)}\n\n` +
            `--- Pytest Stdout ---\n${tr.stdout || '(no output)'}\n` +
            `--- Pytest Stderr ---\n${tr.stderr || '(no errors)'}`;
    } else {
        document.getElementById("content-sandbox").textContent = "No sandbox tests executed yet.";
    }

    // WORM Audit & Telemetry
    const auditInfo = {
        delivery_path: state.delivery_path,
        tradeoff_analysis: state.tradeoff_analysis,
        worm_audit_record_id: state.worm_audit_record_id || "Pending Gate H2 seal",
        close_commit_hash: state.close_commit_hash || "Not merged yet",
        pull_request_url: state.pull_request_url || "Not created yet",
        gcs_artifact_uris: state.gcs_artifact_uris,
        retry_counts: state.retry_counts,
        initiator: state.initiator,
        watch_telemetry: state.watch_telemetry_results
    };
    document.getElementById("content-audit").textContent = JSON.stringify(auditInfo, null, 2);
}
