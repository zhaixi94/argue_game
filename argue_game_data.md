# 官场党争复仇游戏 — 数据存储格式文档

---

## 一、数据分类

| 分类 | 说明 | 示例 |
|------|------|------|
| **静态数据** | 游戏启动时加载，运行时只读 | Trait、Title、OfficialRank、OfficialPositionBuff、OfficialPositionTemplate、BuildingTemplate、Route、State、County |
| **运行时数据** | 存档时持久化，每回合可能变更 | GameState、Family、FamilyRelationship、Character、OfficialPositionInstance、BuildingInstance、IntelligenceCard、Party、EventChainState、Mission、StoryState、ActiveBuff、KejuState、AnnualReviewRecord、QuarterlyTaxRecord、NationalTreasury、NPCAiState |
| **存档元数据** | 存档列表展示用 | SaveMetadata |

---

## 二、全局游戏状态 (GameState)

全局唯一实例，记录游戏整体进度。

| 字段 | 类型 | 说明 |
|------|------|------|
| currentYear | int | 当前游戏年（如景和三年=3） |
| currentMonth | int | 当前月份（1-12） |
| totalTurnsElapsed | int | 从游戏开始累计的总回合数，用于计算科举年等时间节点 |
| gamePhase | enum(Tutorial/Massacre/Exam/Local/Central/Revenge) | 当前剧情期：教学/灭门/科举/地方/中枢/复仇 |
| difficulty | enum(Easy/Normal/Hard) | 难度等级，影响NPC资源加成和AI行为 |
| ngPlusFailCount | int | 失败重开次数，每次+1使声望获取倍率+0.2、金钱获取倍率+0.2（加法叠加，首次×1.2，第二次×1.4，以此类推） |
| protagonistId | string | 主角角色的唯一ID |
| protagonistOriginalFamilyId | string? | 沈家（原家族）ID，灭门后可能不再有效 |

> 科举年由 totalTurnsElapsed 推导：每36回合（3年）一次，初始科举年在剧情第3期开始时设定。

---

## 三、家族 (Family)

每个家族一条记录，共12条（1主控+11NPC）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一ID |
| name | string | 家族名（如陆、苏、钱） |
| isPlayerFamily | bool | 是否为主控家族 |
| patriarchId | string | 当前族长的角色ID |
| partyAffiliation | enum(None/Ji/Huai) | 党派归属：无/畿党/淮党 |
| locationStateId | string? | 家族所在州ID，开局时确定 |
| money | int | 家族持有金钱（单位：文，1贯=1000文，产出公式均以贯为单位，存储时×1000转为文） |
| reputation | int | 家族声望，每月自然衰减 |
| imperialFavor | int | 圣眷，步入中枢后解锁，每月自然衰减 |
| vigilance | int | 戒心（0-100），步入中枢后解锁，30/60/80为debuff阈值 |
| strategicTendency | enum(Political/Economic/Military/Neutral)? | NPC专属战略倾向，决定AI决策偏好 |
| personalityTag | enum(Steady/Aloof/Adventurous/Shrewd/Flexible/Conservative/Fierce)? | NPC专属性格标签，影响截留率、联姻策略等 |
| partyLoyalty | int? | NPC家族的党派忠诚度（0-100），入黨初始70，每月-1 |
| partyContribution | int | 党派贡献累计值，用于换取情报/资源/分红 |
| hasEnteredCentral | bool | 家族是否有成员担任过正三品以上官职，为true时解锁圣眷和戒心 |
| activeBuffs | list[ActiveBuff] | 当前作用于该家族的buff列表 |
| isDefunct | bool | 是否已灭门（如沈家） |

> 家族等级（初级/中级/顶级）由声望阈值推导，不单独存储。

---

## 四、家族间关系 (FamilyRelationship)

任意两个家族之间的关系，主键为(familyAId, familyBId)，确保A的ID字典序小于B以避免重复。

| 字段 | 类型 | 说明 |
|------|------|------|
| familyAId | string | 家族A的ID（字典序较小者） |
| familyBId | string | 家族B的ID（字典序较大者） |
| baseRelationship | int | 基础家族关系值（≥0），由联姻建立，每月可能衰减 |
| marriageCooldownEndTurn | int | 联姻失败后的冷却结束回合，0表示无冷却 |

> 实际家族间关系 = min(100, baseRelationship + 双方成员关系加权平均值)
>
> 双方成员关系加权平均值 = (家族A所有成员对家族B的关系加权平均 + 家族B所有成员对家族A的关系加权平均) / 2
>
> 成员关系权重与主文档一致（族长3、正三品以上3、从四品~从三品2、从九品~正四品1.5、其余成年族人1，仅15岁以上）
>
> NPC间初始关系全部为0，不同党派的关系下降由基础家族关系衰减公式中的党派衰减项自然处理

---

## 五、角色 (Character)

每个角色一条记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一ID |
| name | string | 姓名 |
| age | int | 年龄（0-100） |
| gender | enum(Male/Female) | 性别 |
| birthplace | string | 籍贯，出生时确定，不可变 |
| familyId | string? | 当前所属家族ID，null表示流浪中 |
| originalFamilyId | string? | 原家族ID，嫁出/入赘后与familyId不同 |
| isProtagonist | bool | 是否为主角 |
| isPatriarch | bool | 是否为所在家族的族长 |
| isDeceased | bool | 是否已死亡 |
| knowledge | int | 学识（0-100） |
| military | int | 军事（0-100） |
| commerce | int | 商业（0-100） |
| eloquence | int | 口才（0-100） |
| appearance | int | 样貌（0-100） |
| knowledgePotential | float | 学识潜力（0.5-1.0），隐藏属性，出生时确定终身不变 |
| militaryPotential | float | 军事潜力（0.5-1.0） |
| commercePotential | float | 商业潜力（0.5-1.0） |
| eloquencePotential | float | 口才潜力（0.5-1.0） |
| appearancePotential | float | 样貌潜力（0.5-1.0） |
| traitIds | list[string] | 持有特性ID列表，最多4项 |
| titleIds | list[string] | 持有头衔ID列表，无上限 |
| seniority | int | 官场资历（0-100），隐藏属性，在任时按品阶权重增长，离任时每月-1 |
| currentSlotType | enum(None/FamilyBuilding/CityBuilding/OfficialPosition) | 当前所在位置类型 |
| currentSlotId | string? | 当前所在槽位/官职的ID，与currentSlotType配合使用 |
| familyRelationships | map[string->int] | 该角色与各家族的关系值，key=家族ID，value=关系值(-100~+100)；所有角色（含主控家族角色）对其他家族都有条目；游戏开局时所有NPC间关系初始为0 |
| spouseId | string? | 配偶的角色ID |
| childrenIds | list[string] | 子女的角色ID列表 |
| fatherId | string? | 父亲角色ID |
| motherId | string? | 母亲角色ID |
| isCurrentlyPregnant | bool | 是否正在怀孕中 |
| pregnancyMonth | int | 当前怀孕月份（0-10），0表示未怀孕 |
| kejuAttemptCount | int | 已参加科举次数（0-3，主角仅1次机会） |
| hasJieE | bool | 是否持有解额（可跳过解试直接参加省试） |
| jieEExpiryKejuCycles | int | 解额剩余有效科举周期数（通过省试后消耗，未通过保留2届） |
| hasPassedKeju | bool | 是否通过过科举（获得做官资格） |
| currentRankId | string? | 当前品阶ID，对应OfficialRank表 |
| currentPositionId | string? | 当前实职ID，对应OfficialPositionInstance；null则为散官（有品阶无实职） |
| isOnMaternityLeave | bool | 女性官员是否在产假中 |
| maternityLeaveEndTurn | int | 产假结束回合，0表示不在产假 |
| isInVagrantPool | bool | 是否在流浪池中（被驱逐后） |
| vagrantPoolEndTurn | int | 流浪池死亡截止回合，超过此回合未被收留则死亡 |
| activeBuffs | list[ActiveBuff] | 当前作用于该角色的buff列表 |

---

## 六、官职Buff (OfficialPositionBuff) — 静态数据

28个中枢官职各有独特buff，定义在argue_game_party.md第十四章。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一ID（如"buff_geishizhong"=给事中buff） |
| positionTemplateId | string | 对应的官职模板ID，一对一 |
| name | string | buff名称 |
| description | string | buff效果描述 |
| effectKey | string | 效果键名（如"stability_defense"、"money_output"、"reputation_gain"） |
| value | float | 效果值（如0.05表示+5%） |
| isPartyWide | bool | 是否为党派级加成（如太保的"己方地方官政绩槽受攻击时伤害减免+5%"） |
| isGlobal | bool | 是否为全局级加成（如太尉的"军事类建筑产出+20%"） |

> 叠加规则：同类百分比加法叠加，单维度上限50%。详见argue_game_party.md 14.6节。

---

## 七、特性 (Trait) — 静态数据

游戏启动时加载，运行时只读。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一ID（如"diligent"、"prodigy"） |
| name | string | 显示名（如勤勉、天纵） |
| tier | enum(Common/Good/Rare/Supreme) | 等级：寻常/清良/翘楚/绝伦 |
| knowledgeMod | int | 学识修正值（寻常±3, 清良±6, 翘楚±12, 绝伦+20） |
| militaryMod | int | 军事修正值 |
| commerceMod | int | 商业修正值 |
| eloquenceMod | int | 口才修正值 |
| appearanceMod | int | 样貌修正值 |
| specialEffect | string? | 特殊效果标识（如"keju_hidden_score_+0.1"、"reputation_gain_+15%"），null表示无特殊效果 |
| mutuallyExclusiveWith | list[string] | 互斥特性ID列表，同一角色不可同时拥有互斥特性 |

---

## 八、头衔 (Title) — 静态数据

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一ID |
| name | string | 显示名（如塾师、进士、百官之首） |
| category | enum(Building/Official/Exam/Special) | 类别：建筑头衔/官职头衔/科举头衔/特殊头衔 |
| knowledgeMod | int | 学识修正值 |
| militaryMod | int | 军事修正值 |
| commerceMod | int | 商业修正值 |
| eloquenceMod | int | 口才修正值 |
| appearanceMod | int | 样貌修正值 |
| specialEffect | string? | 特殊效果标识（如"all_title_effect_×1.2"表示百官之首的乘算加成） |
| isPermanent | bool | 是否不可失去（科举头衔为true，建筑/官职头衔为false） |

---

## 九、官阶 (OfficialRank) — 静态数据

九品十八阶，共18条记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一ID（如"rank_1a"=正一品，"rank_9b"=从九品） |
| level | int | 品阶序号（1=正一品，18=从九品） |
| name | string | 显示名（如正一品、从九品） |
| salary | int | 月俸禄（单位：贯） |
| reputationBonus | int | 月声望加成，仅实职享受，散官不享受 |
| imperialFavorProduction | int | 月圣眷产出，正三品以上有值，以下为0 |

---

## 十、官职模板 (OfficialPositionTemplate) — 静态数据

共约110个官职（82地方+28中枢）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一ID（如"weishi_county_magistrate"） |
| name | string | 职位名（如知县事、丞相） |
| rankId | string | 对应OfficialRank的ID |
| category | enum(County/State/Route/Central) | 地方县级/地方州级/地方路级/中枢 |
| locationId | string? | 所在地ID（中枢官职为null） |
| isCentral | bool | 是否为中枢官职（正三品以上） |
| buffId | string? | 中枢官职专属buff的ID，非中枢为null；28个中枢官职各有独特buff |
| performanceBasis1 | enum(Knowledge/Military/Commerce/Eloquence/Reputation) | 政绩槽第一计算能力（Reputation=家族声望/100） |
| basis1Weight | float | 第一能力权重（如0.6） |
| performanceBasis2 | enum(Knowledge/Military/Commerce/Eloquence/Reputation) | 政绩槽第二计算能力（Reputation=家族声望/100） |
| basis2Weight | float | 第二能力权重（如0.4） |
| performanceBasis3 | enum(Knowledge/Military/Commerce/Eloquence/Reputation)? | 政绩槽第三计算能力，仅路级官职有（Reputation=家族声望/100） |
| basis3Weight | float | 第三能力权重，默认0 |

---

## 十一、官职实例 (OfficialPositionInstance) — 运行时数据

每个官职一条记录，与OfficialPositionTemplate一一对应。

| 字段 | 类型 | 说明 |
|------|------|------|
| positionTemplateId | string | 对应的官职模板ID，主键 |
| holderId | string? | 现任者的角色ID，null表示空缺 |
| stabilityValue | int | 稳固值（无硬下限，上限100），仅中枢官职使用，初始60；降至0及以下触发贬官/大朝会 |
| performanceGauge | float | 政绩槽填充百分比（0%+），仅地方官职使用，每年初重置 |
| consecutiveAYears | int | 连续甲等年数，用于升迁判定 |
| consecutiveCYears | int | 连续丙等年数，用于罢免判定 |
| defenseResourcePoints | int | 每月防御预设投入的资源点数（0-3） |
| defenseImperialFavor | int | 每月防御预设投入的圣眷数（0-30），仅中枢 |
| currentRetentionRate | float? | 当前税收截留率（0-0.5），仅地方有征税权的官职 |

---

## 十二、建筑模板 (BuildingTemplate) — 静态数据

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一ID |
| name | string | 显示名（如书院、商铺、翰林院） |
| location | enum(Family/City) | 家族建筑或城市建筑 |
| slotCount | int | 角色卡槽位数（1-3） |
| outputs | list[BuildingOutput] | 产出列表，一个建筑可有多种产出 |
| growthAbility | enum(Knowledge/Military/Commerce/Eloquence)? | 成长类建筑对应的能力名，非成长类为null |
| baseGrowthRate | float? | 成长类基础成长速率，非成长类为null |
| entryCostPerMonth | int? | 城市非金钱建筑入驻每月金钱消耗，家族建筑和城市金钱建筑为0 |
| isSpecialBuilding | bool | 是否为特色建筑（翰林院/织造局/市舶府） |

**嵌套 BuildingOutput：**

| 字段 | 类型 | 说明 |
|------|------|------|
| outputType | enum(Money/Reputation/ImperialFavor/Growth) | 产出类型 |
| baseOutput | int | 基础产出/月 |
| baseCoefficient | float | 建筑基础系数，参与产出公式计算 |
| relatedAbility | enum(Knowledge/Military/Commerce/Eloquence)? | 关联的能力值，参与产出公式计算（如金钱产出关联商业，声望产出关联学识或口才） |

---

## 十三、建筑实例 (BuildingInstance) — 运行时数据

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一实例ID |
| buildingTemplateId | string | 对应建筑模板ID |
| ownerFamilyId | string? | 家族建筑=拥有家族ID，城市建筑=null |
| locationStateId | string? | 城市建筑=所在州ID，家族建筑=null |
| level | int | 建筑等级（1-5），家族建筑由玩家升级，城市建筑=繁荣度映射等级+知州升级等级 |
| governorUpgradeLevel | int | 知州升级次数（0-4），仅城市建筑，家族建筑为0 |
| constructionEndTurn | int? | 建造完成回合，0表示不在建造中 |
| upgradeEndTurn | int? | 升级完成回合，0表示不在升级中 |
| slots | list[BuildingSlot] | 角色卡槽位列表 |
| activeBuffs | list[ActiveBuff] | 当前作用于该建筑的buff列表 |

**嵌套 BuildingSlot：**

| 字段 | 类型 | 说明 |
|------|------|------|
| slotIndex | int | 槽位序号（0起） |
| assignedCharacterId | string? | 入驻角色ID，null表示空闲 |
| resourcePointsAllocated | int | 本回合投入的资源点数（0-3） |
| shareDealFamilyId | string? | 分成协议的对方家族ID，null表示无分成 |
| shareDealPercentage | float? | 分成比例（0.3=30%~0.5=50%），由资源点投入决定 |
| isRented | bool | 是否处于转租状态 |
| rentalEndTurn | int? | 转租到期回合，0表示非转租 |
| rentalFamilyId | string? | 承租方家族ID |

---

## 十四、情报卡 (IntelligenceCard)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一ID |
| type | enum(Accusation/Impeachment/Alienation/TaxEvasion) | 类型：检举/弹劾/离间/截留 |
| level | int | 等级（1=初级/2=中级/3=高级） |
| description | string | 描述文本（如"XXX在Y地贪赃枉法的证据"），用于UI展示 |
| ownerFamilyId | string? | 持有该情报卡的家族ID，null表示仍在党派情报池中 |
| isInPartyPool | bool | 是否仍在党派情报池中（未被领取） |

---

## 十五、党派 (Party)

固定2条记录：畿党和淮党。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | "Ji"或"Huai" |
| name | string | 畿党或淮党 |
| reputation | int | 党派声望（≥100），每月自然衰减1%（最低月衰减1点，下限100），式微线500 |
| leaderCharacterIds | list[string] | 党派领袖的角色ID列表 |
| privateTreasuryFunds | int | 私库金额（单位：贯） |
| privateTreasuryTaxRate | float | 私库抽成率（0-0.10），由领袖设定，影响NPC家族忠诚衰减 |
| partyResourcePoints | int | 党派资源点，由党派声望兑换而来，不跨月累积 |
| intelligenceAgencyLevel | int | 谍报机构等级（0=未解锁，≥1=已解锁，解锁条件：声望≥200） |
| publicOpinionAgencyLevel | int | 舆论机构等级（0=未解锁，≥1=已解锁，解锁条件：声望≥500） |
| privateTreasuryLevel | int | 私库等级（默认1，始终可用） |
| activePartyBuffs | list[ActivePartyBuff] | 当前舆论机构发布的buff列表 |

**嵌套 ActivePartyBuff：**

| 字段 | 类型 | 说明 |
|------|------|------|
| buffType | enum(ClearName/Rumor/Praise/Suspicion/WindBone/Crush) | 舆论类型：清名/流言/颂德/疑云/风骨/倾轧 |
| endTurn | int | buff结束回合 |
| targetScope | enum(Self/Enemy) | 作用于己方或敌方 |

---

## 十六、行政区划 — 静态+运行时混合

### Route（路）

3条记录：京畿路、江南路、岭南路。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一ID |
| name | string | 路名 |
| capitalStateId | string | 路治所在州的ID |
| partyBase | enum(None/Ji/Huai) | 党派根基：畿党=京畿路，淮党=江南路，岭南路=None |

### State（州）

7条记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一ID |
| name | string | 州名 |
| routeId | string | 所属路ID |
| prosperity | int | 繁荣度，每季度可能变动，影响城市建筑等级和产出 |
| specialBuildingType | enum(Hanlin/Zhizao/Shibo/None)? | 特色建筑类型：翰林院/织造局/市舶府，仅路治所在州有 |

### County（县）

14条记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一ID |
| name | string | 县名 |
| stateId | string | 所属州ID |
| prosperity | int | 县级繁荣度 |
| performanceGaugeModifier | float | 政绩槽填充修正（-0.15~+0.10），如溧阳县-0.05、祥符县+0.10 |
| moneyBuildingModifier | float | 金钱建筑产出修正（0~+0.05），如江宁县+0.05 |
| growthBuildingModifier | float | 成长建筑产出修正（0~+0.05），如吴县官学+0.05 |
| knowledgeGrowthModifier | float | 学识类成长建筑额外修正（0~+0.05），如吴县官学+0.05 |
| militaryGrowthModifier | float | 军事类成长建筑额外修正（0~+0.05），如番禺县武馆+0.05 |

---

## 十七、事件链状态 (EventChainState)

| 字段 | 类型 | 说明 |
|------|------|------|
| chainId | string | 事件链ID（如"old_friend_request"） |
| currentStepIndex | int | 当前环节序号（0起），表示玩家进行到哪一步 |
| chosenOptions | list[int] | 已选择的选项历史（每步记录选项编号），用于分支判定 |
| isActive | bool | 是否正在进行中 |
| startTurn | int | 事件链开始的总回合数 |

---

## 十八、任务 (Mission)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一ID |
| type | enum(MainStory/Random/Party) | 主线任务/随机任务/党派任务 |
| name | string | 任务名 |
| description | string | 任务描述 |
| currentProgress | float | 当前进度值 |
| targetProgress | float | 目标进度值，达到即完成 |
| deadlineTurn | int | 截止回合，超过未完成则失败 |
| isCompleted | bool | 是否已完成 |
| rewards | list[MissionReward] | 奖励列表 |

**嵌套 MissionReward：**

| 字段 | 类型 | 说明 |
|------|------|------|
| rewardType | enum(Money/Reputation/ImperialFavor/PartyContribution/Special) | 奖励类型 |
| value | int | 奖励数值 |
| description | string? | 特殊奖励的描述文本（如"获得1片灭门线索碎片"） |

---

## 十九、剧情状态 (StoryState)

全局唯一实例。

| 字段 | 类型 | 说明 |
|------|------|------|
| currentChapter | int | 当前剧情章数（1-6） |
| completedNodeIds | set[string] | 已完成的剧情节点ID集合，用于判定剧情跳过和分支解锁 |
| mainClueCount | int | 已获得的灭门线索碎片数量，影响剧情推进 |
| clueLayer | enum(None/Surface/Middle/Deep) | 当前线索调查深度：未开始/表层/中层/深层 |

**线索碎片与剧情解锁映射：**

| clueLayer | 所需碎片数 (mainClueCount) | 解锁剧情 | 碎片获取来源 |
|-----------|---------------------------|---------|-------------|
| Surface (表层) | 3片 | "灭门非寻常仇杀，与朝中某势力有关" | 事件/调查任务/父亲手札残页 |
| Middle (中层) | 6片 (含表层3片) | "灭门密令经某党派核心人物签发" | 中枢旧档调查/陆鼎臣支线/故交之托事件链 |
| Deep (深层) | 9片 (含前两层6片) | "对立党派领袖=灭门元凶；敌党故人=陆子衡" | 灭门旧痕事件链/陆子衡确认/姑姑遗书 |

- 每层3片，逐层解锁：前一层未完成不可获取下一层碎片
- 碎片来源分布：事件≈1/3、任务≈1/3、剧情支线≈1/3

> 复仇路线、结局等由游戏状态推导，不单独存储。各场景的分支选择由场景自身记录。

---

## 二十、通用Buff (ActiveBuff)

可附加在家族、角色、建筑实例上。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一ID |
| sourceType | enum(Event/Party/Official) | 来源：事件/党派舆论/官职buff |
| sourceId | string? | 来源的具体ID（事件ID/舆论类型/官职模板ID） |
| effectKey | string | 效果键名（如"money_output"、"reputation_gain"、"stability_defense"） |
| value | float | 效果值（如0.2表示+20%） |
| endTurn | int | buff结束回合，到期自动移除 |

> 叠加规则：同类effectKey的事件buff不叠加取最高值；不同来源可叠加；单维度总加成上限50%。

---

## 二十一、科举状态 (KejuState)

每3年一个周期，周期结束后可清理。

| 字段 | 类型 | 说明 |
|------|------|------|
| examYear | int | 科举年 |
| phase | enum(None/JieShiRegistered/JieShiCompleted/ShengShiRegistered/ShengShiCompleted/DianShiCompleted) | 当前阶段 |
| participants | list[KejuParticipant] | 参加者列表 |
| manipulations | list[KejuManipulation] | 礼部尚书操控记录 |

**嵌套 KejuParticipant：**

| 字段 | 类型 | 说明 |
|------|------|------|
| characterId | string | 参加者角色ID |
| hiddenScore | float | 本次科举随机生成的隐藏分（0.1-0.9），被操控时可>1 |
| passedJieShi | bool | 是否通过解试 |
| passedShengShi | bool | 是否通过省试 |
| finalRanking | int? | 殿试最终排名（1-10），未到殿试为null |

**嵌套 KejuManipulation：**

| 字段 | 类型 | 说明 |
|------|------|------|
| targetCharacterId | string | 被操控的角色ID |
| targetHiddenScore | float | 目标隐藏分 |
| imperialFavorCost | int | 消耗的圣眷 |
| reputationCost | int | 消耗的声望 |

---

## 二十二、年度述职记录 (AnnualReviewRecord)

每个地方官职每年一条记录，用于追踪连续甲等/丙等。

| 字段 | 类型 | 说明 |
|------|------|------|
| positionId | string | 官职实例ID |
| year | int | 游戏年 |
| finalGauge | float | 年终政绩槽百分比 |
| rating | enum(A/B/C/D) | 评级：甲/乙/丙/丁 |
| consecutiveAYears | int | 截至该年的连续甲等年数 |
| consecutiveCYears | int | 截至该年的连续丙等年数 |

---

## 二十三、季度税收记录 (QuarterlyTaxRecord)

每个有税收的地点每季度一条记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| locationId | string | 州或县的ID |
| year | int | 游戏年 |
| quarter | int | 季度（1-4） |
| totalCollected | int | 该季总税收（贯） |
| retainedAmount | int | 被地方官截留的金额 |
| remittedToTreasury | int | 上缴国库的金额 |
| jiRemitted | int | 畿党成员家族上缴累计 |
| huaiRemitted | int | 淮党成员家族上缴累计 |

---

## 二十四、国库 (NationalTreasury) — 运行时数据

全局唯一实例，记录国家财政储备。

| 字段 | 类型 | 说明 |
|------|------|------|
| balance | int | 国库当前余额（贯） |
| lastQuarterIncome | int | 上季度总税收上缴额 |
| lastQuarterExpenditure | int | 上季度总支出（城市建筑升级、国家事件等） |
| jiTotalRemittedThisQuarter | int | 本季度畿党成员家族上缴累计 |
| huaiTotalRemittedThisQuarter | int | 本季度淮党成员家族上缴累计 |

> 每季度结算时更新：收入来自各州县税收上缴，支出用于城市建筑升级和国家事件；两党上缴差额×0.3转化为胜出方中枢官员家族圣眷奖励。

---

## 二十五、NPC AI状态 (NPCAiState)

每个NPC家族一条记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| familyId | string | 家族ID，主键 |
| lastMarriageYear | int | 上次发起联姻的游戏年，用于限制联姻频率 |
| lastNegotiationYear | int | 上次发起商议的游戏年 |
| marriageProposalsThisYear | int | 本年已发起联姻次数 |
| negotiationAttemptsThisYear | int | 本年已发起商议次数 |

> NPC的截留率、入党倾向等由personalityTag和当前游戏状态推导，不单独存储。

---

## 二十六、存档数据范围

**存档内容 = 全部运行时数据 + 存档元数据**

| 分类 | 是否存档 | 说明 |
|------|---------|------|
| GameState | 是 | 全局游戏状态 |
| Family | 是 | 所有家族数据 |
| FamilyRelationship | 是 | 家族间关系 |
| Character | 是 | 所有角色数据 |
| OfficialPositionInstance | 是 | 官职实例 |
| BuildingInstance | 是 | 建筑实例 |
| IntelligenceCard | 是 | 情报卡 |
| Party | 是 | 党派数据 |
| EventChainState | 是 | 事件链状态 |
| Mission | 是 | 任务数据 |
| StoryState | 是 | 剧情状态 |
| ActiveBuff | 是 | 所有活跃buff |
| KejuState | 是 | 科举状态 |
| AnnualReviewRecord | 是 | 述职记录 |
| QuarterlyTaxRecord | 是 | 税收记录 |
| NationalTreasury | 是 | 国库数据 |
| NPCAiState | 是 | NPC AI状态 |
| SaveMetadata | 是 | 存档元数据 |
| Trait（静态数据） | 否 | 启动时从配置加载 |
| Title（静态数据） | 否 | 启动时从配置加载 |
| OfficialRank（静态数据） | 否 | 启动时从配置加载 |
| OfficialPositionTemplate（静态数据） | 否 | 启动时从配置加载 |
| BuildingTemplate（静态数据） | 否 | 启动时从配置加载 |
| OfficialPositionBuff（静态数据） | 否 | 启动时从配置加载 |
| Route/State/County（静态+运行时混合） | 是 | 繁荣度为运行时数据需存档 |

---

## 二十七、存档元数据 (SaveMetadata)

每个存档位一条记录，仅用于存档列表展示。

| 字段 | 类型 | 说明 |
|------|------|------|
| slot | int | 存档位（1-10） |
| timestamp | string | 存档时间戳 |
| gameYear | int | 存档时的游戏年 |
| gameMonth | int | 存档时的月份 |
| protagonistName | string | 主角姓名（展示用） |
| protagonistRank | string | 主角品阶名（展示用，如"从八品·知县事"） |
| isAutoSave | bool | 是否为自动存档 |

---

## 二十八、实体引用关系

```
GameState
  └→ protagonistId ──→ Character
  └→ protagonistOriginalFamilyId ──→ Family

Family
  └→ patriarchId ──→ Character
  └→ locationStateId ──→ State
  └→ activeBuffs[].id ──→ ActiveBuff

FamilyRelationship
  └→ familyAId ──→ Family
  └→ familyBId ──→ Family

Character
  └→ familyId ──→ Family
  └→ originalFamilyId ──→ Family
  └→ traitIds[] ──→ Trait
  └→ titleIds[] ──→ Title
  └→ currentRankId ──→ OfficialRank
  └→ currentPositionId ──→ OfficialPositionInstance
  └→ spouseId ──→ Character
  └→ childrenIds[] ──→ Character
  └→ fatherId ──→ Character
  └→ motherId ──→ Character
  └→ activeBuffs[].id ──→ ActiveBuff

OfficialPositionInstance
  └→ positionTemplateId ──→ OfficialPositionTemplate
  └→ holderId ──→ Character

OfficialPositionTemplate
  └→ rankId ──→ OfficialRank
  └→ locationId ──→ County/State/Route
  └→ buffId ──→ OfficialPositionBuff

BuildingInstance
  └→ buildingTemplateId ──→ BuildingTemplate
  └→ ownerFamilyId ──→ Family
  └→ locationStateId ──→ State
  └→ slots[].assignedCharacterId ──→ Character
  └→ slots[].shareDealFamilyId ──→ Family
  └→ slots[].rentalFamilyId ──→ Family
  └→ activeBuffs[].id ──→ ActiveBuff

IntelligenceCard
  └→ ownerFamilyId ──→ Family

Party
  └→ leaderCharacterIds[] ──→ Character

State
  └→ routeId ──→ Route

County
  └→ stateId ──→ State

Mission
  └→ rewards[] ──→ MissionReward

KejuState
  └→ participants[].characterId ──→ Character
  └→ manipulations[].targetCharacterId ──→ Character

AnnualReviewRecord
  └→ positionId ──→ OfficialPositionInstance

QuarterlyTaxRecord
  └→ locationId ──→ County/State

NPCAiState
  └→ familyId ──→ Family
```

---

## 二十九、推导字段一览

以下值由公式计算，**不需要持久化存储**：

| 推导值 | 计算方式 |
|--------|----------|
| 家族等级 | 由声望阈值判定 |
| 资源点上限 | base 3 + floor(声望/1000), max 10 |
| 建筑产出 | 产出公式（基础+角色能力+等级倍率+资源点+buff） |
| 角色能力成长 | 基础速率 × 潜力值 × 年龄段 × buff |
| 政绩槽填充速率 | 8.33% × 能力系数 × (1+加成) |
| 月声望衰减 | 3 + floor(声望/100) × 3 |
| 月圣眷衰减 | 按品阶衰减系数公式 |
| 月戒心变化 | 先+衰减量×0.5, 再-获取量×0.3 |
| 家族间关系实际值 | min(100, baseRelationship + 成员关系加权平均) |
| 稳固值伤害 | 攻击公式 × (1-防御减免) × 受伤系数 |
| 联姻成功率 | 公式实时计算 |
| 商议成功率 | 公式实时计算 |
| 城市建筑等级 | 繁荣度映射等级 + 知州升级等级 |
| 税收金额 | 繁荣度区间 × 建筑产出 |
| 科举年 | 由totalTurnsElapsed和初始科举年推导 |
| 死亡概率 | 年龄段公式（50岁以下0%, 以上((age-50)/50)²） |
| 复仇路线 | 由结局时的游戏状态推导 |
| 结局 | 由主线任务完成/失败状态推导 |
| NPC截留率 | 由personalityTag和当前游戏局势推导 |
