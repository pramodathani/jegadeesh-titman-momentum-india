# corporate_action_parser.py

NSE's corporate action API (`/api/corporates-corporateActions`) was found on 2026-10-07 to answer without session cookies, even though the NSE home page itself answers HTTP 403 to scripts. Its descriptions are free text in a handful of styles, and the parser reads these:

| Style | Example | Factor or dividend |
|---|---|---|
| Bonus | `Bonus 6:11` or `Bonus-1:1` | (6 + 11) / 11 |
| Split, new style | `Face Value Split (Sub-Division) - From Rs 10/- Per Share To Re 1/- Per Share` | 10 / 1 |
| Split, old style | `Fv Split Rs.10/- To Rs.2/` | 10 / 2 |
| Combined | `Bonus 1:1 And Face Value Split Rs.10/- To Rs.5/- Per Share` | 2 × 2 |
| Consolidation | `Consolidation Of Equity Shares From Re 1 Per Share To Rs 10 Per Share` | 1 / 10 |
| Dividend in rupees | `Interim Dividend - Rs 2 Per Share And Special Dividend - Rs 3 Per Share` | Rs 5 |
| Dividend in percent of face value | `Agm/Final Dividend-250%` | 2.5 × face value |

Rights issues, demergers and capital reductions are not adjusted, because the descriptions do not say enough (a demerger needs the value of the demerged company). Large demerger drops are caught by the implausible-move filter instead. Dividend text is read only up to the word "right", because `... / Rights 1:16 @ Premium Rs 400 Per Share` would otherwise add the rights premium as a dividend.

Coverage is thin before 2005: 70 to 250 actions a year in 1995 to 2004, against 800 to 2,700 a year from 2005. The run summary's "data quality by year" table shows how many unexplained large falls remain in each year, which is how the reliable start of the sample is chosen.

Two listed actions count as duplicates only when the share, the ex-date and the description (in lower case, spaces collapsed) all match. Matching on the factor instead wrongly dropped a split listed on the same day as a bonus with the same ratio.
