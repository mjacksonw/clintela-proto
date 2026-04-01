"""Template context processors for agents feature flags."""

import json

from .constants import ENABLE_SUPPORT_GROUP
from .personas import PERSONA_REGISTRY


def support_group_flags(request):
    ctx = {
        "ENABLE_SUPPORT_GROUP": ENABLE_SUPPORT_GROUP,
    }
    if ENABLE_SUPPORT_GROUP:
        # Serialize persona data for profile cards (consumed by window.__sgPersonas)
        persona_data = {
            pid: {
                "id": p.id,
                "name": p.name,
                "age": p.age,
                "background": p.background,
                "procedure": p.procedure,
                "months_post_op": p.months_post_op,
                "therapeutic_role": p.therapeutic_role,
                "avatar_color": p.avatar_color,
                "avatar_initials": p.avatar_initials,
            }
            for pid, p in PERSONA_REGISTRY.items()
        }
        ctx["sg_personas_json"] = json.dumps(persona_data)
    return ctx
