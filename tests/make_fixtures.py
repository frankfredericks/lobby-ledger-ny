"""Fictional fixtures that mirror the documented column names of each dataset.

Every person and organization here is invented. The demo site built from these
files carries a 'Demo data' banner.

    python tests/make_fixtures.py
"""
import csv
import json
import os
import random

random.seed(7)
D = os.path.join(os.path.dirname(__file__), "fixtures")
os.makedirs(D, exist_ok=True)


def dump(name, cols, rows):
    with open(os.path.join(D, f"{name}.json"), "w") as f:
        json.dump({"columns": [{"fieldName": c, "name": c.upper()} for c in cols], "rows": rows}, f, indent=1)


# ---------------------------------------------------------------- city
cand = [("Rivera, Ana M", "5", "R100"), ("Okafor, Daniel", "5", "R200"),
        ("Bellamy, Joan", "1", "R300"), ("Castellano, Peter", "3", "R400"), ("Whitlock, Simone", "5", "R500")]
orgs = [("Harborview Realty LLC", "LLC"), ("Harborview Realty, L.L.C.", "LLC"),
        ("Local 999 Building Trades PAC", "PCOMC"), ("Hotel Workers Union Local 6 COPE", "EMPO"),
        ("NYC Taxi Owners Association", "OTHR"), ("Queens Democratic Party", "PCOMZ"),
        ("Five Boroughs Charter Schools PAC", "PCOMC"), ("Metro Rideshare Technologies Inc", "CORP")]
cols = ["election", "officecd", "recipid", "canclass", "recipname", "committee", "date", "name", "c_code",
        "empname", "amnt", "refno", "schedule"]
rows, ref = [], 1000
for elec in ["2021", "2023", "2025"]:
    for (cn, office, rid) in cand:
        for (on, code) in random.sample(orgs, 5):
            ref += 1
            rows.append({"election": elec, "officecd": office, "recipid": rid, "canclass": "P", "recipname": cn,
                         "committee": "A", "date": f"{elec}-0{random.randint(1, 9)}-15T00:00:00.000",
                         "name": on, "c_code": code, "empname": "", "amnt": str(random.choice([400, 750, 1050, 1250])),
                         "refno": f"R{ref}", "schedule": "ABC"})
        for i in range(3):
            ref += 1
            rows.append({"election": elec, "officecd": office, "recipid": rid, "canclass": "P", "recipname": cn,
                         "committee": "A", "date": f"{elec}-03-01T00:00:00.000", "name": f"Doe, Pat {i}",
                         "c_code": "IND", "empname": "Harborview Realty", "amnt": "250", "refno": f"R{ref}",
                         "schedule": "ABC"})
dump("city_contributions", cols, rows)

lcols = ["client_id", "lobbyist_id", "lobbyist_name", "lobbyist_po", "report_year", "client_name", "client_po",
         "lobbyist_employees", "periodic_id", "period", "periodic_year", "compensation_total",
         "periodic_activities", "periodic_targets", "client_industry"]
acts = [
    ("Metro Rideshare Technologies Inc", "Kestrel Strategies LLC", "Transportation",
     "Local Legislation (including introduction) - Intro 30; Local Legislation - Int. No. 412-2024 - oppose",
     "NYC Council Members Ana Rivera - District No. 22; NYC Council Members Daniel Okafor - District No. 15; Taxi and Limousine Commission (TLC) Sam Lee"),
    ("Harborview Realty LLC", "Pemberton & Hale LLP", "Real Estate, Construction, Engineering & Developer",
     "Determination of Board or Commission - Rezoning change for 22-20 Example Avenue, Queens; Local Legislation - Intro 30",
     "NYC Council Members Ana Rivera - District No. 22; City Planning, Department of (DCP) Mia Chen"),
    ("NYC Taxi Owners Association", "Kestrel Strategies LLC", "Transportation",
     "Local Legislation - Intro 30 - support; Local Legislation - Int 0088-2022",
     "NYC Council Members Simone Whitlock - District No. 3; Mayor's Office Joan Bellamy"),
    ("Five Boroughs Charter Schools", "Pemberton & Hale LLP", "Education",
     "Budget - education funding; Resolution - Res 12",
     "Comptroller's Office Peter Castellano; NYC Council Members Daniel Okafor - District No. 15"),
]
lrows, pid = [], 5000
for y in [2021, 2022, 2023, 2024, 2025, 2026]:
    for per in [1, 4]:
        for (c, l, ind, a, t) in acts:
            if random.random() < 0.25:
                continue
            pid += 1
            lrows.append({"client_id": str(abs(hash(c)) % 9999), "lobbyist_id": str(abs(hash(l)) % 9999),
                          "lobbyist_name": l, "lobbyist_po": "", "report_year": str(y), "client_name": c,
                          "client_po": "", "lobbyist_employees": "", "periodic_id": str(pid), "period": str(per),
                          "periodic_year": str(y), "compensation_total": str(random.choice([5000, 8000, 12000])),
                          "periodic_activities": a, "periodic_targets": t, "client_industry": ind})
dump("city_lobbying", lcols, lrows)

dump("city_fundraising", ["lobbyist_name", "candidate_name", "amount", "report_year", "report_type", "report_id"], [
    {"lobbyist_name": "Kestrel Strategies LLC", "candidate_name": "Ana Rivera", "amount": "18500",
     "report_year": "2025", "report_type": "Fundraising", "report_id": "F1"},
    {"lobbyist_name": "Pemberton & Hale LLP", "candidate_name": "Joan Bellamy", "amount": "42000",
     "report_year": "2025", "report_type": "Fundraising", "report_id": "F2"},
])
dump("city_doing_business", ["name", "entity_name"], [{"name": "Harborview Realty LLC", "entity_name": "Harborview Realty LLC"}])

with open(os.path.join(D, "city_ie_contributions.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["spender", "contributor", "amount", "date", "source_url"])
    w.writerow(["New Yorkers for a Better Tomorrow", "Metro Rideshare Technologies Inc", "250000", "2025-04-02", "https://www.nyccfb.info/follow-the-money/follow-the-money/"])
    w.writerow(["New Yorkers for a Better Tomorrow", "Gregory Thaler", "50000", "2025-04-20", "https://www.nyccfb.info/follow-the-money/follow-the-money/"])
    w.writerow(["Queens Forward Inc", "Harborview Realty LLC", "75000", "2025-05-01", "https://www.nyccfb.info/follow-the-money/follow-the-money/"])
    w.writerow(["Queens Forward Inc", "Local 999 Building Trades PAC", "1500", "2025-05-03", "https://www.nyccfb.info/follow-the-money/follow-the-money/"])
with open(os.path.join(D, "city_ie_expenditures.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["spender", "candidate", "support_oppose", "amount", "date", "source_url"])
    w.writerow(["New Yorkers for a Better Tomorrow", "Ana Rivera", "Support", "180000", "2025-05-20", "https://www.nyccfb.info/follow-the-money/follow-the-money/"])
    w.writerow(["New Yorkers for a Better Tomorrow", "Daniel Okafor", "Oppose", "90000", "2025-06-01", "https://www.nyccfb.info/follow-the-money/follow-the-money/"])
    w.writerow(["Queens Forward Inc", "Ana Rivera", "Support", "60000", "2025-06-05", "https://www.nyccfb.info/follow-the-money/follow-the-money/"])

# ---------------------------------------------------------------- state
scols = ["form_submission_id", "reporting_year", "filing_type", "reporting_period", "principal_lobbyist_name",
         "contractual_client_name", "beneficial_client_name", "current_period_compensation", "level_of_government",
         "type_of_lobbying_focus", "focus_identifying_number_description", "government_body", "parties_lobbied",
         "first_and_last_name_or_title_of_person_lobbied", "monitoring_only"]
foc = [
    ("Metro Rideshare Technologies Inc", "Capitol Bridge Advisors LLC", [
        ("State Bill", "S1464A / 1749 - OPPOSE - REQUESTED AMENDMENTS", "NYS Senate", "SENATOR MARISOL VEGA"),
        ("State Bill", "S1464A / 1749 - OPPOSE", "NYS Assembly", "ASSEMBLY MEMBER THOMAS O'DWYER"),
        ("State Bill", "A3006 - PART BB - SUPPORT", "Executive Chamber", "GOVERNOR HELEN MARCH")]),
    ("Empire Gaming Coalition", "Capitol Bridge Advisors LLC", [
        ("State Bill", "S929", "NYS Senate", "SENATOR MARISOL VEGA"),
        ("State Bill", "Senate Bill 4423 - support", "NYS Assembly", "STAFF MEMBER ASSEMBLY MEMBER THOMAS O'DWYER"),
        ("State Regulation/Rate-making/Rule", "Gaming Commission rule on mobile wagering", "State Agency", "NYS Gaming Commission")]),
    ("Upstate Hospital Association", "Kestrel Strategies LLC", [
        ("State Bill", "S929 - SUPPORT", "NYS Senate", "SENATOR RAYMOND KOWALCZYK"),
        ("State Funding", "Medicaid rates in the FY budget", "Executive Chamber", "GOVERNOR HELEN MARCH")]),
]
srows, fid = [], 9000
for y in [2023, 2024, 2025, 2026]:
    for per in ["Jan/Feb", "Mar/Apr", "May/June"]:
        for (client, lob, items) in foc:
            fid += 1
            for (ft, fx, body, party) in items:
                srows.append({"form_submission_id": str(fid), "reporting_year": str(y), "filing_type": "Original",
                              "reporting_period": per, "principal_lobbyist_name": lob,
                              "contractual_client_name": client, "beneficial_client_name": client,
                              "current_period_compensation": "15000", "level_of_government": "State",
                              "type_of_lobbying_focus": ft, "focus_identifying_number_description": fx,
                              "government_body": body, "parties_lobbied": party,
                              "first_and_last_name_or_title_of_person_lobbied": "", "monitoring_only": "No"})
dump("state_lobbying", scols, srows)

ccols = ["filer_id", "filer_name", "office_desc", "district", "committee_type_desc", "election_year", "sched_date",
         "flng_ent_name", "flng_ent_first_name", "flng_ent_last_name", "cntrbr_type_desc", "org_amt", "trans_number"]
filers = [("F1", "Friends of Marisol Vega", "State Senator", "59", "Authorized Single Candidate"),
          ("F2", "Committee to Elect Thomas O'Dwyer", "Member of Assembly", "36", "Authorized Single Candidate"),
          ("F3", "Helen March for New York", "Governor", "", "Authorized Single Candidate"),
          ("F4", "Raymond Kowalczyk for Senate", "State Senator", "12", "Authorized Single Candidate")]
sdonors = [("Metro Rideshare Technologies Inc", "Corporation"), ("Empire Gaming Coalition PAC", "PAC"),
           ("Upstate Hospital Association PAC", "PAC"), ("Laborers Local 108 PAC", "Union"),
           ("Capitol Bridge Advisors LLC", "LLC")]
crows, tn = [], 1
for y in [2022, 2024, 2026]:
    for (fid_, fn, off, dist, ct) in filers:
        for (dn, dt) in random.sample(sdonors, 3):
            tn += 1
            crows.append({"filer_id": fid_, "filer_name": fn, "office_desc": off, "district": dist,
                          "committee_type_desc": ct, "election_year": str(y), "sched_date": f"{y}-05-10T00:00:00.000",
                          "flng_ent_name": dn, "flng_ent_first_name": "", "flng_ent_last_name": "",
                          "cntrbr_type_desc": dt, "org_amt": str(random.choice([2500, 5000, 10000, 4700])),
                          "trans_number": str(tn)})
        tn += 1
        crows.append({"filer_id": fid_, "filer_name": fn, "office_desc": off, "district": dist,
                      "committee_type_desc": ct, "election_year": str(y), "sched_date": f"{y}-05-10T00:00:00.000",
                      "flng_ent_name": "", "flng_ent_first_name": "Lee", "flng_ent_last_name": "Park",
                      "cntrbr_type_desc": "Individual", "org_amt": "100", "trans_number": str(tn)})
for (dn, amt) in [("Metro Rideshare Technologies Inc", "400000"), ("Gregory Thaler", "125000"), ("Empire Gaming Coalition PAC", "2000")]:
    tn += 1
    crows.append({"filer_id": "F9", "filer_name": "Empire Forward Independent Expenditure Committee", "office_desc": "",
                  "district": "", "committee_type_desc": "Independent Expenditure Committee", "election_year": "2026",
                  "sched_date": "2026-04-01T00:00:00.000", "flng_ent_name": dn, "flng_ent_first_name": "",
                  "flng_ent_last_name": "", "cntrbr_type_desc": "Individual" if "Thaler" in dn else "Corporation",
                  "org_amt": amt, "trans_number": str(tn)})
dump("state_contributions", ccols, crows)

dump("state_ie_expenditures", ["filer_id", "filer_name", "election_year", "filing_sched_desc", "filing_cat_desc",
                               "ie_cand_name", "ie_support_oppose", "org_amt", "trans_number"], [
    {"filer_id": "F9", "filer_name": "Empire Forward Independent Expenditure Committee", "election_year": "2026",
     "filing_sched_desc": "Independent Expenditures", "filing_cat_desc": "IE 24 Hour/Weekly Notices",
     "ie_cand_name": "Marisol Vega", "ie_support_oppose": "Support", "org_amt": "310000", "trans_number": "IE1"},
    {"filer_id": "F9", "filer_name": "Empire Forward Independent Expenditure Committee", "election_year": "2026",
     "filing_sched_desc": "Independent Expenditures", "filing_cat_desc": "IE 24 Hour/Weekly Notices",
     "ie_cand_name": "Raymond Kowalczyk", "ie_support_oppose": "Oppose", "org_amt": "150000", "trans_number": "IE2"},
])
titles = {}
for sess in ["2018-2021", "2022-2023", "2024-2025", "2026-2029"]:
    titles[f"Int 30@{sess}"] = {"title": "Caps on app-based ride fees during peak hours", "url": ""}
    titles[f"Res 12@{sess}"] = {"title": "Calling on the State to fund charter school facilities", "url": ""}
titles["Int 412@2024-2025"] = {"title": "Licensing requirements for for-hire vehicle drivers", "url": ""}
titles["Int 88@2022-2023"] = {"title": "Taxi medallion debt relief program", "url": ""}
for sess in ["2023-2024", "2025-2026"]:
    y = sess[:4]
    titles[f"S1464@{sess}"] = {"title": "Regulates surge pricing by transportation network companies", "url": f"https://www.nysenate.gov/legislation/bills/{y}/S1464"}
    titles[f"A1749@{sess}"] = {"title": "Regulates surge pricing by transportation network companies", "url": f"https://www.nysenate.gov/legislation/bills/{y}/A1749"}
    titles[f"A3006@{sess}"] = {"title": "Enacts the transportation, economic development and environmental conservation budget", "url": f"https://www.nysenate.gov/legislation/bills/{y}/A3006"}
    titles[f"S929@{sess}"] = {"title": "Provides for the protection of patient health information", "url": f"https://www.nysenate.gov/legislation/bills/{y}/S929"}
    titles[f"S4423@{sess}"] = {"title": "Authorizes mobile sports wagering kiosks at racetracks", "url": f"https://www.nysenate.gov/legislation/bills/{y}/S4423"}
with open(os.path.join(D, "bill_titles.json"), "w") as f:
    json.dump(titles, f, indent=1)
print("fixtures written to", D)
