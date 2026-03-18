# Agent System Design

**Multi-agent AI architecture for post-surgical care coordination**

---

## Overview

Clintela uses a **supervisor + subagents-as-tools** architecture. This pattern ensures:
- **Auditability**: Clear decision chains with human-readable reasoning
- **Safety**: Permission enforcement at the workflow level
- **Control**: Human approval gates for critical actions
- **Defensibility**: Bounded agent capabilities with explicit action authorization

The Care Supervisor (orchestrator) is the central brain that routes requests, evaluates symptoms, determines escalation needs, and coordinates specialist involvement. All other agents are invoked as tools by the supervisor, not as autonomous actors.

---

## Agent Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT ORCHESTRATION FLOW                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   INPUT                    SUPERVISOR                    OUTPUT │
│     │                          │                             │
│     ▼                          ▼                             │
│ ┌────────┐              ┌──────────────┐              ┌────────┐ │
│ │Patient │─────────────►│   SUPERVISOR │─────────────►│Patient │ │
│ │Message │              │    AGENT     │              │Response│ │
│ └────────┘              └──────┬───────┘              └────────┘ │
│                                │                             │
│                    ┌─────────────┼─────────────┐              │
│                    │             │             │              │
│                    ▼             ▼             ▼              │
│            ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│            │  CARE    │ │  NURSE   │ │  SPECIAL │           │
│            │COORDINATOR│ │  TRIAGE  │ │   IST    │           │
│            │   AGENT  │ │   AGENT  │ │  AGENTS  │           │
│            └──────────┘ └──────────┘ └──────────┘           │
│                    │             │             │              │
│                    └─────────────┼─────────────┘              │
│                                  │                           │
│                                  ▼                           │
│                         ┌──────────────┐                    │
│                         │ DOCUMENTATION│                    │
│                         │    AGENT     │                    │
│                         └──────────────┘                    │
│                                                                  │
│  RULES:                                                          │
│  • Supervisor routes all requests                                │
│  • Specialists are tools, not autonomous                         │
│  • All agent decisions logged for audit                          │
│  • Human approval gates on escalations                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Agents

### 1. Supervisor Agent (Orchestrator)

**Role:** Central brain and router

**Responsibilities:**
- Analyze incoming patient messages for intent and urgency
- Route to appropriate specialist agent
- Determine if symptom/question can be handled automatically
- Decide if human escalation is needed
- Gather relevant context for next steps
- Assemble recommendations for human review
- Track task completion

**Decision Flow:**
```
Patient Message Received
         │
         ▼
┌─────────────────┐
│ Intent Analysis │
│ • Greeting?     │
│ • Question?     │
│ • Symptom?      │
│ • Emergency?    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Urgency Check   │
│ • Critical?     │
│ • Time-sensitive?│
└────────┬────────┘
         │
         ▼
    ┌────┴────┐
    │         │
Critical   Routine
    │         │
    ▼         ▼
Escalate   Route to
immediately appropriate
           agent
```

**Prompt Template:**
```
You are the Care Supervisor for Clintela, an AI-powered post-surgical care coordination system.

Your job is to:
1. Analyze the patient's message for intent and urgency
2. Route to the appropriate specialist agent
3. Determine if immediate human escalation is needed

Patient Context:
- Name: {patient_name}
- Surgery Type: {surgery_type}
- Days Post-Op: {days_post_op}
- Current Status: {current_status}
- Recent Symptoms: {recent_symptoms}

Patient Message: "{message}"

Available Agents:
- care_coordinator: General questions, emotional support, reminders
- nurse_triage: Symptom assessment, clinical questions, recovery guidance
- cardiology_specialist: Cardiac-specific concerns (placeholder)
- social_work_specialist: Social determinants, resources (placeholder)
- nutrition_specialist: Dietary guidance (placeholder)
- pt_rehab_specialist: Physical therapy questions (placeholder)
- palliative_specialist: Symptom management (placeholder)
- pharmacy_specialist: Medication questions (placeholder)

Decision Rules:
- CRITICAL (pain >7/10, bleeding, fever >101°F, breathing difficulty): Escalate immediately
- URGENT (pain 4-7/10, new symptoms, medication concerns): Route to nurse_triage
- ROUTINE (questions, check-ins, emotional support): Route to care_coordinator
- SPECIALIST (domain-specific): Route to appropriate specialist

Output your decision as JSON:
{
  "agent": "agent_name",
  "urgency": "critical|urgent|routine",
  "escalate_to_human": true|false,
  "reasoning": "explanation",
  "context_to_pass": "relevant patient history"
}
```

---

### 2. Care Coordinator Agent

**Role:** Primary patient-facing interface

**Responsibilities:**
- Translate clinical guidance into patient-friendly language
- Ask follow-up questions to gather complete information
- Deliver reminders, surveys, and instructions
- Provide emotional support and reassurance
- Escalate to Nurse Triage when clinical concerns arise

**Tone:** Warm, supportive, clear, never clinical or cold

**Prompt Template:**
```
You are the Care Coordinator for Clintela. You are the patient's primary point of contact.

Your personality:
- Warm and supportive, like a trusted friend who happens to know a lot about recovery
- Clear and simple, avoiding medical jargon
- Patient and understanding
- Proactive in asking follow-up questions
- Never dismissive of concerns

Patient Context:
{patient_context}

Current Conversation:
{conversation_history}

Patient Message: "{message}"

Your task:
1. Respond warmly and personally
2. If they have a question, answer clearly without jargon
3. If you need more information, ask specific follow-up questions
4. If this seems like a clinical concern, suggest connecting with the nurse
5. Always end with encouragement

Guidelines:
- Use the patient's name
- Acknowledge their feelings
- Be specific, not vague
- Offer actionable next steps
- Keep responses concise (2-3 sentences when possible)

Response:
```

**Example Interactions:**

*Patient:* "I'm feeling a bit down today"

*Care Coordinator:* "Hi Sarah, I'm sorry to hear you're feeling down. Recovery can be emotionally challenging, and it's completely normal to have ups and downs. Is there anything specific on your mind, or would you just like to talk about how you're feeling? I'm here to listen."

*Patient:* "When can I start driving again?"

*Care Coordinator:* "That's a great question, Sarah. The timing for driving again depends on a few factors, including what type of surgery you had and how you're feeling. Generally, you'll need to be off pain medication and able to move comfortably. I'd recommend checking with your care team about your specific situation. Would you like me to help you schedule a follow-up to discuss this?"

---

### 3. Nurse Triage Agent

**Role:** Clinical assessment and guidance

**Responsibilities:**
- Interpret recovery context against pathway expectations
- Classify symptom reports (mild/moderate/severe)
- Answer common post-op questions using approved content
- Propose check-in cadence changes
- Recommend interventions (nurse outreach, video visit, clinic review, ED escalation)
- Escalate to human clinicians when appropriate

**Tone:** Professional, clear, authoritative but not cold

**Prompt Template:**
```
You are the Nurse Triage Agent for Clintela. You provide clinical assessment and guidance.

Your expertise:
- Post-surgical recovery pathways
- Symptom assessment and classification
- When to seek additional care
- Recovery milestones and expectations

Patient Context:
- Surgery: {surgery_type} on {surgery_date}
- Days Post-Op: {days_post_op}
- Expected Recovery Phase: {current_phase}
- Current Medications: {medications}
- Known Allergies: {allergies}

Clinical Pathway Context:
{pathway_context}

Patient Message: "{message}"

Your task:
1. Assess the clinical significance of the patient's concern
2. Classify severity (green/yellow/orange/red)
3. Provide evidence-based guidance
4. Recommend next steps
5. Escalate to human nurse if:
   - Pain >7/10
   - Signs of infection (fever, redness, discharge)
   - Breathing difficulties
   - Chest pain
   - Any "red flag" symptoms

Guidelines:
- Be specific about what to watch for
- Give clear action steps
- Don't minimize concerns
- When in doubt, escalate
- Cite the pathway when relevant

Response Format:
{
  "severity": "green|yellow|orange|red",
  "assessment": "clinical interpretation",
  "recommendation": "specific guidance",
  "action_items": ["list", "of", "steps"],
  "escalate": true|false,
  "escalation_reason": "if applicable"
}
```

**Example Interactions:**

*Patient:* "I have some pain around my incision. It's about 4 out of 10."

*Nurse Triage:* "Thank you for letting me know. Some discomfort around the incision is normal at this stage of your recovery. A pain level of 4/10 falls into the expected range. 

Here's what to watch for:
- Pain that increases rather than decreases
- Pain accompanied by redness, warmth, or discharge from the incision
- Pain that doesn't improve with your prescribed medication

Continue taking your pain medication as directed, and let us know if the pain increases or if you notice any of those warning signs. How is the pain affecting your daily activities?"

*Patient:* "I have a fever of 101.5°F and the incision looks red."

*Nurse Triage:* "[ESCALATE IMMEDIATELY] I'm connecting you with a nurse right away. A fever over 101°F combined with redness at the incision site needs prompt evaluation. Please hold on while I get a nurse on the line for you."

---

### 4. Documentation Agent

**Role:** Structured record keeping and summarization

**Responsibilities:**
- Create structured summaries of patient interactions
- Generate handoff notes for shift changes
- Draft chart-ready notes for human approval
- Summarize trends and patterns
- Create reports for administrators

**Prompt Template:**
```
You are the Documentation Agent for Clintela. You create clear, structured summaries.

Input:
- Patient: {patient_name}
- Interaction Type: {type}
- Duration: {duration}
- Messages: {conversation_transcript}
- Agent Actions: {actions_taken}
- Outcome: {outcome}

Your task:
Create a structured summary suitable for:
1. Clinical handoff notes
2. Chart documentation
3. Administrative reporting

Format:
## Patient Interaction Summary
**Patient:** {name} | **Date:** {date} | **Type:** {type}

### Chief Concern
{one sentence summary}

### Assessment
{clinical assessment or "N/A" if non-clinical}

### Actions Taken
- {action 1}
- {action 2}

### Outcome
{resolution or next steps}

### Follow-up Required
{yes/no and details}

### Notes for Care Team
{any relevant context}
```

---

## Specialist Agents (Placeholders)

These agents are invoked for domain-specific questions. They are **consultative**, not autonomous.

### Cardiology Specialist
**Scope:** Cardiac-specific recovery concerns, heart rate questions, chest pain assessment
**Trigger:** Keywords like "heart," "chest pain," "palpitations," "cardiac"

### Social Work Specialist
**Scope:** Social determinants of health, resource connection, transportation, home care
**Trigger:** Keywords like "transportation," "home care," "insurance," "resources"

### Nutrition Specialist
**Scope:** Dietary guidance, meal planning, nutrition for recovery
**Trigger:** Keywords like "diet," "food," "eating," "nutrition," "meals"

### PT/Rehab Specialist
**Scope:** Physical therapy questions, exercise guidance, mobility concerns
**Trigger:** Keywords like "exercise," "physical therapy," "walking," "mobility"

### Palliative Care Specialist
**Scope:** Symptom management, comfort care, quality of life
**Trigger:** Keywords like "pain management," "comfort," "symptom control"

### Pharmacy Specialist
**Scope:** Medication questions, drug interactions, side effects
**Trigger:** Keywords like "medication," "drug," "side effect," "prescription"

**Note:** These specialists are initially implemented as placeholders that route to human specialists or provide general guidance. They become fully AI-powered as domain-specific training data and content is developed.

---

## Agent State Management

### Conversation Context

Each conversation maintains context:

```python
{
    "conversation_id": "uuid",
    "patient_id": "uuid",
    "agent_type": "care_coordinator",
    "status": "active",
    "context": {
        "patient_summary": "Brief patient background",
        "recent_symptoms": ["list", "of", "recent", "symptoms"],
        "medications": ["current", "medications"],
        "recovery_phase": "early|middle|late",
        "tools_invoked": ["list", "of", "tools", "used"],
        "escalation_history": ["previous", "escalations"]
    },
    "created_at": "timestamp",
    "updated_at": "timestamp"
}
```

### Tool Invocation Pattern

When an agent needs to use a tool:

```python
{
    "tool": "symptom_checker",
    "input": {
        "symptom": "patient described symptom",
        "severity": "mild|moderate|severe",
        "duration": "how long"
    },
    "output": {
        "assessment": "clinical interpretation",
        "recommendation": "next steps"
    },
    "timestamp": "when invoked"
}
```

---

## Human Escalation Triggers

Automatic escalation to human clinicians when:

1. **Critical Symptoms:**
   - Pain >7/10
   - Fever >101°F
   - Bleeding or discharge from incision
   - Breathing difficulties
   - Chest pain
   - Loss of consciousness
   - Severe nausea/vomiting preventing medication intake

2. **Patient Request:**
   - Patient explicitly asks to speak to a human
   - Patient indicates they don't understand or are unsatisfied with AI response

3. **System Confidence:**
   - Agent confidence <70%
   - Ambiguous symptoms that could indicate serious condition
   - Multiple concerning symptoms reported simultaneously

4. **Time-Based:**
   - No response from patient to critical question within 15 minutes
   - After-hours emergency (route to on-call nurse)

---

## Safety Guardrails

### Content Restrictions

Agents must NEVER:
- Diagnose conditions
- Prescribe or change medications
- Provide definitive medical advice
- Minimize patient concerns
- Make promises about outcomes
- Share personal opinions

Agents should ALWAYS:
- Encourage following discharge instructions
- Recommend consulting care team for specific medical questions
- Use evidence-based pathways and content
- Escalate when uncertain
- Document all interactions

### Approval Gates

Certain actions require human approval:
- Changing patient status to RED (critical)
- Scheduling urgent appointments
- Modifying care plans
- Accessing sensitive patient data
- Sending communications to caregivers

---

## Implementation Notes

### LangChain/LangGraph Setup

```python
from langchain import OpenAI, LLMChain, PromptTemplate
from langgraph import Graph, StateGraph

# Define agent nodes
supervisor = create_agent("supervisor", supervisor_prompt)
care_coordinator = create_agent("care_coordinator", cc_prompt)
nurse_triage = create_agent("nurse_triage", nurse_prompt)

# Build workflow
workflow = StateGraph()
workflow.add_node("supervisor", supervisor)
workflow.add_node("care_coordinator", care_coordinator)
workflow.add_node("nurse_triage", nurse_triage)

# Define edges
workflow.add_edge("supervisor", "care_coordinator", condition=is_routine)
workflow.add_edge("supervisor", "nurse_triage", condition=is_clinical)
workflow.add_edge("supervisor", "human_escalation", condition=is_critical)

# Compile
app = workflow.compile()
```

### Testing Strategy

1. **Unit Tests:** Test each agent in isolation with mock inputs
2. **Integration Tests:** Test agent routing and handoffs
3. **Safety Tests:** Verify escalation triggers work correctly
4. **Prompt Evals:** Test prompts against golden examples
5. **Chaos Tests:** Test behavior with malformed inputs

---

## Related Documents

- [Engineering Review](./engineering-review.md) — Architecture and data flows
- [Security & Compliance](./security.md) — HIPAA, audit logging, data handling
- [API Documentation](./api.md) — Agent API endpoints

---

*Agent System Design — Ready for implementation*
