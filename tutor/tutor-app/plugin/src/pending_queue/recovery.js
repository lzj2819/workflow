/**
 * L11 CMP-PENDING-QUEUE — RECOVERY-SCHEDULER（ST-PQ-03 RecoverySchedule）。
 *
 * LCD-005 / LCD-PQ-001 混合触发：启动扫描 + 事件触发（reachability_hint /
 * manual_retry / backoff_due），触发语义由编排枢纽统一为 RecoveryRequested；
 * 本模块只负责：
 * - 指数退避的 next_attempt_at 计算（注入时钟，可测试）；
 * - 可选的退避定时器（注入 scheduler，LCD-PQ-004 的具体 timer API 下沉）。
 *
 * 退避参数、timer 精度为 implementation_detail；不改变 trigger_id 去重
 * 与单任务租约规则（those 由编排枢纽在编排层保证）。
 */

/** 指数退避：attempt 1 → base，之后 ×2，封顶 2^maxShift。 */
export function computeBackoffMs(attemptCount, baseBackoffMs, maxShift = 6) {
  const shift = Math.min(Math.max(attemptCount - 1, 0), maxShift);
  return baseBackoffMs * 2 ** shift;
}

/**
 * @param {Object} opts
 * @param {{now: () => number}} opts.clock        注入时钟（epoch ms）
 * @param {number} [opts.baseBackoffMs]           基础退避（默认 30000）
 * @param {{setTimer: (fn: () => void, ms: number) => unknown, clearTimer?: (h: unknown) => void}} [opts.scheduler]
 *        可选定时器端口；缺省则不自动唤醒（启动扫描 + 显式触发仍保证可恢复）
 * @param {(taskUuid: string, attemptCount: number) => void} [opts.onDue] 定时器到期回调
 */
export function createRecoveryScheduler({ clock, baseBackoffMs = 30_000, scheduler = null, onDue = null }) {
  const timers = new Map();

  function cancel(taskUuid) {
    const handle = timers.get(taskUuid);
    if (handle !== undefined) {
      if (scheduler && typeof scheduler.clearTimer === "function") {
        scheduler.clearTimer(handle);
      }
      timers.delete(taskUuid);
    }
  }

  /**
   * 计算并登记下一次恢复尝试时刻；若注入定时器则同时武装 backoff_due 触发。
   * @returns {{nextAttemptAt: string, delayMs: number}}
   */
  function schedule(taskUuid, attemptCount) {
    const delayMs = computeBackoffMs(attemptCount, baseBackoffMs);
    const nextAttemptAt = new Date(clock.now() + delayMs).toISOString();
    cancel(taskUuid);
    if (scheduler && typeof scheduler.setTimer === "function" && typeof onDue === "function") {
      const handle = scheduler.setTimer(() => {
        timers.delete(taskUuid);
        onDue(taskUuid, attemptCount);
      }, delayMs);
      timers.set(taskUuid, handle);
    }
    return { nextAttemptAt, delayMs };
  }

  function dispose() {
    for (const uuid of [...timers.keys()]) cancel(uuid);
  }

  return Object.freeze({ schedule, cancel, dispose });
}
