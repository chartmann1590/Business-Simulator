# Pet Care System

## Overview

The pet care system provides interactive pet care gameplay for both office pets and home pets. Employees can interact with pets, care for them, and track their happiness, hunger, and energy levels. The system includes AI-powered automatic pet care and manual pet care through the frontend interface.

## Features

- **Office Pets**: Pets that live in the office and can be cared for by employees
- **Home Pets**: Pets that live in employee homes (see [HOME_SYSTEM.md](HOME_SYSTEM.md))
- **Interactive Care**: Feed, play with, or pet animals
- **Pet Stats**: Happiness, hunger, and energy tracking
- **AI-Powered Care**: Automatic pet care by AI employees
- **Care Logs**: Complete history of all pet care interactions
- **Pet Personalities**: Unique personalities affecting care needs
- **Pet Roaming**: Pets move around the office
- **Favorite Employees**: Pets develop preferences for certain employees

## How It Works

### Office Pets

**Pet Types**: Cats and Dogs
- Each pet has a name, breed, age, and personality
- Pets roam around the office
- Pets have favorite employees who care for them more
- Pets need regular care (feeding, playing, petting)

### Pet Stats

Each pet has three stats tracked from 0-100:

1. **Happiness** (0-100)
   - Increases when pet is played with or petted
   - Decreases over time if neglected
   - Affects pet's overall well-being

2. **Hunger** (0-100)
   - Increases when pet is fed
   - Decreases over time
   - Low hunger affects happiness

3. **Energy** (0-100)
   - Increases when pet plays
   - Decreases with activity
   - Affects pet's ability to interact

### Care Actions

**Feed**:
- Increases hunger by 20-30 points
- Slightly increases happiness (+5-10)
- No effect on energy

**Play**:
- Increases happiness by 15-25 points
- Increases energy by 10-20 points
- Slightly decreases hunger (-5-10)

**Pet**:
- Increases happiness by 10-20 points
- Slightly increases energy (+5-10)
- No effect on hunger

### AI-Powered Automatic Care

The system automatically provides care for pets:
- **Frequency**: Every ~1.3 minutes (10 simulation ticks)
- **During Work Hours**: Only during work hours
- **AI Selection**: Uses LLM to select:
  - Which pet needs care most
  - Which employee should provide care
  - What care action to take
- **Business Context**: Considers current business situation when selecting care

**Care Priority**:
1. Pets with low stats (< 50) get priority
2. Up to 5 pets cared for per cycle
3. Employees selected based on availability and relationship with pet

### Manual Pet Care

Employees can manually care for pets through the frontend:
- Interactive pet care game interface
- Real-time stat updates
- Care action selection (feed, play, pet)
- Immediate feedback on care results

### Pet Interactions

Pets can interact with employees:
- **Frequency**: Every ~40 seconds (5 simulation ticks)
- **During Work Hours**: Only during work hours
- **Types**: Greetings, requests for attention, playful behavior
- **AI-Generated**: Uses LLM to create realistic interactions

### Pet Roaming

Pets move around the office:
- **Frequency**: Every simulation tick
- **Rooms**: Pets can be in various rooms (breakrooms, lounges, offices)
- **Movement**: Random but realistic movement patterns
- **Tracking**: Current room tracked in database

## Database Structure

### OfficePet Table

```sql
CREATE TABLE office_pets (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255),
    pet_type VARCHAR(50),  -- 'cat' or 'dog'
    breed VARCHAR(255),
    age INTEGER,
    avatar_path VARCHAR(255),
    personality TEXT,
    current_room VARCHAR(255),
    favorite_employee_id INTEGER REFERENCES employees(id),
    happiness FLOAT DEFAULT 75.0,
    hunger FLOAT DEFAULT 50.0,
    energy FLOAT DEFAULT 70.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### PetCareLog Table

```sql
CREATE TABLE pet_care_logs (
    id INTEGER PRIMARY KEY,
    pet_id INTEGER REFERENCES office_pets(id),
    employee_id INTEGER REFERENCES employees(id),
    care_action VARCHAR(50),  -- 'feed', 'play', or 'pet'
    pet_happiness_before FLOAT,
    pet_hunger_before FLOAT,
    pet_energy_before FLOAT,
    pet_happiness_after FLOAT,
    pet_hunger_after FLOAT,
    pet_energy_after FLOAT,
    reasoning TEXT,  -- AI reasoning for care action
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## API Endpoints

### Get All Office Pets

```
GET /api/pets
```

**Response**:
```json
[
  {
    "id": 1,
    "name": "Whiskers",
    "pet_type": "cat",
    "breed": "Persian",
    "age": 3,
    "avatar_path": "/avatars/cat_orange.png",
    "personality": "Playful, Affectionate",
    "current_room": "Floor 1 Breakroom",
    "favorite_employee_id": 45,
    "happiness": 82.5,
    "hunger": 65.0,
    "energy": 70.0,
    "created_at": "2024-01-15T10:00:00-05:00"
  }
]
```

### Get Pet Care Log

```
GET /api/pets/{pet_id}/care-log?limit=20
```

**Response**:
```json
[
  {
    "id": 1,
    "pet_id": 1,
    "pet_name": "Whiskers",
    "employee_id": 45,
    "employee_name": "Jane Manager",
    "care_action": "play",
    "pet_happiness_before": 75.0,
    "pet_hunger_before": 60.0,
    "pet_energy_before": 65.0,
    "pet_happiness_after": 90.0,
    "pet_hunger_after": 55.0,
    "pet_energy_after": 80.0,
    "reasoning": "Whiskers seemed energetic and wanted to play. Playing increases both happiness and energy.",
    "timestamp": "2024-01-15T14:30:00-05:00"
  }
]
```

### Log Pet Care (Manual)

```
POST /api/pets/{pet_id}/care
```

**Request**:
```json
{
  "employee_id": 45,
  "action": "feed",
  "happiness_before": 75.0,
  "hunger_before": 50.0,
  "energy_before": 70.0
}
```

**Response**:
```json
{
  "success": true,
  "care_log": {
    "id": 123,
    "pet_id": 1,
    "employee_id": 45,
    "care_action": "feed",
    "pet_happiness_after": 80.0,
    "pet_hunger_after": 75.0,
    "pet_energy_after": 70.0,
    "timestamp": "2024-01-15T15:00:00-05:00"
  }
}
```

### Get Pet Stats

```
GET /api/pets/{pet_id}/stats
```

**Response**:
```json
{
  "pet_id": 1,
  "pet_name": "Whiskers",
  "happiness": 82.5,
  "hunger": 65.0,
  "energy": 70.0,
  "overall_health": "good",
  "needs_care": false,
  "last_care": "2024-01-15T14:30:00-05:00"
}
```

## Frontend Integration

### Pet Care Game Page

**File**: `frontend/src/pages/PetCareGame.jsx`

**Features**:
- Interactive pet care interface
- Real-time stat display
- Care action buttons (Feed, Play, Pet)
- Pet selection
- Care history display
- Pet happiness/hunger/energy meters

### Pet Care Log Page

**File**: `frontend/src/pages/PetCareLog.jsx`

**Features**:
- Complete care log history
- Filter by pet or employee
- Care action statistics
- Pet health trends

### Dashboard Integration

The dashboard includes:
- Pet care statistics
- Pets needing care alerts
- Recent care activities

## Implementation

### PetManager Class

**File**: `backend/business/pet_manager.py`

**Key Methods**:

```python
async def check_pet_interactions(self) -> List[dict]:
    """Check for pet interactions with employees."""
    
async def check_and_provide_pet_care(self, business_context: Dict) -> List[PetCareLog]:
    """Automatically provide care for pets needing attention."""
    
async def select_employee_for_pet_care(self, pet: OfficePet, available_employees: List[Employee], business_context: Dict) -> Tuple[Employee, str]:
    """Use AI to select best employee for pet care."""
    
async def select_care_action(self, pet: OfficePet, stats: Dict, employee: Employee, business_context: Dict) -> Tuple[str, str]:
    """Use AI to select best care action."""
    
async def execute_pet_care(self, pet: OfficePet, employee: Employee, action: str, stats_before: Dict, reasoning: str) -> PetCareLog:
    """Execute pet care action and log it."""
    
async def get_pet_stats(self, pet: OfficePet) -> Dict:
    """Get current pet statistics."""
```

### Integration with Office Simulator

The pet manager is called periodically:
- **Pet interactions**: Every 5 ticks (~40 seconds)
- **Pet care**: Every 10 ticks (~1.3 minutes)
- **Pet roaming**: Every tick (movement system)

## Configuration

### Pet Care Frequency

- **Automatic Care**: Every 10 simulation ticks (~1.3 minutes)
- **Pet Interactions**: Every 5 simulation ticks (~40 seconds)
- **During Work Hours**: Only during work hours (8am-6pm)

### Stat Decay Rates

Stats decrease over time:
- **Happiness**: -0.5 per minute if not cared for
- **Hunger**: -1.0 per minute
- **Energy**: -0.3 per minute

### Care Action Effects

**Feed**:
- Hunger: +20-30
- Happiness: +5-10
- Energy: 0

**Play**:
- Happiness: +15-25
- Energy: +10-20
- Hunger: -5-10

**Pet**:
- Happiness: +10-20
- Energy: +5-10
- Hunger: 0

## Troubleshooting

### Pets Not Getting Care

**Possible Causes**:
1. Outside work hours (care only during work hours)
2. No employees available
3. Pet manager not running
4. Database connection issues

**Solution**: Check work hours, employee availability, and pet manager logs

### Pet Stats Not Updating

**Possible Causes**:
1. Care actions not being logged
2. Stat calculations incorrect
3. Database transaction not committed

**Solution**: Check care logs, verify stat calculations, check database commits

### AI Care Not Working

**Possible Causes**:
1. LLM (Ollama) not available
2. AI selection failing
3. Business context missing

**Solution**: Check Ollama connection, verify AI selection logic, check business context

## Best Practices

1. **Regular Care**: Ensure pets get regular care during work hours
2. **Stat Balance**: Monitor all three stats (happiness, hunger, energy)
3. **AI Selection**: Use business context for realistic care decisions
4. **Care Logging**: Log all care actions for tracking
5. **Pet Preferences**: Track favorite employees for better care

## Future Enhancements

Potential improvements:
- Pet training and tricks
- Pet competitions
- Pet health system (illness, vet visits)
- Pet breeding
- Pet adoption system
- Pet accessories and toys
- Pet social interactions (pets playing together)
- Pet performance metrics
- Pet care leaderboard
- Pet care achievements

