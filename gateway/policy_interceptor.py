"""Policy Interceptor enforcing multi-tenant domain authorization and RBAC."""

from __future__ import annotations

import logging
from graphs.state import ActorIdentity
from registry.skill_registry import get_skill_registry

logger = logging.getLogger(__name__)


class PolicyInterceptor:
    """Evaluates whether an actor identity has authorization to initiate loops or sign off on gates for a domain."""

    @classmethod
    def verify_node_access(cls, actor: ActorIdentity, node_id: str) -> bool:
        """Check if actor possesses authorized roles for the target domain node."""
        if actor.actor_type == "agent":
            return True  # Internal engine identity is authorized

        registry = get_skill_registry()
        try:
            skill = registry.get_skill(node_id)
            authorized_roles = set(skill.authorized_roles)
            actor_roles = set(actor.roles)

            # Check role intersection or superuser role
            if "admin" in actor_roles or "finance_admin" in actor_roles:
                return True

            has_access = bool(authorized_roles.intersection(actor_roles))
            if not has_access:
                logger.warning(
                    "Access denied: User '%s' with roles %s lacks required roles %s for domain '%s'",
                    actor.user_email,
                    actor.roles,
                    skill.authorized_roles,
                    node_id,
                )
            return has_access
        except Exception as e:
            logger.error("Error verifying domain access: %s", e)
            return False
