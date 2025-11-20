"""
Home Data Generator - Assigns homes, families, and pets to all employees
This script creates persistent home data for the home view system.
"""
import asyncio
import random
from sqlalchemy import select
from database.database import async_session_maker
from database.models import Employee, HomeSettings, FamilyMember, HomePet

# Available home layouts
CITY_HOME_EXTERIORS = [f"city_home{i:02d}.png" for i in range(1, 11)]
COUNTRY_HOME_EXTERIORS = [f"home{i:02d}.png" for i in range(1, 11)]
CITY_HOME_INTERIORS = [f"city_home_interior_{i}.png" for i in range(1, 6)]
COUNTRY_HOME_INTERIORS = [f"country_home_interior_{i}.png" for i in range(1, 6)]

# Available avatars for family members
WIFE_AVATARS = [f"wife{i}.png" for i in range(1, 8)]
HUSBAND_AVATARS = [f"husband{i}.png" for i in range(1, 8)]
CHILD_AVATARS = [f"child{i}.png" for i in range(1, 8)]

# Available pet avatars
CAT_AVATARS = ["cat_black.png", "cat_calico.png", "cat_gray.png", "cat_orange.png"]
DOG_AVATARS = ["dog_black.png", "dog_brown.png", "dog_spotted.png", "dog_white.png"]

# Pet names
CAT_NAMES = ["Whiskers", "Luna", "Shadow", "Mittens", "Oliver", "Simba", "Bella", "Chloe", "Charlie", "Max"]
DOG_NAMES = ["Buddy", "Max", "Charlie", "Bella", "Lucy", "Cooper", "Daisy", "Rocky", "Bailey", "Sadie"]

# Common first names for family members
MALE_NAMES = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles"]
FEMALE_NAMES = ["Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen"]
CHILD_NAMES = ["Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia", "Mason", "Isabella", "Jacob", "Mia", "William"]

# Occupations for spouses
SPOUSE_OCCUPATIONS = [
    "Teacher", "Nurse", "Engineer", "Accountant", "Designer", "Lawyer", "Doctor",
    "Chef", "Artist", "Writer", "Sales Manager", "Real Estate Agent", "Consultant",
    "Stay-at-home parent", "Entrepreneur", "Architect", "Pharmacist", "Social Worker"
]

# Personality traits
PERSONALITY_TRAITS = [
    "friendly", "outgoing", "introverted", "creative", "analytical", "organized",
    "spontaneous", "patient", "energetic", "calm", "humorous", "serious", "adventurous"
]

# Interests/Hobbies
INTERESTS = [
    "reading", "cooking", "gardening", "sports", "music", "art", "hiking", "gaming",
    "photography", "traveling", "yoga", "cycling", "movies", "dancing", "fishing"
]

# Street names for addresses
STREET_NAMES = [
    "Maple Street", "Oak Avenue", "Pine Road", "Elm Drive", "Cedar Lane", "Birch Way",
    "Willow Court", "Spruce Boulevard", "Ash Circle", "Cherry Street", "Main Street",
    "Park Avenue", "Lake Road", "River Drive", "Hill Lane", "Valley Way", "Forest Path"
]

CITY_NEIGHBORHOODS = ["Downtown", "Midtown", "Uptown", "West Side", "East End"]
COUNTRY_AREAS = ["Countryside", "Rural Route", "Country Lane"]


def generate_address(home_type: str) -> str:
    """Generate a realistic home address."""
    street_number = random.randint(100, 9999)
    street_name = random.choice(STREET_NAMES)

    if home_type == "city":
        neighborhood = random.choice(CITY_NEIGHBORHOODS)
        city = random.choice(["New York", "Brooklyn", "Queens"])
        return f"{street_number} {street_name}, {neighborhood}, {city}, NY"
    else:
        area = random.choice(COUNTRY_AREAS)
        town = random.choice(["Millbrook", "Bedford", "Rhinebeck", "Pine Plains", "Red Hook"])
        return f"{street_number} {street_name}, {area}, {town}, NY"


def create_spouse_data(employee_name: str, employee_gender_hint: str = None):
    """Create spouse data based on employee info."""
    # Determine spouse gender (opposite of employee if we can infer it)
    spouse_gender = random.choice(["male", "female"])

    if spouse_gender == "male":
        name = random.choice(MALE_NAMES)
        avatar = random.choice(HUSBAND_AVATARS)
    else:
        name = random.choice(FEMALE_NAMES)
        avatar = random.choice(WIFE_AVATARS)

    age = random.randint(28, 55)
    occupation = random.choice(SPOUSE_OCCUPATIONS)
    personality = random.sample(PERSONALITY_TRAITS, k=random.randint(2, 4))
    interests = random.sample(INTERESTS, k=random.randint(2, 5))

    return {
        "name": name,
        "relationship_type": "spouse",
        "age": age,
        "gender": spouse_gender,
        "avatar_path": f"/avatars/{avatar}",
        "occupation": occupation,
        "personality_traits": personality,
        "interests": interests
    }


def create_child_data(parent_age: int):
    """Create child data."""
    name = random.choice(CHILD_NAMES)
    avatar = random.choice(CHILD_AVATARS)
    age = random.randint(3, 18)
    gender = random.choice(["male", "female"])
    personality = random.sample(PERSONALITY_TRAITS, k=random.randint(2, 3))
    interests = random.sample(INTERESTS, k=random.randint(2, 4))

    # Children are in school or have hobbies
    if age < 5:
        occupation = "Preschooler"
    elif age < 12:
        occupation = "Elementary School Student"
    elif age < 14:
        occupation = "Middle School Student"
    elif age < 18:
        occupation = "High School Student"
    else:
        occupation = "College Student"

    return {
        "name": name,
        "relationship_type": "child",
        "age": age,
        "gender": gender,
        "avatar_path": f"/avatars/{avatar}",
        "occupation": occupation,
        "personality_traits": personality,
        "interests": interests
    }


async def generate_home_data():
    """Generate home data for all employees without home settings."""
    print("=" * 80)
    print("HOME DATA GENERATOR")
    print("Assigning homes, families, and pets to employees")
    print("=" * 80)

    async with async_session_maker() as db:
        # Get all active employees
        result = await db.execute(
            select(Employee).where(Employee.status == "active")
        )
        employees = result.scalars().all()

        print(f"\n[INFO] Found {len(employees)} active employees")

        # Get employees that already have home settings
        result = await db.execute(select(HomeSettings))
        existing_home_settings = result.scalars().all()
        existing_employee_ids = {hs.employee_id for hs in existing_home_settings}

        print(f"[INFO] {len(existing_employee_ids)} employees already have home data")

        employees_to_process = [e for e in employees if e.id not in existing_employee_ids]

        if not employees_to_process:
            print("\n[SUCCESS] All employees already have home data!")
            return

        print(f"[INFO] Generating home data for {len(employees_to_process)} employees...\n")

        for employee in employees_to_process:
            print(f"[PROCESSING] {employee.name} ({employee.title})")

            # Decide home type (60% city, 40% country)
            home_type = "city" if random.random() < 0.6 else "country"

            # Select home layouts
            if home_type == "city":
                exterior = random.choice(CITY_HOME_EXTERIORS)
                interior = random.choice(CITY_HOME_INTERIORS)
            else:
                exterior = random.choice(COUNTRY_HOME_EXTERIORS)
                interior = random.choice(COUNTRY_HOME_INTERIORS)

            # Decide living situation based on employee characteristics
            # Higher level employees more likely to have families
            if employee.hierarchy_level == 1:  # CEO
                living_situations = ["with_family"] * 8 + ["alone"] * 2
            elif employee.hierarchy_level == 2:  # Manager
                living_situations = ["with_family"] * 6 + ["alone"] * 3 + ["with_roommate"] * 1
            else:  # Employee
                living_situations = ["with_family"] * 4 + ["alone"] * 4 + ["with_roommate"] * 2

            living_situation = random.choice(living_situations)

            # Generate address
            address = generate_address(home_type)

            # Create home settings
            home_settings = HomeSettings(
                employee_id=employee.id,
                home_type=home_type,
                home_layout_exterior=exterior,
                home_layout_interior=interior,
                living_situation=living_situation,
                home_address=address
            )
            db.add(home_settings)

            print(f"  - Home: {home_type} ({exterior})")
            print(f"  - Living: {living_situation}")
            print(f"  - Address: {address}")

            # Create family members if living with family
            if living_situation == "with_family":
                # Create spouse
                spouse_data = create_spouse_data(employee.name)
                spouse = FamilyMember(
                    employee_id=employee.id,
                    **spouse_data
                )
                db.add(spouse)
                print(f"  - Spouse: {spouse_data['name']} ({spouse_data['occupation']})")

                # Create children (0-3 children)
                num_children = random.choices([0, 1, 2, 3], weights=[2, 4, 3, 1])[0]
                for i in range(num_children):
                    child_data = create_child_data(employee.id)
                    child = FamilyMember(
                        employee_id=employee.id,
                        **child_data
                    )
                    db.add(child)
                    print(f"  - Child: {child_data['name']} (age {child_data['age']}, {child_data['occupation']})")

            # Assign pets (50% chance of having a pet, some might have multiple)
            if random.random() < 0.5:
                # Decide number of pets (1-2 pets)
                num_pets = random.choices([1, 2], weights=[7, 3])[0]

                for i in range(num_pets):
                    # Decide pet type (60% dog, 40% cat)
                    pet_type = "dog" if random.random() < 0.6 else "cat"

                    if pet_type == "dog":
                        pet_name = random.choice(DOG_NAMES)
                        avatar = random.choice(DOG_AVATARS)
                        breeds = ["Labrador", "Golden Retriever", "German Shepherd", "Bulldog", "Poodle", "Beagle"]
                    else:
                        pet_name = random.choice(CAT_NAMES)
                        avatar = random.choice(CAT_AVATARS)
                        breeds = ["Siamese", "Persian", "Maine Coon", "Tabby", "Ragdoll", "British Shorthair"]

                    breed = random.choice(breeds)
                    age = random.randint(1, 12)
                    personalities = ["playful", "lazy", "energetic", "calm", "friendly", "shy", "curious"]
                    personality = random.choice(personalities)

                    pet = HomePet(
                        employee_id=employee.id,
                        name=pet_name,
                        pet_type=pet_type,
                        avatar_path=f"/avatars/{avatar}",
                        breed=breed,
                        age=age,
                        personality=personality
                    )
                    db.add(pet)
                    print(f"  - Pet: {pet_name} ({breed} {pet_type}, {age} years old, {personality})")

            print()

        # Commit all changes
        await db.commit()

        print("=" * 80)
        print(f"[SUCCESS] Generated home data for {len(employees_to_process)} employees!")
        print("=" * 80)
        print("\nHome data summary:")
        print(f"  - Total employees: {len(employees)}")
        print(f"  - New home assignments: {len(employees_to_process)}")
        print(f"  - All employees now have home data!")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(generate_home_data())
