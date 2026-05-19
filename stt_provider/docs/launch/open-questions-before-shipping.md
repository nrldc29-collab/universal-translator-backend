# Appendix B: Open Questions Before Shipping

## 1. Who is the customer?

Primary launch customer:

- Voice agents

Secondary future customers:

- Contact centers
- Meeting transcription platforms
- Healthcare scribes

Launch implication:

- Optimize first for low latency.
- Keep diarization available, but do not let advanced speaker identity block launch.
- Prioritize streaming stability over batch transcription features.

## 2. What is the compliance ceiling within 18 months?

Target:

- SOC 2 Type II first
- HIPAA BAA compatible later
- FedRAMP Moderate out of scope for the first 18 months

Launch implication:

- Audit logging, access control, SSO, incident response, and evidence collection are required.
- Full FedRAMP-style controls are not required for launch.

## 3. Which languages?

Launch target:

- English-only

Future expansion:

- Spanish
- French
- German
- Multilingual support after English production quality is stable

Launch implication:

- Use Parakeet-focused self-hosted optimization first.
- Do not block launch on multilingual model routing.

## 4. What is the cloud egress budget?

Target:

- Keep audio and inference traffic inside the tenant's assigned region.
- Avoid cross-region streaming unless explicitly allowed by tenant policy.
- Track egress by tenant and region.

Launch implication:

- Co-located GPU regions become important for high-volume tenants.
- Regional routing must respect tenant residency settings.

## 5. Can we reserve GPU capacity?

Launch requirement:

- Yes, production requires reserved GPU capacity.

Minimum production requirement:

- At least 2 GPU nodes
- Capacity reserved in the launch region
- No spot or preemptible GPU nodes for production streaming workloads

Launch implication:

- Do not launch self-hosted production until GPU capacity is reserved.
- Treat GPU availability as a launch blocker.

This closes the guide's pre-shipping questions: customer type, compliance ceiling, language scope, egress budget, and whether GPU capacity can be reserved for the self-hosted path.
