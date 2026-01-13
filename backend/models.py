from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from datetime import date

class Client(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    cuit: str = Field(index=True, unique=True)
    cva_status: str = "Active"  # Active, Inactive
    # New Fields for Phase 2
    client_type: str = "Responsable Inscripto" # Monotributo, RI, etc
    taxes: str = "IVA" # Comma separated list: "IVA, Ganancias, BP"
    
    obligations: List["Obligation"] = Relationship(back_populates="client")

class TaxPeriod(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str # e.g. "Enero 2026"
    month: int
    year: int
    
    rules: List["TaxRule"] = Relationship(back_populates="period")

class TaxRule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    period_id: int = Field(foreign_key="taxperiod.id")
    cuit_ending_start: int # e.g. 0
    cuit_ending_end: int   # e.g. 1
    due_date: date
    # New Field for Phase 2
    tax_name: str = "IVA" # IVA, Ganancias, etc.
    
    period: TaxPeriod = Relationship(back_populates="rules")

class Obligation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="client.id")
    period_id: int = Field(foreign_key="taxperiod.id") 
    due_date: date
    status: str = "Pending" # Pending, Presented, Late
    tax_name: str = "IVA" # Enriched field for display
    notes: Optional[str] = None
    assignee: Optional[str] = "Sin Asignar" # Veronica, Maria Cruz, etc.
    
    client: Client = Relationship(back_populates="obligations")
