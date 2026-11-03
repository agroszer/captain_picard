"""Background File Transfer Queue & Manager with pause, resume, throttle, and progress tracking."""

from __future__ import annotations
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from pycommander.ops import FileOperations, OpProgress, OverwritePolicy
from pycommander.vfs import VFS


@dataclass
class TransferTask:
    """Represents a file transfer task in the background queue."""
    id: str
    operation: str  # 'copy', 'move', 'delete'
    src_vfs: VFS
    src_path: str
    dst_vfs: Optional[VFS] = None
    dst_path: Optional[str] = None
    policy: OverwritePolicy = OverwritePolicy.OVERWRITE
    throttle_kb_s: float = 0.0
    status: str = "pending"  # pending, running, paused, completed, failed, cancelled
    error: Optional[str] = None
    progress: OpProgress = field(default_factory=OpProgress)


class TransferQueueManager:
    """Sequential or concurrent background queue manager preventing disk thrashing."""

    def __init__(self, file_ops: Optional[FileOperations] = None):
        self.file_ops = file_ops or FileOperations()
        self._tasks: List[TransferTask] = []
        self._queue: queue.Queue = queue.Queue()
        self._lock = threading.RLock()
        self._paused = threading.Event()
        self._paused.set()  # Not paused initially
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._current_task: Optional[TransferTask] = None
        self._throttle_kb_s: float = 0.0
        self._listeners: List[Callable[[TransferTask], None]] = []

    def start(self) -> None:
        """Starts worker thread."""
        with self._lock:
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._stop_event.clear()
                self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
                self._worker_thread.start()

    def stop(self) -> None:
        """Stops the worker thread."""
        self._stop_event.set()
        self.resume()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)

    def pause(self) -> None:
        """Pauses transfer execution."""
        self._paused.clear()
        if self._current_task:
            self._current_task.status = "paused"
            self._notify(self._current_task)

    def resume(self) -> None:
        """Resumes transfer execution."""
        self._paused.set()
        if self._current_task and self._current_task.status == "paused":
            self._current_task.status = "running"
            self._notify(self._current_task)

    def is_paused(self) -> bool:
        return not self._paused.is_set()

    def set_throttle(self, kb_s: float) -> None:
        """Sets global speed throttling in KB/s (0 = unlimited)."""
        self._throttle_kb_s = kb_s

    def add_listener(self, listener: Callable[[TransferTask], None]) -> None:
        self._listeners.append(listener)

    def _notify(self, task: TransferTask) -> None:
        for listener in self._listeners:
            try:
                listener(task)
            except Exception:
                pass

    def enqueue(
        self,
        operation: str,
        src_vfs: VFS,
        src_path: str,
        dst_vfs: Optional[VFS] = None,
        dst_path: Optional[str] = None,
        policy: OverwritePolicy = OverwritePolicy.OVERWRITE,
    ) -> TransferTask:
        task_id = f"task_{len(self._tasks) + 1}_{int(time.time() * 1000)}"
        task = TransferTask(
            id=task_id,
            operation=operation,
            src_vfs=src_vfs,
            src_path=src_path,
            dst_vfs=dst_vfs,
            dst_path=dst_path,
            policy=policy,
            throttle_kb_s=self._throttle_kb_s,
        )
        with self._lock:
            self._tasks.append(task)
            self._queue.put(task)
            self.start()
        return task

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            for t in self._tasks:
                if t.id == task_id:
                    t.status = "cancelled"
                    self._notify(t)
                    return True
        return False

    def list_tasks(self) -> List[TransferTask]:
        with self._lock:
            return list(self._tasks)

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                task: TransferTask = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if task.status == "cancelled":
                self._queue.task_done()
                continue

            self._current_task = task
            task.status = "running"
            self._notify(task)

            try:
                self._execute_task(task)
                if task.status != "cancelled":
                    task.status = "completed"
            except Exception as e:
                task.status = "failed"
                task.error = str(e)
            finally:
                self._notify(task)
                self._current_task = None
                self._queue.task_done()

    def _execute_task(self, task: TransferTask) -> None:
        start_time = time.time()
        last_calc_time = start_time
        bytes_at_last_calc = 0

        def check_pause_and_cancel() -> bool:
            while not self._paused.is_set():
                if self._stop_event.is_set() or task.status == "cancelled":
                    return True
                time.sleep(0.05)
            return self._stop_event.is_set() or task.status == "cancelled"

        def progress_cb(chunk_len: int, total_copied: int) -> None:
            nonlocal last_calc_time, bytes_at_last_calc
            now = time.time()
            elapsed = now - last_calc_time
            if elapsed >= 0.2:
                bps = (total_copied - bytes_at_last_calc) / elapsed
                task.progress.bytes_per_sec = bps
                last_calc_time = now
                bytes_at_last_calc = total_copied

            task.progress.completed_bytes = total_copied
            self._notify(task)

        if task.operation == "copy":
            if task.src_vfs.is_dir(task.src_path):
                self.file_ops.copy_directory(
                    src_vfs=task.src_vfs,
                    src_dir=task.src_path,
                    dst_vfs=task.dst_vfs,
                    dst_dir=task.dst_path,
                    policy=task.policy,
                    progress_callback=progress_cb,
                    cancel_check=check_pause_and_cancel,
                )
            else:
                self.file_ops.copy_file(
                    src_vfs=task.src_vfs,
                    src_path=task.src_path,
                    dst_vfs=task.dst_vfs,
                    dst_path=task.dst_path,
                    policy=task.policy,
                    progress_callback=progress_cb,
                    throttle_kb_s=self._throttle_kb_s,
                    cancel_check=check_pause_and_cancel,
                )

        elif task.operation == "move":
            self.file_ops.move_file(
                src_vfs=task.src_vfs,
                src_path=task.src_path,
                dst_vfs=task.dst_vfs,
                dst_path=task.dst_path,
                policy=task.policy,
            )

        elif task.operation == "delete":
            self.file_ops.delete_item(
                vfs=task.src_vfs,
                path=task.src_path,
                recursive=True,
            )
