/**
 * L10 CMP-UPLOAD-CLIENT — ST-05 UploadCheckpoint 存储端口。
 *
 * ST-05 形状（L1 03 / L2 03，owner = CMP-UPLOAD-SESSION-DRIVER）：
 * {submission_uuid, upload_session_id, confirmed_chunks[], total_chunks, last_ack_at}
 *
 * 不变量：
 * - INV-5 / L2-UP-INV-001：confirmed_chunks 只含服务端已确认分片索引，
 *   写入时机由 SESSION-DRIVER 在 ack 后触发（本模块不决定写入时机）；
 * - 不含令牌、identity、材料内容（仅会话/偏移元数据）；
 * - A-007 要求跨进程持久，但具体文件/KV 机制属 implementation_detail：
 *   本叶子提供内存默认实现，持久化实现经同一接口注入。
 */

/**
 * 内存 checkpoint store（默认；进程重启后由父队列按 ST-04 恢复语义重建上传）。
 * @returns {{load: (uuid: string) => Promise<Object|null>, save: (cp: Object) => Promise<void>, clear: (uuid: string) => Promise<void>}}
 */
export function createMemoryCheckpointStore() {
  const byUuid = new Map();
  return {
    async load(uuid) {
      const cp = byUuid.get(uuid);
      // 返回副本，避免调用方绕过 save 直接改写（单写边界）
      return cp === undefined ? null : structuredClone(cp);
    },
    async save(cp) {
      byUuid.set(cp.submission_uuid, structuredClone(cp));
    },
    async clear(uuid) {
      byUuid.delete(uuid);
    },
  };
}
