"""
Goal focus plugin - turns vision and targets into a laddered execution plan.
为聚焦单一赛道的创业者生成分阶段、可衡量的工作蓝图。
"""

from math import ceil
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, validator

from config import get_api_password


router = APIRouter()
security = HTTPBearer()


async def authenticate_plugin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Authenticate using the API password (shared with chat endpoints)."""

    password = await get_api_password()
    token = credentials.credentials
    if token != password:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="密码错误")
    return token


class FocusGoalRequest(BaseModel):
    """User provided goal inputs for the focus plugin."""

    focus_area: str = Field(..., description="行业或细分方向，例如电子消费品定制")
    product_or_service: str = Field(..., description="要打磨的核心产品或服务")
    timeframe_months: int = Field(12, gt=0, le=24, description="目标时间范围（月）")
    target_monthly_revenue: int = Field(..., ge=0, description="目标月流水（元）")
    target_core_users: int = Field(..., ge=0, description="目标核心用户数量")
    differentiation: Optional[str] = Field(
        None, description="产品/服务的差异化或护城河，如定制能力、供应链优势"
    )
    constraints: List[str] = Field(
        default_factory=list,
        description="已知约束或资源限制，例如预算、团队人数、时间投入",
    )
    personal_priorities: List[str] = Field(
        default_factory=list, description="个人优先级，如家庭陪伴、健康作息"
    )

    @validator("focus_area", "product_or_service", pre=True)
    def _strip_text(cls, value: str) -> str:  # noqa: N805
        return value.strip() if isinstance(value, str) else value


class GoalMetrics(BaseModel):
    monthly_revenue: str
    core_users: str
    timeframe_months: int


class Metric(BaseModel):
    name: str
    target: str
    why_it_matters: str


class Milestone(BaseModel):
    label: str
    focus: str
    deliverables: List[str]
    metrics: List[Metric]
    guardrails: List[str]


class SuccessSnapshot(BaseModel):
    operating_state: str
    team: str
    your_day: str
    finances: str
    life: str


class OperatingRhythm(BaseModel):
    weekly_commitments: List[str]
    daily_rules: List[str]
    review_rituals: List[str]


class GoalPlanResponse(BaseModel):
    goal_statement: str
    numeric_targets: GoalMetrics
    success_snapshot: SuccessSnapshot
    milestones: List[Milestone]
    operating_rhythm: OperatingRhythm
    first_week_actions: List[str]
    focus_guardrails: List[str]


def _fmt_currency(amount: int) -> str:
    return f"{amount:,} 元" if amount else "0 元"


def _build_milestones(req: FocusGoalRequest) -> List[Milestone]:
    """Create laddered milestones from the final target using backward planning."""

    # Stage templates reflect the user's description: 目标->愿景->倒推路径
    stage_templates = [
        {
            "focus": "验证问题与付费意愿",
            "deliverables": [
                f"锁定单一人群画像与痛点，围绕 {req.focus_area} 的 {req.product_or_service} 形成一页纸价值假设",
                "完成 12-20 次深访，并形成可验证的付费理由清单",
                "打磨最小可用版本（MVP），并获得首批付费/订金用户",
            ],
            "guardrails": [
                "只做一类用户、一种场景，暂不扩展功能线",
                "付费验证优先于流量增长，每周输出访谈纪要与决策",
            ],
        },
        {
            "focus": "产品化与首批交付",
            "deliverables": [
                "形成可重复交付的标准作业（SOP）与报价单",
                "完成首批可公开的成功案例/评测，获得用户可转述的口碑",
                "建立基础获客路径：固定渠道+标准话术+可追踪漏斗",
            ],
            "guardrails": [
                "功能追加需绑定明确的付费用户请求",
                "每周聚焦一个主渠道，直到该渠道跑出正向回报",
            ],
        },
        {
            "focus": "放大复购与运营稳定",
            "deliverables": [
                "形成可预测的交付节奏（周期、成本、质量线）",
                "建立复购/续费触点与低成本留存动作",
                "把客户转介绍流程产品化，沉淀脚本与物料",
            ],
            "guardrails": [
                "用现金流自驱，扩张前保持正毛利",
                "除核心渠道外，其余尝试以一页复盘评估，不做长期占用",
            ],
        },
        {
            "focus": "巩固护城河与可持续运营",
            "deliverables": [
                "梳理关键资产：独家供应链/内容库/自动化脚本/用户社群",
                "建立指标看板与例会节奏，明确预警阈值",
                "将创始人从日常交付中抽离，更多投入在增长与产品迭代",
            ],
            "guardrails": [
                "新增方向需对核心指标有直接提升，否则暂缓",
                "保持现金储备与时间缓冲，避免过度承诺",
            ],
        },
    ]

    stage_count = max(1, ceil(req.timeframe_months / 3))
    selected_stages = stage_templates[:stage_count]

    # 以递进方式拆解指标
    revenue_targets = [
        max(1, int(req.target_monthly_revenue * ratio))
        for ratio in [0.1, 0.3, 0.7, 1.0]
    ]
    user_targets = [max(1, int(req.target_core_users * ratio)) for ratio in [0.1, 0.3, 0.7, 1.0]]

    milestones: List[Milestone] = []
    for idx, stage in enumerate(selected_stages):
        label = f"阶段 {idx + 1}"
        revenue_target = revenue_targets[min(idx, len(revenue_targets) - 1)]
        user_target = user_targets[min(idx, len(user_targets) - 1)]

        metrics = [
            Metric(
                name="月流水",
                target=_fmt_currency(revenue_target),
                why_it_matters="验证商业闭环并确保现金流自驱",
            ),
            Metric(
                name="核心用户",
                target=f"{user_target} 人",
                why_it_matters="让产品/服务迭代基于真实复购用户",
            ),
        ]

        milestones.append(
            Milestone(
                label=label,
                focus=stage["focus"],
                deliverables=stage["deliverables"],
                metrics=metrics,
                guardrails=stage["guardrails"],
            )
        )

    return milestones


def _build_success_snapshot(req: FocusGoalRequest) -> SuccessSnapshot:
    differentiation = req.differentiation or "单一细分深度打磨形成的口碑优势"

    return SuccessSnapshot(
        operating_state=(
            f"在 {req.focus_area} 用 {req.product_or_service} 形成稳定交付流程，"
            f"核心指标可视化，现金流覆盖团队与投入。"
        ),
        team=(
            "精干小队：产品/交付、增长、客服/运营三角闭环，外包或工具化重复劳动。"
        ),
        your_day=(
            "每日 2-3 小时用于高杠杆工作（渠道打磨、关键客户、产品迭代），"
            "剩余时间用于复盘与团队例会。"
        ),
        finances=(
            f"月流水达到 {_fmt_currency(req.target_monthly_revenue)}，"
            f"毛利率健康，手头留有 3 个月运营现金，核心护城河：{differentiation}。"
        ),
        life=(
            "保持每周至少 1 天完整休息；"
            "家庭/健康的固定时间块写入日程，确保长期可持续。"
        ),
    )


def _build_operating_rhythm(req: FocusGoalRequest) -> OperatingRhythm:
    return OperatingRhythm(
        weekly_commitments=[
            "每周一确定唯一北极星指标和配套动作，不做并行主线",
            "至少 2 次用户访谈或交付复盘，输出文档沉淀",
            "跑完一个完整获客-转化-交付的闭环并复盘",
        ],
        daily_rules=[
            "上午处理高价值决策与销售/访谈，下午执行交付与跟进",
            "每日至少 60 分钟深度工作窗口，避免消息打断",
            "功能/需求进入待办前，先明确对应的指标提升假设",
        ],
        review_rituals=[
            "周五 1 小时复盘：指标、学到的模式、下周唯一重点",
            "每月回顾：是否仍然服务同一画像？是否偏离主指标？",
            "季度校准：若核心指标连续 4 周未前进，收敛范围、砍掉分支",
        ],
    )


def _build_first_week_actions(req: FocusGoalRequest) -> List[str]:
    return [
        f"写出 1 页愿景稿：12 个月后在 {req.focus_area} 通过 {req.product_or_service} 服务谁、如何赚钱",
        "整理 15 个目标用户名单，预约 5 个访谈，确保反馈闭环",
        "搭建最小成交路径：话术 + 报价 + 支付链接/合同模板",
        "制定本周唯一指标（如付费验证数量）并在可见处展示",
    ]


def _build_focus_guardrails(req: FocusGoalRequest) -> List[str]:
    guardrails = [
        "任何新增想法先写一页假设，再决定是否验证",
        f"优先满足核心用户的复购与转介绍，不盲目拓展 {req.focus_area} 外的场景",
        "保持现金流安全垫，不以未来假设透支投入",
    ]

    if req.constraints:
        guardrails.append(
            "显式考虑的约束：" + "; ".join(req.constraints)
        )
    if req.personal_priorities:
        guardrails.append(
            "个人优先级（必须被日程保护）：" + "; ".join(req.personal_priorities)
        )

    return guardrails


@router.post("/plugins/focus-goal", response_model=GoalPlanResponse)
async def generate_focus_goal_plan(
    request: FocusGoalRequest, token: str = Depends(authenticate_plugin)
):
    """Generate a laddered goal plan for single-focus execution."""

    goal_statement = (
        f"在 {request.timeframe_months} 个月内，聚焦 {request.focus_area}，"
        f"用 {request.product_or_service} 实现月流水 {_fmt_currency(request.target_monthly_revenue)}，"
        f"赢得 {request.target_core_users} 个核心用户。"
    )

    response = GoalPlanResponse(
        goal_statement=goal_statement,
        numeric_targets=GoalMetrics(
            monthly_revenue=_fmt_currency(request.target_monthly_revenue),
            core_users=f"{request.target_core_users} 人",
            timeframe_months=request.timeframe_months,
        ),
        success_snapshot=_build_success_snapshot(request),
        milestones=_build_milestones(request),
        operating_rhythm=_build_operating_rhythm(request),
        first_week_actions=_build_first_week_actions(request),
        focus_guardrails=_build_focus_guardrails(request),
    )

    return response
