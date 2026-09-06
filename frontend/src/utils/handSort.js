/**
 * Three-state sorting cycle for hand history net result:
 * Initial/None -> Ascending (正序) -> Descending (倒序) -> None (不排序/默认)
 */
export const NET_SORT_ORDERS = {
  NONE: 'none',
  ASC: 'asc',
  DESC: 'desc',
};

/**
 * Returns the next sort order in the cycle:
 * 'none' -> 'asc' (点一下正序)
 * 'asc' -> 'desc' (再点一下倒序)
 * 'desc' -> 'none' (再点一下不排序)
 *
 * @param {string} currentOrder - 'none' | 'asc' | 'desc'
 * @returns {string} next sort order
 */
export function getNextNetSortOrder(currentOrder = 'none') {
  if (currentOrder === 'none') return 'asc';
  if (currentOrder === 'asc') return 'desc';
  return 'none';
}

/**
 * Returns the API query parameters for a given netSortOrder.
 *
 * @param {string} sortOrder - 'none' | 'asc' | 'desc'
 * @returns {{ sort_by?: string, order?: string }}
 */
export function getNetSortQueryParams(sortOrder) {
  if (sortOrder === 'asc') {
    return { sort_by: 'net_chips', order: 'asc' };
  }
  if (sortOrder === 'desc') {
    return { sort_by: 'net_chips', order: 'desc' };
  }
  return {};
}

/**
 * Returns tooltip description for current sort order.
 *
 * @param {string} sortOrder - 'none' | 'asc' | 'desc'
 * @returns {string} tooltip text
 */
export function getNetSortTooltip(sortOrder) {
  if (sortOrder === 'asc') return '点击按净结果倒序排列';
  if (sortOrder === 'desc') return '点击恢复默认排序';
  return '点击按净结果正序排列';
}
