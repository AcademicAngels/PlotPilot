"""文风漂移监控服务

计算章节文本与作者指纹的相似度评分，连续 N 章低于阈值时发出告警。
"""
import re
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# 连续低分章节数触发告警
DRIFT_ALERT_CONSECUTIVE = 5
# 相似度告警阈值
DRIFT_ALERT_THRESHOLD = 0.75

# 常见形容词集合（与 VoiceFingerprintService 保持一致）
_COMMON_ADJECTIVES = set(
    "美丽漂亮英俊帅气可爱温柔善良聪明勇敢坚强勤奋努力认真仔细小心谨慎"
    "大小高低长短粗细胖瘦快慢冷热新旧好坏多少轻重深浅明暗干湿软硬"
    "红橙黄绿青蓝紫黑白灰粉棕金银"
)


class VoiceDriftService:
    """文风漂移监控服务"""

    def __init__(self, score_repo, fingerprint_repo):
        """
        Args:
            score_repo: SqliteChapterStyleScoreRepository
            fingerprint_repo: VoiceFingerprintRepository
        """
        self.score_repo = score_repo
        self.fingerprint_repo = fingerprint_repo

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def score_chapter(
        self,
        novel_id: str,
        chapter_number: int,
        content: str,
        pov_character_id: Optional[str] = None,
    ) -> dict:
        """计算章节文风评分并持久化。

        若作者指纹不存在，similarity_score 记为 None。

        Returns:
            包含 chapter_number, similarity_score, drift_alert 的字典
        """
        metrics = self._compute_metrics(content)
        fingerprint = self.fingerprint_repo.get_by_novel(novel_id, pov_character_id)

        if fingerprint and fingerprint.get("sample_count", 0) >= 10:
            similarity = self._cosine_similarity(metrics, fingerprint)
        else:
            similarity = None

        self.score_repo.upsert(
            novel_id=novel_id,
            chapter_number=chapter_number,
            adjective_density=metrics["adjective_density"],
            avg_sentence_length=metrics["avg_sentence_length"],
            sentence_count=metrics["sentence_count"],
            similarity_score=similarity if similarity is not None else 0.0,
        )

        drift_alert = self._check_drift_alert(novel_id)

        return {
            "chapter_number": chapter_number,
            "metrics": metrics,
            "similarity_score": similarity,
            "drift_alert": drift_alert,
        }

    def get_drift_report(self, novel_id: str) -> dict:
        """获取漂移报告（全量评分 + 告警状态）。"""
        scores = self.score_repo.list_by_novel(novel_id)
        drift_alert = self._check_drift_alert(novel_id)

        return {
            "novel_id": novel_id,
            "scores": scores,
            "drift_alert": drift_alert,
            "alert_threshold": DRIFT_ALERT_THRESHOLD,
            "alert_consecutive": DRIFT_ALERT_CONSECUTIVE,
        }

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_metrics(text: str) -> dict:
        """从章节文本提取与指纹相同维度的统计特征。"""
        if not text:
            return {"adjective_density": 0.0, "avg_sentence_length": 0.0, "sentence_count": 0}

        adj_count = sum(1 for ch in text if ch in _COMMON_ADJECTIVES)
        total_chars = len(text)
        adj_density = adj_count / total_chars if total_chars else 0.0

        sentences = re.split(r"[。！？]", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        sentence_count = len(sentences)
        avg_len = sum(len(s) for s in sentences) / sentence_count if sentence_count else 0.0

        return {
            "adjective_density": round(adj_density, 4),
            "avg_sentence_length": round(avg_len, 2),
            "sentence_count": sentence_count,
        }

    @staticmethod
    def _cosine_similarity(chapter_metrics: dict, fingerprint: dict) -> float:
        """用二维向量近似计算相似度（形容词密度 + 平均句长归一化）。

        归一化方式：以指纹值为参照，计算相对差异后映射到 [0,1]。
        """
        def _relative_closeness(a: float, b: float) -> float:
            """返回 a 与 b 的接近程度 (0~1)，b 为参照基准。"""
            if b == 0:
                return 1.0 if a == 0 else 0.0
            diff = abs(a - b) / b
            return max(0.0, 1.0 - diff)

        adj_sim = _relative_closeness(
            chapter_metrics["adjective_density"],
            fingerprint["adjective_density"],
        )
        len_sim = _relative_closeness(
            chapter_metrics["avg_sentence_length"],
            fingerprint["avg_sentence_length"],
        )
        # 加权平均：两个维度各 50%
        return round((adj_sim + len_sim) / 2, 4)

    def _check_drift_alert(self, novel_id: str) -> bool:
        """检查最近 N 章是否连续低于阈值。"""
        scores = self.score_repo.list_by_novel(novel_id, limit=DRIFT_ALERT_CONSECUTIVE * 2)
        if len(scores) < DRIFT_ALERT_CONSECUTIVE:
            return False

        recent = scores[-DRIFT_ALERT_CONSECUTIVE:]
        return all(s["similarity_score"] < DRIFT_ALERT_THRESHOLD for s in recent)
