import requests
import time
from datetime import datetime
import database
from database import SessionLocal, Opportunity

# --- API CONFIGURATION ---
ADZUNA_APP_ID = "74c3c80e"   
ADZUNA_APP_KEY = "faef94592e059bbb018d54c11b747a65" 
# Harvesting from the top 3 global Biotech Hubs
COUNTRIES = ["in", "us", "gb"] 

def fetch_broad_sweep(db, search_term, forced_field=None, max_pages=2):
    """Scrapes jobs globally. Parses titles to find PhDs/Internships dynamically."""
    print(f"\n[ SYSTEM ]: Harvesting global data for '{search_term}'...")

    for country in COUNTRIES:
        for page in range(1, max_pages + 1):
            url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
            params = {
                "app_id": ADZUNA_APP_ID,
                "app_key": ADZUNA_APP_KEY,
                "results_per_page": 50, # Grabbing 50 results at a time
                "what": search_term,
                "content-type": "application/json"
            }

            try:
                response = requests.get(url, params=params)
                if response.status_code != 200:
                    break # Stop if API limits are hit
                
                data = response.json()
                results = data.get("results", [])
                if not results:
                    break # Move to next country if this page is empty
                    
                live_opportunities = []
                for job in results:
                    title = job.get("title", "Biotech Role")
                    desc = job.get("description", "")
                    title_lower = title.lower()
                    desc_lower = desc.lower()
                    
                    # 1. Smart Category Sorter
                    if any(word in title_lower for word in ["phd", "postdoc", "doctoral", "jrf", "srf", "research fellow"]):
                        cat = "PhD"
                    elif any(word in title_lower for word in ["msc", "master", "m.sc", "graduate program"]):
                        cat = "Masters"
                    elif any(word in title_lower for word in ["intern", "internship", "trainee", "student"]):
                        cat = "Internship"
                    elif any(word in title_lower for word in ["workshop", "training", "seminar", "course"]):
                        cat = "Workshop"
                    else:
                        cat = "Job"

                    # 2. Smart Field Assigner (If we are doing a generic academic sweep)
                    final_field = forced_field
                    if not final_field:
                        # Guess the field based on reading the description
                        fields_to_check = [
                            "Bioinformatics", "Genetics", "Microbiology", "Clinical Research", 
                            "Synthetic Biology", "Biomedical Engineering", "Biomanufacturing",
                            "Agricultural Biotechnology", "Pharmacogenomics"
                        ]
                        assigned = False
                        for f in fields_to_check:
                            if f.lower() in title_lower or f.lower() in desc_lower:
                                final_field = f
                                assigned = True
                                break
                        if not assigned:
                            final_field = "Biotechnology (General)"

                    # 3. Clean up Company & Add Country Flag
                    company_name = job.get("company", {}).get("display_name", "Institution")
                    loc_name = job.get("location", {}).get("display_name", "Remote")
                    flag = "🇮🇳" if country == "in" else "🇺🇸" if country == "us" else "🇬🇧"
                    full_location = f"{flag} {company_name} | {loc_name}"
                    
                    # 4. Process Date
                    created_raw = job.get("created", "")
                    try:
                        upload_date = datetime.strptime(created_raw, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d")
                    except:
                        upload_date = datetime.now().strftime("%Y-%m-%d")
                        
                    opp = Opportunity(
                        title=title,
                        category=cat, 
                        field=final_field, 
                        eligibility="See official description.", 
                        skills_required="Review Official Portal", 
                        location=full_location,
                        uploaded_date=upload_date,
                        deadline="Rolling / Check Portal",
                        exams_required="Refer to Official Portal",
                        fellowship_details="Review compensation on official site.",
                        link=job.get("redirect_url", "#"),
                        description=desc[:400] + "..." 
                    )
                    live_opportunities.append(opp)
                    
                db.add_all(live_opportunities)
                db.commit()
                time.sleep(1.5) # Crucial: Pauses so Adzuna doesn't block your IP address
                
            except Exception as e:
                print(f"  -> [API LIMIT] Interrupted. Details: {e}")
                break

def update_database():
    database.init_db()
    db = SessionLocal()
    
    print("Sweeping out old database completely...")
    db.query(Opportunity).delete() 
    db.commit()
    
    # ── SWEEP 1: Core Fields (Will harvest mostly Jobs) ──
    core_fields = [
        "Bioinformatics", "Genetics", "Microbiology", "Clinical Research", 
        "Biomedical Engineering", "Synthetic Biology", "Agricultural Biotechnology"
    ]
    for field in core_fields:
        # Grabs 300 jobs per field across 3 countries
        fetch_broad_sweep(db, search_term=field, forced_field=field, max_pages=2)
        
    # ── SWEEP 2: Academic & Training Focus (Forces the API to find Internships/PhDs) ──
    academic_sweeps = [
        "Biotechnology Internship", 
        "Life Sciences PhD", 
        "Biology Masters", 
        "Biotech Workshop",
        "Clinical Trainee"
    ]
    for term in academic_sweeps:
        # Searches deeply for these and maps them to the right field automatically
        fetch_broad_sweep(db, search_term=term, forced_field=None, max_pages=3)
    
    total_records = db.query(Opportunity).count()
    print(f"\n✅ SUCCESS: Database Fully Loaded with {total_records} Real, Global Opportunities!")
    db.close()

if __name__ == "__main__":
    update_database()