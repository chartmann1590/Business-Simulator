# Home System

## Overview

The home system provides a complete home life simulation for employees, including family members, home pets, and realistic home activities. Each employee has a home with family members (spouses, children) and pets (cats and dogs) that have their own activities, sleep schedules, and interactions.

## Features

- **Home Settings**: Each employee has a home with type, layout, and address
- **Family Members**: Spouses and children with individual personalities, occupations, and activities
- **Home Pets**: Cats and dogs with unique personalities and care needs
- **Home Layouts**: Visual interior and exterior views of employee homes
- **Sleep Coordination**: Family members and pets sleep when employees sleep
- **Home Conversations**: AI-generated conversations between family members
- **Location Tracking**: Family members and pets can be inside or outside
- **Real-time Updates**: Home view shows current state of all occupants

## How It Works

### Home Creation

When employees are created, they automatically get:
- A home type (city home or country home)
- Home layout images (interior and exterior)
- Family members (spouse and 0-3 children)
- Home pets (1-2 pets, cats or dogs)
- Home address

### Family Members

**Spouse**:
- Name, age, gender, occupation
- Personality traits and interests
- Avatar image
- Sleep schedule (coordinates with employee)
- Current location (inside/outside)

**Children**:
- Name, age, gender
- Personality traits and interests
- Avatar image
- Sleep schedule (coordinates with employee)
- Current location (inside/outside)
- Can have 0-3 children per employee

### Home Pets

**Types**: Cats and Dogs
- Name, breed, age
- Personality traits
- Avatar image
- Sleep schedule (coordinates with employee)
- Current location (inside/outside)
- Care needs (happiness, hunger, energy)

### Sleep Coordination

When an employee goes to sleep:
1. All family members in the home also go to sleep
2. All home pets in the home also go to sleep
3. Sleep states are updated simultaneously
4. Activity logs are created for all entities

When an employee wakes up:
1. Employee wakes at their scheduled time (5:30am-6:45am)
2. Family members wake later (7:30am-9:00am)
3. Pets wake with family members

### Home Conversations

The system generates realistic conversations:
- **During Work Hours**: Conversations between family members (employee is at work)
- **After Work Hours**: Conversations between employee and family members
- **Context-Aware**: Conversations reflect time of day, activities, and relationships
- **AI-Generated**: Uses LLM to create natural, contextual conversations

### Location Management

Family members and pets can be:
- **Inside**: In the home interior
- **Outside**: In the home exterior (yard, patio, etc.)

Locations are updated based on:
- Time of day
- Weather conditions
- Sleep state (sleeping people are inside)
- Random movement

## Database Structure

### HomeSettings Table

```sql
CREATE TABLE home_settings (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(id),
    home_type VARCHAR(50),  -- 'city_home' or 'country_home'
    home_layout_exterior VARCHAR(255),  -- Path to exterior image
    home_layout_interior VARCHAR(255),  -- Path to interior image
    living_situation TEXT,
    home_address TEXT
);
```

### FamilyMember Table

```sql
CREATE TABLE family_members (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(id),
    name VARCHAR(255),
    relationship_type VARCHAR(50),  -- 'spouse' or 'child'
    age INTEGER,
    gender VARCHAR(50),
    avatar_path VARCHAR(255),
    occupation TEXT,
    personality_traits TEXT,
    interests TEXT,
    current_location VARCHAR(50),  -- 'inside' or 'outside'
    sleep_state VARCHAR(50)  -- 'awake' or 'sleeping'
);
```

### HomePet Table

```sql
CREATE TABLE home_pets (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(id),
    name VARCHAR(255),
    pet_type VARCHAR(50),  -- 'cat' or 'dog'
    breed VARCHAR(255),
    age INTEGER,
    avatar_path VARCHAR(255),
    personality TEXT,
    current_location VARCHAR(50),  -- 'inside' or 'outside'
    sleep_state VARCHAR(50)  -- 'awake' or 'sleeping'
);
```

## API Endpoints

### Get Employee Home

```
GET /api/home/employees/{employee_id}
```

**Response**:
```json
{
  "employee": {
    "id": 123,
    "name": "John Doe",
    "title": "Senior Developer",
    "department": "Engineering",
    "avatar_path": "/avatars/...",
    "activity_state": "at_home",
    "hobbies": "Reading, Hiking",
    "personality_traits": "Analytical, Creative"
  },
  "home_settings": {
    "home_type": "city_home",
    "home_layout_exterior": "/home_layout/city_home01.png",
    "home_layout_interior": "/home_layout/city_home_interior_1.png",
    "living_situation": "Lives with spouse and 2 children",
    "home_address": "123 Main St, New York, NY"
  },
  "family_members": [
    {
      "id": 1,
      "name": "Jane Doe",
      "relationship_type": "spouse",
      "age": 35,
      "gender": "Female",
      "avatar_path": "/avatars/wife1.png",
      "occupation": "Teacher",
      "personality_traits": "Caring, Patient",
      "interests": "Reading, Gardening",
      "current_location": "inside",
      "sleep_state": "awake"
    },
    {
      "id": 2,
      "name": "Emma Doe",
      "relationship_type": "child",
      "age": 8,
      "gender": "Female",
      "avatar_path": "/avatars/child1.png",
      "occupation": null,
      "personality_traits": "Curious, Energetic",
      "interests": "Drawing, Playing",
      "current_location": "inside",
      "sleep_state": "awake"
    }
  ],
  "home_pets": [
    {
      "id": 1,
      "name": "Fluffy",
      "pet_type": "cat",
      "breed": "Persian",
      "age": 3,
      "avatar_path": "/avatars/cat_orange.png",
      "personality": "Playful, Affectionate",
      "current_location": "inside",
      "sleep_state": "awake"
    }
  ]
}
```

### Get Home Layout

```
GET /api/home/layout/{employee_id}?view=interior
```

**Parameters**:
- `view`: "interior" or "exterior" (default: "interior")

**Response**:
```json
{
  "employee_id": 123,
  "view": "interior",
  "layout_image": "/home_layout/city_home_interior_1.png",
  "occupants": [
    {
      "id": 1,
      "name": "Jane Doe",
      "type": "family",
      "relationship_type": "spouse",
      "avatar_path": "/avatars/wife1.png",
      "sleep_state": "awake",
      "position": {
        "x": 45.2,
        "y": 60.8
      }
    },
    {
      "id": 2,
      "name": "Fluffy",
      "type": "pet",
      "pet_type": "cat",
      "avatar_path": "/avatars/cat_orange.png",
      "sleep_state": "awake",
      "position": {
        "x": 52.1,
        "y": 55.3
      }
    }
  ],
  "locations_present": ["bedroom", "living_room", "kitchen", "children_room"]
}
```

### Generate Home Conversations

```
POST /api/home/conversations
```

**Request**:
```json
{
  "employee_id": 123
}
```

**Response**:
```json
{
  "conversations": [
    {
      "participants": ["Jane Doe", "Emma Doe"],
      "conversation": "Jane: How was school today?\nEmma: It was fun! We learned about dinosaurs.",
      "timestamp": "2024-01-15T18:30:00-05:00"
    }
  ]
}
```

### Update Home Locations

```
POST /api/home/locations
```

**Request**:
```json
{
  "employee_id": 123,
  "location": "outside"
}
```

**Response**:
```json
{
  "success": true,
  "employee_id": 123,
  "location": "outside",
  "family_members_updated": 3,
  "pets_updated": 1
}
```

## Frontend Integration

### Home View Page

**File**: `frontend/src/pages/HomeView.jsx`

**Features**:
- Visual representation of employee homes
- Interior and exterior views
- Real-time occupant positions
- Sleep state visualization
- Conversation display
- Location switching (inside/outside)

### Employee Detail Integration

The employee detail page includes:
- Home information card
- Family members list
- Home pets list
- Link to full home view

## Implementation

### Home Manager

**File**: `backend/business/home_manager.py` (if exists) or integrated in seed/employee creation

**Key Functions**:
- Create home settings for employees
- Generate family members
- Generate home pets
- Update home locations
- Generate home conversations

### Integration with Sleep System

The home system integrates with the sleep system:
- Family members and pets sleep when employee sleeps
- Wake-up times are coordinated
- Sleep states are synchronized

### Integration with Clock System

The home system integrates with the clock system:
- Employees are at home when not at work
- Family members are visible when employee is at home
- Home activities occur during non-work hours

## Configuration

### Home Types

- **City Home**: Urban residence with modern layout
- **Country Home**: Suburban/rural residence with spacious layout

### Family Generation

- **Spouse**: Always generated (if employee is married)
- **Children**: 0-3 children per employee (random)
- **Ages**: Realistic age distribution
- **Personalities**: AI-generated based on employee personality

### Pet Generation

- **Count**: 1-2 pets per employee (random)
- **Types**: Cats and dogs
- **Breeds**: Various breeds with appropriate avatars
- **Personalities**: AI-generated unique personalities

## Troubleshooting

### Missing Home Settings

If an employee doesn't have home settings:
1. Check if employee was created before home system was added
2. Run seed script to generate homes for existing employees
3. Verify `home_settings` table exists

### Family Members Not Sleeping

**Possible Causes**:
1. Employee not sleeping (family sleeps when employee sleeps)
2. Sleep system not running
3. Database issue

**Solution**: Check employee sleep state and sleep system logs

### Home View Not Loading

**Possible Causes**:
1. Missing layout images
2. Employee has no home settings
3. API endpoint error

**Solution**: 
- Check image paths in `home_layout` directory
- Verify employee has home settings
- Check browser console for API errors

## Best Practices

1. **Coordinate Sleep**: Ensure family and pets sleep with employees
2. **Realistic Conversations**: Generate context-aware conversations
3. **Location Updates**: Update locations based on time and weather
4. **Visual Consistency**: Use consistent avatar and layout images
5. **Performance**: Cache home data for frequently accessed employees

## Future Enhancements

Potential improvements:
- Home customization (furniture, decorations)
- Home activities (cooking, cleaning, hobbies)
- Neighbor interactions
- Home events (parties, gatherings)
- Home maintenance and repairs
- Home expansion (moving to bigger home)
- Pet training and tricks
- Family member careers and activities
- Home security system
- Smart home features

