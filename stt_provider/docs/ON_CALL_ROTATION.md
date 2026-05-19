# On-Call Rotation Process for STT Platform

## Overview

This document defines the on-call rotation process for the STT Platform engineering team. It ensures 24/7 coverage for critical incidents and provides clear escalation paths.

## On-Call Structure

### Roles

**Primary On-Call**
- First point of contact for all alerts
- Expected to respond within 5 minutes of P1/P2 alerts
- Expected to respond within 15 minutes of P3 alerts
- Available via phone, Slack, and PagerDuty

**Secondary On-Call**
- Backup for primary on-call
- Takes over if primary is unavailable
- Expected to respond within 10 minutes of escalation
- Available via phone and Slack

**On-Call Manager**
- Oversees on-call schedule
- Handles schedule changes and conflicts
- Reviews on-call performance
- Provides support during major incidents

### Rotation Schedule

- **Weekly rotation**: Changes every Monday at 00:00 UTC
- **Handover window**: Sunday 20:00-23:59 UTC
- **Schedule published**: 2 weeks in advance
- **Schedule location**: Slack #on-call channel and Google Calendar

## Alert Priorities

### P1 - Critical (Immediate Response)

**Definition**: Complete service outage affecting all users

**Examples**:
- STT Gateway completely down
- Triton backend down
- Database down
- Security breach

**Response Time**: 5 minutes

**Escalation**: Escalate to secondary after 10 minutes, to engineering lead after 20 minutes

### P2 - High (Urgent Response)

**Definition**: Significant degradation affecting most users

**Examples**:
- High error rate (>10%)
- Severe latency (>10s)
- Partial service outage
- Data loss risk

**Response Time**: 15 minutes

**Escalation**: Escalate to secondary after 30 minutes, to engineering lead after 45 minutes

### P3 - Medium (Standard Response)

**Definition**: Partial degradation affecting some users

**Examples**:
- Moderate error rate (5-10%)
- Moderate latency (5-10s)
- Non-critical feature down
- Performance degradation

**Response Time**: 1 hour

**Escalation**: Escalate to secondary after 2 hours, to engineering lead after 4 hours

### P4 - Low (Low Priority)

**Definition**: Minor issues with minimal user impact

**Examples**:
- Low error rate (<5%)
- Minor latency (<5s)
- Documentation issues
- Cosmetic bugs

**Response Time**: Next business day

**Escalation**: No escalation required

## On-Call Responsibilities

### During Shift

**Monitoring**
- Monitor PagerDuty for alerts
- Check Grafana dashboards for anomalies
- Review Slack #alerts channel
- Monitor email for security alerts

**Response**
- Acknowledge alerts within SLA
- Join incident bridge for major incidents
- Document incident progress
- Communicate status updates

**Resolution**
- Attempt to resolve issues using runbooks
- Escalate if unable to resolve
- Coordinate with other teams if needed
- Ensure proper handoff after resolution

### Handoff

**Before Handoff**
- Document all open incidents
- Update incident status in Slack
- Review runbooks for recent changes
- Note any ongoing issues

**During Handoff**
- Schedule 15-minute handoff call
- Review open incidents and their status
- Discuss any patterns or concerns
- Transfer PagerDuty responsibility

**After Handoff**
- Confirm PagerDuty transfer complete
- Update on-call calendar
- Post handoff summary to Slack

## Escalation Path

### Level 1: Primary On-Call
- Initial responder
- Expected to handle most incidents independently

### Level 2: Secondary On-Call
- Backup for primary
- Provides support during complex incidents
- Takes over if primary is unavailable

### Level 3: Engineering Lead
- Technical escalation
- Provides guidance on complex issues
- Makes architectural decisions if needed

### Level 4: CTO/VP Engineering
- Executive escalation
- Handles business-impacting decisions
- Coordinates with other departments

### Level 5: CEO
- Critical incidents only
- Customer communication
- Legal/PR coordination

## Communication

### Internal Communication

**Slack Channels**
- `#on-call`: On-call coordination
- `#alerts`: Alert notifications
- `#incidents`: Incident discussion
- `#engineering`: General engineering updates

**Incident Bridge**
- Use for all P1 and P2 incidents
- Join within 5 minutes of alert
- Keep line open during incident

**Status Updates**
- Update incident status every 15 minutes during active incidents
- Post resolution summary after incident
- Document in incident log

### External Communication

**Customer Communication**
- Only for P1 incidents
- Coordinated with customer success team
- Use approved communication templates
- Include ETA for resolution when known

**Social Media**
- Only for P1 incidents
- Coordinated with PR team
- Use approved messaging
- Update as situation evolves

## On-Call Compensation

**Compensation Structure**
- Weekly on-call stipend: $500
- Overtime for incidents >2 hours: $50/hour
- Weekend on-call: Additional $200
- Holiday on-call: Additional $300

**Time Off**
- 1 day off after on-call week
- Additional day off for major incidents
- Flexible scheduling for personal events

**Training**
- Quarterly on-call training
- Runbook review sessions
- Incident response drills
- Shadowing for new team members

## Tools and Access

### Required Tools

**Monitoring**
- PagerDuty: Alert management
- Grafana: Dashboard monitoring
- Prometheus: Metrics queries
- Loki: Log analysis

**Communication**
- Slack: Team communication
- Zoom/Google Meet: Incident bridge
- Phone: Emergency contact

**Infrastructure**
- kubectl: Kubernetes management
- AWS Console: Cloud infrastructure
- GitHub: Code and CI/CD

### Access Requirements

**Primary On-Call**
- PagerDuty admin access
- Grafana admin access
- Kubernetes cluster admin
- AWS production access
- GitHub production access

**Secondary On-Call**
- PagerDuty responder access
- Grafana read access
- Kubernetes cluster admin
- AWS production access
- GitHub production access

## Performance Metrics

### On-Call KPIs

**Response Time**
- P1 alerts: <5 minutes (95th percentile)
- P2 alerts: <15 minutes (95th percentile)
- P3 alerts: <1 hour (95th percentile)

**Resolution Time**
- P1 incidents: <2 hours (median)
- P2 incidents: <4 hours (median)
- P3 incidents: <24 hours (median)

**Escalation Rate**
- Escalations <20% of total alerts
- Self-resolution >80% of incidents

### Review Process

**Weekly Review**
- Review all incidents from past week
- Identify patterns or recurring issues
- Update runbooks based on lessons learned

**Monthly Review**
- Review on-call performance metrics
- Identify training needs
- Discuss schedule adjustments

**Quarterly Review**
- Comprehensive on-call process review
- Update escalation paths if needed
- Review compensation structure
- Plan process improvements

## Training and Onboarding

### New On-Call Engineer

**Week 1**
- Shadow primary on-call
- Review all runbooks
- Set up all required tools
- Practice incident response drills

**Week 2**
- Secondary on-call (with backup)
- Handle P3 and P4 incidents
- Practice escalation procedures
- Document lessons learned

**Week 3**
- Primary on-call (with secondary backup)
- Handle all incident priorities
- Lead incident bridge calls
- Post-incident reviews

**Week 4**
- Independent primary on-call
- Full responsibility
- Regular feedback sessions
- Performance evaluation

### Ongoing Training

**Monthly**
- Runbook review session
- Incident response drill
- New feature training

**Quarterly**
- Major incident simulation
- Security incident drill
- Process improvement workshop

## Incident Response Process

### Initial Response

1. **Acknowledge Alert** (within SLA)
   - Acknowledge in PagerDuty
   - Join incident bridge
   - Post to #incidents channel

2. **Assess Impact**
   - Determine severity
   - Identify affected users
   - Estimate resolution time

3. **Investigate**
   - Check logs in Loki
   - Review metrics in Grafana
   - Check recent deployments

4. **Implement Fix**
   - Use runbooks for common issues
   - Escalate if needed
   - Coordinate with other teams

5. **Verify Recovery**
   - Confirm service is healthy
   - Run smoke tests
   - Monitor for recurrence

### Post-Incident

1. **Document Incident**
   - Timeline of events
   - Root cause analysis
   - Resolution steps

2. **Post-Incident Review**
   - Schedule within 48 hours
   - Invite all participants
   - Document action items

3. **Update Runbooks**
   - Add new procedures
   - Update existing procedures
   - Share lessons learned

## Emergency Contacts

**Engineering Team**
- Primary On-Call: PagerDuty
- Secondary On-Call: PagerDuty
- Engineering Lead: [Phone/Slack]
- CTO: [Phone/Slack]

**Support Teams**
- Security Team: [Slack]
- DevOps Team: [Slack]
- Customer Success: [Slack]

**External**
- PagerDuty Support: +1-800-123-4567
- AWS Support: +1-800-123-4567
- Cloudflare Support: +1-800-123-4567

## Schedule Management

### Scheduling

**Schedule Creation**
- Created 2 weeks in advance
- Posted to Google Calendar
- Posted to #on-call Slack channel
- Sent via email to team

**Schedule Changes**
- Request via #on-call channel
- Requires 48-hour notice
- Manager approval for changes
- Update all communication channels

**Conflicts**
- Trade shifts with another engineer
- Manager approval required
- Document trade in calendar
- Notify team of change

### Time Off

**Requesting Time Off**
- Submit request 2 weeks in advance
- Manager approval required
- Find replacement if needed
- Update schedule

**Emergency Time Off**
- Contact on-call manager immediately
- Secondary on-call takes over
- Schedule makeup shift
- Document emergency

## Appendix

### On-Call Checklist

**Before Shift**
- [ ] Confirm PagerDuty assignment
- [ ] Test phone connectivity
- [ ] Review recent incidents
- [ ] Check for scheduled maintenance
- [ ] Review runbook updates

**During Shift**
- [ ] Monitor PagerDuty
- [ ] Check Grafana dashboards
- [ ] Review #alerts channel
- [ ] Document all incidents
- [ ] Communicate status updates

**After Shift**
- [ ] Document open incidents
- [ ] Complete handoff
- [ ] Update calendar
- [ ] Post handoff summary
- [ ] Submit time off requests

### Runbook Index

- [Service Degradation](OPERATIONAL_RUNBOOKS.md#service-degradation)
- [Database Issues](OPERATIONAL_RUNBOOKS.md#database-issues)
- [High Latency](OPERATIONAL_RUNBOOKS.md#high-latency)
- [Security Incidents](OPERATIONAL_RUNBOOKS.md#security-incidents)
- [Rollback Procedures](OPERATIONAL_RUNBOOKS.md#rollback-procedures)

### Contact Information

**On-Call Manager**: [Name, Email, Phone]
**Engineering Lead**: [Name, Email, Phone]
**CTO**: [Name, Email, Phone]
**HR**: [Name, Email, Phone]

---

Last updated: 2024-03-01
Version: 1.0
