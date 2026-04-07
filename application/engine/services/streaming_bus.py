"""流式消息总线 - 用于自动驾驶守护进程与 SSE 接口之间的实时通信

守护进程在独立进程中运行，SSE 接口在主进程中运行。
使用 multiprocessing.Queue 实现跨进程通信。

注意：每个小说有独立的队列，避免消息混乱。
"""
import asyncio
import json
import multiprocessing as mp
import threading
import time
import logging
from collections import defaultdict
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# 全局队列管理器（单例）
# 使用 Manager 创建跨进程共享的字典
_manager: Optional[mp.Manager] = None
_stream_queues: Optional[Dict] = None  # novel_id -> Queue
_lock = threading.Lock()


def _get_manager():
    """获取或创建全局 Manager（懒加载）"""
    global _manager, _stream_queues
    if _manager is None:
        with _lock:
            if _manager is None:
                _manager = mp.Manager()
                _stream_queues = _manager.dict()
                logger.info("[StreamingBus] Manager 已初始化")
    return _manager, _stream_queues


def _get_or_create_queue(novel_id: str) -> mp.Queue:
    """获取或创建指定小说的队列"""
    _, queues = _get_manager()
    if novel_id not in queues:
        with _lock:
            if novel_id not in queues:
                queues[novel_id] = _manager.Queue(maxsize=2000)
                logger.debug(f"[StreamingBus] 创建队列: {novel_id}")
    return queues[novel_id]


class StreamingBus:
    """流式消息总线 - 发布/订阅模式（基于 multiprocessing.Queue）"""
    
    def __init__(self):
        # 本地订阅者（SSE 接口使用）
        self._subscribers: Dict[str, asyncio.Queue] = defaultdict(list)
        # 本地读取位置追踪（用于从 mp.Queue 读取时去重）
        self._local_positions: Dict[str, int] = defaultdict(int)
    
    def publish(self, novel_id: str, chunk: str):
        """发布增量文字（守护进程调用）"""
        if not chunk:
            return
        
        try:
            queue = _get_or_create_queue(novel_id)
            # 非阻塞写入，队列满时丢弃最旧的
            try:
                queue.put_nowait(chunk)
            except:
                # 队列满，清空一部分后重试
                try:
                    for _ in range(100):
                        queue.get_nowait()
                except:
                    pass
                try:
                    queue.put_nowait(chunk)
                except:
                    pass
            
            logger.debug(f"[StreamingBus] publish: {novel_id}, {len(chunk)} chars")
        except Exception as e:
            logger.error(f"[StreamingBus] publish 失败: {e}")
    
    def subscribe(self, novel_id: str) -> asyncio.Queue:
        """订阅增量文字（SSE 接口调用）"""
        queue = asyncio.Queue(maxsize=1000)
        self._subscribers[novel_id].append(queue)
        return queue
    
    def unsubscribe(self, novel_id: str, queue: asyncio.Queue):
        """取消订阅"""
        if novel_id in self._subscribers:
            try:
                self._subscribers[novel_id].remove(queue)
            except ValueError:
                pass
    
    def get_chunk(self, novel_id: str, timeout: float = 0.1) -> Optional[str]:
        """从跨进程队列获取增量文字（非阻塞，带超时）"""
        try:
            _, queues = _get_manager()
            if novel_id not in queues:
                return None
            
            mp_queue = queues[novel_id]
            try:
                # 使用短超时避免阻塞
                chunk = mp_queue.get(timeout=timeout)
                return chunk
            except:
                return None
        except Exception as e:
            logger.debug(f"[StreamingBus] get_chunk 异常: {e}")
            return None
    
    def clear(self, novel_id: str):
        """清空指定小说的队列"""
        try:
            _, queues = _get_manager()
            if novel_id in queues:
                mp_queue = queues[novel_id]
                # 清空队列
                while True:
                    try:
                        mp_queue.get_nowait()
                    except:
                        break
                logger.debug(f"[StreamingBus] 清空队列: {novel_id}")
        except Exception as e:
            logger.debug(f"[StreamingBus] clear 异常: {e}")


# 全局单例
streaming_bus = StreamingBus()
