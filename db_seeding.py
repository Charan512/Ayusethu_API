# repopulate_database.py
import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import random

MONGO_URI = "mongodb+srv://charan_db:cHaran554@ayusethu.ioefhpr.mongodb.net/ayusethu_db?retryWrites=true&w=majority"

async def repopulate_database():
    """Completely repopulate the database with rich test data."""
    print("🚀 Connecting to MongoDB Atlas...")
    
    client = AsyncIOMotorClient(MONGO_URI)
    db = client.ayusethu_db
    
    try:
        await client.admin.command('ping')
        print("✅ Successfully connected to MongoDB Atlas!")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return
    
    # ================= FIRST: CLEAR EXISTING DATA =================
    print("\n🧹 Clearing existing data...")
    await db.users.delete_many({})
    print("✅ Cleared all users")
    
    # ================= CREATE COLLECTORS (10) =================
    collectors = []
    collector_regions = ['North', 'South', 'East', 'West', 'Central', 'North-East', 'South-West']
    
    for i in range(1, 11):
        region = random.choice(collector_regions)
        accuracy = random.uniform(95, 99.9)
        rating = random.uniform(4.0, 5.0)
        
        collector = {
            "fullName": f"Collector {i} - {region}",
            "email": f"collector{i}@herbchain.com",
            "role": "Collector",
            "phone": f"+91 98765{random.randint(10000, 99999)}",
            "organization": f"{region} India Herbs",
            "region": region,
            "assignedBatches": random.randint(5, 20),
            "completed": random.randint(3, 18),
            "avgTime": f"{random.randint(1, 3)}.{random.randint(0, 9)} days",
            "accuracy": f"{accuracy:.1f}%",
            "rating": round(rating, 1),
            "status": "active",
            "specialization": random.choice(["Medicinal Herbs", "Aromatic Plants", "Leafy Greens", "Root Herbs"]),
            "experience_years": random.randint(1, 10),
            "createdAt": datetime.now(timezone.utc)
        }
        collectors.append(collector)
    
    # ================= CREATE TESTERS (8) =================
    testers = []
    tester_names = [
        "Dr. Sharma Analytical Labs",
        "BioChem Quality Testing",
        "GreenLeaf Pharmaceutical Testing", 
        "Ayush Standards Laboratory",
        "PhytoTest Research Center",
        "Herbal Certify Laboratories",
        "Organic Validation Center",
        "PureTest Analytics"
    ]
    
    accreditations = ["ISO 9001", "NABL", "FDA Approved", "WHO-GMP", "USP", "Ayush Certified", "Organic Certified"]
    
    for i, lab_name in enumerate(tester_names, 1):
        turnaround = random.choice(["24 hrs", "36 hrs", "48 hrs", "72 hrs"])
        accuracy = random.uniform(98.5, 99.9)
        acceptance_rate = random.uniform(85, 98)
        rating = random.uniform(4.2, 5.0)
        
        tester = {
            "fullName": lab_name,
            "email": f"lab{i}@test.com",
            "role": "Tester",
            "labName": lab_name,
            "licenseNumber": f"LIC-2023-T{random.randint(100, 999)}",
            "accreditation": random.choice(accreditations),
            "turnaround": turnaround,
            "accuracy": f"{accuracy:.1f}%",
            "acceptanceRate": f"{acceptance_rate:.0f}%",
            "rating": round(rating, 1),
            "status": "active",
            "tests_conducted": random.randint(50, 500),
            "specialization": random.choice(["Phytochemical", "Microbiological", "Heavy Metals", "Pesticide Residue"]),
            "createdAt": datetime.now(timezone.utc)
        }
        testers.append(tester)
    
    # ================= CREATE MANUFACTURERS (8) =================
    manufacturers = []
    company_names = [
        "AyurPharma Ltd",
        "Herbal Remedies Inc.",
        "Nature's Cure Pharmaceuticals",
        "Organic Herb Products",
        "Ayurvedic Solutions Co.",
        "PureHerb Manufacturing",
        "GreenMed Formulations",
        "Vedic Herbal Labs"
    ]
    
    for i, company in enumerate(company_names, 1):
        manufacturer = {
            "fullName": company,
            "email": f"manufacturer{i}@company.com",
            "role": "Manufacturer",
            "companyName": company,
            "licenseNumber": f"MFG-LIC-2023-{random.randint(1000, 9999)}",
            "status": "active",
            "manufacturing_capacity": f"{random.randint(100, 1000)} kg/month",
            "specialization": random.choice(["Tablets", "Capsules", "Powders", "Oils", "Extracts"]),
            "years_experience": random.randint(3, 25),
            "certifications": random.choice(["GMP", "ISO", "Organic", "Ayush", "FDA"]),
            "createdAt": datetime.now(timezone.utc)
        }
        manufacturers.append(manufacturer)
    
    # ================= INSERT ALL DATA =================
    all_users = collectors + testers + manufacturers
    
    print(f"\n📦 Inserting {len(all_users)} users...")
    result = await db.users.insert_many(all_users)
    print(f"✅ Inserted {len(result.inserted_ids)} users")
    
    # ================= VERIFICATION =================
    print("\n📊 VERIFICATION REPORT:")
    print("=" * 40)
    
    # Count by role
    for role, role_name in [("Collector", "Collectors"), ("Tester", "Testers"), ("Manufacturer", "Manufacturers")]:
        count = await db.users.count_documents({"role": role})
        print(f"   {role_name}: {count}")
    
    # Show sample from each role
    print("\n👥 SAMPLE USERS:")
    for role in ["Collector", "Tester", "Manufacturer"]:
        user = await db.users.find_one({"role": role})
        if user:
            print(f"   {role}: {user.get('fullName')} - {user.get('email')}")
    
    # Total stats
    total = await db.users.count_documents({})
    print(f"\n📈 TOTAL USERS: {total}")
    
    client.close()
    print("\n✨ Database repopulation complete! Your AyuSethu system now has rich test data.")

if __name__ == "__main__":
    asyncio.run(repopulate_database())