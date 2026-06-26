"""知识图谱初始数据导入脚本。

运行方式：
  cd backend && python -m app.scripts.seed_knowledge

导入常见症状-疾病关联、鉴别诊断关系和推荐检查。
"""

import asyncio
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.models.knowledge import KnowledgeEdge


# ── 症状-疾病关联 ───────────────────────────────────
# (疾病, 症状, 权重, 来源)
SYMPTOM_DISEASE: list[tuple[str, str, float, str]] = [
    # 呼吸系统
    ("社区获得性肺炎", "发热", 0.95, "guideline"),
    ("社区获得性肺炎", "咳嗽", 0.87, "guideline"),
    ("社区获得性肺炎", "咳脓痰", 0.82, "guideline"),
    ("社区获得性肺炎", "胸痛", 0.60, "guideline"),
    ("社区获得性肺炎", "呼吸困难", 0.55, "guideline"),
    ("社区获得性肺炎", "湿啰音", 0.85, "guideline"),
    ("急性支气管炎", "咳嗽", 0.90, "guideline"),
    ("急性支气管炎", "咳痰", 0.80, "guideline"),
    ("急性支气管炎", "发热", 0.50, "guideline"),
    ("急性支气管炎", "咽痛", 0.45, "guideline"),
    ("慢性阻塞性肺疾病", "咳嗽", 0.85, "guideline"),
    ("慢性阻塞性肺疾病", "咳痰", 0.80, "guideline"),
    ("慢性阻塞性肺疾病", "呼吸困难", 0.75, "guideline"),
    ("慢性阻塞性肺疾病", "喘息", 0.60, "guideline"),
    ("上呼吸道感染", "咽痛", 0.85, "guideline"),
    ("上呼吸道感染", "鼻塞", 0.80, "guideline"),
    ("上呼吸道感染", "流涕", 0.78, "guideline"),
    ("上呼吸道感染", "咳嗽", 0.70, "guideline"),
    ("上呼吸道感染", "发热", 0.55, "guideline"),

    # 心血管系统
    ("原发性高血压", "头痛", 0.55, "guideline"),
    ("原发性高血压", "头晕", 0.60, "guideline"),
    ("原发性高血压", "耳鸣", 0.30, "guideline"),
    ("原发性高血压", "心悸", 0.35, "guideline"),
    ("冠状动脉粥样硬化性心脏病", "胸痛", 0.85, "guideline"),
    ("冠状动脉粥样硬化性心脏病", "胸闷", 0.75, "guideline"),
    ("冠状动脉粥样硬化性心脏病", "心悸", 0.50, "guideline"),
    ("心力衰竭", "呼吸困难", 0.85, "guideline"),
    ("心力衰竭", "水肿", 0.70, "guideline"),
    ("心力衰竭", "乏力", 0.65, "guideline"),
    ("心力衰竭", "端坐呼吸", 0.60, "guideline"),

    # 消化系统
    ("胃炎", "上腹痛", 0.85, "guideline"),
    ("胃炎", "腹胀", 0.65, "guideline"),
    ("胃炎", "反酸", 0.70, "guideline"),
    ("胃炎", "恶心", 0.55, "guideline"),
    ("胃食管反流病", "反酸", 0.90, "guideline"),
    ("胃食管反流病", "烧心", 0.85, "guideline"),
    ("胃食管反流病", "胸骨后痛", 0.60, "guideline"),
    ("消化性溃疡", "上腹痛", 0.80, "guideline"),
    ("消化性溃疡", "黑便", 0.55, "guideline"),
    ("消化性溃疡", "恶心", 0.45, "guideline"),
    ("急性阑尾炎", "右下腹痛", 0.90, "guideline"),
    ("急性阑尾炎", "恶心呕吐", 0.65, "guideline"),
    ("急性阑尾炎", "发热", 0.55, "guideline"),
    ("急性阑尾炎", "转移性腹痛", 0.80, "guideline"),

    # 内分泌系统
    ("2型糖尿病", "多饮", 0.80, "guideline"),
    ("2型糖尿病", "多食", 0.75, "guideline"),
    ("2型糖尿病", "多尿", 0.78, "guideline"),
    ("2型糖尿病", "体重下降", 0.65, "guideline"),
    ("2型糖尿病", "乏力", 0.50, "guideline"),
    ("甲状腺功能亢进症", "心悸", 0.75, "guideline"),
    ("甲状腺功能亢进症", "手抖", 0.70, "guideline"),
    ("甲状腺功能亢进症", "多汗", 0.70, "guideline"),
    ("甲状腺功能亢进症", "消瘦", 0.60, "guideline"),
    ("甲状腺功能亢进症", "突眼", 0.55, "guideline"),

    # 神经系统
    ("脑梗死", "偏瘫", 0.85, "guideline"),
    ("脑梗死", "言语不清", 0.75, "guideline"),
    ("脑梗死", "口角歪斜", 0.70, "guideline"),
    ("脑梗死", "意识障碍", 0.50, "guideline"),
    ("偏头痛", "头痛", 0.90, "guideline"),
    ("偏头痛", "恶心呕吐", 0.60, "guideline"),
    ("偏头痛", "畏光", 0.50, "guideline"),

    # 泌尿系统
    ("尿路感染", "尿频", 0.85, "guideline"),
    ("尿路感染", "尿急", 0.80, "guideline"),
    ("尿路感染", "尿痛", 0.82, "guideline"),
    ("尿路感染", "发热", 0.40, "guideline"),
    ("肾结石", "腰痛", 0.85, "guideline"),
    ("肾结石", "血尿", 0.70, "guideline"),

    # 其他
    ("缺铁性贫血", "乏力", 0.75, "guideline"),
    ("缺铁性贫血", "头晕", 0.60, "guideline"),
    ("缺铁性贫血", "面色苍白", 0.70, "guideline"),
    ("缺铁性贫血", "心悸", 0.45, "guideline"),
    ("焦虑障碍", "焦虑", 0.90, "guideline"),
    ("焦虑障碍", "失眠", 0.70, "guideline"),
    ("焦虑障碍", "心悸", 0.60, "guideline"),
    ("焦虑障碍", "紧张", 0.80, "guideline"),
]

# ── 鉴别诊断关系 ───────────────────────────────────
# (疾病A, 疾病B, 权重)
DIFFERENTIAL_DIAGNOSIS: list[tuple[str, str, float]] = [
    ("社区获得性肺炎", "急性支气管炎", 0.80),
    ("社区获得性肺炎", "心力衰竭", 0.40),
    ("社区获得性肺炎", "肺结核", 0.50),
    ("急性支气管炎", "社区获得性肺炎", 0.80),
    ("急性支气管炎", "上呼吸道感染", 0.60),
    ("胃炎", "消化性溃疡", 0.70),
    ("胃炎", "胃食管反流病", 0.50),
    ("胃食管反流病", "胃炎", 0.50),
    ("消化性溃疡", "胃炎", 0.70),
    ("消化性溃疡", "胃癌", 0.30),
    ("原发性高血压", "肾性高血压", 0.40),
    ("原发性高血压", "焦虑障碍", 0.20),
    ("2型糖尿病", "1型糖尿病", 0.40),
    ("甲状腺功能亢进症", "焦虑障碍", 0.35),
    ("脑梗死", "脑出血", 0.60),
    ("尿路感染", "肾结石", 0.30),
]

# ── 推荐检查 ───────────────────────────────────
# (疾病, 检查项, 权重)
SUGGESTED_TESTS: list[tuple[str, str, float]] = [
    ("社区获得性肺炎", "血常规", 0.90),
    ("社区获得性肺炎", "胸部X线", 0.95),
    ("社区获得性肺炎", "CRP", 0.85),
    ("急性支气管炎", "血常规", 0.70),
    ("急性支气管炎", "胸部X线", 0.60),
    ("原发性高血压", "血压监测", 0.95),
    ("原发性高血压", "心电图", 0.70),
    ("原发性高血压", "肾功能", 0.60),
    ("冠状动脉粥样硬化性心脏病", "心电图", 0.90),
    ("冠状动脉粥样硬化性心脏病", "心肌酶", 0.80),
    ("2型糖尿病", "空腹血糖", 0.95),
    ("2型糖尿病", "糖化血红蛋白", 0.85),
    ("胃炎", "胃镜", 0.90),
    ("胃炎", "幽门螺杆菌检测", 0.80),
    ("消化性溃疡", "胃镜", 0.90),
    ("消化性溃疡", "幽门螺杆菌检测", 0.85),
    ("尿路感染", "尿常规", 0.95),
    ("尿路感染", "尿培养", 0.70),
    ("缺铁性贫血", "血常规", 0.95),
    ("缺铁性贫血", "铁蛋白", 0.80),
    ("脑梗死", "头颅CT", 0.95),
    ("脑梗死", "头颅MRI", 0.85),
    ("甲状腺功能亢进症", "甲状腺功能", 0.95),
    ("甲状腺功能亢进症", "甲状腺超声", 0.60),
]

# ── 药品-疾病关系 ───────────────────────────────────
DRUG_DISEASE: list[tuple[str, str, float]] = [
    ("阿莫西林", "社区获得性肺炎", 0.85),
    ("头孢呋辛", "社区获得性肺炎", 0.80),
    ("左氧氟沙星", "社区获得性肺炎", 0.80),
    ("硝苯地平", "原发性高血压", 0.90),
    ("氨氯地平", "原发性高血压", 0.85),
    ("厄贝沙坦", "原发性高血压", 0.85),
    ("奥美拉唑", "胃炎", 0.90),
    ("奥美拉唑", "胃食管反流病", 0.90),
    ("奥美拉唑", "消化性溃疡", 0.85),
    ("二甲双胍", "2型糖尿病", 0.90),
    ("阿卡波糖", "2型糖尿病", 0.75),
    ("阿司匹林", "冠状动脉粥样硬化性心脏病", 0.85),
    ("阿托伐他汀", "冠状动脉粥样硬化性心脏病", 0.80),
    ("布洛芬", "偏头痛", 0.60),
]


async def _import_edges(
    db: AsyncSession,
    source_type: str,
    target_type: str,
    edge_type: str,
    rows: list[tuple[str, str, float] | tuple[str, str, float, str]],
) -> tuple[int, int]:
    created = 0
    skipped = 0
    for row in rows:
        source_value = row[0]
        target_value = row[1]
        weight = row[2]
        source = row[3] if len(row) > 3 else "manual"

        # Check if edge already exists
        stmt = select(KnowledgeEdge).where(
            KnowledgeEdge.source_type == source_type,
            KnowledgeEdge.source_value == source_value,
            KnowledgeEdge.target_type == target_type,
            KnowledgeEdge.target_value == target_value,
            KnowledgeEdge.edge_type == edge_type,
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            skipped += 1
            continue

        edge = KnowledgeEdge(
            source_type=source_type,
            source_value=source_value,
            target_type=target_type,
            target_value=target_value,
            edge_type=edge_type,
            weight=weight,
            occurrence_count=1,
            source=source,
        )
        db.add(edge)
        created += 1
    return created, skipped


async def main():
    print("开始导入知识图谱初始数据...")
    async with async_session_maker() as db:
        # 1. 症状-疾病关联
        c, s = await _import_edges(
            db, "disease", "symptom", "has_symptom",
            [(d, s, w, src) for d, s, w, src in SYMPTOM_DISEASE],
        )
        print(f"  症状-疾病: {c} 创建, {s} 跳过")

        # 2. 鉴别诊断
        c, s = await _import_edges(
            db, "disease", "disease", "differential_of",
            [(a, b, w, "guideline") for a, b, w in DIFFERENTIAL_DIAGNOSIS],
        )
        print(f"  鉴别诊断: {c} 创建, {s} 跳过")

        # 3. 推荐检查
        c, s = await _import_edges(
            db, "disease", "test", "suggests_test",
            [(d, t, w, "guideline") for d, t, w in SUGGESTED_TESTS],
        )
        print(f"  推荐检查: {c} 创建, {s} 跳过")

        # 4. 药品-疾病治疗关系
        c, s = await _import_edges(
            db, "drug", "disease", "treats",
            [(drug, disease, w, "guideline") for drug, disease, w in DRUG_DISEASE],
        )
        print(f"  药品-疾病: {c} 创建, {s} 跳过")

        await db.commit()
        print("\n知识图谱初始数据导入完成！")


if __name__ == "__main__":
    asyncio.run(main())
