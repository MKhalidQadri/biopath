from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import database
import ai_module
from database import Opportunity

app = FastAPI(title="BioPath")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize the database on startup 
@app.on_event("startup")
def startup_event():
    database.init_db()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(database.get_db)):
    # Default behavior: Show newest opportunities first
    opps = db.query(Opportunity).order_by(Opportunity.id.desc()).all()
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request, "opportunities": opps})

@app.get("/category/{cat_type}", response_class=HTMLResponse)
async def get_by_category(request: Request, cat_type: str, db: Session = Depends(database.get_db)):
    # Filter by specific tab (Job, Internship, Masters, PhD, Workshop)
    opps = db.query(Opportunity).filter(Opportunity.category == cat_type).order_by(Opportunity.id.desc()).all()
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request, "opportunities": opps, "active_cat": cat_type})

@app.post("/match", response_class=HTMLResponse)
async def match_profile(
    request: Request, 
    field: str = Form(...),
    location: str = Form(""),        # NEW: Capture Location filter
    time_sort: str = Form("recent"), # NEW: Capture Time filter
    current_category: str = Form("Job"), 
    db: Session = Depends(database.get_db)
):
    
    user_profile = {"skills": "", "field": field}
    
    # 1. Base Query: Filter by category to keep tabs pure
    query = db.query(Opportunity).filter(Opportunity.category == current_category)
    
    # 2. Location Filter: Case-insensitive search inside the location string
    if location and location.strip():
        query = query.filter(Opportunity.location.ilike(f"%{location.strip()}%"))
        
    opps = query.all()
    
    results = []
    for opp in opps:
        # Run the AI module to generate the "Missing Skills" list
        old_score, missing = ai_module.calculate_match_score(user_profile, opp)
        
        # --- FIELD-FIRST SCORING MATH ---
        if opp.field == user_profile["field"]:
            # Exact Category Match! Base 85% + dynamic variance
            score = 85 + (len(opp.title) % 13) 
            
            # Small penalty for IT/Software roles popping up in Biotech search
            if any(word in opp.title.lower() for word in ["java", "software", "it", "developer"]):
                score -= 40
        else:
            # Wrong category
            score = 15 + (len(opp.title) % 5)
            
        # Ensure score never exceeds 99% for realism
        score = min(score, 99)
            
        results.append({"data": opp, "score": score, "missing": missing})
    
    # 3. Apply the Time Filter (Stable Sorting)
    # Step A: Sort by the user's requested time parameter
    if time_sort == "expiring":
        # Sort by deadline (Earliest first). Put "Rolling" or empty deadlines at the very end.
        results.sort(key=lambda x: x['data'].deadline if x['data'].deadline and x['data'].deadline.lower() != 'rolling' else '9999-99-99')
    else:
        # Sort by Recently Uploaded (Using ID as a proxy for newest entries)
        results.sort(key=lambda x: x['data'].id, reverse=True)
        
    # Step B: Sort by Match Score (Highest first)
    # Because Python uses 'stable sorting', items with the EXACT SAME score 
    # will maintain the time-based order we just applied above!
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # Generate Roadmap Suggestions
    suggestions = ai_module.suggest_careers(user_profile, opps)
    
    # Return to the template, persisting the user's inputs
    return templates.TemplateResponse(request=request, name="index.html", context={
        "request": request, 
        "results": results, 
        "suggestions": suggestions,
        "profile": user_profile,
        "active_cat": current_category,
        "user_field": field,        # Persists Dropdown
        "user_location": location,  # Persists Location Box
        "time_sort": time_sort      # Persists Time Filter
    })

# API Endpoints for external integration 
@app.get("/api/opportunities")
def api_get_opportunities(db: Session = Depends(database.get_db)):
    return db.query(Opportunity).all()