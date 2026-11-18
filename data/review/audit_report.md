# Data audit

Sample size per dataset: up to 5,000 rows from 2019 onward.

## Schema

### NYC Campaign Contributions (Campaign Finance Board) (`rjkp-yttg`)
- `election` → `election`
- `office` → `officecd`
- `recip_id` → `recipid`
- `recip_name` → `recipname`
- `cand_first` → `candfirst`
- `committee` → `committee`
- `date` → `date`
- `donor_name` → `name`
- `donor_type` → `c_code`
- `employer` → `empname`
- `amount` → `amnt`
- `refno` → `refno`
- `schedule` → `schedule`
- Columns not used: canclass, candmi, filing, pageno, sequenceno, refunddate, strno, strname, apartment, boroughcd, city, state, zip, occupation, empstrno, empstrname, empcity, empstate, matchamnt, prevamnt, pay_method, intermno, intermname, intstrno, intstrnm, intaptno, intcity, intst, intzip, intempname, intempstno, intempstnm, intempcity, intempst, intoccupa, purposecd, exemptcd, adjtypecd, rr_ind, seg_ind

### City Clerk eLobbyist Data (`fmf3-knd8`)
- `client_id` → `client_id`
- `client_name` → `client_name`
- `lobbyist_id` → `lobbyist_id`
- `lobbyist_name` → `lobbyist_name`
- `year` → `periodic_year`
- `period` → `period`
- `periodic_id` → `periodic_id`
- `activities` → `periodic_activities`
- `targets` → `periodic_targets`
- `compensation` → `compensation_total`
- `industry` → `client_industry`
- Columns not used: lobbyist_po, report_year, client_po, lobbyist_employees, lobbyist_activities, lobbyist_targets, lobbyist_is_colobbyist, lobbyist_has_finacial_interest, num_periods, start_date, end_date, registration_id, lobbying_expenses_total, small_expense_total, itemized_expense_total, salary_expense_total, reimbursed_expenses_total

### Lobbyists Fundraising and Political Consulting Reports (`7arw-dbem`)
- `lobbyist_name` → `lobbyist_employees`
- `candidate` → `candidate_last_name`
- `amount` → `total_expenses`
- `year` → `filing_year`
- `kind` → `report_type`
- `record_id` → `report_id`
- Columns not used: filing_period, period_start_date, period_end_date, entity_name, street_address, city, state, zip, phone, principal_last_name, principal_first_name, target_office, candidate_first_name, candidate_type, political_committee, third_party, compensation_owed, total_raised

### Doing Business Contributions Summary (CFB) (`fbkk-n4e3`)
- `name` → `name`
- `entity` → `empname`
- Columns not used: election, officecd, candid, canclass, candlast, candfirst, candmi, committee, filing, schedule, refno, date, refunddate, c_code, strno, strname, apartment, city, boroughcd, state, zip, db_entity_name, db_entity_start, occupation, empstrno, empstrname, empcity, empstate, amnt, matchamnt, prevamnt, pay_method, intermno, intermname, intstrno, intstrnm, intaptno, intcity, intst, intzip

### NYS Campaign Finance Disclosure Reports Contributions (Board of Elections) (`4j2b-6a2j`)
- `filer_id` → `filer_id`
- `filer_name` → `cand_comm_name`
- `cand_name` → **not found**
- `office` → `office_desc`
- `district` → `district`
- `committee_type` → **not found**
- `year` → `election_year`
- `date` → `sched_date`
- `donor_name` → `flng_ent_name`
- `donor_first` → `flng_ent_first_name`
- `donor_last` → `flng_ent_last_name`
- `donor_type` → `cntrbr_type_desc`
- `amount` → `org_amt`
- `trans_id` → `trans_number`
- Columns not used: filer_previous_id, election_type, county_desc, filing_abbrev, filing_desc, r_amend, filing_cat_desc, filing_sched_abbrev, filing_sched_desc, loan_lib_number, trans_mapping, org_date, cntrbn_type_desc, transfer_type_desc, receipt_type_desc, receipt_code_desc, purpose_code_desc, r_subcontractor, flng_ent_middle_name, flng_ent_add1, flng_ent_city, flng_ent_state, flng_ent_zip, flng_ent_country, payment_type_desc, pay_number, owed_amt, loan_other_desc, trans_explntn, r_itemized, r_liability, election_year_r, dist_off_cand_bal_prop

### Lobbyist Bi-Monthly Reports, 2019 to present (COELIG) (`t9kf-dqbc`)
- `form_id` → `form_submission_id`
- `year` → `reporting_year`
- `filing_type` → `filing_type`
- `period` → `reporting_period`
- `lobbyist_name` → `principal_lobbyist_name`
- `contract_client` → `contractual_client_name`
- `client_name` → `beneficial_client_name`
- `compensation` → `compensation`
- `level` → `level_of_government`
- `focus_type` → `lobbying_focus_type`
- `focus` → `focus_identifying_number`
- `gov_body` → `government_body`
- `party` → `party_name`
- `person` → `person_lobbied`
- `monitoring_only` → `monitoring_only`
- Columns not used: co_lobbyist, sub_lobbyist, individual_lobbyist_name, reimbursed_expenses, expenses_less_than_75, lobbying_expenses_for_non, itemized_expenses, expense_type, expense_paid_to, expense_reimbursed_by_client, expense_purpose, expense_date, expense_details_name, expense_details_title, expense_details_employer, expense_details_amount, coalition_name, contribution_amount, was_an_expense_incurred_on, total_amount_of_the_expense, was_the_expense_paid_for, if_pooled_funds_were_used, total_contribution_amount, coalition_contribution_expense, lobbying_subjects, type_of_lobbying_communication, department_lobbied, unique_id

### NYS Campaign Finance Disclosure Reports (all transactions) (`e9ss-239a`)
- `filer_id` → `filer_id`
- `filer_name` → `cand_comm_name`
- `year` → `election_year`
- `sched_desc` → `filing_sched_desc`
- `filing_cat` → `filing_cat_desc`
- `target` → `r_ie_supported`
- `stance` → `r_support_oppose`
- `amount` → `org_amt`
- `trans_id` → `trans_number`
- Columns not used: filer_previous_id, election_type, county_desc, filing_abbrev, filing_desc, r_amend, filing_sched_abbrev, loan_lib_number, trans_mapping, sched_date, org_date, cntrbr_type_desc, cntrbn_type_desc, transfer_type_desc, receipt_type_desc, receipt_code_desc, purpose_code_desc, r_subcontractor, flng_ent_name, flng_ent_first_name, flng_ent_middle_name, flng_ent_last_name, flng_ent_add1, flng_ent_city, flng_ent_state, flng_ent_zip, flng_ent_country, payment_type_desc, pay_number, owed_amt, loan_other_desc, trans_explntn, r_itemized, r_liability, election_year_r, office_desc, district, dist_off_cand_bal_prop, treas_occupation, treas_employer

## City

- Contribution donor types in sample: {'IND': 4907, 'PCOMP': 61, 'CAN': 14, 'EMPO': 10, 'PCOMZ': 5, 'FAM': 2, 'PCOMC': 1}
- Non-individual share of contributions: 2%
- Organization→candidate pairs at or above $2,500 in sample: 5% of 59
- Lobbying clients that also appear as organization donors: 0% (2 of 495)
- Lobbying rows mentioning legislation: 272; rows with a parsed bill ID: 297 (109% of mentions)
- Council-member targets linked to a named official: 17% (5077 of 30715)
- Organization donors found on the Doing Business list: 10%

## State

- Bill-type lobbying rows parsed into bill IDs: 94% (1766 of 1883)
- Self-described position on bill rows: {'': 1883}
- Party-lobbied rows naming a legislator or governor: 100%
- Top government bodies lobbied: {'NYS Assembly': 2133, 'NYS Senate': 224, 'Assembly Committee': 140, '': 3}
- Contribution donor types in sample: {'Individual': 4883, 'Partnership including LLPs': 53, 'Candidate Family Member': 23, 'Candidate/Candidate Spouse': 17, 'Unitemized': 13, '': 10, 'Political Committee': 1}
- Lobbying clients that also appear as donors: 0%
- Contribution rows whose committee links to a lobbied official: 0%
- Office column present: yes
- IE spending target column present: yes
