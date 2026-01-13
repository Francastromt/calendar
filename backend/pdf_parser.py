import pdfplumber
import re
from datetime import datetime
import locale

# Set locale for Spanish dates if possible, else handle manual mapping
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except:
    pass

MONTH_MAP = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
}

def parse_tax_calendar(pdf_path: str):
    results = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            
            for table in tables:
                if not table: continue
                
                # Check column count
                if len(table[0]) < 2: continue

                # normalize headers
                # Use robust safe extraction
                h0 = str(table[0][0]).lower().strip() if table[0][0] else ""
                h1 = str(table[0][1]).lower().strip() if len(table[0]) > 1 and table[0][1] else ""
                
                # Header Check: "Terminación..." AND "Fecha..."
                if "terminación" in h0 and "vencimiento" in h1:
                    
                    period_data = {
                        "rules": []
                    }
                    
                    dates_found = []
                    
                    for row in table[1:]:
                        if not row or len(row) < 2: continue
                        
                        term_cell = row[0]
                        date_cell = row[1]
                        
                        if not term_cell or not date_cell: continue
                        
                        term_str = str(term_cell).strip().replace("\n", "")
                        date_str = str(date_cell).strip().replace("\n", "")
                        
                        # Parse Date first (must be valid)
                        dt_obj = None
                        try:
                            # Try DD/MM/YYYY
                            dt_obj = datetime.strptime(date_str, "%d/%m/%Y").date()
                        except:
                            continue # Skip non-date rows
                        
                        dates_found.append(dt_obj)

                        # Parse CUIT Range: "0-1", "0-1-2-3", "todos"
                        # Strategy: extract all digits, take min and max
                        if "todos" in term_str.lower():
                             period_data["rules"].append({"start": 0, "end": 9, "date": dt_obj})
                        else:
                            # extract all single digits
                            digits = re.findall(r'\d+', term_str)
                            if digits:
                                d_ints = [int(d) for d in digits]
                                # Create a rule for the range min-max, 
                                # OR strictly specific digits? The model assumes range start-end.
                                # "0-1-2-3" -> start=0, end=3.
                                # "4-5-6" -> start=4, end=6.
                                # "0-1" -> start=0, end=1.
                                period_data["rules"].append({
                                    "start": min(d_ints),
                                    "end": max(d_ints),
                                    "date": dt_obj
                                })

                    if period_data["rules"] and dates_found:
                        # Infer period name from the first date found
                        first_d = dates_found[0]
                        period_data["month"] = first_d.month
                        period_data["year"] = first_d.year
                        period_data["period_name"] = first_d.strftime("%B %Y").capitalize()
                        
                        results.append(period_data)
    
    return results

if __name__ == "__main__":
    # Test with dummy file if exists
    print("PDF Parser module loaded.")
    pass
