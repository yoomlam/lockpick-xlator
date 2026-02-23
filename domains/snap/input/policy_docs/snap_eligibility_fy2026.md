# SNAP Income Eligibility Rules — FY2026

**Program:** Supplemental Nutrition Assistance Program (SNAP)
**Administering Agency:** USDA Food and Nutrition Service (FNS)
**Effective Period:** October 1, 2025 – September 30, 2026
**Jurisdiction:** 48 contiguous states and the District of Columbia
**Primary Authority:** 7 CFR § 273.9

---

## Overview

SNAP provides nutrition assistance to low-income households. To receive benefits, a household must meet income eligibility criteria. There are two income tests — a gross income test and a net income test — that households must pass. Households containing an elderly or disabled member are exempt from the gross income test but must still pass the net income test.

---

## Who Is in a SNAP Household

A SNAP household generally includes people who live together and purchase and prepare food together. Household composition affects the income limits applied. (7 CFR § 273.1)

**Elderly member:** A person age 60 or older. (7 CFR § 273.1(b)(7))

**Disabled member:** A person who receives Supplemental Security Income (SSI), Social Security Disability Insurance (SSDI), or otherwise meets the SSA disability definition; or a veteran with a service-connected or total disability; or a person receiving disability retirement benefits from a government agency. (7 CFR § 273.1(b)(7))

---

## Test 1: Gross Income Test

A household's total gross monthly income must not exceed **130% of the Federal Poverty Level** for the household's size. (7 CFR § 273.9(a)(1))

**Exemption:** Households that contain at least one elderly (age 60+) or disabled member are **exempt from the gross income test**. They are only subject to the net income test. (7 CFR § 273.9(a)(1))

### FY2026 Gross Income Limits (130% FPL, Monthly)

| Household Size | Gross Monthly Limit |
|---|---|
| 1 | $1,696 |
| 2 | $2,292 |
| 3 | $2,888 |
| 4 | $3,483 |
| 5 | $4,079 |
| 6 | $4,675 |
| 7 | $5,271 |
| 8 | $5,867 |
| Each additional person | +$596 |

Source: USDA FNS, FY2026 SNAP Income Standards (effective October 1, 2025)

---

## Test 2: Net Income Test

All households — including those with elderly or disabled members — must have a net monthly income at or below **100% of the Federal Poverty Level** for the household's size after allowable deductions are applied. (7 CFR § 273.9(a)(2))

### FY2026 Net Income Limits (100% FPL, Monthly)

| Household Size | Net Monthly Limit |
|---|---|
| 1 | $1,305 |
| 2 | $1,763 |
| 3 | $2,221 |
| 4 | $2,680 |
| 5 | $3,138 |
| 6 | $3,596 |
| 7 | $4,055 |
| 8 | $4,513 |
| Each additional person | +$459 |

Source: USDA FNS, FY2026 SNAP Income Standards (effective October 1, 2025)

---

## Allowable Deductions

Net income is computed by subtracting the following allowable deductions from gross income, applied in this order. (7 CFR § 273.9(b)–(d))

### Deduction 1: Earned Income Deduction

**Amount:** 20% of earned income (wages and self-employment income)

This deduction applies only to earned income — income from wages, salaries, or net self-employment earnings. It does not apply to unearned income such as Social Security, child support, or unemployment compensation. (7 CFR § 273.9(b))

**Formula:** `earned_income_deduction = earned_income × 0.20`

### Deduction 2: Standard Deduction

All households receive a standard deduction regardless of actual expenses. The amount varies by household size. (7 CFR § 273.9(c))

**FY2026 Standard Deduction Amounts:**

| Household Size | Monthly Deduction |
|---|---|
| 1 | $209 |
| 2 | $209 |
| 3 | $209 |
| 4 | $223 |
| 5 | $261 |
| 6+ | $299 |

### Deduction 3: Dependent Care Deduction

Households may deduct actual out-of-pocket costs for the care of a child or other dependent when care is needed so a household member can work, look for work, or attend training/education. (7 CFR § 273.9(d)(4))

**Amount:** Actual dependent care costs paid (no fixed cap under federal rules)

### Deduction 4: Excess Shelter Deduction

Households may deduct shelter costs that exceed 50% of the household's income after all prior deductions are applied.

**Shelter costs** include rent, mortgage payments, property taxes, homeowners insurance, and utility costs (or a standard utility allowance). (7 CFR § 273.9(d)(6))

**Shelter cap:** For households without an elderly or disabled member, the shelter deduction is capped at **$744 per month**. Households with an elderly or disabled member have no cap on the shelter deduction. (7 CFR § 273.9(d)(6)(ii))

**Formula:**
```
income_after_prior_deductions = gross_income
                                - earned_income_deduction
                                - standard_deduction
                                - dependent_care_deduction

shelter_excess = max(0, shelter_costs - (0.50 × income_after_prior_deductions))

if household has elderly or disabled member:
    shelter_deduction = shelter_excess       # no cap
else:
    shelter_deduction = min(shelter_excess, $744)
```

---

## Net Income Calculation (Full Formula)

```
gross_income
  − (earned_income × 0.20)                            [Deduction 1: earned income]
  − standard_deduction[household_size]                [Deduction 2: standard]
  − dependent_care_costs                              [Deduction 3: dependent care]
  − shelter_deduction                                 [Deduction 4: excess shelter]
= net_income
```

The household passes the net income test if: `net_income ≤ net_income_limit[household_size]`

---

## What Is Counted as Income

**Countable income includes:**
- Wages and salaries (earned income)
- Net self-employment earnings (earned income)
- Social Security, SSI, SSDI payments (unearned income)
- Child support and alimony received (unearned income)
- Unemployment compensation (unearned income)
- Most other regular payments

**Not counted (excluded from gross income):**
- SNAP benefits themselves
- Most education assistance
- Certain vendor payments
- TANF payments to third parties

(7 CFR § 273.9(a)–(b); this POC uses gross monthly income as reported — income exclusions are handled upstream before this module is invoked.)

---

## Out of Scope for This Module

The following SNAP eligibility criteria are **not** addressed in this income eligibility module:

- **Asset/resource limits** — households with elderly/disabled members are subject to a resource test; others generally are not (under broad-based categorical eligibility)
- **Categorical eligibility** — households receiving TANF or certain TANF-funded services may be automatically eligible (BBCE)
- **Medical deduction** — elderly/disabled households may deduct out-of-pocket medical costs above $35/month
- **Homeless shelter standard** — a fixed deduction of $198.99/month in lieu of actual shelter costs
- **State-level variations** — states may implement higher gross income limits (up to 200% FPL) under BBCE waivers

---

## Primary Legal Citations

| Citation | Description |
|---|---|
| 7 CFR § 273.1 | Household and membership definitions |
| 7 CFR § 273.9(a)(1) | Gross income test and elderly/disabled exemption |
| 7 CFR § 273.9(a)(2) | Net income test |
| 7 CFR § 273.9(b) | Earned income deduction |
| 7 CFR § 273.9(c) | Standard deduction |
| 7 CFR § 273.9(d)(4) | Dependent care deduction |
| 7 CFR § 273.9(d)(6) | Excess shelter deduction and cap |

**Source documents:**
- USDA FNS SNAP Eligibility: https://www.fns.usda.gov/snap/recipient/eligibility
- FY2026 SNAP Income Standards: https://www.fns.usda.gov/snap/allotment/cola/fy26
- Code of Federal Regulations, Title 7, Part 273: https://www.ecfr.gov/current/title-7/subtitle-B/chapter-II/subchapter-C/part-273
