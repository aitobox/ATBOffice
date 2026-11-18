# Issue #409: Restore worksheet chart fills and titles

## Problem

`openxml-sdk__NoExtDataB1.xlsx` and `poi__60509.xlsx` omit the chart-area `c:spPr` and store an
empty `c:title`. Excel treats those as an opaque white chart area and an automatic title. The
importer read them as a transparent chart with no title, so cell values showed through the chart
and the "Demo" title was missing.

## Design

`parse_chart_xml` gains a keyword-only `worksheet_defaults` flag, and only the XLSX reader sets it.
Slide and Word charts keep their current import results.

| Source | Result |
| --- | --- |
| No chart-area fill, or an unsupported fill | Opaque white |
| `a:noFill` | Transparent |
| `a:solidFill` | Its colour and alpha |
| No chart-area line | `#868686` border |
| `a:ln` with `a:noFill` | No border |
| `a:ln` with `a:solidFill` | Its colour |
| Rich or cell-linked title text | That text |
| Empty `c:title`, one series | Series name |
| Empty `c:title`, several series | "Chart Title" |
| No `c:title`, one series, automatic title not deleted | Series name |
| No `c:title`, otherwise | No title |

The title rules follow the reference reader in `.vibeoffice/public/lectern/js/pptx-read.js`.

## Known limits

- Colour modifiers such as `lumMod` are not applied to chart-area theme colours.
- Theme colours use the chart module's static theme map, not the workbook theme.

## Task list

- [x] Task 1: Add regression tests for fills, borders, titles, and both fixtures
- [x] Task 2: Resolve worksheet chart defaults during XLSX import
- [x] Task 3: Paint chart-area alpha
- [x] Task 4: Verify the fixtures and the spreadsheet and presentation suites
