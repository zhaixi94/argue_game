"""
官场党争复仇游戏 — NPC家族AI基础决策类

对应文档: argue_game_AI.md

本模块包含:
  - BaseAIFamily: 基础决策类, 涵盖所有NPC共有的行为与基础决策

依赖: argue_game_AI_types.py (枚举/数据类/配置)
子类: argue_game_AI_subclasses.py (PoliticalAI/EconomicAI/MilitaryAI/NeutralAI)
"""

import math
import random
from typing import Optional
from argue_game_AI_types import (
    Tendency, Personality, FamilyState, Posture, Difficulty,
    BuildingType, IntelType, ShortGoalCategory, AttackMethod,
    BuffType, NegotiateType, MarryType,
    Official, Character, IntelCard, ShortGoal, FamilyProfile, ActionLogEntry,
    DIFFICULTY_CONFIG,
    PERSONALITY_EMBEZZLE_DEFAULT, PERSONALITY_MAINTAIN_DEFAULT,
    PERSONALITY_DONATE_TENDENCY, PERSONALITY_DONATE_TARGET,
)


# ============================================================
# BaseAIFamily — 基础决策类
# ============================================================

class BaseAIFamily:
    """
    NPC家族AI基础决策类

    涵盖所有NPC共有的行为与基础决策(对应AI.md第三章~第二十一章):
      - 家族状态评估(危局/紧张/正常/优势) → 三、3.2节
      - 态势评估(长期目标方向) → 十八、18.2节
      - 短期目标生成与管理 → 十八、18.3/18.4节
      - 资源点分配 → 四、4.1/4.2节
      - 建筑建造/升级/入驻 → 五、5.1~5.3节
      - 角色放置 → 六、6.1/6.2节
      - 联姻决策 → 七、7.1~7.3节
      - 结交决策 → 八、8.1~8.3节
      - 商议决策 → 九、9.1~9.3节
      - 党争决策(攻防/情报/策反/机构) → 十、10.0~10.5节
      - 官职决策(科举/空缺/政绩槽) → 十一、11.1~11.3节
      - 税收贪取与维护 → 十二、12.1~12.4节
      - 党派忠诚与入党 → 十三、13.1~13.2节
      - 大朝会自动结算 → 十四、14节
      - 目标驱动的行动优先级调整 → 十八、18.5节
      - 主动行为 → 十九、19.1~19.6节
      - 党派协调 → 二十、20.1~20.5节
      - NPC间对抗与对玩家感知 → 二十一、21.1~21.4节
    """

    def __init__(self, profile: FamilyProfile, difficulty: Difficulty = Difficulty.NORMAL):
        """
        初始化AI

        Args:
            profile: 家族档案, 包含所有家族属性数据
            difficulty: 难度等级, 影响NPC行为强度和资源加成
        """
        self.p = profile                                    # 家族档案引用
        self.difficulty = difficulty                        # 难度等级
        self.config = DIFFICULTY_CONFIG[difficulty]         # 难度配置参数
        self.current_month: int = 0                         # 当前月份(回合)
        self._resource_points: int = 0                      # 本月可用资源点缓存
        self._current_month_log: Optional[ActionLogEntry] = None  # 本月日志(月末写入FamilyProfile)

    # ----------------------------------------------------------
    # 日志系统: 查询/记录家族历史行动 (每家族一份, 保留12个月)
    # ----------------------------------------------------------

    def query_log(self, months: int = 24) -> list:
        """
        查询过去N个月的行动日志

        玩家可通过家族详情界面的"家族日志"按钮查看此记录

        Args:
            months: 查询月数(默认24, 即过去两年)

        Returns:
            list[ActionLogEntry]: 按月份降序排列的日志列表
        """
        return self.p.action_log[-months:]

    def query_log_field(self, field: str, months: int = 24) -> list:
        """
        查询过去N个月日志中某个字段的值列表

        Args:
            field: ActionLogEntry的字段名(如"embezzle_rate"/"attacks_received"等)
            months: 查询月数

        Returns:
            list: 该字段在过去N个月的值列表(降序, 最新在前)
        """
        return [getattr(entry, field, None) for entry in reversed(self.p.action_log[-months:])]

    def get_quarter_embezzle_total(self) -> float:
        """
        计算过去一个季度(3个月)的累计贪取金额占税收比例

        Returns:
            float: 季度贪取总额/季度税收总额(简化: 用贪取金额占家族收入估算)
        """
        recent = self.p.action_log[-3:]
        if not recent:
            return 0.0
        total_embezzle = sum(e.embezzle_amount for e in recent)
        # 简化: 用贪取金额/基础月税收(50贯)×3月 作为比例
        estimated_quarter_tax = 150.0
        return total_embezzle / estimated_quarter_tax if estimated_quarter_tax > 0 else 0.0

    def get_recent_attack_count(self, months: int = 3) -> int:
        """
        统计过去N个月受到的攻击次数(用于防御决策参考)
        """
        recent = self.p.action_log[-months:]
        return sum(len(e.attacks_received) for e in recent)

    def get_recent_marry_fail_count(self, months: int = 6) -> int:
        """
        统计过去N个月联姻失败次数(避免重复向同一家族联姻)
        """
        recent = self.p.action_log[-months:]
        count = 0
        for e in recent:
            for m in e.marries_attempted:
                if not m.get("success", True):
                    count += 1
        return count

    def _start_month_log(self, month: int):
        """月初: 创建本月日志条目"""
        self._current_month_log = ActionLogEntry(month=month)

    def _finish_month_log(self):
        """月末: 将本月日志写入FamilyProfile, 清理超过12个月的旧日志"""
        if self._current_month_log is not None:
            self.p.action_log.append(self._current_month_log)
            # 保留最近24个月日志
            if len(self.p.action_log) > 24:
                self.p.action_log = self.p.action_log[-24:]
            self._current_month_log = None

    def evaluate_family_state(self) -> FamilyState:
        """
        评估家族当前状态

        判定优先级: 危局 > 紧张 > 优势 > 正常

        危局条件(满足任一):
          - 金钱<50贯: 无法维持基本运营
          - 戒心>=60: 进入"危险"debuff区间, 官员收益-20%
          - 有中枢官员稳固值<30: 随时可能被击倒罢免

        紧张条件(满足任一):
          - 金钱<200贯: 资金紧张
          - 戒心>=30: 进入"警戒"debuff区间, 官员收益-10%
          - 有地方官员政绩槽<60%: 丁等风险

        优势条件(全部满足):
          - 金钱>1000贯 且 声望>5000 且 无官员受威胁(稳固值>=50/政绩槽>=60%)

        正常: 不满足以上条件时
        """
        # 先判定危局(最高优先级)
        if self.p.money < 50 or self.p.suspicion >= 60:
            return FamilyState.CRISIS
        if any(o.is_central and o.stability < 30 for o in self.p.officials):
            return FamilyState.CRISIS

        # 再判定紧张
        if self.p.money < 200 or self.p.suspicion >= 30:
            return FamilyState.TENSE
        if any(not o.is_central and o.performance < 60 for o in self.p.officials):
            return FamilyState.TENSE

        # 再判定优势
        no_threat = all(
            o.stability >= 50 if o.is_central else o.performance >= 60
            for o in self.p.officials
        )
        if self.p.money > 1000 and self.p.fame > 5000 and no_threat:
            return FamilyState.ADVANTAGE

        # 默认正常
        return FamilyState.NORMAL

    # ----------------------------------------------------------
    # 18. 态势评估 (对应十八、18.2节)
    # ----------------------------------------------------------

    def evaluate_posture(self) -> Posture:
        """
        评估长期目标当前态势

        长期目标是不可达成的终极愿景, 只有"态势"没有"达标":
          - 优势: 核心指标稳步增长 且 无重大威胁 → 短期目标侧重扩张与巩固
          - 平稳: 核心指标持平 或 有可控威胁 → 短期目标侧重维持与突破瓶颈
          - 劣势: 核心指标下降 或 有重大威胁 → 短期目标侧重止损与防御

        各倾向核心指标不同, 子类覆写 _posture_metrics()
        """
        metrics = self._posture_metrics()
        growing = metrics["growing"]          # 核心指标是否在增长
        has_major_threat = metrics["major_threat"]  # 是否有重大威胁

        if has_major_threat or not growing:
            return Posture.DISADVANTAGE
        if growing:
            return Posture.ADVANTAGE
        return Posture.STABLE

    def _posture_metrics(self) -> dict:
        """
        基础态势指标(子类覆写提供倾向专用指标)

        基础实现:
          - growing: 简单判定为True(无历史数据时)
          - major_threat: 是否处于危局或紧张状态
          - safe_officials: 稳固值>50(中枢)/政绩槽>60%(地方)的官员数

        Returns:
            dict: {"growing": bool, "major_threat": bool, "safe_officials": int, ...}
        """
        safe_officials = sum(
            1 for o in self.p.officials
            if (o.stability > 50 if o.is_central else o.performance > 60)
        )
        return {
            "growing": True,  # 无历史数据时默认为增长
            "major_threat": self.evaluate_family_state() in (FamilyState.CRISIS, FamilyState.TENSE),
            "safe_officials": safe_officials,
        }

    # ----------------------------------------------------------
    # 18. 短期目标生成 (对应十八、18.3/18.4节)
    # ----------------------------------------------------------

    def generate_short_goals(self) -> list:
        """
        每月月初生成短期目标

        流程:
          1. 检查现有目标完成状态(已完成→移除, 连续3月无进展→替换)
          2. 从长期目标+态势推导必选目标(优先级2)
          3. 从局势推导紧急目标(优先级1)
          4. 补充自由目标至1~3个(优先级3)

        Returns:
            list[ShortGoal]: 本月短期目标列表(1~3个)
        """
        self._refresh_existing_goals()

        goals = []

        # 必选目标: 从长期目标+态势推导
        mandatory = self._derive_mandatory_goal()
        if mandatory:
            mandatory.priority = 2
            goals.append(mandatory)

        # 紧急目标: 从局势推导
        urgent = self._derive_urgent_goal()
        if urgent:
            urgent.priority = 1
            goals.append(urgent)

        # 自由目标: 补充至1~3个
        if len(goals) < 3:
            free = self._derive_free_goal()
            if free:
                free.priority = 3
                goals.append(free)

        self.p.short_goals = goals
        return goals

    def _refresh_existing_goals(self):
        """检查现有短期目标: 已完成→移除; 连续3月无进展→替换"""
        remaining = []
        for g in self.p.short_goals:
            # 已完成的目标移除
            if g.is_completed():
                continue
            # 无进展则累加计数器
            if not g.has_progress():
                g.months_no_progress += 1
            else:
                g.months_no_progress = 0
            # 连续3月无进展则替换
            if g.months_no_progress >= 3:
                continue
            remaining.append(g)
        self.p.short_goals = remaining

    def _derive_mandatory_goal(self) -> Optional[ShortGoal]:
        """
        从长期目标+态势推导必选目标(子类覆写)

        基础逻辑:
          - 劣势/危局/紧张: 保护最危急的官员
          - 家族人数<上限50%: 联姻获取角色卡
        """
        posture = self.evaluate_posture()
        state = self.evaluate_family_state()

        # 劣势或危局/紧张时: 保护最危急官员
        if posture == Posture.DISADVANTAGE or state in (FamilyState.CRISIS, FamilyState.TENSE):
            unsafe = [o for o in self.p.officials
                      if (o.is_central and o.stability < 50) or
                      (not o.is_central and o.performance < 60)]
            if unsafe:
                # 选择最危急的官员(稳固值/政绩槽最低的)
                target = min(unsafe, key=lambda o: o.stability if o.is_central else o.performance)
                return ShortGoal(ShortGoalCategory.OFFICE, f"保护{target.name}", 2)

        # 家族人数不足: 联姻获取角色卡
        if len(self.p.members) < self._member_cap() * 0.5:
            return ShortGoal(ShortGoalCategory.FAMILY, "联姻获取角色卡", 2)

        return None

    def _derive_urgent_goal(self) -> Optional[ShortGoal]:
        """
        从局势推导紧急目标(所有倾向通用)

        紧急条件:
          - 有中枢官员稳固值<30 → "紧急保护该官员"
          - 有地方官政绩槽<60%且距述职<3月 → "该官员述职通过"
          - 戒心>=60 → "降低戒心至30以下"
        """
        for o in self.p.officials:
            # 中枢官员稳固值<30: 随时可能被击倒
            if o.is_central and o.stability < 30:
                return ShortGoal(ShortGoalCategory.OFFICE, f"紧急保护{o.name}", 1)
            # 地方官政绩槽<60%且距述职<3月: 丁等风险(直接罢免)
            if not o.is_central and o.performance < 60 and o.months_to_review < 3:
                return ShortGoal(ShortGoalCategory.OFFICE, f"{o.name}述职通过", 1)

        # 戒心>=60: 进入"危险"区间, 官员收益-20%, 且每月5%~30%概率贬官/罢免
        if self.p.suspicion >= 60:
            return ShortGoal(ShortGoalCategory.RESOURCE, "降低戒心至30以下", 1)

        return None

    def _derive_free_goal(self) -> Optional[ShortGoal]:
        """
        自由目标从目标池按倾向权重选择(子类覆写权重)

        基础目标池: 声望提升/结交目标家族/培养角色能力
        """
        pool = [
            ShortGoal(ShortGoalCategory.RESOURCE, "声望提升", 3),
            ShortGoal(ShortGoalCategory.RELATION, "结交目标家族", 3),
            ShortGoal(ShortGoalCategory.FAMILY, "培养角色能力", 3),
        ]
        return random.choice(pool) if pool else None

    def _member_cap(self) -> int:
        """
        家族人数上限(对应资源系统声望与家族等级)

        初级家族(声望<3000): 10人
        中级家族(声望3000~6999): 20人
        顶级家族(声望>=7000): 30人
        """
        if self.p.fame >= 7000:
            return 30
        if self.p.fame >= 3000:
            return 20
        return 10

    # ----------------------------------------------------------
    # 4. 资源点分配 (对应四、4.1/4.2节)
    # ----------------------------------------------------------

    def calc_resource_points(self) -> int:
        """
        计算本月可用资源点

        公式: 基础3点 + 声望加成(每1000声望+1点)
        上限: 10点/月
        未用完的资源点不跨月累积
        """
        base = 3
        fame_bonus = min(7, self.p.fame // 1000)  # 声望7000即满额+7
        return min(10, base + fame_bonus)

    def allocate_resource_points(self) -> dict:
        """
        按优先级分配资源点

        优先级:
          1. 官职防御预设(中枢官员每人1~3点)
          2. 政绩槽加成(地方官每人1~3点)
          3~5. 建筑投入(按倾向偏好分配)
          6. 党争行动(优势状态时1~3点)
          月末: 剩余投入产出最高建筑

        Returns:
            dict: {用途: 点数}, 如 {"防御_太师": 2, "政绩_知县": 1, "声望建筑": 2}
        """
        total = self.calc_resource_points()
        allocated = {}
        remaining = total

        # 优先级1: 官职防御预设(中枢官员)
        central_officials = [o for o in self.p.officials if o.is_central]
        for o in central_officials:
            if remaining <= 0:
                break
            pts = self._defense_rp_alloc(o)
            allocated[f"防御_{o.name}"] = min(pts, remaining)
            remaining -= allocated[f"防御_{o.name}"]

        # 优先级2: 政绩槽加成(地方官员)
        local_officials = [o for o in self.p.officials if not o.is_central]
        for o in local_officials:
            if remaining <= 0 or o.performance >= 100:
                continue
            pts = self._performance_rp_alloc(o)
            allocated[f"政绩_{o.name}"] = min(pts, remaining)
            remaining -= allocated[f"政绩_{o.name}"]

        # 优先级3~5: 建筑投入(按倾向偏好)
        building_alloc = self._building_rp_alloc(remaining)
        allocated.update(building_alloc)
        remaining -= sum(building_alloc.values())

        # 优先级6: 党争行动(仅优势状态)
        state = self.evaluate_family_state()
        if state == FamilyState.ADVANTAGE and remaining > 0:
            party_pts = min(remaining, 3)
            allocated["党争行动"] = party_pts
            remaining -= party_pts

        # 月末: 剩余投入产出最高建筑
        if remaining > 0:
            allocated["溢出投入"] = remaining

        return allocated

    def _defense_rp_alloc(self, official: Official) -> int:
        """
        中枢官员防御预设资源点分配 (对应十、10.2节)

        稳固值>=80: 0~1点(安全, 无需重防)
        稳固值50~79: 1~2点(正常防御)
        稳固值30~49: 2~3点(加强防御)
        稳固值<30: 3点(全力防御)

        戒心>=60时额外+1点(受伤系数高, 更重视防御)
        上限3点/官员
        """
        if official.stability >= 80:
            pts = random.randint(0, 1)
        elif official.stability >= 50:
            pts = random.randint(1, 2)
        elif official.stability >= 30:
            pts = random.randint(2, 3)
        else:
            pts = 3

        # 家族戒心>=60: 受伤系数高(×1.2或×2.0), 需额外防御
        if self.p.suspicion >= 60:
            pts += 1

        return min(pts, 3)

    def _defense_favor_alloc(self, official: Official) -> int:
        """
        中枢官员防御预设圣眷分配 (对应十、10.2节)

        稳固值>=80: 0点(安全)
        稳固值50~79: 5~10点(正常)
        稳固值30~49: 10~20点(加强)
        稳固值<30: 20~30点(全力)

        圣眷稀缺, 仅在稳固值低时投入
        """
        if official.stability >= 80:
            return 0
        elif official.stability >= 50:
            return random.randint(5, 10)
        elif official.stability >= 30:
            return random.randint(10, 20)
        else:
            return random.randint(20, 30)

    def _performance_rp_alloc(self, official: Official) -> int:
        """
        地方官政绩槽资源点分配 (对应十一、11.3节)

        政绩槽<60%(丁等风险): 3点(全力)
        政绩槽60~79%(丙等): 2点
        政绩槽80~99%(乙等): 1点
        政绩槽>=100%(甲等): 0点(无需投入)

        距述职<3月且<80%: 额外+2点(紧急冲刺)
        上限3点/官员
        """
        pct = official.performance
        if pct < 60:
            pts = 3
        elif pct < 80:
            pts = 2
        elif pct < 100:
            pts = 1
        else:
            return 0

        # 距述职<3月且<80%: 紧急冲刺
        if official.months_to_review < 3 and pct < 80:
            pts += 2

        return min(pts, 3)

    def _performance_favor_alloc(self, official: Official) -> int:
        """
        地方官政绩槽圣眷分配 (对应十一、11.3节)

        政绩槽<60%: 3~5点(丁等风险, 需圣眷加成)
        政绩槽60~79%: 1~2点
        政绩槽>=80%: 0点
        """
        pct = official.performance
        if pct < 60:
            return random.randint(3, 5)
        elif pct < 80:
            return random.randint(1, 2)
        return 0

    def _building_rp_alloc(self, remaining: int) -> dict:
        """
        建筑投入资源点分配 (对应四、4.2节)

        按倾向偏好分配: 金钱/声望/圣眷/成长建筑各投入若干点
        剩余不足时按比例缩减
        """
        result = {}
        if remaining <= 0:
            return result

        # 获取倾向偏好 (金钱, 声望, 圣眷, 成长)
        money_pts, fame_pts, favor_pts, growth_pts = self._building_rp_preference()
        total_needed = money_pts + fame_pts + favor_pts + growth_pts
        if total_needed == 0:
            return result

        # 按比例分配, 不足时缩减
        ratio = min(1.0, remaining / total_needed) if total_needed > 0 else 0

        if money_pts > 0:
            result["金钱建筑"] = max(1, int(money_pts * ratio))
        if fame_pts > 0:
            result["声望建筑"] = max(1, int(fame_pts * ratio))
        if favor_pts > 0:
            result["圣眷建筑"] = max(1, int(favor_pts * ratio))
        if growth_pts > 0:
            result["成长建筑"] = max(1, int(growth_pts * ratio))

        # 超出剩余时逐个缩减
        actual = sum(result.values())
        if actual > remaining:
            keys = list(result.keys())
            while actual > remaining and keys:
                k = keys.pop(0)
                if result[k] > 1:
                    result[k] -= 1
                    actual -= 1

        return result

    def _building_rp_preference(self) -> tuple:
        """
        建筑投入倾向偏好 (对应四、4.2节)

        Returns:
            tuple: (金钱建筑点数, 声望建筑点数, 圣眷建筑点数, 成长建筑点数)
        """
        return (1, 2, 1, 1)

    # ----------------------------------------------------------
    # 5. 建筑决策 (对应五、5.1~5.3节)
    # ----------------------------------------------------------

    def should_build(self) -> bool:
        """
        是否触发建造 (对应五、5.1节)

        条件: 建筑数未达空地上限 且 金钱>建造费用×2(留有余量)
        """
        max_buildings = self._max_building_slots()
        current = len(self.p.buildings)
        return current < max_buildings and self.p.money > self._build_cost() * 2

    def choose_building_to_build(self) -> Optional[str]:
        """
        选择建造哪栋建筑

        按倾向优先级列表选择, 已建则跳过取下一栋
        """
        priorities = self._building_priority()
        existing = set(self.p.buildings)
        for b in priorities:
            if b not in existing:
                return b
        return None

    def _building_priority(self) -> list:
        """建造优先级列表(子类覆写)"""
        return ["私塾", "书院", "祠堂", "演武场", "论辩台"]

    def _max_building_slots(self) -> int:
        """建筑空地上限(简化为9)"""
        return 9

    def _build_cost(self) -> int:
        """建造费用(简化为100贯)"""
        return 100

    def should_upgrade(self, building_name: str) -> bool:
        """
        是否升级建筑 (对应五、5.2节)

        条件: 金钱>升级费用×1.5 且 声望>50×1.2
        """
        cost = self._upgrade_cost(building_name)
        return self.p.money > cost * 1.5 and self.p.fame > 50 * 1.2

    def _upgrade_cost(self, building_name: str) -> int:
        """升级费用(简化为150贯)"""
        return 150

    def choose_city_building_type(self) -> BuildingType:
        """
        城市建筑入驻类型选择 (对应五、5.3节)

        按倾向权重随机选择建筑类型
        """
        weights = self._city_building_weights()
        types = list(weights.keys())
        probs = list(weights.values())
        return random.choices(types, weights=probs, k=1)[0]

    def _city_building_weights(self) -> dict:
        """
        城市建筑入驻类型权重(子类覆写)

        默认: 金钱30%, 声望35%, 成长35%
        """
        return {
            BuildingType.MONEY: 0.3,
            BuildingType.FAME: 0.35,
            BuildingType.GROWTH: 0.35,
        }

    def choose_character_for_building(self, building_type: BuildingType) -> Optional[Character]:
        """
        选择入驻角色 (对应五、5.3节)

        逻辑: 该建筑对应能力最高的空闲成年角色
        金钱类→商业, 声望类→口才, 成长类→学识
        """
        idle = [c for c in self.p.members if c.is_idle and not c.is_official and c.age >= 15]
        if not idle:
            return None

        # 建筑类型→能力映射
        ability_key = {
            BuildingType.MONEY: "commerce",     # 金钱类建筑看商业
            BuildingType.FAME: "eloquence",     # 声望类建筑看口才
            BuildingType.GROWTH: "knowledge",   # 成长类建筑看学识
        }.get(building_type, "knowledge")

        return max(idle, key=lambda c: getattr(c, ability_key))

    def should_withdraw_from_city(self, slot) -> bool:
        """
        是否撤出城市建筑 (对应五、5.3节)

        条件: 金钱不足以支付入驻消耗
        """
        if self.p.money < 20:
            return True
        return False

    # ----------------------------------------------------------
    # 6. 角色放置 (对应六、6.1/6.2节)
    # ----------------------------------------------------------

    def place_characters(self) -> dict:
        """
        角色放置决策

        优先级:
          1. 担任官职的角色 → 不在建筑中(官职优先)
          2. 高能力成年角色(>=18岁) → 按能力匹配最高产出的建筑
          3. 低能力/年轻角色(<18岁) → 成长类建筑
          4. 无合适建筑的空闲角色 → 留空

        Returns:
            dict: {角色名: 建筑名}
        """
        placements = {}
        officials_names = {o.name for o in self.p.officials}
        available = [c for c in self.p.members
                     if c.name not in officials_names and c.age >= 15 and c.is_idle]

        adults_high = [c for c in available if c.age >= 18]   # 成年高能力
        youths = [c for c in available if c.age < 18]          # 年轻成长

        for c in adults_high:
            building = self._match_character_to_building(c)
            if building:
                placements[c.name] = building
                c.is_idle = False

        for c in youths:
            building = self._match_youth_to_building(c)
            if building:
                placements[c.name] = building
                c.is_idle = False

        return placements

    def _match_character_to_building(self, char: Character) -> Optional[str]:
        """
        高能力成年角色匹配最高产出建筑 (对应六、6.2节)

        逻辑:
          - 取角色最高能力对应的建筑(学识→书院, 商业→商号, 口才→论辩台, 军事→演武场)
          - 样貌最高时按次高能力匹配(样貌无专属建筑)
          - 首选建筑无空槽时按次高能力匹配
        """
        abilities = {
            "knowledge": char.knowledge,
            "military": char.military,
            "commerce": char.commerce,
            "eloquence": char.eloquence,
        }
        # 样貌最高时按次高能力匹配(样貌无专属建筑, 为联姻储备)
        best = max(abilities, key=lambda k: abilities[k] or 0)

        # 能力→建筑映射
        mapping = {
            "knowledge": ["书院", "官学"],
            "commerce": ["商号", "商铺", "钱庄", "漕运司"],
            "eloquence": ["论辩台", "名士馆", "诗社", "御前馆"],
            "military": ["演武场", "武馆"],
        }

        # 首选: 最高能力对应建筑
        for b in mapping.get(best, []):
            if b in self.p.buildings and self._building_has_slot(b):
                return b

        # 次选: 按能力降序匹配其他建筑
        for key in sorted(abilities, key=lambda k: abilities[k] or 0, reverse=True):
            if key == best:
                continue
            for b in mapping.get(key, []):
                if b in self.p.buildings and self._building_has_slot(b):
                    return b

        return None

    def _match_youth_to_building(self, char: Character) -> Optional[str]:
        """年轻角色匹配成长类建筑(私塾/演武场/陶朱院/论辩台)"""
        growth_buildings = ["私塾", "演武场", "陶朱院", "论辩台"]
        for b in growth_buildings:
            if b in self.p.buildings and self._building_has_slot(b):
                return b
        return None

    def _building_has_slot(self, building_name: str) -> bool:
        """建筑是否有空槽位(简化为True, 实际需查建筑槽位数)"""
        return True

    # ----------------------------------------------------------
    # 7. 联姻决策 (对应七、7.1~7.3节)
    # ----------------------------------------------------------

    def can_marry(self) -> bool:
        """
        是否满足发起联姻条件 (对应七、7.1节)

        条件:
          - 非危局状态(危局时暂停联姻)
          - 金钱>=50贯(最低联姻投入门槛)
          - 联姻冷却为0(失败后5回合冷却)
          - 有适龄未婚角色(男>=15岁, 女>=16岁, 且非官员)
        """
        if self.evaluate_family_state() == FamilyState.CRISIS:
            return False
        if self.p.money < 50:
            return False
        if self.p.marry_cooldown > 0:
            return False
        has_eligible = any(
            (c.gender == "M" and c.age >= 15 or c.gender == "F" and c.age >= 16)
            for c in self.p.members
        )
        return has_eligible

    def score_marry_target(self, target: FamilyProfile) -> float:
        """
        联姻目标评分 (对应七、7.2节)

        公式: 评分 = 关系加成 + 声望加成 + 党派加成 + 战略加成

        关系加成 = 与目标家族关系值 × 0.5 (上限30分)
        声望加成 = min(30, 目标家族声望 / 200) (倾向高声望家族)
        党派加成 = 同党+20 / 无党派+10 / 敌对-20
        战略加成 = 有官职+15 / 有中枢官职+30
        """
        relation = self.p.relations.get(target.name, 0)
        relation_score = min(30, relation * 0.5)   # 关系加成, 上限30

        fame_score = min(30, target.fame / 200)     # 声望加成, 上限30

        # 党派加成: 同党+20, 无党派+10, 敌对-20
        if self.p.party and target.party:
            if self.p.party == target.party:
                party_score = 20
            else:
                party_score = -20
        elif not target.party:
            party_score = 10  # 无党派家族可拉拢
        else:
            party_score = 0

        # 战略加成: 有官职+15, 有中枢官职+30
        strategy_score = 0
        if target.officials:
            strategy_score += 15
        if any(o.is_central for o in target.officials):
            strategy_score += 15

        total = relation_score + fame_score + party_score + strategy_score
        # 子类可调整评分(如政治型+50%党派加成, 经济型+50%声望加成)
        total = self._adjust_marry_score(total, relation_score, fame_score, party_score, strategy_score)
        return total

    def _adjust_marry_score(self, total, relation, fame, party, strategy) -> float:
        """子类覆写: 倾向对联姻评分的调整"""
        return total

    def decide_marry_invest(self, target: FamilyProfile) -> dict:
        """
        联姻投入决策 (对应七、7.3节)

        正常: 资源点min(3, 可用), 声望min(200, 可用×30%), 金钱min(500, 可用×40%)
        危局: 资源点1, 金钱100贯
        目标声望远高于己方(>1.5倍): 投入增加50%
        """
        state = self.evaluate_family_state()
        if state == FamilyState.CRISIS:
            return {"resource_points": 1, "fame": 0, "money": 100}

        rp = min(3, self.calc_resource_points())          # 资源点: 通常全力投入
        fame = min(200, int(self.p.fame * 0.3))          # 声望: 保留70%
        money = min(500, int(self.p.money * 0.4))         # 金钱: 保留60%

        # 目标声望远高于己方: 投入增加50%
        if target.fame > self.p.fame * 1.5:
            money = int(money * 1.5)
            fame = int(fame * 1.5)

        return {"resource_points": rp, "fame": fame, "money": money}

    def choose_marry_type(self, target: FamilyProfile) -> MarryType:
        """
        联姻类型选择 (对应主文档家族系统→联姻类型)

        四种类型:
          婚娶: 娶对方女性入本族(修正值1.4, 阻力大但获取角色卡)
          招婿: 招对方男性入本族(修正值1.4, 阻力大但获取角色卡)
          婚嫁: 本族女性嫁出(修正值0.8, 阻力小但失去角色卡)
          入赘: 本族男性入赘(修正值0.8, 阻力小但失去角色卡)

        决策逻辑:
          1. 优先选择能获取对方角色卡的类型(婚娶/招婿), 即使修正值高
          2. 家族人数不足时更倾向获取角色卡
          3. 金钱紧张时倾向婚嫁/入赘(成功率高, 资源消耗少)

        Args:
            target: 联姻目标家族

        Returns:
            MarryType: 联姻类型
        """
        # 检查双方适龄角色性别
        my_females = [c for c in self.p.members if c.gender == "F"
                      and c.age >= 16 and not c.took_exam]
        my_males = [c for c in self.p.members if c.gender == "M"
                    and c.age >= 15 and not c.took_exam]
        target_females = [c for c in target.members if c.gender == "F"
                          and c.age >= 16 and not c.took_exam]
        target_males = [c for c in target.members if c.gender == "M"
                        and c.age >= 15 and not c.took_exam]

        # 家族人数不足: 优先获取对方角色卡
        need_members = len(self.p.members) < self._member_cap() * 0.5

        if need_members or self.p.money > 300:
            # 优先获取对方角色卡
            if target_females and my_males:
                return MarryType.MARRY      # 娶对方女性
            if target_males and my_females:
                return MarryType.WOO        # 招对方男性

        # 金钱紧张或无法获取对方角色卡: 嫁出(成功率高)
        if my_females and target_males:
            return MarryType.WED_OUT        # 本族女性嫁出
        if my_males and target_females:
            return MarryType.JOIN           # 本族男性入赘

        # 兜底: 有适龄角色就选一种
        if target_females and my_males:
            return MarryType.MARRY
        if target_males and my_females:
            return MarryType.WOO

        return MarryType.MARRY  # 默认

    def can_befriend(self) -> bool:
        """
        是否满足发起结交条件 (对应八、8.1节)

        条件:
          - 非危局状态
          - 金钱>=20贯(最低结交门槛)
          - 结交冷却为0
          - 有空闲成年角色可派出
        """
        if self.evaluate_family_state() == FamilyState.CRISIS:
            return False
        if self.p.money < 20:
            return False
        if self.p.befriend_cooldown > 0:
            return False
        has_idle = any(c.is_idle and not c.is_official and c.age >= 15 for c in self.p.members)
        return has_idle

    def choose_befriend_target(self, all_families: list) -> Optional[FamilyProfile]:
        """
        结交目标选择 (对应八、8.2节)

        优先级:
          1. 同党派中关系<30的族长 → 防止忠诚度过低
          2. 无党派家族族长 → 拉拢入党派
          3. 敌对党派中关系>20的官员所属家族 → 策反前铺垫
          4. 城市建筑槽位被占家族 → 为商议铺路

        跳过关系>=80的家族(已很高, 不浪费资源)
        """
        candidates = []

        for f in all_families:
            if f.name == self.p.name:
                continue
            relation = self.p.relations.get(f.name, 0)
            if relation >= 80:  # 已很高则不浪费资源
                continue

            if self.p.party and f.party == self.p.party and relation < 30:
                candidates.append((1, f, relation))   # 同党低关系
            elif not f.party:
                candidates.append((2, f, relation))   # 无党派可拉拢
            elif self.p.party and f.party != self.p.party and relation > 20:
                candidates.append((3, f, relation))   # 敌对可策反

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0])  # 按优先级排序
        return candidates[0][1]

    def choose_befriend_emissary(self) -> Optional[Character]:
        """
        派出角色选择 (对应八、8.2节)

        逻辑: 家族中口才最高的空闲角色(口才直接影响结交效率)
        """
        idle = [c for c in self.p.members if c.is_idle and not c.is_official and c.age >= 15]
        if not idle:
            return None
        return max(idle, key=lambda c: c.eloquence)

    def befriend_interval(self) -> int:
        """
        结交间隔(回合数) (对应八、8.3节)

        基础: 每2回合最多1次
        政治型: 每1回合可1次(覆写)
        """
        return 2

    # ----------------------------------------------------------
    # 9. 商议决策 (对应九、9.1~9.3节)
    # ----------------------------------------------------------

    def can_negotiate(self) -> bool:
        """
        是否满足发起商议条件 (对应九、9.1节)

        条件:
          - 金钱>=100贯(商议最低投入)
          - 距上次商议>=12个月(每年最多1次)
        """
        if self.p.money < 100:
            return False
        if self.current_month - self.p.last_negotiate_month < 12:
            return False
        return True

    def choose_negotiate_type(self, target_relation: int, building_type: str) -> NegotiateType:
        """
        商议类型选择 (对应九、9.2节)

        成长类建筑(官学/武馆/茶楼)只能出让
        关系>=50: 分成(短期使用, 低成本)
        关系>=40且金钱>500贯: 出让(长期需要, 高成本)
        关系>=30: 转租(中期使用, 中成本)
        关系<30: 出让(关系差只能买断)
        """
        if building_type in ("官学", "武馆", "茶楼"):
            return NegotiateType.TRANSFER  # 成长类建筑只能出让

        if target_relation >= 50:
            return NegotiateType.SHARE       # 分成: 关系好, 低成本共享
        elif target_relation >= 40 and self.p.money > 500:
            return NegotiateType.TRANSFER    # 出让: 关系还行, 有钱买断
        elif target_relation >= 30:
            return NegotiateType.SUBLEASE    # 转租: 关系一般, 租用3年
        else:
            return NegotiateType.TRANSFER    # 关系差只能买断

    # ----------------------------------------------------------
    # 10. 党争决策 (对应十、10.0~10.5节)
    # ----------------------------------------------------------

    def choose_attack_target(self, enemy_officials: list) -> Optional[Official]:
        """
        攻击目标选择 (对应十、10.1节)

        优先级:
          1. 威胁己方官员的敌方官员(己方稳固值<50时优先反击)
          2. 敌方中枢最低稳固值官员(最容易击倒)
          3. 敌方中枢最高品级官员(打击敌方核心)
          4. 击倒后有升迁机会的目标

        每个NPC家族每回合最多发起1次稳固值攻击
        """
        if not enemy_officials:
            return None

        # 己方有中枢官员受威胁时, 优先反击攻击方
        my_central = [o for o in self.p.officials if o.is_central]
        my_threatened = [o for o in my_central if o.stability < 50]

        if my_threatened:
            recent_attackers = self._find_recent_attackers(my_threatened, enemy_officials)
            if recent_attackers:
                # 反击: 攻击敌方最薄弱的官员
                return min(recent_attackers, key=lambda o: o.stability)

        # 无己方威胁: 攻击敌方最低稳固值官员
        central_enemies = [o for o in enemy_officials if o.is_central]
        if central_enemies:
            return min(central_enemies, key=lambda o: o.stability)

        return None

    def _find_recent_attackers(self, my_officials, enemy_officials) -> list:
        """查找最近攻击己方官员的敌方官员(简化实现: 返回敌方中枢官员)"""
        return [o for o in enemy_officials if o.is_central]

    def choose_attack_method(self, target: Official,
                             target_family_suspicion: int = 0) -> AttackMethod:
        """
        攻击方式选择 (对应十、10.1节)

        优先级:
          有检举情报且目标稳固值<50 → 检举(必中收割)
          有离间情报且目标圣眷>30 → 离间(削圣眷涨戒心)
          有弹劾情报且目标戒心>=60 → 弹劾(高戒心时更容易贬官)
          目标稳固值<20 → 攒情报等检举/弹劾(不浪费攻讦)
          无情报 → 攻讦(高频磨血)
        """
        has_report = any(c.intel_type == IntelType.REPORT for c in self.p.intel_cards)
        has_alienate = any(c.intel_type == IntelType.ALIENATE for c in self.p.intel_cards)
        has_impeach = any(c.intel_type == IntelType.IMPEACH for c in self.p.intel_cards)

        # 稳固值<20: 攒情报等收割, 不浪费攻讦
        if target.stability < 20:
            if has_report:
                return AttackMethod.REPORT
            if has_impeach:
                return AttackMethod.IMPEACH
            return AttackMethod.REPORT  # 无情报也等

        # 有检举情报且稳固值<50: 必中收割
        if has_report and target.stability < 50:
            return AttackMethod.REPORT
        # 有离间情报且圣眷>30: 削圣眷涨戒心
        if has_alienate and target.favor > 30:
            return AttackMethod.ALIENATE
        # 有弹劾情报且目标家族戒心>=60: 高戒心时弹劾更容易贬官
        if has_impeach and target_family_suspicion >= 60:
            return AttackMethod.IMPEACH

        # 无情报: 攻讦(高频磨血)
        return AttackMethod.ACCUSE

    def decide_defense_preset(self, official: Official) -> dict:
        """
        防御预设决策 (对应十、10.2节)

        Returns:
            dict: {"resource_points": 投入资源点数, "favor": 投入圣眷数}
        """
        rp = self._defense_rp_alloc(official)
        favor = self._defense_favor_alloc(official)
        return {"resource_points": rp, "favor": favor}

    def choose_intel_to_claim(self, available_intel: list, party_contribution: int) -> Optional[IntelCard]:
        """
        情报领取优先级 (对应十、10.3节)

        弹劾(30贡献) > 检举(5/15/30贡献) > 离间(5/15/30贡献)
        情报卡持有达上限时不再领取
        贡献不足时保留贡献用于兑换资源
        """
        priority = [IntelType.IMPEACH, IntelType.REPORT, IntelType.ALIENATE]
        cost = {1: 5, 2: 15, 3: 30}  # 按情报等级的党派贡献消耗

        for itype in priority:
            matching = [c for c in available_intel if c.intel_type == itype]
            for card in matching:
                if party_contribution >= cost.get(card.level, 30):
                    return card
        return None

    def can_subvert(self) -> bool:
        """
        是否发起拉拢策反 (对应十、10.4节)

        条件: 非危局 且 金钱>=200贯
        """
        if self.evaluate_family_state() == FamilyState.CRISIS:
            return False
        return self.p.money >= 200

    def decide_subvert_invest(self, target_loyalty: int) -> dict:
        """
        策反投入 (对应十、10.4节)

        资源点1~2点 + 金钱200~500贯
        忠诚越低投入越少(易策反)
        """
        rp = random.randint(1, 2)
        money = random.randint(200, 500)
        if target_loyalty < 15:
            money = 200   # 忠诚极低, 最少投入即可
        elif target_loyalty < 25:
            money = 300
        return {"resource_points": rp, "money": money}

    def choose_subvert_target(self, enemy_families: list) -> Optional[FamilyProfile]:
        """
        策反目标选择 (对应十、10.4节)

        选择逻辑: 敌方忠诚最低的家族优先
          - 筛选敌方党派家族中忠诚<30的(可被策反)
          - 忠诚越低越容易策反, 优先选择忠诚最低的
          - 无可策反目标时返回None

        Args:
            enemy_families: 敌对党派家族列表

        Returns:
            Optional[FamilyProfile]: 最佳策反目标 或 None
        """
        subvertable = [f for f in enemy_families
                       if f.party_loyalty < 30 and f.party is not None
                       and f.party != self.p.party]
        if not subvertable:
            return None
        # 忠诚最低的优先
        return min(subvertable, key=lambda f: f.party_loyalty)
        """
        谍报机构投入 (对应十、10.5节)

        有攻击目标: 3点(全力产出情报)
        无攻击目标: 1点(维持基础产出)
        """
        if has_attack_target:
            return 3
        return 1

    def choose_buff(self, needs: list) -> Optional[BuffType]:
        """
        舆论buff选择 (对应十、10.5节)

        根据当前需求匹配:
          己方被围攻 → 清名(防御+10%)
          准备集中攻击 → 流言(攻讦+10%)
          需要圣眷 → 颂德(圣眷+10%)
          敌方戒心高 → 疑云(额外戒心+2)
          准备大朝会 → 风骨(连线血量+50)
          敌方有家族动摇 → 倾轧(忠诚-3)
        """
        buff_map = {
            "defend": BuffType.QINGMING,
            "attack": BuffType.LIUYAN,
            "favor": BuffType.SONGDE,
            "suspicion": BuffType.YIYUN,
            "grand_court": BuffType.FENGU,
            "loyalty": BuffType.QINGYA,
        }
        for need in needs:
            if need in buff_map:
                return buff_map[need]
        return None

    # ----------------------------------------------------------
    # 11. 官职决策 (对应十一、11.1~11.3节)
    # ----------------------------------------------------------

    def should_take_exam(self, char: Character) -> bool:
        """
        科举报名决策 (对应十一、11.1节)

        基础: 学识>=50报名, <50不报名(浪费报名费)
        子类覆写门槛差异:
          - 政治型: 学识>=45即报名(更重视科举)
          - 军事型: 学识>=55才报名(不浪费资源)

        一生最多3次(主角1次), 已参加过不再报名
        """
        if char.took_exam or char.exam_count >= 3:
            return False
        if char.age < 15:
            return False
        return char.knowledge >= 50

    def decide_vacancy_bid(self, vacancy_rank: int, is_central: bool) -> dict:
        """
        空缺填补投入决策 (对应十一、11.2节)

        地方官: 基础5点 × (1 + 竞争者数 × 0.5)
        中枢暗标: 资源点×10 + 圣眷×1 + 声望×0.5
        危局时不参与中枢暗标(资源留给防御)
        """
        if is_central:
            # 中枢暗标
            if self.evaluate_family_state() == FamilyState.CRISIS:
                return {"resource_points": 0, "favor": 0, "fame": 0}
            rp = min(self.calc_resource_points(), 5)
            favor = min(int(self.p.favor * 0.4), 30)  # 圣眷投入40%比例
            fame = min(int(self.p.fame * 0.2), 500)    # 声望投入20%比例
            return {"resource_points": rp, "favor": favor, "fame": fame}
        else:
            # 地方官: 基础5点 × 竞争系数
            competitors = 1  # 简化, 实际应查竞争者数
            rp = int(5 * (1 + competitors * 0.5))
            return {"resource_points": rp}

    # ----------------------------------------------------------
    # 12. 税收贪取与维护 (对应十二、12.1~12.4节)
    # ----------------------------------------------------------

    def calc_embezzle_rate(self, enemy_intel_level: int = 0) -> float:
        """
        贪取比例计算 (对应十二、12.1节)

        默认值由性格决定:
          稳健3%, 清高1%, 冒险8%, 精明5%, 灵活4%, 保守1%, 强势5%, 刚猛5%

        动态调整:
          - 对立党派谍报>=2级: -3%(被抓风险高)
          - 家族金钱<100贯: +3%(急需用钱)
          - 强势/刚猛: 不因戒心降低贪取
          - 稳健: 戒心>=40时降至1%
          - 冒险: 戒心>=60时降至5%
          - 精明: 有截留情报产出时降至2%

        范围: 0%~10%
        """
        rate = PERSONALITY_EMBEZZLE_DEFAULT.get(self.p.personality, 0.03)

        # 对立党派谍报等级>=2: 被抓风险高, 降低贪取
        if enemy_intel_level >= 2:
            rate -= 0.03
        # 金钱紧缺: 急需用钱, 提高贪取
        if self.p.money < 100:
            rate += 0.03

        # 性格特殊调整
        if self.p.personality in (Personality.DOMINEERING, Personality.FIERCE):
            pass  # 强势/刚猛: 不因戒心降低
        elif self.p.suspicion >= 40 and self.p.personality == Personality.STEADY:
            rate = min(rate, 0.01)  # 稳健: 戒心>=40降至1%
        elif self.p.suspicion >= 60 and self.p.personality == Personality.RISKY:
            rate = min(rate, 0.05)  # 冒险: 戒心>=60降至5%

        # 精明: 过去一个季度(3个月)已贪取超过10%时降至2%(贪取越多截留风险越大, 精明性格见风险就收)
        if self.p.personality == Personality.SHREWD and self.get_quarter_embezzle_total() > 0.10:
            rate = 0.02

        # 难度修正
        rate += self.config["embezzle_modifier"]
        return max(0.0, min(0.10, rate))

    def calc_maintenance_rate(self, level: str, treasury_balance: float,
                              monthly_tax: float, same_party_count: int,
                              own_performance: float, co_officials_relations: dict) -> float:
        """
        维护比例计算 (对应十二、12.2/12.3节)

        Args:
            level: "county"(县级) 或 "circuit"(路级)
            treasury_balance: 金库余额
            monthly_tax: 月度税收(县/路)
            same_party_count: 同党派共事官员数
            own_performance: 自身政绩槽百分比
            co_officials_relations: {共事官员家族名: 关系值}

        默认值由性格决定, 动态调整:
          - 金库<月度税收×2: -2%(节约开支)
          - 金库为负: 0%(无法维护)
          - 同党>=2人: +2%(配合党派利益)
          - 自身政绩槽<60%: +2%(急需补政绩)
          - 关系>60的共事官员: +1%(维护关系)
          - 关系<-20的共事官员: -2%(不在乎或刻意打击)
          - 精明性格: 金库充裕时拉满(10%), 紧张时降低(5%)

        范围: 0%~10%
        """
        rate = PERSONALITY_MAINTAIN_DEFAULT.get(self.p.personality, 0.05)

        # 金库紧张: 节约开支
        if treasury_balance < monthly_tax * 2:
            rate -= 0.02
        # 金库为负: 无法维护
        if treasury_balance < 0:
            return 0.0

        # 同党派配合
        if same_party_count >= 2:
            rate += 0.02

        # 自身政绩槽低: 急需补政绩
        if own_performance < 60:
            rate += 0.02

        # 关系影响: 增益+1%/月每1%, 惩罚-2%/月每1%
        for fam, rel in co_officials_relations.items():
            if rel > 60:
                rate += 0.01   # 关系好: 倾向拉高维护
            elif rel < -20:
                rate -= 0.02   # 关系差: 倾向降低维护

        # 精明性格: 动态调整
        if self.p.personality == Personality.SHREWD:
            if treasury_balance > monthly_tax * 6:
                rate = max(rate, 0.10)   # 金库充裕: 拉满维护
            elif treasury_balance < monthly_tax * 3:
                rate = min(rate, 0.05)    # 金库紧张: 降低维护

        # 灵活性格: 跟随同县/同路多数派设定(不标新立异)
        if self.p.personality == Personality.FLEXIBLE and co_officials_relations:
            avg_others = 0.0
            count = 0
            for fam, rel in co_officials_relations.items():
                # 简化: 用关系值推算共事官员的大致维护倾向
                # 关系好→倾向高维护, 关系差→倾向低维护
                avg_others += 0.05 if rel > 0 else 0.03
                count += 1
            if count > 0:
                avg_others /= count
                # 将自身维护比例向多数派平均值靠拢(移动30%距离)
                rate = rate + (avg_others - rate) * 0.3

        return max(0.0, min(0.10, rate))

    def choose_maintenance_strategy(self, level: str, co_officials: list,
                                    own_performance: float) -> Optional[str]:
        """
        进阶维护策略选择 (对应十二、12.2/12.3节进阶策略)

        策略:
          焦土: 同县全为敌对 → 0%维护+大量贪取, 让政敌什么都得不到
          断粮: 有敌对高政绩官员 → 0%维护, 断其加成, 迫使政绩放缓
          捧杀: 全为同党 → 10%维护, 帮同党快速升迁
          精准投喂: 有中立/可拉拢家族 → 8%~10%维护, 给中立派甜头

        Returns:
            Optional[str]: 策略名或None(无特殊策略)
        """
        enemy_same_level = [o for o in co_officials if o.get("party") != self.p.party]
        ally_same_level = [o for o in co_officials if o.get("party") == self.p.party]
        neutral_same_level = [o for o in co_officials if o.get("party") is None]

        # 焦土: 同县全为敌对, 自身被孤立
        if len(enemy_same_level) == len(co_officials) and level == "county":
            return "焦土"

        # 断粮: 有敌对高政绩官员, 断其加成
        if enemy_same_level:
            enemy_high_perf = any(o.get("performance", 0) > 80 for o in enemy_same_level)
            if enemy_high_perf:
                return "断粮"

        # 捧杀: 全为同党, 帮同党快速升迁
        if not enemy_same_level and own_performance > 80:
            return "捧杀"

        # 精准投喂: 有中立家族可拉拢
        if neutral_same_level and self.p.party:
            return "精准投喂"

        return None

    def choose_circuit_strategy(self, level: str, co_officials: list,
                                own_performance: float, has_supervision: bool) -> Optional[str]:
        """
        路级进阶策略选择 (对应十二、12.3节进阶策略)

        路级特有策略(县级无):
          督办狙击: 宣抚使为对立党派, 己方控制设施被督办→反制
          漕运要挟: 转运使为己方, 同路有大量敌对州县官员→漕运维护降至0%~2%
          监察反杀: 提点刑狱为己方, 对立党派声望依赖度高→监察署维护降至0%

        Args:
            level: "circuit"时才判断路级策略
            co_officials: 同路共事官员列表
            own_performance: 自身政绩槽百分比
            has_supervision: 宣抚使是否为己方(可使用督办权)

        Returns:
            Optional[str]: 策略名或None
        """
        if level != "circuit":
            return None

        enemy = [o for o in co_officials if o.get("party") not in (self.p.party, None)]

        # 漕运要挟: 转运使为己方 + 同路有大量敌对州县官员
        if enemy and len(enemy) >= 2:
            # 检查是否有转运使控制权(简化: 由外部传入)
            has_transport = any(
                o.get("position", "") == "转运使" and o.get("party") == self.p.party
                for o in co_officials
            )
            if has_transport:
                return "漕运要挟"

        # 监察反杀: 提点刑狱为己方 + 敌方声望依赖度高
        has_judicial = any(
            o.get("position", "") == "提点刑狱" and o.get("party") == self.p.party
            for o in co_officials
        )
        if has_judicial and enemy:
            return "监察反杀"

        # 督办狙击: 宣抚使为对立党派, 己方设施被督办
        if has_supervision is False:  # 宣抚使非己方, 即为对立党派
            own_facilities = [o for o in co_officials
                              if o.get("party") == self.p.party
                              and o.get("position", "") in ("军屯署", "漕运署")]
            if own_facilities:
                return "督办狙击"

        return None

    def decide_donation(self, local_treasury: float, official_performance: float) -> Optional[dict]:
        """
        捐献决策 (对应十二、12.4节)

        判定流程:
          1. 按性格倾向概率决定是否捐献(清高50%, 冒险5%等)
          2. 金钱<200贯: 不捐献
          3. 官员政绩槽<30%: 优先本地捐献冲刺政绩
          4. 官员政绩槽>80%: 停止本地捐献, 转向国库换圣眷
          5. 按性格选择捐献对象(县/州/路/国库)
          6. 本地金库为负: 优先输血使金库回正
          7. 金额不超过金钱30%

        高级策略:
          买名: 声望低但金钱充裕 → 大额捐国库换圣眷
          冲刺: 政绩槽>90% → 捐献刚好补满
          输血: 金库为负 → 捐献使金库回正
          装穷: 敌方监察等级高 → 不捐献

        Returns:
            Optional[dict]: {"target": 捐献对象, "amount": 金额} 或 None
        """
        # 按性格倾向概率决定是否捐献
        tendency = PERSONALITY_DONATE_TENDENCY.get(self.p.personality, 0.2)
        if random.random() > tendency:
            return None

        # 金钱不足不捐献
        if self.p.money < 200:
            return None

        # 官员政绩槽<30%: 优先本地捐献冲刺政绩
        if official_performance < 30:
            target = "county"
            amount = random.randint(10, 30)  # 县金库: 10~30贯(1%~3%政绩槽)
        # 官员政绩槽>80%: 停止本地, 转向国库换圣眷
        elif official_performance > 80:
            if self.p.money > 1000:
                target = "national"
                amount = random.randint(100, 500)  # 国库: 100~500贯(1~5点圣眷)
            else:
                return None
        # 中等状态: 按性格选择对象
        elif self.p.money > 500:
            target = PERSONALITY_DONATE_TARGET.get(self.p.personality, "prefecture")
            if target == "none":
                return None  # 冒险型不捐献
            if target == "county":
                amount = random.randint(10, 30)       # 县金库
            elif target == "prefecture":
                amount = random.randint(50, 150)       # 州金库
            elif target == "circuit":
                amount = random.randint(100, 300)      # 路金库
            else:
                amount = random.randint(100, 500)      # 国库
        else:
            # 金钱200~500贯: 仅考虑县金库
            target = "county"
            amount = random.randint(10, 30)

        # 本地金库为负: 优先输血使金库回正(解除0%惩罚)
        if local_treasury < 0:
            target = "county"
            amount = int(abs(local_treasury)) + 10

        # 金额不超过金钱30%
        if amount > self.p.money * 0.3:
            amount = int(self.p.money * 0.3)

        return {"target": target, "amount": amount}

    def choose_donation_strategy(self, enemy_intel_level: int) -> Optional[str]:
        """
        捐献高级策略选择 (对应十二、12.4节高级策略)

        策略:
          买名: 家族声望低但金钱充裕(>1000贯) → 大额捐国库换圣眷
          冲刺: 官员政绩槽>90% → 捐献刚好补满政绩槽(立即升迁)
          输血: 本地金库为负 → 捐献使金库回正(解除0%惩罚)
          装穷: 对立党派监察等级>=2 → 不捐献, 避免引起注意

        Args:
            enemy_intel_level: 对立党派谍报/监察等级

        Returns:
            Optional[str]: 策略名或None(使用常规捐献逻辑)
        """
        # 装穷: 敌方监察等级高, 捐献会暴露财力
        if enemy_intel_level >= 2:
            return "装穷"

        # 输血: 本地金库为负(需外部传入, 此处简化判断)
        # (实际在decide_donation中已处理local_treasury<0情况)

        # 冲刺: 官员政绩槽>90%, 捐献刚好补满
        for o in self.p.officials:
            if not o.is_central and 90 < o.performance < 100:
                return "冲刺"

        # 买名: 声望低但金钱充裕
        if self.p.fame < 3000 and self.p.money > 1000:
            return "买名"

        return None

    def should_join_party(self, ji_party_fame: int, huai_party_fame: int) -> Optional[str]:
        """
        无党派家族入党判定 (对应十三、13.1节)

        各家族入党条件不同(子类覆写):
          顾家: 声望>=4000 或 被结交关系>=60
          梁家: 声望>=3000 或 地方官升至州级
          何家: 有家族成员任武职(正七品以上)
          陆家: 声望>=6000 或 被结交关系>=50 或 主角入党后

        Returns:
            Optional[str]: "畿党"/"淮党" 或 None(不入党)
        """
        return None

    def behavior_by_loyalty(self) -> str:
        """
        根据忠诚度决定行为模式 (对应十三、13.2节)

        70~100: 正常攻击(积极攻击敌方)
        50~69: 减少攻击(减少党派资源点投入, 防御为主)
        30~49: 仅防御(不主动攻击, 开始结交敌对)
        <30: 可被策反(不再参与任何党派行动)
        0: 自动叛离(加入对立党派, 忠诚重置为50)
        """
        loy = self.p.party_loyalty
        if loy <= 0:
            return "defect"         # 自动叛离
        if loy < 30:
            return "subvertable"    # 可被策反
        if loy < 50:
            return "defend_only"    # 仅防御
        if loy < 70:
            return "reduced_attack" # 减少攻击
        return "normal_attack"      # 正常攻击

    # ----------------------------------------------------------
    # 14. 大朝会自动结算 (对应十四、14节)
    # ----------------------------------------------------------

    def calc_grand_court_result(self, attacker_elocution: int, defender_elocution: int,
                                attacker_favor: int, defender_favor: int,
                                attacker_party_total_favor: int = 0,
                                defender_party_total_favor: int = 0) -> dict:
        """
        大朝会自动结算(NPC不进入小游戏, 使用公式结算)

        公式:
          击倒概率 = min(0.95, 攻方口才/(攻方口才+守方口才) × (1+圣眷差加成))
            圣眷差加成 = max(0, (攻方党派总圣眷-守方党派总圣眷)/100 × 0.05), 上限+0.3
            党派总圣眷 = 该党派所有中枢官员所在家族的圣眷之和

          反击概率 = min(0.5, 守方口才/(攻方口才+守方口才) × 守方圣眷/(守方圣眷+10) × 0.5)
            守方圣眷为防守方主控官员个人圣眷

          未击倒概率 = max(0.05, 1-击倒概率-反击概率)

        NPC vs NPC: 直接公式判定, 不消耗圣眷
        玩家 vs NPC: AI可消耗圣眷使用防御技能(雷霆/断链/天罗), 详见decide_grand_court_defense()

        Args:
            attacker_elocution: 主攻方口才
            defender_elocution: 主守方口才
            attacker_favor: 主攻方个人圣眷(反击概率不使用, 仅备用)
            defender_favor: 主守方个人圣眷(反击概率分母)
            attacker_party_total_favor: 攻方党派总圣眷(击倒概率圣眷差加成)
            defender_party_total_favor: 守方党派总圣眷(击倒概率圣眷差加成)

        Returns:
            dict: {"knockdown": 击倒概率, "counterattack": 反击概率, "survive": 未击倒概率}
        """
        # 圣眷差加成: 攻方党派总圣眷高于守方时额外加成, 上限+0.3
        favor_diff_bonus = max(0, (attacker_party_total_favor - defender_party_total_favor) / 100 * 0.05)
        favor_diff_bonus = min(0.3, favor_diff_bonus)

        # 击倒概率: 上限0.95
        knockdown = min(0.95,
                        attacker_elocution / max(1, attacker_elocution + defender_elocution)
                        * (1 + favor_diff_bonus))

        # 反击概率: 上限0.5, 分母用守方个人圣眷
        counterattack = min(0.5,
                            defender_elocution / max(1, attacker_elocution + defender_elocution)
                            * (defender_favor / (defender_favor + 10))
                            * 0.5)

        # 未击倒概率: 下限0.05
        survive = max(0.05, 1 - knockdown - counterattack)

        return {
            "knockdown": round(knockdown, 4),
            "counterattack": round(counterattack, 4),
            "survive": round(survive, 4),
        }

    def decide_grand_court_defense(self, defender_favor: int,
                                    defender_stability: int) -> dict:
        """
        大朝会防御技能决策 — 仅在玩家vs AI时生效 (对应冲突16)

        AI可消耗圣眷释放防御技能:
          雷霆: 对主攻方实体造成40点伤害, 消耗5圣眷
          断链: 断开1条已连接的逻辑链路, 消耗8圣眷
          天罗: 全屏放置障碍物+3秒内弹幕伤害×2, 消耗10圣眷

        决策逻辑:
          稳固值<30(危急): 优先释放天罗(最强控制)
          稳固值30~50(告急): 释放断链(断开对方进度)
          稳固值>50(尚可): 释放雷霆(伤害优先)
          圣眷不足5: 无法使用任何技能

        Args:
            defender_favor: 防守方家族当前圣眷
            defender_stability: 防守方官员当前稳固值

        Returns:
            dict: {"skill": 技能名或None, "favor_cost": 消耗圣眷}
        """
        if defender_favor < 5:
            return {"skill": None, "favor_cost": 0}

        if defender_stability < 30 and defender_favor >= 10:
            return {"skill": "天罗", "favor_cost": 10}
        elif defender_stability < 50 and defender_favor >= 8:
            return {"skill": "断链", "favor_cost": 8}
        elif defender_favor >= 5:
            return {"skill": "雷霆", "favor_cost": 5}

        return {"skill": None, "favor_cost": 0}

    # ----------------------------------------------------------
    # 15. 学识小游戏自动结算 (对应十五节)
    # ----------------------------------------------------------

    def knowledge_game_auto_result(self, char: Character) -> dict:
        """
        学识小游戏自动结算 (对应十五节)

        NPC不参与填字小游戏, 自动结算:
          - NPC始终视为触发(玩家50%概率触发)
          - 结算比例: 100%~200%之间随机(影响学识成长倍率)

        Args:
            char: 参与学识小游戏的角色

        Returns:
            dict: {"triggered": True, "growth_bonus": 加成系数(1.0~2.0随机), "ability": 成长能力名}
        """
        # 结算比例: 100%~200%之间随机
        growth_bonus = random.uniform(1.0, 2.0)

        # 根据角色最高能力确定成长方向
        abilities = {
            "knowledge": char.knowledge,
            "military": char.military,
            "commerce": char.commerce,
            "eloquence": char.eloquence,
        }
        best_ability = max(abilities, key=lambda k: abilities[k] or 0)

        return {
            "triggered": True,
            "growth_bonus": round(growth_bonus, 2),
            "ability": best_ability,
        }

    def debate_game_auto_result(self, char: Character) -> dict:
        """
        辩论小游戏自动结算 (对应十四节大朝会)

        NPC不参与辩论小游戏, 自动结算:
          - NPC始终视为触发
          - 结算比例: 100%~200%之间随机(影响口才/圣眷等收益倍率)

        Args:
            char: 参与辩论小游戏的角色

        Returns:
            dict: {"triggered": True, "result_bonus": 加成系数(1.0~2.0随机), "ability": "eloquence"}
        """
        result_bonus = random.uniform(1.0, 2.0)

        return {
            "triggered": True,
            "result_bonus": round(result_bonus, 2),
            "ability": "eloquence",
        }

    # ----------------------------------------------------------
    # 16. NPC家族间互动 (对应十六、16.1~16.3节)
    # ----------------------------------------------------------

    def should_npc_marry(self, target: FamilyProfile) -> bool:
        """
        NPC间联姻判定 (对应十六、16.1节)

        条件: 双方关系>=30 且 联姻冷却为0
        频率: 每年最多1次
        """
        relation = self.p.relations.get(target.name, 0)
        if relation < 30:
            return False
        if self.p.marry_cooldown > 0:
            return False
        return True

    def should_npc_befriend(self) -> bool:
        """
        NPC间自动结交判定 (对应十六、16.2节)

        触发概率: 5%/月(每对家族独立判定)
        效果: 关系+2~+5, 消耗1资源点+5贯金钱
        """
        return random.random() < 0.05

    def should_npc_negotiate(self) -> bool:
        """
        NPC间商议判定 (对应十六、16.3节)

        条件: 距上次商议>=12个月
        频率: 每年最多1次
        """
        if self.current_month - self.p.last_negotiate_month < 12:
            return False
        return True

    # ----------------------------------------------------------
    # 18.5 目标驱动的行动优先级调整 (对应十八、18.5节)
    # ----------------------------------------------------------

    def adjust_action_priority(self) -> list:
        """
        根据短期目标调整行动优先级 (对应十八、18.5节)

        基础优先级:
          1. 生存维护(资源点分配、防御预设)
          2. 发展经营(建筑建造/升级、角色放置、城市入驻)
          3. 家族行动(联姻、结交、商议)
          4. 党争行动(攻防、策反、情报)

        调整规则:
          官职类: 空缺填补提升至优先级1, 政绩/行动槽提升至优先级2
          资源类: 对应资源建筑投入提升至优先级2
          关系类: 结交目标家族提升至优先级3
          党争类: 党争行动提升至优先级3
          家族类: 联姻提升至优先级3
          紧急目标: 直接提升至优先级0(最高)

        Returns:
            list: [(优先级, 行为名), ...]
        """
        base_priority = [
            (1, "生存维护"),
            (2, "发展经营"),
            (3, "家族行动"),
            (4, "党争行动"),
        ]

        # 按短期目标类别添加调整项
        for goal in self.p.short_goals:
            if goal.category == ShortGoalCategory.OFFICE:
                base_priority.append((1, "空缺填补"))
                base_priority.append((2, "政绩/行动槽投入"))
            elif goal.category == ShortGoalCategory.RESOURCE:
                base_priority.append((2, "对应资源建筑投入"))
            elif goal.category == ShortGoalCategory.RELATION:
                base_priority.append((3, "结交目标家族"))
            elif goal.category == ShortGoalCategory.PARTY:
                base_priority.append((3, "党争行动"))
            elif goal.category == ShortGoalCategory.FAMILY:
                base_priority.append((3, "联姻"))

        # 紧急目标直接提升至优先级0(最高)
        for goal in self.p.short_goals:
            if goal.priority == 1:
                base_priority.insert(0, (0, goal.description))

        base_priority.sort(key=lambda x: x[0])
        return base_priority
