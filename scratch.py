import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

companies = [
    ("Apple", "US", 2024, "Q1", "Apple reported strong earnings for Q1 2024. Revenue was up 5%. Services grew double digits. iPhone sales were steady. Tim Cook mentioned AI investments."),
    ("Microsoft", "US", 2024, "Q1", "Microsoft Cloud drove growth. Satya Nadella highlighted AI integration across the stack. Office 365 commercial revenue increased 15%."),
    ("Reliance", "India", 2024, "Q1", "Reliance Jio and Retail segments saw strong growth. O2C margins were stable. Mukesh Ambani discussed new green energy initiatives.")
]

base_dir = "data"

for company, market, year, quarter, text in companies:
    dir_path = os.path.join(base_dir, market, company)
    os.makedirs(dir_path, exist_ok=True)
    
    filename = f"{company}_{market}_{year}_{quarter}.pdf"
    filepath = os.path.join(dir_path, filename)
    
    c = canvas.Canvas(filepath, pagesize=letter)
    c.drawString(72, 720, f"{company} Earnings Call {quarter} {year}")
    c.drawString(72, 700, text)
    c.save()
    print(f"Created {filepath}")

