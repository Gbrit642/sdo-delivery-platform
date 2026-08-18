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
        });
    });
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

        try {
            const resp = await fetch("/api/v1/loops", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    node_id: nodeId,
                    owner_email: ownerEmail,
                    brief_text: briefText
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
        document.getElementById("gate-desc").textContent = "Review the sandbox test report (100% pass rate) and pull request. Approve to squash-merge and deploy.";
    } else {
        gatePanel.style.display = "none";
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
        worm_audit_record_id: state.worm_audit_record_id || "Pending Gate H2 seal",
        close_commit_hash: state.close_commit_hash || "Not merged yet",
        pull_request_url: state.pull_request_url || "Not created yet",
        retry_counts: state.retry_counts,
        initiator: state.initiator,
        watch_telemetry: state.watch_telemetry_results
    };
    document.getElementById("content-audit").textContent = JSON.stringify(auditInfo, null, 2);
}
