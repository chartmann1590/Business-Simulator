# Office Simulator Enhancement Plan
## Vision: Autonomous Business & Life Simulator

The goal is to create a system that runs itself - you just sit back and watch the drama unfold.

## Phase 1: Database Schema (Priority 1)
### New Tables

**home_conversations**
- id, employee_id, conversation_type, participants, topic, content, sentiment, timestamp
- Stores formatted family conversations (dinner talks, spouse chats, kid interactions)

**home_activities**
- id, employee_id, activity_type, description, duration, cost, satisfaction_impact, timestamp
- Tracks hobbies, repairs, social events, weekend activities

**home_finances**
- id, employee_id, transaction_type, amount, category, description, balance_after, timestamp
- Personal budgets, savings, major purchases, unexpected expenses

**office_incidents**
- id, incident_type, severity, location, description, affected_employees, resolution_status, cost, resolved_at, timestamp
- Equipment failures, repairs, maintenance issues

**employee_relationships**
- id, employee_id_1, employee_id_2, relationship_type, strength, history, last_interaction
- Tracks friendships, rivalries, mentorships, romances

**office_drama_events**
- id, event_type, primary_employee_id, secondary_employee_ids, description, severity, gossip_spread, resolution, timestamp
- Arguments, gossip, conflicts, political events

## Phase 2: Random Event System (Priority 1)

### Equipment Failure Events (10-15% chance daily)
1. Printer Jam/Break - affects productivity, costs $ to fix
2. AC/Heating Failure - affects morale, emergency repair needed
3. Internet Outage - stops work, IT scrambles to fix
4. Coffee Machine Break - CRISIS! morale tanks instantly
5. Elevator Breakdown - people stuck/late to meetings
6. Power Outage - emergency, everyone sent home
7. Plumbing Issues - bathrooms closed, chaos ensues

### Surprise Visitor Events (5-10% chance daily)
1. Health Inspection - stress spike, cleanup frenzy
2. Fire Drill - interrupts work, annoyance
3. VIP Client Tour - executives panic, cleanup rush
4. Food Truck Arrival - morale boost, long lunch breaks
5. Package Delivery Chaos - wrong deliveries, confusion
6. Building Maintenance - noise, disruption
7. Lost Delivery Driver - interrupts reception

### Office Drama Events (20% chance daily)
1. Employee Arguments - two people fight, affects team morale
2. Gossip Chain Starting - rumor spreads through office
3. Clique Formation - groups form, exclusion happens
4. Rivalry Development - competition turns personal
5. Office Romance Revealed - gossip explosion
6. Political Power Struggle - departments compete for resources
7. Manager Favoritism Noticed - resentment builds

### Employee Personal Events (15% chance weekly)
1. Work Anniversary - celebration, morale boost
2. Unexpected Promotion - happiness, possible jealousy
3. Family Emergency - sudden absence, coverage needed
4. Major Life Event - engagement, baby, house purchase
5. Personal Achievement - outside work success shared

## Phase 3: Homelife System (Priority 2)

### Conversation System
**Format:** Properly structured dialogue logs
```json
{
  "type": "dinner_conversation",
  "participants": ["John Doe", "Jane Doe (spouse)", "Timmy (age 8)"],
  "topic": "Work stress",
  "exchange": [
    {"speaker": "Jane", "line": "How was work today?"},
    {"speaker": "John", "line": "Terrible. The printer broke again and Sarah argued with Tom all afternoon."},
    {"speaker": "Timmy", "line": "Can we get a dog?"},
    {"speaker": "Jane", "line": "Not now, Timmy. John, maybe you should talk to HR?"}
  ],
  "outcome": "John feels slightly better after venting",
  "impact": {"stress": -5, "marriage_happiness": +2}
}
```

**Conversation Types:**
- Dinner table (daily)
- Morning rush (daily)
- Weekend planning (weekly)
- Financial discussions (monthly)
- Conflict resolution (as needed)
- Quality time (random)

### Home Activity Tracking
**Daily Activities:**
- Wake up routine
- Breakfast with family
- Commute reflections
- Evening relaxation
- Bedtime routine

**Weekend Activities:**
- Hobbies (gardening, gaming, sports)
- Home repairs/improvements
- Social gatherings
- Kids' activities
- Date nights

**Special Events:**
- Birthday parties
- Holiday celebrations
- Neighborhood events
- Friend visits

### Financial Simulation
**Monthly Tracking:**
- Salary deposit
- Bills paid (utilities, mortgage, insurance)
- Groceries and daily expenses
- Entertainment spending
- Savings progress

**Major Decisions:**
- Car repairs vs new car
- Home improvement projects
- Vacation planning
- Kids' college savings
- Emergency fund status

## Phase 4: Database Optimizations (Priority 2)

### New Indexes
```sql
-- Activity lookups
CREATE INDEX idx_activities_employee_timestamp ON activities(employee_id, timestamp DESC);
CREATE INDEX idx_activities_type ON activities(activity_type) WHERE activity_type IN ('work', 'meeting', 'break');

-- Home conversations
CREATE INDEX idx_home_conversations_employee_date ON home_conversations(employee_id, timestamp::date);
CREATE INDEX idx_home_conversations_type ON home_conversations(conversation_type);

-- Relationships
CREATE INDEX idx_relationships_employee ON employee_relationships(employee_id_1, employee_id_2);
CREATE INDEX idx_relationships_type ON employee_relationships(relationship_type);

-- Incidents
CREATE INDEX idx_incidents_unresolved ON office_incidents(resolution_status) WHERE resolution_status = 'unresolved';
CREATE INDEX idx_incidents_date ON office_incidents(timestamp::date);
```

### Query Optimizations
- Batch insert operations
- Reduce N+1 queries
- Use CTEs for complex queries
- Implement query result caching

## Phase 5: Integration & Polish (Priority 3)

### Office Simulator Integration
- Random events trigger every 30-60 minutes
- Incidents affect productivity/morale
- Drama affects relationships
- Equipment failures require AI decisions

### Home Life Integration
- Conversations happen every evening
- Weekend activities affect Monday mood
- Financial stress impacts work performance
- Family events can cause absences

### Activity Log Enhancements
- Group related activities
- Show conversation threads
- Highlight dramatic events
- Track ongoing situations

## Success Metrics

When complete, the simulator should:
1. Run completely autonomously
2. Generate interesting stories naturally
3. Have consequences that cascade through systems
4. Show realistic cause-and-effect
5. Be entertaining to watch without interaction
6. Generate 50-100 interesting events per simulated day

## Implementation Order

1. Database models (home_conversations, etc.)
2. Home conversation system
3. Enhanced random events
4. Office incident system
5. Relationship tracking
6. Financial simulation
7. Database optimizations
8. Integration & testing
