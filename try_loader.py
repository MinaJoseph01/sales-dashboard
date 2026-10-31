"""Scratch script: tries the loader on good and messy data. Safe to delete later."""
import io
from src.data_loader import load_sales_data, DataValidationError

# 1. The real generated file
df, report = load_sales_data("data/sales_data.csv")
print("CLEAN FILE:", report.rows_read, "->", report.rows_kept, "| notes:", report.notes)
print(df.dtypes, "\n")

# 2. A deliberately messy file (note the lower-case 'order date' heading)
messy = """order date,Region,Country,Product,Category,Sales_Channel,Quantity,Unit_Price,Revenue,Cost,Profit,Order_ID
2025-01-05,Europe,France,Laptop,Technology,Online,2,"$1,000.00",,1500,,ORD-1
2025-01-05,Europe,France,Laptop,Technology,Online,2,"$1,000.00",,1500,,ORD-1
not a date,Europe,France,Mouse,Accessories,Online,1,30,30,15,15,ORD-2
2025-01-07,,France,Mouse,Accessories,Online,abc,30,30,15,15,ORD-3
2025-01-08,Asia Pacific,India,Chair,Furniture,Retail Store,3,100,300,200,100,ORD-4
2025-01-09,Asia Pacific,India,Chair,Furniture,Retail Store,-1,100,-100,50,-150,ORD-5
"""
df, report = load_sales_data(io.StringIO(messy))
print("MESSY FILE:", report.rows_read, "->", report.rows_kept)
for note in report.notes:
    print(" -", note)
print(df, "\n")

# 3. A file with the wrong columns
try:
    load_sales_data(io.StringIO("Name,Age\nAnna,30\n"))
except DataValidationError as err:
    print("WRONG COLUMNS ->", err, "\n")

# 4. An empty file
try:
    load_sales_data(io.StringIO(""))
except DataValidationError as err:
    print("EMPTY FILE ->", err)