\# Sales Performance Dashboard



An interactive sales dashboard built with \*\*Python, Streamlit, Pandas and Plotly\*\*. It runs locally, reads a CSV file, and lets you explore revenue, orders, profit and margin by date, region, product category and sales channel.



> All data in this repository is \*\*synthetic (fictional)\*\*, created by `generate\_data.py`.

<img width="1917" height="941" alt="image" src="https://github.com/user-attachments/assets/77d596bc-dbf7-4baf-941e-c6f55c29c735" />






\## Features



\- \*\*Executive overview:\*\* six KPI cards (Total Revenue, Total Orders, Units Sold, Average Order Value, Total Profit, Profit Margin) with change versus the previous period

\- \*\*Seven interactive Plotly charts:\*\* monthly revenue trend, revenue by region, channel and category, top 5 and bottom 5 products, profit and margin by category

\- \*\*Sidebar filters:\*\* date range, region, product category, sales channel. Every KPI and chart responds to them

\- \*\*Upload your own CSV\*\* from the dashboard, or download a template. The dashboard refreshes automatically

\- \*\*Data validation and cleaning:\*\* clear error messages, duplicate removal, missing-value handling, automatic date parsing and number conversion

\- \*\*Automated tests:\*\* 44 pytest checks covering calculations, filters, data cleaning, charts and the app itself



\## Tech stack



| Tool | Purpose |

|---|---|

| Python | Language (developed on 3.12) |

| Pandas | Loading, cleaning, filtering, aggregating data |

| Plotly | Interactive charts |

| Streamlit | Turns the Python code into a local web dashboard |

| pytest | Automated tests |



\## Quick start (Windows PowerShell)



```powershell

git clone https://github.com/<your-username>/sales-dashboard.git

cd sales-dashboard

py -m venv .venv

.\\.venv\\Scripts\\Activate.ps1

pip install -r requirements.txt

streamlit run app.py

```



The dashboard opens at <http://localhost:8501>. Sample data is included in `data/sales\_data.csv`. To recreate it, run `python generate\_data.py`.



On macOS/Linux, use `python3 -m venv .venv` and `source .venv/bin/activate`.



\## Updating the data (no code changes needed)



| Method | How | Lasts |

|---|---|---|

| Upload in the dashboard | Sidebar → \*\*Upload a sales CSV\*\*. Remove the file (x) to return to the sample data. | Current browser session |

| Replace the default file | Overwrite `data/sales\_data.csv` with a file in the same format, then refresh the browser | Until you change it again |

| Regenerate sample data | `python generate\_data.py` (edit the settings at the top of that file for size or date range) | Overwrites the default file |



\## CSV format



Download the template from the sidebar, or use these columns (names are matched ignoring case and spaces):



| Column | Meaning |

|---|---|

| Order\_ID | Order identifier. An order can have several rows (lines) |

| Order\_Date | Use `YYYY-MM-DD`. Other formats work, see the note on dates below |

| Region, Country | Where the order was sold |

| Product, Category | What was sold |

| Sales\_Channel | Online, Retail Store, etc. |

| Quantity | Units on this line (must be above 0) |

| Unit\_Price | Price per unit |

| Revenue | Quantity × Unit\_Price |

| Cost | \*\*Total\*\* cost of the whole line, not per unit |

| Profit | Revenue − Cost |



\*\*Dates:\*\* `2025-04-03` is always read correctly. For ambiguous dates such as `03/04/2025`, choose the format in the sidebar after uploading (default is month first).



\## How the numbers are calculated



| Metric | Calculation |

|---|---|

| Revenue | Quantity × Unit\_Price |

| Profit | Revenue − Cost |

| Total Orders | Number of \*\*unique\*\* Order\_IDs |

| Average Order Value | Total Revenue ÷ Total Orders |

| Profit Margin | Total Profit ÷ Total Revenue × 100 |

| Previous period | Same number of days, ending the day before the selected start date |

| Margin change | Percentage points (pp), not percent |



\## Data cleaning rules



| Situation | What happens |

|---|---|

| Exact duplicate row | Removed |

| Missing or unreadable Order\_ID, Order\_Date, Quantity, Unit\_Price or Cost | Row removed |

| Quantity ≤ 0 or negative Unit\_Price | Row removed |

| Missing Region, Country, Product, Category or Sales\_Channel | Filled with "Unknown" |

| Missing Revenue or Profit | Calculated from the formulas above |

| Revenue or Profit that disagree with the formulas | Kept, with a warning |

| Text like `$1,250.50` in a number column | Converted to 1250.5 |



Every removal or fix is reported in the sidebar under "Data quality notes".



\## Project structure



```

sales-dashboard/

├── app.py                  # Dashboard page: layout, filters, upload

├── generate\_data.py        # Creates the synthetic dataset

├── requirements.txt        # Libraries needed to run

├── requirements-dev.txt    # Adds pytest for development

├── pytest.ini

├── data/sales\_data.csv     # Default (synthetic) data

├── src/

│   ├── data\_loader.py      # Read, validate, clean

│   ├── metrics.py          # KPIs, filters, previous-period logic

│   └── charts.py           # One function per Plotly chart

├── tests/test\_dashboard.py # 44 automated tests

└── .streamlit/config.toml  # Theme

```



\## Running the tests



```powershell

pip install -r requirements-dev.txt

python -m pytest

```



\## Troubleshooting



| Problem | Fix |

|---|---|

| `running scripts is disabled` when activating the venv | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`, then activate again |

| `ModuleNotFoundError` | The virtual environment isn't active. Run `.\\.venv\\Scripts\\Activate.ps1` |

| `Port 8501 is already in use` | Close the old instance, or use `streamlit run app.py --server.port 8502` |

| "Sample data not found" | Run `python generate\_data.py` |

| `TypeError` about `width` or `border` | Streamlit is too old: `pip install -U streamlit` |

| "Upload rejected" | Read the message. It lists missing columns or what is wrong with the file |

| Dates look wrong after upload | Change "Date format in your file" in the sidebar |



\## Design decisions and limitations



\- \*\*Cost is the total cost of an order line\*\*, so Profit = Revenue − Cost holds exactly.

\- \*\*Previous-period comparison is sequential.\*\* Seasonal businesses will see distorted changes (for example, Q1 compared with a busy Q4). A same-period-last-year option would be a useful addition.

\- \*\*Identical rows are treated as duplicates and removed.\*\* In real data, two identical lines in one order could be legitimate.

\- The app is \*\*local and single-user\*\*: no login, and uploaded files are not saved to disk.

\- The data is synthetic, so the figures illustrate the dashboard and say nothing about any real business.



\## Possible next steps



\- Same-period-last-year comparison toggle

\- Column mapping, so files with different column names (such as the public Superstore dataset) can be loaded

\- Optional deployment to a hosting service



\## Built with AI assistance



I built this project as a learning exercise, using Claude (Anthropic) as a guide: it explained each step and I built, ran and tested the code myself. The dashboard itself contains no AI features.

