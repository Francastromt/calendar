from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from sqlmodel import SQLModel, Session, create_engine, select
from typing import List
import shutil
import os
import sys
from datetime import date

# Fix Import Path for Render/Imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import Client, TaxPeriod, TaxRule, Obligation
from pdf_parser import parse_tax_calendar, extract_text_from_pdf

# Database Setup
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url, echo=False)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

app = FastAPI()

# Seed Data (Blue Clients from Screenshot)
def seed_clients():
    with Session(engine) as session:
        existing = session.exec(select(Client)).first()
        if not existing:
            clients = [
                Client(name="LAS PAIVA SA", cuit="30-71238604-1"),
                Client(name="Enrique Olivero", cuit="20-24961998-2"),
                Client(name="EPC S.A.S.", cuit="30-71582929-7"),
                Client(name="Irenne Valeria", cuit="27-23226169-8"),
                Client(name="BANYAK SA", cuit="30-71431597-4"),
                Client(name="ABASTO EL 50 SAS", cuit="30-71694554-1"),
                Client(name="FARMACIA SAN LUCAS SRL", cuit="33-70804828-9")
            ]
            for c in clients:
                session.add(c)
            session.commit()
            print("Seeded clients from screenshot.")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    seed_clients()

# API Endpoints

@app.get("/api/clients", response_model=List[Client])
def get_clients(session: Session = Depends(get_session)):
    return session.exec(select(Client)).all()

@app.post("/api/clients", response_model=Client)
def create_client(client: Client, session: Session = Depends(get_session)):
    session.add(client)
    session.commit()
    session.refresh(client)
    return client

@app.post("/api/upload-calendar")
async def upload_calendar(file: UploadFile = File(...), session: Session = Depends(get_session)):
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # Parse PDF
        periods_data = parse_tax_calendar(temp_path)
        
        created_count = 0
        for p_data in periods_data:
            # Create Period
            # Check if exists
            statement = select(TaxPeriod).where(TaxPeriod.month == p_data['month'], TaxPeriod.year == p_data['year'])
            period = session.exec(statement).first()
            
            if not period:
                period = TaxPeriod(name=p_data['period_name'], month=p_data['month'], year=p_data['year'])
                session.add(period)
                session.commit()
                session.refresh(period)
            
            # Create Rules
            for r in p_data['rules']:
                # Check for duplicate rules? Simple logic: just add if strictly new or assume pdf is truth
                # For MVP, let's just add.
                rule = TaxRule(
                    period_id=period.id,
                    cuit_ending_start=r['start'],
                    cuit_ending_end=r['end'],
                    due_date=r['date']
                )
                session.add(rule)
                created_count += 1
            
            session.commit()
            
            # Generate Obligations for Active Clients
            clients = session.exec(select(Client).where(Client.cva_status == "Active")).all()
            for client in clients:
                # Find matching rule
                cuit_last_digit = int(client.cuit.strip()[-1])
                
                # Find the rule that covers this digit
                # We need to query the rules we just added or available in period
                # (Ideally we do this in memory or query back)
                matching_rule = None
                for r in p_data['rules']:
                    if r['start'] <= cuit_last_digit <= r['end']:
                        matching_rule = r
                        break
                
                if matching_rule:
                    # Check if obligation exists
                    obs = session.exec(select(Obligation).where(
                        Obligation.client_id == client.id, 
                        Obligation.period_id == period.id,
                        Obligation.tax_name == "IVA"
                    )).first()
                    
                    if not obs:
                        new_ob = Obligation(
                            client_id=client.id, 
                            period_id=period.id,
                            due_date=matching_rule['date'],
                            status="Pending",
                            tax_name="IVA"
                        )
                        session.add(new_ob)
            
            session.commit()

        os.remove(temp_path)
        return {"message": "Calendar processed", "rules_created": created_count}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
             return {"response": "⚠️ El asistente está recibiendo muchas consultas (Límite de cuota gratuito). Por favor espera 1 minuto e intenta de nuevo."}
        elif "404" in error_msg:
             return {"response": "⚠️ Error de modelo de IA. Contacta al administrador."}
             
        raise HTTPException(status_code=500, detail=str(e))

    session.add(new_client)
    session.commit()
    session.refresh(new_client)
    return new_client

@app.delete("/api/clients/{client_id}")
def delete_client(client_id: int, session: Session = Depends(get_session)):
    client = session.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Cascade delete obligations
    obligations = session.exec(select(Obligation).where(Obligation.client_id == client_id)).all()
    for ob in obligations:
        session.delete(ob)
        
    session.delete(client)
    session.commit()
    return {"message": "Client deleted"}

@app.post("/api/upload-clients")
async def upload_clients(file: UploadFile, session: Session = Depends(get_session)):
    try:
        import pandas as pd
        temp_path = f"temp_clients_{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(await file.read())
            
        # Read Excel
        # Expected columns: Razon Social, CUIT, Tipo, Impuestos
        df = pd.read_excel(temp_path)
        
        # Normalize columns to lowercase for easier matching
        df.columns = [c.lower().strip() for c in df.columns]
        
        created_count = 0
        updated_count = 0
        
        for _, row in df.iterrows():
            # Extract data with safe fallbacks
            # Mapping: 'razon social' -> name, 'cuit' -> cuit
            name = row.get('razon social') or row.get('nombre')
            cuit = str(row.get('cuit', '')).strip()
            ctype = row.get('tipo', 'Responsable Inscripto')
            taxes = row.get('impuestos', 'IVA')
            
            if not name or len(cuit) < 10:
                continue # Skip invalid rows
                
            # Check existance
            client = session.exec(select(Client).where(Client.cuit == cuit)).first()
            if client:
                client.name = name
                client.client_type = ctype
                client.taxes = str(taxes) # Ensure string
                session.add(client)
                updated_count += 1
            else:
                new_client = Client(
                    name=name,
                    cuit=cuit,
                    client_type=str(ctype),
                    taxes=str(taxes)
                )
                session.add(new_client)
                created_count += 1
        
        session.commit()
        os.remove(temp_path)
        return {
            "message": "Clients processed successfully",
            "created": created_count,
            "updated": updated_count
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing Excel: {str(e)}")


@app.get("/api/dashboard")
def get_dashboard(session: Session = Depends(get_session)):
    # Get all obligations sorted by date
    # Join with Client and Period
    statement = select(Obligation, Client, TaxPeriod).where(Obligation.client_id == Client.id).where(Obligation.period_id == TaxPeriod.id).order_by(Obligation.due_date)
    results = session.exec(statement).all()
    
    data = []
    for ob, client, period in results:
        data.append({
            "id": ob.id,
            "client_name": client.name,
            "client_type": client.client_type, # NEW
            "cuit": client.cuit,
            "period": period.name,
            "tax_name": ob.tax_name, # NEW
            "due_date": ob.due_date,
            "status": ob.status,
            "assignee": ob.assignee, # NEW
            "days_left": (ob.due_date - date.today()).days
        })
    return data

import google.generativeai as genai
from pydantic import BaseModel

# Configure Gemini
# Configure Gemini
GENAI_KEY = os.getenv("GENAI_KEY", "AIzaSyB5qpyeK4Y87w1flk5hOxohXv0-E-H76A0")
if not GENAI_KEY:
    print("WARNING: GENAI_KEY not found in environment variables.")
genai.configure(api_key=GENAI_KEY)
# Using 'gemini-flash-latest' to find the most stable available model (likely 1.5 Flash)
model = genai.GenerativeModel('gemini-flash-latest')

class ChatRequest(BaseModel):
    message: str

def build_context(session: Session):
    # Fetch all data to give context to the AI
    clients = session.exec(select(Client)).all()
    obligations = session.exec(select(Obligation, Client).where(Obligation.client_id == Client.id)).all()
    
    context = "ACT AS AN ACCOUNTING STUDIO ASSISTANT. You are helpful, concise, and friendly.\n"
    context += "INSTRUCTIONS:\n"
    context += "1. ALWAYS RESPOND IN SPANISH (Argentina).\n"
    context += "GREETINGS/STATUS: If the user says 'Hola' or asks about simple status, be brief and direct.\n"
    context += "TECHNICAL QUESTIONS/RESEARCH: If the user asks HOW to do something, provide a detailed step-by-step guide.\n"
    context += "FORMATTING: DO NOT USE MARKDOWN (No **, No #, No `). Write in PLAIN TEXT. Use simple dashes (-) for lists. Use UPPERCASE for titles if needed.\n"
    context += "CONTEXT AWARENESS: Use the provided database info for specific client data, but use your General Knowledge for broad questions.\n\n"
    context += "DATABASE STATE:\n"
    context += "CLIENTS:\n"
    for c in clients:
        context += f"- {c.name} ({c.cuit}) [TaxType: {c.client_type}, Taxes: {c.taxes}]\n"
    
    context += "\nOBLIGATIONS/VENCIMIENTOS:\n"
    for ob, c in obligations:
        context += f"- {c.name}: Due {ob.due_date} | Status: {ob.status} | Tax: {ob.tax_name}\n"

    # Inject Knowledge Base
    try:
        if os.path.exists("knowledge.txt"):
            with open("knowledge.txt", "r", encoding="utf-8") as kf:
                k_content = kf.read()
                context += f"\n\nKNOWLEDGE BASE (INTERNAL RULES & TAX LAWS):\n{k_content}\n"
    except Exception as e:
        print(f"Error reading knowledge base: {e}")
        
    context += "\nUser Question: "
    return context

@app.post("/api/chat")
def chat_with_assistant(req: ChatRequest, session: Session = Depends(get_session)):
    try:
        context = build_context(session)
        full_prompt = context + req.message
        
        response = model.generate_content(full_prompt)
        return {"response": response.text}
    except Exception as e:
        import traceback
        traceback.print_exc() # Log full error to terminal
        print(f"GEMINI ERROR: {e}") # Explicit print
        
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
             return {"response": "⚠️ El asistente está saturado (Límite de cuota). Intenta en unos minutos o usa otro modelo."}
        elif "404" in error_msg:
             return {"response": "⚠️ Error de configuración de IA (Modelo no encontrado)."}
             
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/obligations/{ob_id}/toggle")
def toggle_status(ob_id: int, session: Session = Depends(get_session)):
    ob = session.get(Obligation, ob_id)
    if not ob:
        raise HTTPException(status_code=404, detail="Obligation not found")
    
    ob.status = "Presented" if ob.status == "Pending" else "Pending"
    session.add(ob)
    session.commit()
    return ob

class KnowledgeRequest(BaseModel):
    content: str

@app.get("/api/knowledge")
def get_knowledge():
    try:
        if os.path.exists("knowledge.txt"):
            with open("knowledge.txt", "r", encoding="utf-8") as f:
                return {"content": f.read()}
        return {"content": ""}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/knowledge")
def save_knowledge(req: KnowledgeRequest):
    try:
        with open("knowledge.txt", "w", encoding="utf-8") as f:
            f.write(req.content)
        return {"message": "Conocimiento actualizado explícitamente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/knowledge/upload-pdf")
async def upload_knowledge_pdf(file: UploadFile = File(...)):
    temp_path = f"temp_knowledge_{file.filename}"
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        extracted_text = extract_text_from_pdf(temp_path)
        
        # Append to knowledge.txt
        current_content = ""
        if os.path.exists("knowledge.txt"):
            with open("knowledge.txt", "r", encoding="utf-8") as f:
                current_content = f.read()
        
        new_content = current_content + f"\n\n--- CONTENIDO EXTRAÍDO DE {file.filename} ---\n" + extracted_text
        
        with open("knowledge.txt", "w", encoding="utf-8") as f:
            f.write(new_content)
            
        os.remove(temp_path)
        return {"message": "PDF procesado y añadido al conocimiento.", "text_length": len(extracted_text)}

    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")

# ... imports
from sqlalchemy import text

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    # Migration for assignee column
    try:
        with Session(engine) as session:
            session.exec(text("ALTER TABLE obligation ADD COLUMN assignee TEXT DEFAULT 'Sin Asignar'"))
            session.commit()
            print("MIGRATION: Added assignee column to Obligation table.")
    except Exception as e:
        # Common if column already exists
        print(f"MIGRATION CHECK: {e}")

# ... (existing endpoints)

class AssignmentRequest(BaseModel):
    assignee: str

@app.post("/api/obligations/{ob_id}/assign")
def assign_obligation(ob_id: int, req: AssignmentRequest, session: Session = Depends(get_session)):
    ob = session.get(Obligation, ob_id)
    if not ob:
        raise HTTPException(status_code=404, detail="Obligation not found")
    
    ob.assignee = req.assignee
    session.add(ob)
    session.commit()
    return ob

# Mount Static Frontend
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../static")
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
