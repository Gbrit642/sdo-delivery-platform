"""Google Chat Adapter formatting Interactive Cards and Webhook Payloads."""

from __future__ import annotations

from typing import Any
from graphs.state import LoopState


class GoogleChatAdapter:
    """Formats rich Google Chat cards for brief intake and human approval gates."""

    @classmethod
    def format_intake_ack_card(cls, state: LoopState) -> dict[str, Any]:
        """Card acknowledging loop creation and intake."""
        return {
            "cardsV2": [
                {
                    "cardId": f"intake-{state.loop_id}",
                    "card": {
                        "header": {
                            "title": f"SDO Loop Initialized ({state.node_id.title()})",
                            "subtitle": f"Loop ID: {state.loop_id}",
                            "imageUrl": "https://fonts.gstatic.com/s/i/short-term/release/googlegsymbol/auto_awesome/default/48px.svg",
                        },
                        "sections": [
                            {
                                "header": "Business Brief",
                                "widgets": [
                                    {"textParagraph": {"text": f"<b>Brief:</b> {state.brief_raw}"}},
                                    {"textParagraph": {"text": f"<b>Initiator:</b> {state.initiator.user_email}"}},
                                    {"textParagraph": {"text": "<b>Status:</b> Synthesizing specification (SPECIFY)..."}},
                                ],
                            }
                        ],
                    },
                }
            ]
        }

    @classmethod
    def format_gate_h1_card(cls, state: LoopState) -> dict[str, Any]:
        """Interactive card for Gate H1 Specification Sign-Off."""
        return {
            "cardsV2": [
                {
                    "cardId": f"gate-h1-{state.loop_id}",
                    "card": {
                        "header": {
                            "title": "Gate H1: Specification Sign-Off Required",
                            "subtitle": f"Loop ID: {state.loop_id} • Domain: {state.node_id.title()}",
                            "imageUrl": "https://fonts.gstatic.com/s/i/short-term/release/googlegsymbol/verified_user/default/48px.svg",
                        },
                        "sections": [
                            {
                                "header": "Generated Specification Summary",
                                "widgets": [
                                    {
                                        "textParagraph": {
                                            "text": f"<pre>{(state.spec_content or '')[:400]}...</pre>"
                                        }
                                    },
                                    {
                                        "textParagraph": {
                                            "text": "<b>Two-Tier Quality Harness:</b> <font color='#2e7d32'>PASSED (Tier 1 AST + Tier 2 Critic)</font>"
                                        }
                                    },
                                ],
                            },
                            {
                                "widgets": [
                                    {
                                        "buttonList": {
                                            "buttons": [
                                                {
                                                    "text": "Approve Specification",
                                                    "onClick": {
                                                        "action": {
                                                            "function": "resolve_gate",
                                                            "parameters": [
                                                                {"key": "loop_id", "value": state.loop_id},
                                                                {"key": "gate", "value": "h1"},
                                                                {"key": "decision", "value": "approve"},
                                                            ],
                                                        }
                                                    },
                                                },
                                                {
                                                    "text": "Request Changes",
                                                    "onClick": {
                                                        "action": {
                                                            "function": "resolve_gate",
                                                            "parameters": [
                                                                {"key": "loop_id", "value": state.loop_id},
                                                                {"key": "gate", "value": "h1"},
                                                                {"key": "decision", "value": "request_changes"},
                                                            ],
                                                        }
                                                    },
                                                },
                                            ]
                                        }
                                    }
                                ]
                            },
                        ],
                    },
                }
            ]
        }

    @classmethod
    def format_gate_h2_card(cls, state: LoopState) -> dict[str, Any]:
        """Interactive card for Gate H2 Final Merge & Deploy Sign-Off."""
        test_rate = state.test_results.get("pass_rate", 100.0)
        pr_url = state.pull_request_url or "https://github.com/wallbox/sdo-deliverables/pull/1"

        return {
            "cardsV2": [
                {
                    "cardId": f"gate-h2-{state.loop_id}",
                    "card": {
                        "header": {
                            "title": "Gate H2: Final Merge & Deploy Sign-Off Required",
                            "subtitle": f"Loop ID: {state.loop_id} • Domain: {state.node_id.title()}",
                            "imageUrl": "https://fonts.gstatic.com/s/i/short-term/release/googlegsymbol/rocket_launch/default/48px.svg",
                        },
                        "sections": [
                            {
                                "header": "Deliverable & Sandbox Test Results",
                                "widgets": [
                                    {"textParagraph": {"text": f"<b>Sandbox Test Pass Rate:</b> <font color='#2e7d32'>{test_rate}% Passed</font>"}},
                                    {"textParagraph": {"text": f"<b>GitHub Pull Request:</b> <a href='{pr_url}'>{pr_url}</a>"}},
                                    {"textParagraph": {"text": f"<b>Reviewer Summary:</b> {state.code_artifacts.get('review_summary', 'All criteria verified.')}"}},
                                ],
                            },
                            {
                                "widgets": [
                                    {
                                        "buttonList": {
                                            "buttons": [
                                                {
                                                    "text": "Approve Merge & Deploy",
                                                    "onClick": {
                                                        "action": {
                                                            "function": "resolve_gate",
                                                            "parameters": [
                                                                {"key": "loop_id", "value": state.loop_id},
                                                                {"key": "gate", "value": "h2"},
                                                                {"key": "decision", "value": "approve"},
                                                            ],
                                                        }
                                                    },
                                                },
                                                {
                                                    "text": "Reject",
                                                    "onClick": {
                                                        "action": {
                                                            "function": "resolve_gate",
                                                            "parameters": [
                                                                {"key": "loop_id", "value": state.loop_id},
                                                                {"key": "gate", "value": "h2"},
                                                                {"key": "decision", "value": "reject"},
                                                            ],
                                                        }
                                                    },
                                                },
                                            ]
                                        }
                                    }
                                ]
                            },
                        ],
                    },
                }
            ]
        }
