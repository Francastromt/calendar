import pdfplumber

pdf_path = "/Users/francisco/Desktop/ARCA - Agencia de Recaudación y Control Aduanero.pdf"

try:
    print(f"--- INSPECTING: {pdf_path} ---")
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            print(f"\n=== PAGE {i+1} ===")
            
            # 1. Extract Text
            print("--- TEXT ---")
            text = page.extract_text()
            print(text[:500] + "..." if text else "[NO TEXT FOUND]")
            
            # 2. Extract Tables
            print("\n--- TABLES ---")
            tables = page.extract_tables()
            for j, table in enumerate(tables):
                print(f"Table {j+1}:")
                for row in table[:3]: # Print first 3 rows
                    print(row)
                print("...")

except Exception as e:
    print(f"ERROR: {e}")
