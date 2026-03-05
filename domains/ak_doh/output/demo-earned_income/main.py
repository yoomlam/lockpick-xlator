"""
Xlator AK DOH Earned Income Demo — FastAPI Backend

Accepts applicant facts from the browser form, evaluates them against the
OPA-compiled AK APA/ADLTC Medicaid earned income policy, and returns a
structured decision.

Requires OPA REST server running on port 8181:
    opa run --server --addr :8181 domains/ak_doh/output/earned_income.rego

Start this server:
    uvicorn main:app --host 0.0.0.0 --port 8000
"""

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

OPA_URL = "http://localhost:8181"
OPA_DECISION_PATH = "/v1/data/ak_doh/earned_income/decision"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify OPA is reachable at startup
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{OPA_URL}/health", timeout=3.0)
            resp.raise_for_status()
        log.info("OPA server reachable at %s", OPA_URL)
    except Exception as e:
        log.error(
            "WARNING: OPA server not reachable at %s: %s\n"
            "Start OPA before using the eligibility endpoint:\n"
            "    opa run --server --addr :8181 domains/ak_doh/output/earned_income.rego",
            OPA_URL,
            e,
        )
    yield


app = FastAPI(
    title="Xlator AK DOH Earned Income Demo",
    description="Evaluates AK APA/ADLTC Medicaid earned income eligibility using OPA-compiled CIVIL rules",
    version="2026Q1",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="static", html=True), name="static")


class InputFacts(BaseModel):
    household_type: str = Field(
        ...,
        description="APA household type code (A1E, B1E, H1E, A2S, B2S, H2S, A2C, B2C, H2C, NHR) used to look up the Expanded Refused Cash Income Limit",
    )
    is_couple: bool = Field(
        False,
        description="Applying as a couple; $20 and $65 exclusions applied once to combined income, not per-member",
    )
    is_blind_or_disabled: bool = Field(
        False,
        description="Blind or disabled per APA eligibility determination; required for student exclusion (step 4), IRWE (step 7), and self-support plan (step 10)",
    )
    is_blind: bool = Field(
        False,
        description="Specifically blind; receives broader blind work expense exclusion (step 9) instead of IRWE (step 7)",
    )
    age: int = Field(
        ...,
        ge=0,
        description="Age in years; must be under 22 to qualify for the student earned income exclusion",
    )
    gross_wages: float = Field(
        0.0, ge=0, description="Wages, salaries, commissions, bonuses, severance pay (APA § 441-1 A)"
    )
    flex_benefit_excess: float = Field(
        0.0,
        ge=0,
        description="Flexible health benefit excess paid directly to employee above mandatory health insurance cost (§ 441-1 B)",
    )
    sick_leave_within_6mo: float = Field(
        0.0,
        ge=0,
        description="Sick leave received within 6 months of work stopping due to sickness or disability (§ 441-1 C)",
    )
    garnishment_amount: float = Field(
        0.0,
        ge=0,
        description="Wages withheld to satisfy a debt or legal obligation; counted as earned income even if not received (§ 441-1 D)",
    )
    net_self_employment_income: float = Field(
        0.0,
        ge=0,
        description="Net self-employment income (gross less 50% standard or actual IRS costs), annualized and divided by 12 (§ 441-1 E)",
    )
    sheltered_workshop_earnings: float = Field(
        0.0,
        ge=0,
        description="Earnings from sheltered workshop or work activities center designed to prepare for self-support (§ 441-1 F)",
    )
    federal_law_exclusion_amount: float = Field(
        0.0,
        ge=0,
        description="Caseworker-determined total of earned income exclusions authorized by federal laws (§ 442-2 A; step 1)",
    )
    eitc_ctc_payment: float = Field(
        0.0,
        ge=0,
        description="EITC or Child Tax Credit payment (advance payroll or year-end refund); fully excluded (§ 442-2 B; step 2)",
    )
    infrequent_earned_amount: float = Field(
        0.0,
        ge=0,
        description="Infrequent/irregular earned income in current calendar quarter from a single source; quarterly cap $30 (§ 442-1 A; step 3)",
    )
    non_needs_unearned_income: float = Field(
        0.0,
        ge=0,
        description="Monthly non-needs-based unearned income; determines how much of the $20 general exclusion is consumed before applying to earned income (§ 442-1 B)",
    )
    college_hours_per_week: float = Field(
        0.0, ge=0, description="College/university hours per week; at least 8 required for regular school attendance (§ 442-2 D)"
    )
    grades7_12_hours_per_week: float = Field(
        0.0, ge=0, description="Grades 7–12 enrollment hours per week; at least 12 required (§ 442-2 D)"
    )
    training_shop_hours_per_week: float = Field(
        0.0, ge=0, description="Job training with shop practice hours per week; at least 15 required (§ 442-2 D)"
    )
    training_no_shop_hours_per_week: float = Field(
        0.0, ge=0, description="Job training without shop practice hours per week; at least 12 required (§ 442-2 D)"
    )
    student_earned_income: float = Field(
        0.0,
        ge=0,
        description="Earned income of blind/disabled student subject to exclusion; monthly cap $2,410 for 2026 (§ 442-2 D; step 4)",
    )
    irwe_amount: float = Field(
        0.0,
        ge=0,
        description="Impairment-related work expenses paid by a disabled (non-blind) individual; caseworker-verified (§ 442-2 G; step 7)",
    )
    blind_work_expense_amount: float = Field(
        0.0,
        ge=0,
        description="Work expenses paid by a blind individual; any expense qualifies; caseworker-verified (§ 442-2 I; step 9)",
    )
    self_support_plan_amount: float = Field(
        0.0,
        ge=0,
        description="Income set aside for SSA- or DVR-approved plan for achieving self-support; caseworker-verified (§ 442-2 J; step 10)",
    )


class ComputedBreakdown(BaseModel):
    total_gross_earned_income: float
    federal_exclusion: float
    eitc_exclusion: float
    infrequent_earned_exclusion: float
    is_regular_school_attendance: bool
    student_exclusion: float
    general_exclusion_used_on_unearned: float
    general_exclusion_on_earned: float
    dollar_65_exclusion: float
    irwe_exclusion: float
    pre_half_subtotal: float
    half_exclusion: float
    blind_work_exclusion: float
    self_support_exclusion: float
    final_earned_income: float


class DenialReason(BaseModel):
    code: str
    message: str
    citation: str = ""


class EligibilityResponse(BaseModel):
    eligible: bool
    denial_reasons: list[DenialReason]
    computed: ComputedBreakdown


@app.post("/api/ak_doh/earned_income", response_model=EligibilityResponse)
async def check_eligibility(facts: InputFacts):
    """
    Evaluate AK APA/ADLTC Medicaid earned income eligibility for an applicant.

    Posts applicant facts to the OPA REST server, which evaluates them against
    the transpiled earned income rules (domains/ak_doh/output/earned_income.rego).
    """
    payload = {"input": facts.model_dump()}

    async with httpx.AsyncClient() as client:
        try:
            opa_resp = await client.post(
                OPA_URL + OPA_DECISION_PATH,
                json=payload,
                timeout=10.0,
            )
            opa_resp.raise_for_status()
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail=f"Policy engine unavailable. Is OPA running at {OPA_URL}?",
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=502,
                detail=f"OPA returned error: {e.response.status_code}",
            )
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Policy engine timed out")

    body = opa_resp.json()
    result = body.get("result")

    if result is None:
        raise HTTPException(
            status_code=422,
            detail="Policy engine returned undefined — check that all required input fields are present",
        )

    return EligibilityResponse(
        eligible=result["eligible"],
        denial_reasons=[DenialReason(**r) for r in result.get("denial_reasons", [])],
        computed=ComputedBreakdown(**result["computed"]),
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
