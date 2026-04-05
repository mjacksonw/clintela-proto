"""Support Group router and orchestrator.

Single LLM call routes patient messages to the right persona(s),
then generates the primary response and schedules followups via Celery.
"""

import logging
from typing import Literal

from asgiref.sync import sync_to_async
from django.db import transaction
from django.db.models import F
from pydantic import BaseModel, field_validator

from apps.agents.constants import (
    CRITICAL_KEYWORDS,
    LLM_MAX_TOKENS_ROUTER,
    LLM_MAX_TOKENS_SUPPORT_GROUP,
    LLM_TEMPERATURE_SUPPORT_GROUP,
    SG_CONVERSATION_HISTORY_LIMIT,
    SUPPORT_GROUP_DISTRESS_KEYWORDS,
)
from apps.agents.personas import PERSONA_REGISTRY, build_persona_prompt, get_persona

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models for router output
# ---------------------------------------------------------------------------


class FollowupPlan(BaseModel):
    persona_id: str
    delay: int  # seconds
    intent: str  # short hint for the persona prompt

    @field_validator("persona_id")
    @classmethod
    def validate_persona(cls, v: str) -> str:
        if v not in PERSONA_REGISTRY:
            raise ValueError(f"Unknown persona_id: {v}")
        return v


class ReactionPlan(BaseModel):
    persona_id: str
    emoji: str
    delay: int

    @field_validator("persona_id")
    @classmethod
    def validate_persona(cls, v: str) -> str:
        if v not in PERSONA_REGISTRY:
            raise ValueError(f"Unknown persona_id: {v}")
        return v


class GroupResponsePlan(BaseModel):
    """Validated router output for the entire group response."""

    crisis_detected: bool
    patient_mood: Literal["positive", "neutral", "struggling", "distressed"]
    primary_responder: str
    followups: list[FollowupPlan]
    reactions: list[ReactionPlan]
    silent: list[str]

    @field_validator("primary_responder")
    @classmethod
    def validate_primary(cls, v: str) -> str:
        if v not in PERSONA_REGISTRY:
            raise ValueError(f"Unknown primary_responder: {v}")
        return v


# ---------------------------------------------------------------------------
# Crisis detection (Layer 1: keyword scan, pre-LLM)
# ---------------------------------------------------------------------------


def detect_crisis_keywords(message: str) -> bool:
    """Pre-LLM keyword scan for crisis indicators."""
    lower = message.lower()
    return any(keyword in lower for keyword in CRITICAL_KEYWORDS) or any(
        keyword in lower for keyword in SUPPORT_GROUP_DISTRESS_KEYWORDS
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

ROUTER_SYSTEM_PROMPT = """\
You are the support group router. Given a patient's message and context, \
decide which AI personas should respond.

Personas:
{persona_summaries}

Patient context:
- Name: {patient_name}
- Procedure: {procedure}
- Days post-op: {days_post_op}

Rules:
- Select 1 primary responder and 0-2 followups.
- If patient_mood is "struggling" or "distressed", prefer Maria and Priya.
- If patient_mood is "positive", give space to James and Robert.
- Diane speaks rarely (only when message is deeply reflective).
- Set crisis_detected to true if the message indicates suicidal thoughts, self-harm, or medical emergency.
- Each followup needs a delay (30-180 seconds) and a one-line intent hint.
- Reactions: 0-3 emoji reactions from non-speaking personas. Delay 15-30s.
- Personas NOT responding go in the "silent" list.

Respond ONLY with valid JSON matching this schema:
{{
  "crisis_detected": false,
  "patient_mood": "neutral",
  "primary_responder": "maria",
  "followups": [{{"persona_id": "james", "delay": 60, "intent": "share similar experience"}}],
  "reactions": [{{"persona_id": "tony", "emoji": "thumbs_up", "delay": 20}}],
  "silent": ["linda", "robert", "diane"]
}}
"""


class SupportGroupRouter:
    """Single LLM call -> GroupResponsePlan for entire group."""

    def __init__(self, llm_client=None):
        from apps.agents.llm_client import get_llm_client

        self.llm_client = llm_client or get_llm_client()

    def _build_persona_summaries(self) -> str:
        lines = []
        for p in PERSONA_REGISTRY.values():
            lines.append(f"- {p.id} ({p.name}): {p.therapeutic_role}. {p.speaking_style.split('.')[0]}.")
        return "\n".join(lines)

    async def plan_group_response(
        self,
        message: str,
        patient_context: dict,
        conversation_history: list[dict],
    ) -> GroupResponsePlan:
        """Route a patient message to the right personas."""
        system_prompt = ROUTER_SYSTEM_PROMPT.format(
            persona_summaries=self._build_persona_summaries(),
            patient_name=patient_context.get("name", "Patient"),
            procedure=patient_context.get("procedure", "cardiac surgery"),
            days_post_op=patient_context.get("days_post_op", "unknown"),
        )

        messages = [
            {"role": "system", "content": system_prompt},
        ]
        # Include recent conversation for context
        for msg in conversation_history[-SG_CONVERSATION_HISTORY_LIMIT:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": message})

        try:
            result = await self.llm_client.generate_json(
                messages=messages,
                temperature=0.5,
                max_tokens=LLM_MAX_TOKENS_ROUTER,
            )
            plan = GroupResponsePlan(**result)
            return plan
        except Exception as e:
            logger.warning(f"Router failed ({e}), falling back to Maria")
            # On malformed JSON, run a simple crisis re-check before Maria fallback
            crisis = await self._crisis_recheck(message)
            return self._maria_fallback(crisis_detected=crisis)

    async def _crisis_recheck(self, message: str) -> bool:
        """Simple yes/no crisis check when router fails."""
        try:
            result = await self.llm_client.generate_json(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Does this message indicate a crisis, suicidal thoughts, or medical emergency? "
                            'Respond with JSON: {"crisis": true} or {"crisis": false}'
                        ),
                    },
                    {"role": "user", "content": message},
                ],
                temperature=0.0,
                max_tokens=50,
            )
            return result.get("crisis", False)
        except Exception:
            return False

    def _maria_fallback(self, crisis_detected: bool = False) -> GroupResponsePlan:
        """Default fallback: Maria responds alone."""
        return GroupResponsePlan(
            crisis_detected=crisis_detected,
            patient_mood="neutral",
            primary_responder="maria",
            followups=[],
            reactions=[],
            silent=[pid for pid in PERSONA_REGISTRY if pid != "maria"],
        )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class SupportGroupOrchestrator:
    """Manages full flow: crisis scan -> router -> generation -> scheduling."""

    def __init__(self, llm_client=None):
        from apps.agents.llm_client import get_llm_client

        self.llm_client = llm_client or get_llm_client()
        self.router = SupportGroupRouter(self.llm_client)

    async def process_message(self, patient, conversation, message: str) -> dict:
        """Process a patient message through the support group pipeline.

        Returns dict with primary response, or escalation info.
        """

        # 1. Pre-LLM crisis keyword scan (Layer 1)
        keyword_crisis = detect_crisis_keywords(message)

        # 2. Save message + handle crisis atomically
        if keyword_crisis:
            return await self._handle_crisis(patient, conversation, message, source="keyword")

        # 3. Increment generation_id atomically
        await self._increment_generation_id(conversation)

        # 4. Build context (ORM access must run in sync context — async consumer)
        patient_context = await sync_to_async(self._build_patient_context)(patient)
        history = await self._get_conversation_history(conversation)

        # 5. Router call (Layer 2 crisis detection)
        plan = await self.router.plan_group_response(message, patient_context, history)

        if plan.crisis_detected:
            return await self._handle_crisis(patient, conversation, message, source="router")

        # 6. Generate primary persona response
        persona = get_persona(plan.primary_responder)
        memory = conversation.persona_memories.get(persona.id, "")
        prompt = build_persona_prompt(persona, patient_context, memory)

        primary_response = await self._generate_persona_response(
            persona, prompt, message, history, plan_intent="primary responder"
        )

        # 7. Save primary response
        primary_msg = await self._save_message(
            conversation=conversation,
            role="assistant",
            content=primary_response,
            persona_id=persona.id,
            generation_id=conversation.generation_id,
        )

        # 8. Schedule followups and reactions via Celery
        await self._schedule_followups(conversation, plan, patient_context)
        await self._schedule_reactions(primary_msg, plan, conversation.generation_id)

        return {
            "type": "support_group_message",
            "message_id": str(primary_msg.id),
            "persona_id": persona.id,
            "persona_name": persona.name,
            "content": primary_response,
            "avatar_color": persona.avatar_color,
            "avatar_color_dark": persona.avatar_color_dark,
            "avatar_initials": persona.avatar_initials,
            "escalate": False,
        }

    async def _handle_crisis(self, patient, conversation, message, source):
        """Handle crisis: save message + create escalation atomically."""
        from apps.agents.models import AgentMessage
        from apps.agents.services import EscalationService

        # Get recent messages for escalation context
        recent = await self._get_recent_messages_text(conversation, limit=5)
        excerpt = f"[TRIGGERING MESSAGE]\n{message}\n\n[RECENT CONTEXT]\n{recent}"

        @transaction.atomic
        def _create_crisis_records():
            msg = AgentMessage.objects.create(
                conversation=conversation,
                role="user",
                content=message,
                metadata={"crisis_source": source},
            )
            EscalationService.create_escalation(
                patient=patient,
                conversation=conversation,
                reason=f"Support group crisis detected ({source}): {message[:200]}",
                severity="critical",
                conversation_summary=f"Crisis detected in support group via {source} scan",
                patient_context={"source": "support_group"},
            )
            # Update the conversation_excerpt on the escalation
            from apps.agents.models import Escalation

            esc = Escalation.objects.filter(patient=patient, conversation=conversation).order_by("-created_at").first()
            if esc:
                esc.conversation_excerpt = excerpt
                esc.save(update_fields=["conversation_excerpt"])
            return msg

        from asgiref.sync import sync_to_async

        await sync_to_async(_create_crisis_records)()

        # Cancel pending followups by incrementing generation_id
        await self._increment_generation_id(conversation)

        return {
            "type": "crisis_detected",
            "escalate": True,
            "source": source,
        }

    async def _increment_generation_id(self, conversation):
        """Atomically increment generation_id using queryset.update()."""
        from asgiref.sync import sync_to_async

        from apps.agents.models import AgentConversation

        def _do_increment():
            AgentConversation.objects.filter(pk=conversation.pk).update(generation_id=F("generation_id") + 1)
            conversation.refresh_from_db(fields=["generation_id"])

        await sync_to_async(_do_increment)()

    def _build_patient_context(self, patient) -> dict:
        """Build patient context dict for prompts."""
        ctx = {
            "name": patient.user.first_name if patient.user else "Patient",
            "procedure": "cardiac surgery",
            "days_post_op": 0,
        }
        try:
            ctx["days_post_op"] = patient.days_post_op()
        except Exception:  # noqa: BLE001
            logger.debug("Could not get days_post_op for patient %s", patient.id)
        try:
            if hasattr(patient, "procedure_type") and patient.procedure_type:
                ctx["procedure"] = patient.procedure_type
            elif hasattr(patient, "primary_diagnosis") and patient.primary_diagnosis:
                ctx["procedure"] = patient.primary_diagnosis
        except Exception:  # noqa: BLE001
            logger.debug("Could not get procedure for patient %s", patient.id)
        try:
            prefs = patient.preferences
            if prefs.preferred_name:
                ctx["name"] = prefs.preferred_name
            if prefs.procedure_type:
                ctx["procedure_type"] = prefs.procedure_type
        except Exception:  # noqa: BLE001
            logger.debug("Could not get preferences for patient %s", patient.id)
        return ctx

    async def _get_conversation_history(self, conversation) -> list[dict]:
        """Get recent conversation messages as dicts."""
        from asgiref.sync import sync_to_async

        from apps.agents.models import AgentMessage

        def _fetch():
            msgs = AgentMessage.objects.filter(conversation=conversation).order_by("-created_at")[
                :SG_CONVERSATION_HISTORY_LIMIT
            ]
            return [{"role": m.role, "content": m.content, "persona_id": m.persona_id} for m in reversed(msgs)]

        return await sync_to_async(_fetch)()

    async def _get_recent_messages_text(self, conversation, limit=5) -> str:
        """Get recent messages as formatted text for escalation context."""
        from asgiref.sync import sync_to_async

        from apps.agents.models import AgentMessage

        def _fetch():
            msgs = AgentMessage.objects.filter(conversation=conversation).order_by("-created_at")[:limit]
            lines = []
            for m in reversed(msgs):
                role = "Patient" if m.role == "user" else (m.persona_id or "AI")
                lines.append(f"{role}: {m.content}")
            return "\n".join(lines)

        return await sync_to_async(_fetch)()

    async def _generate_persona_response(self, persona, system_prompt, patient_message, history, plan_intent="") -> str:
        """Generate a single persona's response."""
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history[-SG_CONVERSATION_HISTORY_LIMIT:]:
            if msg["role"] == "user":
                messages.append({"role": "user", "content": msg["content"]})
            else:
                name = msg.get("persona_id", "assistant")
                messages.append({"role": "assistant", "content": f"[{name}]: {msg['content']}"})

        if plan_intent:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        f"Respond to the patient's latest message. Intent: {plan_intent}. "
                        "Keep your response warm, concise (2-4 sentences), and in character."
                    ),
                }
            )
        messages.append({"role": "user", "content": patient_message})

        try:
            result = await self.llm_client.generate(
                messages=messages,
                temperature=LLM_TEMPERATURE_SUPPORT_GROUP,
                max_tokens=LLM_MAX_TOKENS_SUPPORT_GROUP,
            )
            return result["content"].strip()
        except Exception as e:
            logger.error(f"Persona {persona.id} generation failed: {e}")
            return "I'm here, just gathering my thoughts. Give me a moment."

    async def _save_message(self, conversation, role, content, persona_id=None, generation_id=None, metadata=None):
        """Save a message to the conversation."""
        from asgiref.sync import sync_to_async

        from apps.agents.models import AgentMessage

        def _create():
            return AgentMessage.objects.create(
                conversation=conversation,
                role=role,
                content=content,
                persona_id=persona_id,
                generation_id=generation_id,
                metadata=metadata or {},
            )

        return await sync_to_async(_create)()

    async def _schedule_followups(self, conversation, plan, patient_context):
        """Schedule Celery tasks for followup personas."""
        from apps.agents.tasks import deliver_support_group_followup

        for followup in plan.followups:
            deliver_support_group_followup.delay(
                conversation_id=str(conversation.id),
                persona_id=followup.persona_id,
                intent=followup.intent,
                generation_id=conversation.generation_id,
                patient_context=patient_context,
            )

    async def _schedule_reactions(self, message, plan, generation_id):
        """Schedule Celery tasks for emoji reactions."""
        from apps.agents.tasks import deliver_support_group_reaction

        for reaction in plan.reactions:
            deliver_support_group_reaction.delay(
                message_id=str(message.id),
                persona_id=reaction.persona_id,
                emoji=reaction.emoji,
                generation_id=generation_id,
            )
