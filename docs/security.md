# Security & Compliance

**HIPAA-aligned security practices for healthcare AI**

---

## Overview

Clintela handles Protected Health Information (PHI) and must comply with HIPAA (Health Insurance Portability and Accountability Act) regulations. This document outlines our security architecture, data handling practices, and compliance measures.

**Compliance Target:** HIPAA Security Rule, Privacy Rule, and Breach Notification Rule  
**Certification Roadmap:** HITRUST, ISO 27001, SOC 2 Type 2

---

## Security Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     SECURITY LAYERS                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 1: Network Security                                         │
│  ├── TLS 1.3 for all connections                                 │
│  ├── VPN for internal services                                   │
│  ├── WAF (Web Application Firewall)                              │
│  └── DDoS protection                                             │
│                                                                  │
│  Layer 2: Application Security                                     │
│  ├── Authentication (leaflet codes + DOB)                        │
│  ├── Authorization (role-based access control)                     │
│  ├── Input validation & sanitization                             │
│  ├── CSRF protection                                             │
│  └── Rate limiting                                               │
│                                                                  │
│  Layer 3: Data Security                                            │
│  ├── Encryption at rest (AES-256)                                  │
│  ├── Encryption in transit (TLS 1.3)                               │
│  ├── Database encryption (PostgreSQL TDE)                        │
│  └── Field-level encryption for SSNs, etc.                       │
│                                                                  │
│  Layer 4: Audit & Monitoring                                         │
│  ├── Comprehensive audit logging                                 │
│  ├── Real-time alerting                                          │
│  ├── Access monitoring                                           │
│  └── Intrusion detection                                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Authentication & Authorization

### Patient Authentication

**Two-Factor Authentication via Leaflet Codes:**

1. **Something they have:** 4-digit code from discharge leaflet
2. **Something they know:** Date of birth

**Flow:**
```
Patient receives leaflet with code at discharge
         │
         ▼
Patient texts/web chats with code
         │
         ▼
System validates code + phone number match
         │
         ▼
Patient provides DOB (flexible parsing)
         │
         ▼
3-attempt lockout with escalation
         │
         ▼
Session created (24-hour expiry)
```

**Security Measures:**
- Codes expire after 7 days or first use
- 3-attempt lockout triggers human verification
- Sessions expire after 24 hours of inactivity
- No passwords to remember or reset
- Magic links as alternative (SMS-based)

### Clinician Authentication

**SAML 2.0 Single Sign-On (Phase 2):**
- Integration with hospital identity providers
- Multi-factor authentication required
- Session timeout: 15 minutes idle, 8 hours max
- Role-based access control (RBAC)

**Roles:**
- **Nurse:** View assigned patients, respond to escalations, update status
- **Physician:** Full patient access, override AI recommendations, access all data
- **Admin:** Aggregate metrics only (no PHI access), system configuration

### Caregiver Authentication

**Invitation-Based:**
- Patient initiates invitation
- Caregiver receives SMS/email with secure link
- Caregiver verifies with patient's DOB
- Consent recorded in audit log
- Access limited to view-only (no modifications)

---

## Data Protection

### Encryption

**At Rest:**
- Database: PostgreSQL TDE (Transparent Data Encryption)
- Files: AES-256 encryption
- Backups: Encrypted with separate keys
- Keys: Managed via AWS KMS or HashiCorp Vault

**In Transit:**
- TLS 1.3 minimum
- Certificate pinning for mobile apps (future)
- HSTS headers
- No mixed content (HTTPS only)

**Field-Level Encryption:**
- SSNs (if collected)
- Insurance IDs
- Other sensitive identifiers

### Data Classification

| Data Type | Classification | Handling |
|-----------|---------------|----------|
| Patient name, DOB | PHI | Encrypted, audit logged |
| Medical history | PHI | Encrypted, access controlled |
| Messages | PHI | Encrypted, retained 7 years |
| Aggregated metrics | Non-PHI | Anonymized, no individual identification |
| System logs | Internal | Access controlled, retained 1 year |
| Audit logs | Compliance | Tamper-evident, retained 7 years |

### Data Retention

**PHI:**
- Active patients: Duration of care + 7 years
- Inactive patients: 7 years from last activity
- Deleted securely (cryptographic erasure)

**Audit Logs:**
- Retained: 7 years
- Immutable (append-only)
- Separate from application logs

**System Logs:**
- Retained: 1 year
- Rotated monthly
- Anonymized where possible

---

## Access Control

### Principle of Least Privilege

Users can only access data necessary for their role:

**Patients:**
- Own data only
- Cannot view other patients
- Cannot access clinician notes

**Caregivers:**
- Patient data with explicit consent
- View-only access
- No access to clinical assessments

**Clinicians:**
- Assigned patients (full access)
- Escalations from any patient
- Cannot access patients outside their assignment

**Administrators:**
- Aggregate metrics only
- No individual PHI access
- System configuration access

### Multi-Tenancy Isolation

**Hospital-Level Isolation:**
- Row-level security with `hospital_id`
- Database queries automatically scoped
- No cross-hospital data access
- Separate encryption keys per hospital (future)

**Implementation:**
```python
# All queries include hospital_id filter
Patient.objects.filter(
    hospital_id=request.user.hospital_id,
    id=patient_id
)
```

---

## Audit Logging

### What We Log

**All PHI Access:**
- Who accessed what data
- When (timestamp with timezone)
- From where (IP address)
- Action taken (view, create, update, delete)
- Outcome (success/failure)

**Agent Interactions:**
- Patient messages (content logged for care continuity)
- Agent responses
- Tool invocations
- Routing decisions
- Escalation triggers

**System Events:**
- Authentication attempts (success and failure)
- Authorization failures
- Configuration changes
- Data exports
- Backup/restore operations

### Audit Log Format

```json
{
  "event_id": "uuid",
  "timestamp": "2026-03-17T14:30:00Z",
  "user": {
    "id": "user_uuid",
    "type": "patient|caregiver|clinician|admin",
    "hospital_id": "hospital_uuid"
  },
  "action": "view|create|update|delete|export",
  "resource": {
    "type": "patient|message|care_plan",
    "id": "resource_uuid"
  },
  "context": {
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0...",
    "session_id": "session_uuid"
  },
  "outcome": "success|failure",
  "reason": "optional_reason_for_failure"
}
```

### Audit Log Protection

- **Immutable:** Append-only, no modifications
- **Tamper-evident:** Cryptographic hashing of log entries
- **Separate storage:** Isolated from application database
- **Access controlled:** Only compliance officers can query
- **Regular review:** Monthly audit log analysis

---

## HIPAA Compliance

### Administrative Safeguards

**Security Management:**
- Risk analysis conducted annually
- Security policies and procedures documented
- Workforce training on HIPAA requirements
- Incident response procedures

**Workforce Security:**
- Background checks for employees
- Role-based access assignment
- Termination procedures (immediate access revocation)
- Training records maintained

**Information Access Management:**
- Access authorization procedures
- Access modification procedures
- Regular access reviews (quarterly)

### Physical Safeguards

**Facility Access:**
- Data centers: SOC 2 Type II certified
- Physical access logs
- Visitor procedures
- Workstation security

**Device Security:**
- Mobile device management (for clinician apps)
- Remote wipe capability
- Encryption required on all devices
- No PHI on personal devices

### Technical Safeguards

**Access Control:**
- Unique user IDs
- Emergency access procedures
- Automatic logoff (15 minutes idle)
- Encryption and decryption

**Audit Controls:**
- Comprehensive audit logging (see above)
- Regular audit reviews
- Alerting on suspicious activity

**Integrity Controls:**
- Data validation on input
- Checksums for data integrity
- Version control for care plans
- Backup verification

**Transmission Security:**
- TLS 1.3 for all transmissions
- Certificate management
- No email transmission of PHI (unless encrypted)

---

## Incident Response

### Breach Notification

**Discovery to Notification Timeline:**
- Discovery: Immediate
- Risk assessment: Within 24 hours
- Notification (if required): Within 60 days
- HHS notification: Within 60 days
- Media notification: If >500 individuals affected

**Breach Assessment Criteria:**
- Nature and extent of PHI involved
- Unauthorized person who accessed PHI
- Whether PHI was actually acquired or viewed
- Extent to which risk has been mitigated

### Incident Response Plan

1. **Detection:** Automated alerts + manual reporting
2. **Containment:** Isolate affected systems
3. **Investigation:** Determine scope and cause
4. **Remediation:** Fix vulnerability, restore systems
5. **Notification:** If required by HIPAA
6. **Documentation:** Full incident report
7. **Review:** Post-incident analysis

---

## Third-Party Services (Business Associates)

### Current Business Associates

| Service | Provider | BAA Status | Data Handled |
|---------|----------|------------|--------------|
| LLM API | Ollama Cloud | **PENDING** | Patient messages (anonymized in production) |
| SMS/Voice | Twilio | **PENDING** | Phone numbers, message content |
| Hosting | AWS/Azure | **PENDING** | All application data |
| Database | AWS RDS / Azure PostgreSQL | **PENDING** | All PHI |

**Note:** Before production deployment, all Business Associate Agreements (BAAs) must be executed.

### BAA Requirements

All third-party services handling PHI must:
- Sign Business Associate Agreement
- Implement equivalent security safeguards
- Report breaches within 24 hours
- Allow audit rights
- Return or destroy PHI upon termination

---

## Security Testing

### Regular Assessments

**Vulnerability Scanning:**
- Weekly automated scans
- Monthly manual penetration testing
- Quarterly third-party security audit

**Code Security:**
- Static analysis (SAST) in CI/CD
- Dependency vulnerability scanning
- Secrets detection (no hardcoded credentials)

**Compliance Audits:**
- Annual HIPAA audit
- Quarterly access reviews
- Monthly audit log analysis

### Penetration Testing

**Scope:**
- External network
- Web applications
- APIs
- Mobile applications (future)

**Frequency:**
- Initial: Before production launch
- Ongoing: Quarterly
- After major changes: Within 30 days

---

## Development Security

### Secure Development Lifecycle

**Requirements:**
- Security requirements defined
- Threat modeling for new features
- Privacy impact assessments

**Design:**
- Security architecture review
- Data flow diagrams
- Trust boundaries defined

**Implementation:**
- Secure coding standards
- Code reviews (security focus)
- Static analysis tools

**Testing:**
- Security test cases
- Penetration testing
- Vulnerability scanning

**Deployment:**
- Secure configuration
- Environment hardening
- Monitoring setup

### Secrets Management

**Never commit to code:**
- API keys
- Database passwords
- Encryption keys
- JWT secrets

**Use environment variables:**
```python
# settings.py
DATABASE_URL = os.environ.get('DATABASE_URL')
TWILIO_API_KEY = os.environ.get('TWILIO_API_KEY')
```

**Secrets rotation:**
- Database credentials: Every 90 days
- API keys: Every 180 days
- Emergency rotation procedure documented

---

## Privacy Considerations

### Data Minimization

**Collect only what's necessary:**
- Patient: Name, DOB, phone, surgery type, recovery plan
- Clinician: Name, email, role, hospital assignment
- No SSN unless required for EHR integration

**Purpose limitation:**
- Data used only for care coordination
- No marketing use
- No sale of data
- No secondary uses without consent

### Patient Rights

**Access:**
- Patients can view their data
- Export in machine-readable format
- Request corrections

**Amendment:**
- Patients can request corrections
- Response within 60 days

**Accounting of Disclosures:**
- Track who accessed PHI
- Provide report upon request

---

## Compliance Checklist

### Pre-Production

- [ ] Risk analysis completed
- [ ] Security policies documented
- [ ] BAAs executed with all vendors
- [ ] Encryption implemented (at rest and in transit)
- [ ] Audit logging implemented
- [ ] Access controls tested
- [ ] Incident response plan documented
- [ ] Workforce training completed
- [ ] Penetration test passed
- [ ] Vulnerability scan clean

### Ongoing

- [ ] Quarterly access reviews
- [ ] Monthly audit log review
- [ ] Quarterly penetration testing
- [ ] Annual risk analysis
- [ ] Annual HIPAA audit
- [ ] Continuous vulnerability scanning
- [ ] Regular workforce training

---

## Related Documents

- [Engineering Review](./engineering-review.md) — Security architecture details
- [Agent System Design](./agents.md) — AI safety and content restrictions
- [Development Setup](./development.md) — Secure development environment

---

*Security & Compliance — HIPAA-aligned, audit-ready*
